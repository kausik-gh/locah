"""Are different businesses getting different websites — for the right reasons?

Random difference is not the goal; evidence-driven difference is. Two
businesses that said different things about themselves should not come out
with the same design signature, and one family must not swallow a whole
portfolio of fixtures. Deterministic, over composed payloads — no rendering.

A signature is what a visitor would notice first: design family, variant,
hero composition, type system, palette (and its hue), card treatment, section
rhythm.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from typing import Any

SIGNATURE_FIELDS = ("family", "variant", "hero", "type_system", "palette", "hue", "cards", "rhythm")


def signature(payload: dict[str, Any]) -> dict[str, str]:
    theme = payload.get("theme_hints") or {}
    hero = next((s.get("layout_variant", "") for s in payload["pages"][0]["sections"]
                 if s.get("section_type_id") == "hero"), "")
    return {
        "family": str(theme.get("design_family", "")), "variant": str(theme.get("design_variant", "")),
        "hero": str(hero), "type_system": str(theme.get("type_system", "")),
        "palette": str(theme.get("palette_key", "")), "hue": str(theme.get("palette_hue", "")),
        "cards": str(theme.get("card_style", "")), "rhythm": str(theme.get("rhythm", "")),
    }


def differences(a: dict[str, str], b: dict[str, str]) -> int:
    return sum(1 for f in SIGNATURE_FIELDS if a.get(f) != b.get(f))


@dataclass
class Report:
    sites: int
    families: dict[str, int]
    palettes: dict[str, int]
    clusters: list[str] = field(default_factory=list)  # problems
    identical: list[tuple[str, str]] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.clusters and not self.identical


def report(sites: dict[str, tuple[dict[str, str], dict[str, Any]]], *, max_family_share: float = 0.3) -> Report:
    """sites: key -> (signature, dimensions). Flags clustering the evidence doesn't justify."""
    families = Counter(sig["family"] for sig, _ in sites.values())
    palettes = Counter(sig["palette"] for sig, _ in sites.values())
    out = Report(len(sites), dict(families), dict(palettes))
    limit = max(2, int(len(sites) * max_family_share))
    for family, count in families.items():
        if count > limit:
            out.clusters.append(f"{family} used by {count} of {len(sites)} sites (limit {limit})")
    for (family, hue), count in Counter((s["family"], s["hue"]) for s, _ in sites.values()).items():
        if count > max(2, limit - 1):
            out.clusters.append(f"{family} in {hue} used by {count} sites")
    keys = sorted(sites)
    evidence_fields = ("offering", "journey", "positioning", "personality", "energy", "audience", "service_mode")
    for i, a in enumerate(keys):
        for b in keys[i + 1:]:
            sig_a, dims_a = sites[a]
            sig_b, dims_b = sites[b]
            same_evidence = all(dims_a.get(f) == dims_b.get(f) for f in evidence_fields)
            if not same_evidence and differences(sig_a, sig_b) == 0:
                out.identical.append((a, b))
    return out
