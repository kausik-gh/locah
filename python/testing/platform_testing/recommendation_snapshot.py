"""Per-subcategory module recommendation snapshot (Capability Universe §27).

    PYTHONPATH=python/testing uv run python -m platform_testing.recommendation_snapshot          # print a diff summary
    PYTHONPATH=python/testing uv run python -m platform_testing.recommendation_snapshot --write  # rewrite the fixture
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

from platform_core.catalog.recommendation import recommend
from platform_core.catalog.taxonomy import CATEGORIES

FIXTURE = Path(__file__).resolve().parents[3] / "apps" / "api" / "tests" / "fixtures" / "module_recommendations.json"


def snapshot() -> dict[str, Any]:
    out: dict[str, Any] = {}
    for c in CATEGORIES:
        for s in c.subcategories:
            rec = recommend(subcategory_key=s.key if s.key != "other" else None,
                            playbook=s.playbook, traits=s.traits)
            out[s.key] = {
                "category": c.key,
                "family": rec.family,
                "traits": sorted(s.traits),
                "core": rec.tier("core"),
                "recommended": rec.tier("recommended"),
                "optional": rec.tier("optional"),
            }
    return out


def main(argv: list[str]) -> int:
    data = snapshot()
    if "--write" in argv:
        FIXTURE.parent.mkdir(parents=True, exist_ok=True)
        FIXTURE.write_text(json.dumps(data, indent=1, sort_keys=True) + "\n")
        print(f"wrote {FIXTURE} ({len(data)} subcategories)")
        return 0
    old = json.loads(FIXTURE.read_text()) if FIXTURE.exists() else {}
    changed = sorted(k for k in set(old) | set(data) if old.get(k) != data.get(k))
    print(f"{len(changed)} subcategories differ from the fixture")
    for k in changed[:40]:
        print(" ", k)
    return 1 if changed else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
