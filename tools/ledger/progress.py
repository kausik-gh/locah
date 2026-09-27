"""Progress recorded against the audited baseline, one block per packet.

The rows in rows_*.py are the audit of main @ 0c56419. Each packet records
what it changed here — status plus the cells it made true — so the ledger
shows both where a capability started and where it is now.
"""

from __future__ import annotations

from typing import Any

C, P, S, A, F = "COMPLETE", "PARTIAL", "NOT_STARTED", "ACTIVATION_REQUIRED", "FUTURE"

UPDATES: dict[str, dict[str, Any]] = {}
RESOLVED_DECISIONS: dict[str, str] = {}


def done(packet: str, rows: dict[str, dict[str, Any]]) -> None:
    for rid, change in rows.items():
        change = dict(change)
        change["code"] = f"[{packet}] {change.get('code', '')}".strip()
        UPDATES[rid] = change


# ---------------------------------------------------------------- P1-01
done("P1-01", {
    "TX-01": dict(status=C, code="427 subcategories + synonyms, deterministic spelling-tolerant search; Settings picker + /start",
                  svc="✓ /v1/public/taxonomy", web="✓", ws="✓ Settings › How your business works",
                  test="✓ test_taxonomy_recommendations"),
    "TX-02": dict(status=P, code="15 tiles from First Launch; §4.1 says the 12 most-chosen — needs real usage data to pick them"),
    "TX-03": dict(status=P, code="interview proposes the kind, owner confirms; trait proposals (source ai_suggested_confirmed) not produced yet",
                  db="✓ business_traits.source"),
    "TX-04": dict(status=C, code="business_type unchanged = website template key; every subcategory maps to a template via its category",
                  db="✓", test="✓"),
    "TX-05": dict(status=C, code="33 categories; every §4.2 subcategory individually selectable (~130 added)",
                  svc="✓", test="✓ test_md_subcategories_are_individually_selectable"),
    **{rid: dict(status=C, code="trait group in the registry with its §4.3 switch-on rules (TRIGGERS/REQUIRES)",
                 svc="✓ catalog/recommendation.py", test="✓ test_owner_trait_changes_move_modules")
       for rid in ("TX-06", "TX-07", "TX-08", "TX-09", "TX-10", "TX-11", "TX-12", "TX-14")},
    "TX-13": dict(status=P, code="regulated traits exist and drive invoice mode + recommendations; compliance/guardian/AI-guardrail consumers arrive with those modules",
                  svc="✓", test="✓"),
    "TX-15": dict(status=P, code="traits seeded from the subcategory, editable in Settings, owner choices survive re-seed; interview does not yet ask ≤2 trait-confirming questions",
                  db="✓ business_traits", svc="✓ PATCH /traits", ws="✓ Settings › How your business works",
                  test="✓ test_business_classification"),
    "TX-16": dict(status=P, code="org_shape stored + editable; drives role templates only once role templates land (P1 roles packet)",
                  db="✓ businesses.org_shape", ws="✓"),
    "TX-17": dict(status=C, code="migration 20260927100000: category_key, subcategory_key, org_shape; business_traits with RLS; backfilled from metadata",
                  db="✓", perm="✓ RLS + isolation test", test="✓ test_business_traits_are_tenant_isolated"),
    "TX-18": dict(status=P, code="one registry package (taxonomy + families + rules + module catalogue) behind one endpoint; the Marketplace still groups categories separately",
                  svc="✓ /v1/public/taxonomy"),
    "TX-19": dict(status=C, code="pure function traits → always/core/recommended/optional; every subcategory snapshot-tested; §21 tables re-parsed from the MD",
                  svc="✓", test="✓ 427-subcategory snapshot"),
    "TX-20": dict(status=P, code="operating-model traits and org shapes exist; per-row behaviours land with their modules"),
    "PM-01": dict(status=C, code="taxonomy registry versioned 2026-09-27.1", svc="✓", test="✓"),
    "PM-02": dict(status=C, code="recommendation rules", svc="✓", test="✓"),
    "FD-06": dict(status=C, code="Modules page: what / why / customers can / team can / setup remaining from real data; enabled ≠ ready; unbuilt tools never offered",
                  svc="✓ /module-recommendations", ws="✓ Tools page", test="✓ API + browser flow p1_01_modules"),
    "FD-10": dict(status=P, code="unbuilt modules cannot be enabled and are hidden; readiness computed from data; website/marketplace gating still to wire",
                  svc="✓ module_readiness"),
    "PR-02": dict(status=C, code="any business can switch on any built tool ('More tools'); category only pre-ticks", ws="✓"),
    "PR-03": dict(status=C, code="trait requirements demote, owner-added traits recommend", test="✓"),
    "PK-00": dict(status=P, code="modules carry their §5 packs; pack-level presentation not built"),
    "TS-01": dict(status=P, code="subcategory→module fixtures added; tax/BOM/ladder/series fixtures come with their packets", test="◐"),
})
for rid in [f"PB-{n}" for n in (list(range(101, 109)) + list(range(201, 210)) + list(range(301, 311))
                              + list(range(401, 411)) + list(range(501, 509)) + list(range(601, 611))
                              + list(range(701, 709)) + list(range(801, 812)) + list(range(901, 909))
                              + list(range(1001, 1009)) + list(range(1101, 1104)))]:
    UPDATES[rid] = dict(status=P, code="[P1-01] fixture asserts this family's Core/Rec for every subcategory; Core modules not all built yet",
                        test="✓ fixture")

RESOLVED_DECISIONS["OD-01"] = (
    "Resolved in P1-01 (MD §1 'registry key wins'): queue → queue-operations, insights → analytics; "
    "trade-network is new and distinct from b2b-network (supplier discovery, P6); payroll stays FUTURE; "
    "business-passport / business-community are outside the MD and untouched."
)
