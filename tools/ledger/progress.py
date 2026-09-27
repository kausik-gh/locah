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


# ---------------------------------------------------------------- P1-02
done("P1-02", {
    "PM-03": dict(status=P, code="automation triggers consume inventory.stock.low/replenished and every lead.* event through the subscriber registry; events for modules not built yet arrive with them",
                  db="✓ platform_outbox_events", svc="✓", test="✓ drain_events in tests"),
    "PM-04": dict(status=C, code="one ladder engine (automation_rules/automation_steps): idempotency key ladder:entity:period:step, quiet hours 21:00–08:00 IST, owner switch cancels pending steps with a reason, worker automation lane; 9 source ladders defined, a ladder is only offered once its steps have code (stock.low, lead.followup today)",
                  db="✓ migration 20260927110000 + RLS", svc="✓ AutomationEngine + /automations", perm="✓ settings.read/update + actor matrix",
                  ws="✓ Settings › Automations", auto="✓ worker lane", test="✓ test_platform_primitives + browser p1_02"),
    "PM-05": dict(status=C, code="gapless row-locked series per (business, series key, period) with FY helper; offline number blocks reserve/release; first consumer is GST invoicing (P1-04)",
                  db="✓ number_series, number_series_blocks + RLS", svc="✓ NumberSeriesService", test="✓ 20 concurrent allocations with rollbacks → 1..20; blocks never overlap"),
    "PM-06": dict(status=P, code="Money type (integer paise + currency, Indian grouping, allocation without losing a paisa) for all new tables; First Launch tables stay NUMERIC(12,2) — converting them is a data migration not yet planned",
                  svc="✓ platform_core.money", test="✓"),
    "PM-07": dict(status=P, code="reportlab renderer (A4, 58 mm, 80 mm; bundled DejaVu fonts; deterministic bytes) + hashed, versioned store + permission-checked download; no module renders through it yet (invoices in P1-04); Tamil/Hindi shaping not supported by reportlab",
                  db="✓ rendered_documents + RLS", svc="✓ /documents/{id}", test="✓ deterministic + dedupe + stranger denied"),
    "PM-08": dict(status=C, code="consent store: a grant is a row, a withdrawal closes it, history never overwritten; purpose/channel/source/evidence; staff records and withdraws on the customer page",
                  db="✓ customer_consents + RLS", svc="✓ ConsentService + /consents", perm="✓ customers.read/update + actor matrix",
                  ws="✓ Customer › What they agreed to", test="✓ API + isolation + browser p1_02"),
    "PM-09": dict(status=C, code="per-business monthly meters with idempotent counting, owner caps (carried forward), 80%/100% alerts to Notifications; AI tokens counted and capped today (website + interview generation fall back to the plain draft at the cap); WhatsApp/SMS/email/voice/maps start counting when their providers connect",
                  db="✓ usage_meters, usage_events + RLS", svc="✓ UsageMeterService + /usage", ws="✓ Settings › Usage",
                  test="✓ caps/alerts + generation metered and capped"),
    "PM-12": dict(status=P, code="server contract built: client mutation UUIDs, idempotent replay, per-mutation permission check, rejection reasons; no production mutation kinds or device queue until POS (P1-05)",
                  db="✓ offline_mutations + RLS", svc="✓ POST /sync", test="✓ replay idempotent + permission checked"),
    "PM-17": dict(status=C, code="ladders are scheduled and cancelled only by event subscribers (automation_triggers); the engine imports no module code",
                  test="✓"),
    "PM-19": dict(status=P, code="P1-01/P1-02 tables each ship RLS + isolation test (assert_tenant_isolated) + actor-matrix rows; rule continues per packet",
                  test="✓ test_platform_primitives isolation ×9, test_actor_matrix primitives ×7"),
    "PR-10": dict(status=P, code="INR default, DPDP consent records exist; English UI only; GST/UPI arrive with invoicing/POS"),
    "PR-11": dict(status=C, code="every owner automation runs on the ladder engine: idempotent steps, owner activity log with outcome, per-automation and per-step off switch, never offered without code behind it",
                  ws="✓ Settings › Automations", test="✓"),
    "PR-13": dict(status=P, code="metering + caps + alerts built and live for AI tokens; pass-through pricing waits on OD-04; WhatsApp/voice/Maps meters count once connected"),
    "CR-05": dict(status=C, code="consent per purpose/channel with timestamp, source and evidence on the customer page (see PM-08)",
                  db="✓", svc="✓", ws="✓", test="✓"),
    "CR-02": dict(status=P, code="timeline now reads as sentences on the customer page (was printing raw objects); invoices/messages/reviews/jobs join as those modules land",
                  ws="✓ Customer › Activity"),
    "AU-03": dict(status=C, code="stock below reorder point → one alert per item per day to everyone with inventory.read; cancelled when stock is replenished; skipped if already restored; drafting a purchase request waits for Buying (P4)",
                  svc="✓", ws="✓ Settings › Automations + Notifications", auto="✓ stock.low", test="✓ API + browser p1_02"),
    "AU-07": dict(status=C, code="follow-up date → nudge to the assignee (or everyone with leads.read); stops when the lead moves stage, closes or is deleted; a new date replaces the old",
                  svc="✓", ws="✓ Settings › Automations + Notifications", auto="✓ lead.followup", test="✓"),
    "AU-09": dict(status=C, code="activity log lists every step with outcome and status; whole-automation and per-step switches; switching off cancels pending steps with a reason",
                  ws="✓ Settings › Automations", test="✓ API + browser p1_02"),
    "PK-01": dict(status=P, code="'Storefront is always on': built Storefront modules (customer-relationships today) start active on every business, are backfilled (migration 20260927120000) and cannot be switched off; reviews/messaging/insights/compliance not built yet",
                  test="✓ test_storefront_is_always_on"),
    "TS-01": dict(status=P, code="subcategory→module fixtures; ladder schedules + quiet hours; number-series concurrency; tax/BOM/yield fixtures come with their packets", test="◐"),
    "TS-02": dict(status=P, code="full suite on the RLS-enforcing platform_api role (890 tests); every new table has isolation + actor-matrix rows", test="✓"),
    "TS-09": dict(status=P, code="Phase B CDP flows p1_01_modules (11 checks) and p1_02_primitives (21 checks), desktop + 390 px, screenshots in acceptance-out/phase_b", test="✓"),
})
UPDATES["PKT-01"] = dict(status=C, code="[P1-01] every subcategory's recommendation matches the snapshot fixture (427 subcategories)",
                         test="✓ test_taxonomy_recommendations")
