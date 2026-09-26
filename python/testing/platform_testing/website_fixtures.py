"""Website fixtures: 24 businesses, their interviews, their first websites — zero AI.

Each owner's conversation runs through the real interview (scripted model
readings, see interview_personas / website_personas); the website is composed
exactly as "Build my website" composes it — creative direction, composition,
semantic validation — with no model and no image generation. What comes out:

* the payload (what would be stored as the draft),
* its design signature (distinctness),
* its semantic findings,
* a site-lab file (the public renderer's input) for screenshots.

    uv run python -m platform_testing.website_fixtures <out_dir>
"""

from __future__ import annotations

import asyncio
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from platform_core.interview.capabilities import resolve_recommendations
from platform_core.interview.creative_director import direct
from platform_core.interview.distinctness import Report, report, signature
from platform_core.interview.models import BusinessBlueprint
from platform_core.interview.site_composer import compose_site
from platform_core.interview.website import with_draft
from platform_testing.interview_eval import Persona, every_module_entitled, run_persona
from platform_testing.interview_personas import PERSONAS
from platform_testing.website_personas import WEBSITE_PERSONAS

# Every distinct business, once (the interview's talk-first variants are the
# same businesses).
FIXTURE_PERSONAS: list[Persona] = [p for p in PERSONAS if p.key != "wift-app"] + WEBSITE_PERSONAS


@dataclass
class SiteFixture:
    key: str
    name: str
    business: str
    bp: BusinessBlueprint
    payload: dict[str, Any]
    signature: dict[str, str]
    dimensions: dict[str, Any]


def contact_for(bp: BusinessBlueprint) -> dict[str, str]:
    from platform_core.services.business_interview import public_contact

    return {k: str(v) for k, v in public_contact(bp).items() if isinstance(v, str)}


def compose(bp: BusinessBlueprint, business_type: str) -> dict[str, Any]:
    """The first website, as the build composes it — deterministic, no model."""
    resolve_recommendations(bp, every_module_entitled(), business_type)
    active = frozenset(m.module_id for m in bp.recommended_modules if m.strength == "strong")
    direction = direct(bp, business_type)
    return dict(compose_site(
        bp, direction, with_draft(bp, None), business_type=business_type, contact=contact_for(bp),
        active_modules=active, meta={"stage": "immediate", "creative_strategy": "deterministic",
                                     "fallback_used": False},
    ))


async def build(p: Persona) -> SiteFixture:
    run = await run_persona(p, "model")
    payload = compose(run.bp, p.business_type)
    theme = payload["theme_hints"]
    dims = dict((theme.get("creative_direction") or {}).get("dimensions") or {})
    return SiteFixture(p.key, p.name, p.business, run.bp, payload, signature(payload), dims)


async def build_all(personas: list[Persona] | None = None) -> list[SiteFixture]:
    return [await build(p) for p in (personas or FIXTURE_PERSONAS)]


def distinctness(fixtures: list[SiteFixture]) -> Report:
    return report({f.key: (f.signature, f.dimensions) for f in fixtures})


def lab_payload(f: SiteFixture) -> dict[str, Any]:
    """The public renderer's input (PublicWebsitePayload), for the site lab."""
    page = f.payload["pages"][0]
    contact = contact_for(f.bp)
    return {
        "business": {"id": str(f.bp.business_id), "slug": f.key, "display_name": f.name,
                     "business_type": None, "contact": contact},
        "capabilities": {},
        "website": {"status": "draft"},
        "page": {
            "title": page.get("title", "Home"), "slug": "home", "seo_title": page.get("seo_title"),
            "seo_description": page.get("seo_description"),
            "sections": [{"id": f"{f.key}-{i}", "section_type_id": s["section_type_id"],
                          "layout_variant": s.get("layout_variant"), "content": s.get("content", {}),
                          "assets": {}, "is_visible": s.get("is_visible", True)}
                         for i, s in enumerate(page["sections"])],
        },
        "navigation": f.payload.get("navigation", []),
        "theme": f.payload.get("theme_hints", {}),
        "is_preview": False,
        "fixture": {"business": f.business, "signature": f.signature,
                    "semantic": f.payload["theme_hints"]["quality"].get("semantic", []),
                    "reasons": (f.payload["theme_hints"].get("creative_direction") or {}).get("reasons", [])},
    }


def main(out: str) -> None:  # pragma: no cover — a tool
    root = Path(out)
    root.mkdir(parents=True, exist_ok=True)
    fixtures = asyncio.run(build_all())
    index = []
    for f in fixtures:
        (root / f"{f.key}.json").write_text(json.dumps(lab_payload(f), ensure_ascii=False, indent=1),
                                            encoding="utf-8")
        index.append({"key": f.key, "name": f.name, "business": f.business, **f.signature})
    rep = distinctness(fixtures)
    (root / "index.json").write_text(json.dumps({"sites": index, "distinctness": {
        "ok": rep.ok, "families": rep.families, "palettes": rep.palettes, "clusters": rep.clusters,
        "identical": rep.identical}}, indent=1), encoding="utf-8")
    for row in index:
        print(f"{row['key']:22} {row['family']:22} {row['variant']:14} {row['hero']:16} {row['palette']}")
    print("distinct:", rep.ok, rep.clusters, rep.identical)


if __name__ == "__main__":  # pragma: no cover
    main(sys.argv[1] if len(sys.argv) > 1 else "site-lab")
