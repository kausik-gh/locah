"""Read the sector-playbook tables straight out of the Capability Universe.

`families.py` is generated from these tables and a test re-parses the MD and
compares, so the registry can never quietly drift from the source (MD §21:
"Each row configures modules that are built once in §6").

Only the test and the generator call this; nothing at runtime reads the doc.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

MD_PATH = Path(__file__).resolve().parents[4] / "Documentations" / "LOCAH — Business Capability Universe.md"


@dataclass(frozen=True)
class SourceFamily:
    group: str  # "21.1"
    label: str  # the bold business-family name
    runs: str
    core: str
    rec: str
    people: str
    ai: str


def _split_modules(cell: str) -> tuple[str, str]:
    """'Core: a, b · Rec: c, d' -> ('a, b', 'c, d'). Some rows have no labels."""
    cell = cell.strip()
    if cell.startswith("Core:"):
        body = cell[len("Core:"):]
        if "· Rec:" in body:
            core, rec = body.split("· Rec:", 1)
            return core.strip(), rec.strip()
        return body.strip(), ""
    # e.g. beauty academies: "academics, memberships (fees), bookings"
    return cell, ""


def parse_families(md_text: str | None = None) -> list[SourceFamily]:
    text = md_text if md_text is not None else MD_PATH.read_text(encoding="utf-8")
    out: list[SourceFamily] = []
    group = ""
    in_21 = False
    for line in text.splitlines():
        m = re.match(r"^### (21\.\d+) ", line)
        if m:
            group, in_21 = m.group(1), True
            continue
        if line.startswith("## 22."):
            break
        if not in_21 or not line.startswith("| **"):
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        name = re.sub(r"\*\*", "", cells[0]).strip()
        core, rec = _split_modules(cells[2])
        people, _, ai = cells[3].partition(" · ")
        out.append(SourceFamily(group, name, cells[1], core, rec, people.strip(), ai.strip()))
    return out


_NAME = {
    "offerings": "offerings-catalog",
    "queue": "queue-operations",
    "insights": "analytics",
    "website": "core-website",
    "rentals": "bookings",
    "price lists": "offerings-catalog",
}
_FUTURE = {"payroll FUTURE"}


def parse_module_list(text: str) -> list[tuple[str, str]]:
    """'offerings (weighed), inventory (yield)' -> [('offerings-catalog','weighed'), ...].

    Commas inside parentheses belong to the hint.
    """
    items: list[str] = []
    depth, buf = 0, ""
    for ch in text:
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
        if ch == "," and depth == 0:
            items.append(buf)
            buf = ""
        else:
            buf += ch
    if buf.strip():
        items.append(buf)
    out: list[tuple[str, str]] = []
    for raw in items:
        raw = raw.strip().rstrip(".")
        if not raw or raw == "—" or raw in _FUTURE:
            continue
        m = re.match(r"^(.*?)\s*\((.*)\)\s*$", raw)
        name, hint = (m.group(1), m.group(2)) if m else (raw, "")
        name = name.strip()
        if name == "rentals":
            hint = hint or "rental"
        if name == "price lists":
            hint = "price_lists"
        out.append((_NAME.get(name, name), hint.strip()))
    return out
