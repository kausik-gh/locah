"""Personalization lands on a draft the owner may already be changing.

The first version is written the moment the owner presses Build; the
personalized one (model words, drawn pictures) arrives a minute later. Before
this module, any message the owner sent in that minute — even "looks good" —
changed the draft, and the whole personalized site was thrown away as
"superseded".

Now the build records a fingerprint of every section it wrote. When
personalization finishes, each section is compared with that fingerprint:

* untouched since the build → the personalized section replaces it;
* changed by the owner (talking to LOCAH, the editor) → the owner's section
  stays exactly as it is — owner edits always win;
* removed by the owner → stays removed;
* added by the owner → kept.

Theme and navigation follow the same rule. Pure functions over plain dicts.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any

_SECTION_KEYS = ("content", "layout_variant", "is_visible")


def _digest(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, default=str).encode()).hexdigest()[:24]


def section_fingerprint(section: dict[str, Any]) -> str:
    return _digest({k: section.get(k) for k in _SECTION_KEYS})


def _home(pages: list[dict[str, Any]]) -> dict[str, Any] | None:
    return next((p for p in pages if p.get("slug") == "home"), pages[0] if pages else None)


def base_fingerprints(draft: dict[str, Any]) -> dict[str, Any]:
    """What the build wrote, as fingerprints: from a draft aggregate's "draft"."""
    home = _home(draft.get("pages") or [])
    sections: dict[str, str] = {}
    for section in (home or {}).get("sections") or []:
        sections.setdefault(str(section["section_type_id"]), section_fingerprint(section))
    return {"sections": sections, "theme": _digest(draft.get("theme") or {}),
            "navigation": _digest(draft.get("navigation") or []),
            "pages": len(draft.get("pages") or [])}


def _as_payload_section(section: dict[str, Any]) -> dict[str, Any]:
    out = {"section_type_id": section["section_type_id"], "content": dict(section.get("content") or {}),
           "is_visible": section.get("is_visible", True)}
    if section.get("layout_variant"):
        out["layout_variant"] = section["layout_variant"]
    return out


def merge(personalized: dict[str, Any], live: dict[str, Any], base: dict[str, Any]
          ) -> tuple[dict[str, Any] | None, list[str]]:
    """The personalized payload with every owner change since the build kept.

    Returns (payload, kept) — ``kept`` names the section types (and "theme",
    "navigation") the owner had changed. Returns (None, []) when the owner
    restructured the site (added pages): then personalization does not apply.
    """
    live_pages = live.get("pages") or []
    if len(live_pages) > max(1, int(base.get("pages") or 1)):
        return None, []
    live_home = _home(live_pages) or {"sections": []}
    live_by_type: dict[str, dict[str, Any]] = {}
    for section in live_home.get("sections") or []:
        live_by_type.setdefault(str(section["section_type_id"]), section)
    base_sections: dict[str, str] = base.get("sections") or {}
    page = dict(personalized["pages"][0])
    kept: list[str] = []
    merged: list[dict[str, Any]] = []
    for section in page["sections"]:
        kind = str(section["section_type_id"])
        mine = live_by_type.get(kind)
        if mine is None:
            if kind in base_sections:
                kept.append(kind)  # the owner removed it: it stays removed
                continue
            merged.append(section)
        elif section_fingerprint(mine) == base_sections.get(kind):
            merged.append(section)
        else:
            kept.append(kind)
            merged.append(_as_payload_section(mine))
    composed = {str(s["section_type_id"]) for s in page["sections"]}
    extras = [s for s in live_home.get("sections") or []
              if str(s["section_type_id"]) not in composed
              and section_fingerprint(s) != base_sections.get(str(s["section_type_id"]))]
    if extras:
        kept += [str(s["section_type_id"]) for s in extras]
        at = next((i for i, s in enumerate(merged) if s["section_type_id"] == "contact"), len(merged))
        merged[at:at] = [_as_payload_section(s) for s in extras]
    page["sections"] = merged
    out = {**personalized, "pages": [page]}
    if _digest(live.get("theme") or {}) != base.get("theme"):
        out["theme_hints"] = {**(live.get("theme") or {}),
                              "generation": (personalized.get("theme_hints") or {}).get("generation", {})}
        kept.append("theme")
    if _digest(live.get("navigation") or []) != base.get("navigation"):
        out["navigation"] = live.get("navigation") or []
        kept.append("navigation")
    return out, kept
