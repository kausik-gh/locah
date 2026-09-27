"""Generate python/core/platform_core/catalog/families.py from MD §21.

    uv run python tools/codegen/families.py

Re-run when the Capability Universe's playbook tables change; the test
`test_taxonomy_families.py` fails until the generated file matches.
"""

from __future__ import annotations

import re
from pathlib import Path

from platform_core.catalog.source_tables import parse_families

OUT = Path(__file__).resolve().parents[2] / "python/core/platform_core/catalog/families.py"


def slug(label: str) -> str:
    words = re.sub(r"\(.*?\)", "", label.lower())
    words = re.sub(r"[^a-z0-9]+", " ", words).split()
    stop = {"and", "the", "of", "a", "an", "e", "g"}
    words = [w for w in words if w not in stop]
    return "_".join(words[:4])


def main() -> None:
    fams = parse_families()
    keys = [slug(f.label) for f in fams]
    assert len(set(keys)) == len(keys), "family keys collide"
    lines = [
        '"""Sector playbook families (Capability Universe §21) — GENERATED, do not edit.',
        "",
        "Regenerate with `uv run python tools/codegen/families.py`. Each family",
        "configures modules built once in §6; `core` modules are on by default and",
        "`rec` modules are pre-ticked (owner can untick). Hints in parentheses are",
        "the configuration the source names (e.g. inventory (yield)).",
        '"""',
        "",
        "from __future__ import annotations",
        "",
        "from dataclasses import dataclass",
        "",
        "",
        "@dataclass(frozen=True)",
        "class Family:",
        "    key: str",
        "    group: str",
        "    label: str",
        "    runs: str",
        "    core: str",
        "    rec: str",
        "    people: str",
        "    ai: str",
        "",
        "",
        "FAMILIES: tuple[Family, ...] = (",
    ]
    for k, f in zip(keys, fams):
        lines.append(f"    Family({k!r}, {f.group!r}, {f.label!r},")
        lines.append(f"           {f.runs!r},")
        lines.append(f"           {f.core!r},")
        lines.append(f"           {f.rec!r},")
        lines.append(f"           {f.people!r}, {f.ai!r}),")
    lines += [")", "", "BY_KEY: dict[str, Family] = {f.key: f for f in FAMILIES}", ""]
    OUT.write_text("\n".join(lines), encoding="utf-8")
    print(f"wrote {OUT} ({len(fams)} families)")
    for k, f in zip(keys, fams):
        print(f"  {k:40} {f.label}")


if __name__ == "__main__":
    main()
