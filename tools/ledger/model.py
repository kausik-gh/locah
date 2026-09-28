"""Row model for the Business OS implementation ledger.

The ledger is data first: every capability named in the two canonical sources
(`Documentations/LOCAH — Business Capability Universe.md`, "MD", and
`Documentations/LOCAH_Business_OS_Guide.pdf`, "PDF") is one `Row`. The markdown
ledger is rendered from these rows so the per-phase gate counts are computed,
never typed.

Cell vocabulary (kept short so a row stays one readable line):
  ✓  built and exercised by a test in this repository
  ◐  partly built — the note says what exists and what is missing
  ✗  not built
  —  not applicable to this capability
"""

from __future__ import annotations

from dataclasses import dataclass, field

STATUSES = ("COMPLETE", "PARTIAL", "NOT_STARTED", "ACTIVATION_REQUIRED", "FUTURE")
KINDS = ("EXISTING", "EXTEND", "NEW", "FUTURE")
PHASES = ("P0", "P1", "P2", "P3", "P4", "P5", "P6", "X")


@dataclass
class Row:
    id: str
    phase: str
    src: str
    cap: str
    mod: str
    kind: str
    status: str
    code: str
    db: str = "—"
    svc: str = "—"
    perm: str = "—"
    ws: str = "—"
    cust: str = "—"
    web: str = "—"
    role: str = "—"
    auto: str = "—"
    integ: str = "—"
    test: str = "—"

    def __post_init__(self) -> None:
        if self.status not in STATUSES:
            raise ValueError(f"{self.id}: bad status {self.status}")
        if self.kind not in KINDS:
            raise ValueError(f"{self.id}: bad kind {self.kind}")
        if self.phase not in PHASES:
            raise ValueError(f"{self.id}: bad phase {self.phase}")


@dataclass
class Section:
    title: str
    intro: str
    rows: list[Row] = field(default_factory=list)


@dataclass
class Decision:
    id: str
    phase: str
    text: str
    state: str  # OPEN_DECISION | RESOLVED
    note: str


@dataclass
class Verify:
    id: str
    topic: str
    confirm: str
    src: str
    state: str  # VERIFY_AT_BUILD (not reached) | VERIFIED | NOT_VERIFIABLE_HERE
    note: str


def r(id: str, phase: str, src: str, cap: str, mod: str, kind: str, status: str, code: str,
      **cells: str) -> Row:
    return Row(id, phase, src, cap, mod, kind, status, code, **cells)