UPDATES["PKT-02"] = dict(status=C, code="[P1-02] all 9 new tables have isolation tests; idempotency proven for ladders, number series, meters, offline replay, document store and consent",
                         test="✓ test_platform_primitives (24) + actor matrix (7)")


# ---------------------------------------------------------------- P1-SH (part 1): roles, scope, staff logins
done("P1-SH", {
    "FD-07": dict(status=P, code="owner adds a person with a role + scope; LOCAH makes a one-time join link (hash stored, shareable on WhatsApp); the person creates their own login with the invited email or signs in, joins with the role applied (inviter's authority re-checked at join); role homes land with the navigation step",
                  db="✓ business_invitations.role_template/access_scope/display_name/join_token_hash + token RLS arm",
                  svc="✓ /team/people, /team/invitations/{id}/link, /v1/public/join/{token}", perm="✓ team.invite + delegation ceiling",
                  ws="✓ Team › Add a person, /join/{token}", test="✓ API + browser p1_team (staff signs up in a separate browser)"),
    "RL-01": dict(status=P, code="Owner template (everything, business scope, Workspace); home question recorded — the three-band home is the navigation step",
                  perm="✓", ws="◐"),
    "RL-02": dict(status=P, code="Manager template (operations, bookings, stock, staff rota, customers) with location scope enforced server-side (ORM filter + write guard) and by restrictive RLS on orders, bookings, deliveries, stock, quotes, projects; approvals up to a limit need the approval engine",
                  perm="✓ location scope enforced + tested", test="✓ test_roles_and_scope"),
    "RL-05": dict(status=P, code="Cashier template defined (location scope, POS surface); offered once POS ships (P1-05)"),
    "RL-07": dict(status=P, code="Store keeper template (stock, counts, adjustments) at chosen locations — verified in the browser seeing only their location; goods receipt, transfers and requisitions come with Buying (P4)",
                  perm="✓", ws="✓ Team", test="✓ API + browser p1_team"),
    "RL-14": dict(status=P, code="Accountant template (payments, orders, quotes, memberships, stock valuation, exports; no customer messaging); invoices/ledger/expenses join with P1-04/P1-06"),
    "RL-16": dict(status=C, code="owners make custom roles from a template in plain words; nobody can create, give or add a person with more than they hold (checked on create, assign, add and again at join)",
                  db="✓ business_custom_roles + RLS", svc="✓ /roles, /roles/custom", perm="✓ delegation ceiling",
                  ws="✓ Team › Roles", test="✓ API + isolation + browser p1_team"),
})


# ---------------------------------------------------------------- P1-SH (part 2): navigation and role homes
done("P1-SH", {
    "FD-07": dict(status=C, code="owner adds a person with a role + scope; one-time join link (hash stored, WhatsApp share); the person creates their own login with the invited email and lands on their role's home with only their areas",
                  db="✓", svc="✓", perm="✓ delegation ceiling, inviter re-checked at join", ws="✓ Team › Add a person, /join",
                  role="✓ role home + role-shaped navigation", test="✓ API + browser p1_team, p1_shell"),
    "FD-08": dict(status=C, code="the Guide's areas in fixed order (Home, Business presence, Sell/Serve, Offerings, Customers, Money, Team, Reach, Insights, AI employees, Modules & integrations, Settings); each shows only children whose module is on and whose permission the person holds; Reach/Insights/AI employees appear once their tools are built; area label follows what the business does (Sell / Serve / Sell & serve)",
                  ws="✓ AppSidebar + lib/workspace-nav", role="✓", test="✓ browser p1_shell (owner, store keeper, manager)"),
    "FD-09": dict(status=P, code="home answers the role's question from real records within permissions and locations: owner (needs you now · today · your business incl. setup next), manager (late or stuck at my location · today), store keeper (what is low · what arrived), accountant (unpaid · due); cashier, front desk, provider and dispatcher homes come with POS (P1-05) and the P2 roles",
                  svc="✓ /home", ws="✓", role="✓", test="✓ test_role_home + browser p1_shell"),
    "RL-01": dict(status=C, code="Owner: everything, business scope, Workspace; home answers needs you now · today · your business (Build Spec §8)",
                  perm="✓", ws="✓", role="✓", test="✓"),
    "SF-01": dict(status=C, code="Workspace serves owner, manager and office roles with role-shaped navigation and homes",
                  ws="✓", role="✓", test="✓ browser p1_shell"),
})
