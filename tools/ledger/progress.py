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


# ---------------------------------------------------------------- P1-03 offering kinds
done("P1-03", {
    "OF-01": dict(status=C, code="all 13 §6.3 kinds on one catalogue (First Launch keys kept: class_session, accommodation, rental, membership_plan) with kind fields validated server-side; new kinds enforce required fields, First Launch kinds report missing_fields so existing clients keep working",
                  db="✓ attributes, option_groups, sell_units, variant_options, stock_unit, hsn_sac", svc="✓ catalog/offering_kinds + /v1/public/offering-kinds",
                  ws="✓ Products & services: kind picker + one editor per kind", web="✓ per-kind cards", test="✓ test_offering_kinds + browser p1_03"),
    "OF-02": dict(status=C, code="HSN (4/6/8 digits) for goods, SAC (6 digits, 99…) for services; GTIN-shaped barcodes must pass the GS1 check digit",
                  db="✓ hsn_sac", svc="✓", ws="✓", test="✓"),
    "OF-03": dict(status=P, code="stock counted in pieces, grams or millilitres; goods sold by weight in packs (500 g takes 500 g of stock); buying units (crate, case) arrive with Buying (P4)",
                  db="✓ stock_unit, sell_units, order line stock_quantity", test="✓ 2 × 500 g reserves 1,000 g"),
    "OF-04": dict(status=C, code="variant options (e.g. Size × Colour) generate one variant per combination with its own stock; attributes checked against the options; the website offers the variant choice",
                  db="✓ variant_options, variants.attributes", svc="✓ /variants/matrix", ws="✓", web="✓", test="✓"),
    "OK-01": dict(status=P, code="product (variants optional) → cart → order on the website; POS arrives in P1-05", web="✓"),
    "OK-02": dict(status=P, code="sold by weight: price per kg, packs and cuts chosen on the website, priced and reserved in grams by the server; POS weighed label arrives in P1-05",
                  web="✓ pack + cut chooser", test="✓ API + browser (500 g boneless → ₹240, 500 g reserved)"),
    "OK-03": dict(status=P, code="menu items with required choices and add-ons (limits enforced, prices added server-side); table orders and KOT arrive with Kitchen (P2)",
                  web="✓", test="✓"),
    "OK-04": dict(status=P, code="service kind carries duration and at-home; booking flow unchanged (duration drives slots once bookings reads it, P2)"),
    "OK-05": dict(status=P, code="class books as before; course is a kind with length/sessions/mode/next batch and takes enquiries until Academics (P5)"),
    "OK-06": dict(status=P, code="room type and rental carry guests, beds, size, deposit, amenities; date-range booking as before"),
    "OK-07": dict(status=P, code="plan kind carries period and inclusions; joining online runs through the enquiry until membership sign-up online (P2)"),
    "OK-08": dict(status=P, code="package sold through the cart with what's included, sessions and validity; redeeming sessions arrives with memberships session packs (P2)"),
    "OK-09": dict(status=P, code="property project (status, location, RERA, possession, unit types, amenities) and unit kinds; website shows projects under status tabs with 'Book a site visit' and 'Enquire', both landing as leads with the preferred date; unit grid, availability chart and brochure lead (§19.2) are P2",
                  web="✓ projects tabs + enquiry", test="✓ browser p1_03"),
    "OK-10": dict(status=P, code="vehicle kind with specs; 'Book a test drive' request becomes a lead with the date; test-drive booking slots are P2",
                  web="✓", test="✓ API + browser"),
    "OK-11": dict(status=C, code="portfolio piece shown on the website with client/year/type and an enquiry action",
                  web="✓", test="✓"),
    "OK-12": dict(status=P, code="digital product sold through the cart with its format and how the buyer receives it; automatic download links need private file storage (not configured) — the business sends it after payment"),
    "OK-13": dict(status=P, code="cause takes gifts through checkout above its smallest gift with suggested amounts and real progress (paid gifts only); receipts and 80G come with Donations (P5)",
                  web="✓", test="✓ API + browser"),
    "OK-14": dict(status=C, code="new kinds render on the tenant site in the business's own theme; all existing catalogue tests pass (912 backend tests)",
                  web="✓", test="✓ browser p1_03 + full suite"),
    "PKT-03": dict(status=C, code="done-when met: existing catalogue tests still pass; new kinds render on the tenant site", test="✓"),
    "LD-01": dict(status=C, code="website enquiries now reach leads through /v1/public/websites/{slug}/enquiries (with purpose and preferred date; honeypot; rate-limited). Correction: the audit marked this complete, but no anonymous route existed until P1-03 — the site's enquiry form rendered nothing and 'Enquire' links led to a missing page",
                  svc="✓", web="✓ /enquire page + enquiry_form section", test="✓ test_website_enquiries_become_leads + browser"),
    "FD-03": dict(status=P, code="sites now present each item by its kind (packs/cuts, choices, variants, gifts, projects by status, test drive and site visit) and only offer actions whose tools are on; module-driven section placement by the CreativeDirector still to wire",
                  web="◐"),
})


# ---------------------------------------------------------------- P1-04 GST invoicing
_IV_TEST = "✓ test_invoicing_gst (36) + actor matrix + browser p1_04 (39 checks)"
done("P1-04", {
    "IV-01": dict(status=C, code="tax invoice carries GSTIN, FY number, HSN/SAC, taxable value, CGST + SGST (same state) or IGST (other state) and place of supply; prices with or without GST as the owner chose, discounts before tax",
                  db="✓ invoicing_documents/_lines + RLS + location scope", svc="✓ one engine (invoicing/tax_engine) for orders and bills",
                  api="✓ /invoices", perm="✓ invoices.*", ws="✓ Money › Bills & invoices", test=_IV_TEST),
    "IV-02": dict(status=C, code="B2B tax invoice with the buyer's GSTIN (check character and state verified), place of supply defaulting to the buyer's state, reverse-charge flag (tax shown, not collected); IRN/QR stays IV-12 (P4)",
                  svc="✓", ws="✓ new bill: registered business, place of supply, reverse charge", test=_IV_TEST),
    "IV-03": dict(status=C, code="composition registration issues a bill of supply: no tax computed or printed (A4 and thermal), the owner's declaration printed; orders of a composition business carry no tax either",
                  svc="✓", ws="✓", web="✓", test="✓ never prints a tax line (spec + browser)"),
    "IV-04": dict(status=C, code="not-registered business issues a plain bill with no GSTIN, place of supply or tax", svc="✓", test="✓"),
    "IV-05": dict(status=C, code="credit notes (return by quantity with optional restock, price reduction, correction) and debit notes (price increase, correction) reference the original, can never credit more than was billed, own gapless CN/DN series per GSTIN × FY, reduce what is owed",
                  svc="✓", ws="✓ bill page › Credit note / Debit note", test=_IV_TEST),
    "IV-06": dict(status=C, code="rates are data: per HSN/SAC (longest prefix) or per item with effective dates; a new rate ends the previous one; nothing seeded or guessed; a tax invoice is refused while any line has no rate; issued bills keep their rate",
                  db="✓ invoicing_tax_rates", ws="✓ Money › Tax rates (items without a rate named)", test=_IV_TEST),
    "IV-07": dict(status=C, code="numbers taken on issue from NumberSeriesService: one series per GSTIN × FY (Apr–Mar) × register, e.g. CHN1/26-27/00001; drafts have none; cancelled bills keep theirs and stay listed; 'Documents issued' report proves no gaps. VB-20: default padding 5 (source example has 6 → 17 characters)",
                  db="✓ unique (series, FY, seq)", test="✓ gapless across cancel/draft; two registers' blocks never overlap"),
    "IV-08": dict(status=P, code="A4, 80 mm and 58 mm PDFs (hashed, stored, versioned); 'Your bill from <business>' customer page on the business's site with its PDF; 'Send on WhatsApp' opens the owner's WhatsApp with the message and link. Sending from the business's WhatsApp number waits on messaging (P1-07, provider activation); email not sent (no email provider configured)",
                  web="✓ /<slug>/bill/<token>", ws="✓", test="✓ browser p1_04 (390 px)"),
    "IV-09": dict(status=P, code="sales register, HSN/SAC summary, tax by rate, documents issued and a GSTR-1 worksheet (B2B, B2C, inter-state B2C listed, notes, HSN, documents), each as CSV; portal file format to confirm (VB-14); Tally export arrives with the Tally connector (§15, P4)",
                  svc="✓ invoicing_reports", ws="✓ Money › Reports for your CA", perm="✓ invoices.export", test=_IV_TEST),
    "IV-10": dict(status=C, code="'Confirm with your CA' beside every tax-treatment choice: prices incl./excl. GST, advances (setting, 'not decided' by default), rate choices (rates are the owner's data), reverse charge per bill, composition declaration wording; the owner can record that their CA checked",
                  ws="✓ Settings › Tax & invoicing", test="✓ browser"),
    "IV-11": dict(status=C, code="§14.6: same-state CGST/SGST and other-state IGST from place of supply; composition never prints a tax line; round-off is its own line and never changes the tax — unit, API and browser",
                  test=_IV_TEST),
    "IV-13": dict(status=P, code="website and WhatsApp orders are priced by the same engine and billed when the owner chose (accepted / completed / manual), or from the order page; B2B and walk-in bills raised directly move stock on issue and back on cancel; returns restock. Counter bills join with POS (P1-05)",
                  svc="✓ invoicing.auto_bill subscriber (blocked bills notify, never guessed)", ws="✓ order page › Bill", test=_IV_TEST),
    "PKT-04": dict(status=P, code="§14.6 tests pass for the tax split, composition and round-off; register number blocks are proven not to overlap, but offline bills syncing from two registers can only be tested with the POS (P1-05)",
                   test=_IV_TEST),
    "CO-03": dict(status=P, code="invoice content and numbering per §14.4 done; e-invoice above threshold and e-way bills need a GSP (P4, OD-10)"),
    "RL-14": dict(status=P, code="accountant role now holds invoices (issue, cancel, record money, set up tax, export for the CA) with 'Unpaid' and 'Due' homes counting bills; ledger (P1-06), expenses and connectors (P4) not built yet",
                  perm="✓", role="✓ home: bills not fully paid, bills past due", test="✓"),
    "OR-07": dict(status=P, code="catalogue → cart → order → payment → invoice (engine-priced, auto or on demand) → inventory → fulfilment → tracking; review and customer-timeline links still absent",
                  test="✓ test_checkout_flow + test_invoicing_gst"),
    "AU-04": dict(status=S, code="overdue bills are visible (list filter, owner and accountant homes); the reminder ladder stays unwired until messaging (P1-07) can send the statement — it is not offered as an automation before then"),
})


# ---------------------------------------------------------------- P1-05 counter billing (POS)
_PS_TEST = "✓ test_pos (14, incl. TS↔Python engine parity on 300 bills) + actor matrix + browser p1_05 (25 checks, network cut)"
done("P1-05", {
    "PS-01": dict(status=C, code="a register is the invoicing register (one concept); a shift opens with the counted opening cash on a device and closes counted vs expected; one open shift per register; same person can continue on another device",
                  db="✓ pos_shifts + RLS + location scope", svc="✓ PosService", ws="✓ /pos/{id} full screen", test=_PS_TEST),
    "PS-02": dict(status=C, code="scan (barcode, item code, scale label) or search from the cached catalogue → bill; optional customer by phone (found or added), name and business GSTIN",
                  ws="✓", test=_PS_TEST),
    "PS-03": dict(status=P, code="cash with change, UPI (QR for the exact amount to the business's own UPI ID; the cashier confirms, or marks 'UPI to verify'), card on an external terminal with its reference, split tenders; change only from cash. Automatic UPI confirmation by payment webhook needs a payment provider (Cashfree, activation required); khata tender arrives with the credit book (P1-06)",
                  ws="✓", test=_PS_TEST),
    "PS-04": dict(status=C, code="hold and recall bills for a queue of customers; held bills are kept on the device and survive a reload", ws="✓", test="✓ browser"),
    "PS-05": dict(status=C, code="returns at the counter become a credit note against the bill, put stock back, and refund cash from the drawer (or record UPI/card refund)",
                  svc="✓ pos.return", ws="✓ Return", test=_PS_TEST),
    "PS-06": dict(status=C, code="discount cap per role (owner none; cashier/manager set by the owner); voids outside the open shift and returns past the window need a manager's PIN — hashed, lockout after 5 wrong tries, approval is a short-lived signed token checked on the server",
                  perm="✓ pos.approve", svc="✓", ws="✓", test=_PS_TEST),
    "PS-07": dict(status=P, code="receipt prints through the browser in an 80 mm layout (checked in print emulation) and as the bill's 58/80 mm PDF; ESC/POS bytes with drawer kick sent over Web Serial where the browser has it — built, not yet tried on a physical printer (TS-08); 'Send on WhatsApp' opens WhatsApp with the customer's bill link once the bill has synced",
                  ws="✓", test="✓ browser (print layout)"),
    "PS-09": dict(status=P, code="the counter keeps selling with the network cut: catalogue cached with a version stamp, bills and drawer entries queued on the device and synced automatically when the connection returns (verified by cutting the network in the browser). Reloading the page while offline needs the app shell cached (service worker) — not built yet",
                  ws="✓", test="✓ browser p1_05 offline"),
    "PS-10": dict(status=C, code="each register holds a block of numbers (default 50, owner-set) for offline bills; the next block is reserved while online when fewer than 10 remain; the unused end goes back to the series at close so numbers stay gapless",
                  svc="✓ ensure_block / return_tail", test=_PS_TEST),
    "PS-11": dict(status=C, code="UPI taken offline (or without seeing it arrive) is 'UPI to verify'; Settings › Counter billing lists them; 'not received' puts the amount back as owed on the bill",
                  ws="✓", test=_PS_TEST),
    "PS-12": dict(status=P, code="USB/Bluetooth scanners work as keyboard input into the scan box; in-store codes (EAN-13, 20… range, VB-21) given per item and printed on an A4 sheet or 50×25 mm labels. Camera scanning not built yet",
                  ws="✓ item page › Barcode and labels", test=_PS_TEST),
    "PS-13": dict(status=C, code="scale labels decoded with the business's own format (prefix, item digits, weight or price, decimals; check digit verified; cannot clash with in-store codes); item code = the item's SKU. VB-16: confirm against the pilot's scales",
                  test=_PS_TEST + " + browser scale label"),
    "PS-14": dict(status=C, code="expected = opening + cash sales + cash put in − cash refunds − petty expenses − cash taken out; counted and variance logged per shift; a short or over drawer notifies the managers; Money › Counter shifts",
                  ws="✓", test=_PS_TEST),
    "PS-15": dict(status=C, code="bills rung up offline on two registers, synced late, out of order and replayed, number each register 1..n with no duplicates or gaps and move stock once", test=_PS_TEST),
    "PKT-05": dict(status=C, code="done-when met: two-register offline sync test passes (API + browser)", test=_PS_TEST),
    "PKT-04": dict(status=C, code="§14.6 tests all pass now that the counter exists: tax split, composition, round-off, and two-register offline numbering", test="✓ test_invoicing_gst + test_pos"),
    "IV-13": dict(status=C, code="counter, website and B2B bills all come from the one engine with a stock movement; orders are priced by it; WhatsApp orders use the same order path (P1-08)", test="✓"),
    "RL-05": dict(status=C, code="Cashier role offered wherever the counter is on: bill, take payments, returns within the window, cash shift, discount up to the owner's cap; location-limited; home 'Your counter' shows the open shift and drawer",
                  perm="✓", role="✓", ws="✓", test=_PS_TEST),
    "SF-03": dict(status=C, code="the counter is a full-screen surface outside the Workspace shell for tablet or desktop, usable at 390 px", ws="✓", test="✓ browser"),
    "OK-01": dict(status=C, code="products sold on the website (cart → order) and at the counter", test="✓"),
    "OK-02": dict(status=C, code="goods sold by weight: packs and cuts on the website; at the counter by weight (typed or from a scale label) or by pack", test="✓ browser p1_03 + p1_05"),
    "IN-13": dict(status=P, code="online orders and counter bills move the same stock records; WhatsApp orders join with P1-08"),
    "CN-20": dict(status=P, code="scanner as keyboard ✓, scale labels ✓, ESC/POS receipts + drawer kick over Web Serial built (not hardware-tested), camera scanning and kitchen printers not built"),
    "PR-09": dict(status=P, code="the counter works over a dropped connection with its own queue; the crew app arrives in P2; device testing on entry-level hardware is TS-08"),
})


# ---------------------------------------------------------------- P1-06 khata / credit book
_LG_TEST = "✓ test_khata (12, incl. 30 concurrent writers) + actor matrix + browser p1_06 (25 checks)"
done("P1-06", {
    "LG-01": dict(status=C, code="one account per customer (linked to their customer record) or supplier; balance moves only with an append-only entry under the account's row lock (entries cannot be updated or deleted — a DB trigger refuses it; mistakes are corrections with a reason); opening balances carried over from the notebook",
                  db="✓ ledger_accounts + ledger_entries + RLS + append-only trigger", svc="✓ LedgerService", api="✓ /ledger/accounts",
                  ws="✓ Money › Khata (credit book)", perm="✓ ledger.read / record / manage", test=_LG_TEST),
    "LG-02": dict(status=C, code="credit comes from bills so the tax record and the khata agree: a Workspace bill 'on their khata' or the counter's khata tender posts the unpaid part to the customer's account; money recorded on a khata bill, credit/debit notes on it and cancelling it flow back to the khata",
                  svc="✓ charge_bill / on_bill_payment / on_note / on_cancel", ws="✓ New bill › Put this bill on their khata; counter › Khata tab", test=_LG_TEST),
    "LG-03": dict(status=C, code="the owner (ledger.manage) sets each customer's limit and days to pay; at the limit the counter refuses khata unless a manager approves with their PIN (signed short-lived approval, recorded on the entry and notified to those who manage the book); in the Workspace only ledger.manage can allow a bill over the limit",
                  ws="✓", test=_LG_TEST + " + browser PIN override"),
    "LG-04": dict(status=C, code="ageing by FIFO (money received settles the oldest amounts first) into not due / 1–30 / 31–60 / 61–90 / 90+ days late, for customers and suppliers; totals for receivable, payable and past due; late and over-limit accounts on the owner's 'Needs you now' and the accountant's 'Unpaid' and 'Due'",
                  ws="✓ account page + list", role="✓ owner, accountant homes", test=_LG_TEST),
    "LG-05": dict(status=P, code="statement link (hash-only token, opens just that account on the business's own website in its theme) with a UPI link and QR to the business's own UPI ID for the amount due; sent from the account page through WhatsApp click-to-chat; statement PDF for any period. Automatic WhatsApp sending and reminder ladders need the messaging foundation (P1-07, provider activation)",
                  web="✓ /{slug}/khata/{token}", ws="✓", test=_LG_TEST),
    "LG-06": dict(status=C, code="money received (cash, UPI, card, bank transfer, cheque) settles the customer's oldest open khata bills first and marks them paid / part paid; paid at the counter it lands in that shift's drawer; payments made to suppliers; purchases on credit from suppliers with their bill number and due date",
                  ws="✓ account page; counter › Khata", test=_LG_TEST),
    "LG-07": dict(status=C, code="§26.3 done-when: 30 concurrent writers (entries, corrections, payments with bill settlement) leave balance = sum of entries, running balances consistent and line numbers 1..n with no gap. The test first failed (a row already in the session kept a stale balance after the lock) and the locked read now refreshes the row",
                  test=_LG_TEST),
    "PKT-06": dict(status=C, code="done-when met: balance equals sum of entries under concurrent writes (test_khata)", test=_LG_TEST),
    "GP-03": dict(status=P, code="udhaar notebook → khata with limits, ageing, statements and UPI links, carried-over balances; WhatsApp reminders on a schedule wait for messaging (P1-07)", test=_LG_TEST),
    "PS-03": dict(status=P, code="cash with change, UPI QR (cashier confirms or 'UPI to verify'), card with reference, khata (customer by phone, limit checked online, manager's PIN above it), split tenders; change only from cash. Automatic UPI confirmation by payment webhook needs a payment provider (Cashfree, activation required)",
                  ws="✓", test="✓ test_pos + test_khata + browser p1_05/p1_06"),
    "PS-05": dict(status=C, code="returns at the counter become a credit note against the bill, put stock back, and refund cash from the drawer, UPI/card — or back to the customer's khata when the bill was on khata",
                  svc="✓ pos.return", ws="✓ Return", test="✓ test_pos + test_khata"),
    "PS-14": dict(status=C, code="expected = opening + cash sales + khata paid in cash + cash put in − cash refunds − petty expenses − cash taken out; khata given and received shown at close; counted and variance logged per shift; a short or over drawer notifies the managers",
                  ws="✓", test="✓ test_pos + test_khata + browser p1_06"),
    "RL-14": dict(status=P, code="accountant role holds invoices and the khata (record money, set limits, corrections, statements) with 'Unpaid' and 'Due' homes counting bills and khata; expenses and connectors (P4) not built yet",
                  perm="✓", role="✓", test="✓ test_khata roles"),
    "RL-05": dict(status=C, code="Cashier: bill, take payments incl. khata within the limit and khata paid at the counter, returns within the window, cash shift, discount up to the owner's cap; location-limited",
                  perm="✓ + ledger.read/record", role="✓", ws="✓", test="✓ test_pos + test_khata"),
})


# ---------------------------------------------------------------- P1-07 WhatsApp foundation
_MS_TEST = "✓ test_messaging (18, recorded Meta webhook payloads + sandbox) + actor matrix + browser p1_07 (21 checks)"
done("P1-07", {
    "MS-01": dict(status=P, code="one inbox of WhatsApp conversations and messages (in, out, templates, locations, media notes, delivery status); a new number becomes a customer. Other channels (SMS, email) are MS-06, activation required",
                  db="✓ messaging_conversations + messaging_messages + RLS", svc="✓ MessagingService", api="✓ /messaging/*",
                  ws="✓ Reach › WhatsApp inbox", perm="✓ messaging.read / reply / configure", test=_MS_TEST),
    "MS-02": dict(status=P, code="library of 12 templates (order received / confirmed / out for delivery / delivered, booking confirmed / reminder, review request, payment due, your bill, renewal due, offer, team alert) in English, Tamil and Hindi, parameters in order, checked against WhatsApp's rules; submitted and tracked per business and language. Approval by Meta needs a real number (MS-07); Tamil and Hindi wording needs a native review (VB-22); renewal (P2) and offer (P3) are not sent yet",
                  ws="✓ WhatsApp › Message templates", test=_MS_TEST),
    "MS-03": dict(status=C, code="marketing templates go only to customers with an open WhatsApp marketing opt-in in the consent store; STOP (English, Tamil, Hindi) withdraws it and says so; transactional messages follow the customer's own order or booking",
                  test=_MS_TEST + " (§12.6 consent test)"),
    "MS-04": dict(status=P, code="router, cheapest branch first: STOP → opt-out; 'talk to a person' (button or words, English/Tamil/Hindi) → inbox; buttons and menu words → structured journeys (hook in place, journeys are P1-08); free text → a person until the AI WhatsApp Manager (P3)",
                  svc="✓ MessagingService.route", test=_MS_TEST),
    "MS-05": dict(status=C, code="a person's reply — in the inbox, or from the WhatsApp Business app on a coexistence number — keeps LOCAH's automatic replies out of that chat for the owner's pause (12 h default, 1–72); 'Hand back to LOCAH' lifts it",
                  ws="✓ inbox + WhatsApp settings", test=_MS_TEST + " (§12.6 12-hour test)"),
    "MS-07": dict(status=A, code="built, not exercised against Meta: Embedded Signup in the owner's browser (with the coexistence option), code exchange, app subscription to the WABA, token encrypted at rest, Cloud API sends and template submission; switched on only when LOCAH's Meta app (app id, secret, Embedded Signup configuration, Graph API version) is configured — until then the page says so. A dev-only sandbox number stands in on test stacks",
                  ws="✓ WhatsApp › Your WhatsApp number"),
    "MS-08": dict(status=C, code="webhook: Meta's verify-token handshake and X-Hub-Signature-256 on every delivery (refused unsigned or wrongly signed; off until configured); resolves the business by phone number id under RLS; one message per delivery id; forward-only delivery statuses; coexistence echoes. Notification routing: order received / confirmed / delivered, booking confirmed to customers (owner switches each), out-for-delivery, booking reminders, bill and khata payment reminders on ladders; team members' own alerts (new orders, bookings, enquiries, chats waiting, khata over limit). Every message is metered and stops at the owner's cap",
                  api="✓ /v1/webhooks/whatsapp", svc="✓ messaging_notify subscribers + ladder steps", test=_MS_TEST),
    "MS-22": dict(status=P, code="chips: needs a person (with wait), LOCAH replying, topic, assignee, unread; side panel: customer, khata balance, recent orders, bookings, membership, with links. The 'AI handling' chip arrives with the AI WhatsApp Manager (P3); topics are set by the journeys (P1-08)",
                  ws="✓", test="✓ browser p1_07"),
    "MS-23": dict(status=C, code="assign to anyone who may reply, quick replies (saved from any reply), wait timer; a chat waiting over 10 minutes shows in Needs you now (owner) and Late or stuck (manager), and alerts those who asked on WhatsApp and in Notifications",
                  ws="✓", role="✓", test=_MS_TEST),
    "MS-24": dict(status=P, code="§12.6 here: duplicate webhook deliveries create one message; no automatic message within 12 h of a person's reply; no marketing template without consent — zero model calls. 'Cart price = catalogue price' and duplicate deliveries creating one order arrive with the order journey (P1-08)",
                  test=_MS_TEST),
    "PKT-07": dict(status=A, code="done-when met on the test stack: the owner connects a number, turns on new-order alerts, an order arrives and the owner's alert and the customer's update are sent (API test + browser). Doing it with a real number needs Meta activation (MS-07)",
                   test=_MS_TEST),
    "CO-02": dict(status=P, code="opt-in enforced; template categories (utility / marketing) carried and metered; the bot handles only this business's tasks (router sends anything else to a person); the number's quality rating and limit are shown when Meta reports them. Off-topic redirect wording comes with the journeys (P1-08)"),
    "GP-01": dict(status=P, code="one WhatsApp inbox with the customer's orders, bookings and khata beside the chat; WhatsApp flows that create real orders and bookings are P1-08"),
    "AU-04": dict(status=C, code="bills with a due date and khata balances get payment reminders on the due day, 7 days late (and 15 days for bills, with an owner notification), with the bill or statement link; they stop when paid, cancelled or settled; the owner switches them in Automations. Live delivery needs a real number (MS-07)",
                  test=_MS_TEST),
    "AU-02": dict(status=C, code="booking confirmation on confirm and reminders the day before and 2 hours before; stops on cancel or reschedule (a rescheduled confirmed booking is reminded at its new time)", test="✓ test_messaging (confirm, reminder, cancel)"),
    "AU-05": dict(status=C, code="out for delivery → tracking link to the customer; 'delivered' when delivered, which also stops the tracking step", test="✓ test_messaging"),
    "LG-05": dict(status=C, code="statement link on the business's own site with UPI link and QR; sent from the business's WhatsApp number (or from the staff member's phone); khata reminders when a balance falls due and 7 days later. Live delivery needs a real number (MS-07)",
                  web="✓", ws="✓", test="✓ test_khata + test_messaging"),
    "GP-03": dict(status=C, code="udhaar notebook → khata with limits, ageing, statements, UPI links, carried-over balances and WhatsApp reminders", test="✓ test_khata + test_messaging"),
    "PM-09": dict(status=P, code="per-business monthly meters with idempotent counting, caps, 80%/100% alerts; AI tokens and WhatsApp messages counted and capped today; SMS/email/voice/maps start counting when their providers connect"),
    "IV-08": dict(status=P, code="A4 PDF, 58/80 mm thermal PDF, the customer's bill page, and 'Your bill from <business>' sent from the business's WhatsApp number or the staff member's phone; email not built (no email provider for business mail yet); GSTR-1 format VB-14"),
})


# ---------------------------------------------------------------- P1-08 WhatsApp journeys
_JR_TEST = ("✓ test_journeys (6: order with a price change between summary and tap, duplicate deliveries, stock "
            "short, zone, COD cap, reorder, cancel; book from opening hours with a resource held; enquiry; dues; a "
            "person's pause; entry points — zero model calls, AI guard record empty) + browser p1_08 (30 checks)")
done("P1-08", {
    "MS-04": dict(status=C, code="router, cheapest branch first: STOP → opt-out; 'talk to a person' → inbox; button and list replies, menu words (English, Tamil, Hindi) and plain keywords ('track', 'cancel my booking', 'how much do I owe') → the structured journey; other free text → a person, with 'send menu' offered, until the AI WhatsApp Manager (P3)",
                  svc="✓ MessagingService.route + messaging.journeys", test=_JR_TEST),
    "MS-09": dict(status=A, code="built: the business number's wa.me link with 'menu' typed, its QR (download for counter and packaging) on the WhatsApp page; the tenant website's WhatsApp button, phone bar and footer say 'Order / Book on WhatsApp' and open the menu; the Marketplace listing's WhatsApp action does the same — each only when the number is connected and a journey can run. Google Business Profile links (MK-06) and Click-to-WhatsApp ads (MK-04) need those providers",
                  ws="✓ WhatsApp › Customers order and book here", web="✓ website + Marketplace", test=_JR_TEST),
    "MS-10": dict(status=A, code="menu → category → item (today's price) → option / pack / required choices as lists → quantity (buttons or typed) → cart (checkout row kept while adding) → delivery or pickup → address → summary → 'Place order' → the same order the website creates (CheckoutService.place_for_contact: stock reserved, fulfilment job, channel whatsapp) with the tracking link. Pay on delivery / at pickup with the owner's first-order cap. Online payment links need a payment provider; WhatsApp Flows (form screens) need Flow publishing through Meta (MS-07) — lists and buttons carry the same choices meanwhile",
                  svc="✓ journeys order_*", test=_JR_TEST),
    "MS-11": dict(status=C, code="service → location (when several) → day → free times from the location's weekly opening hours, each checked like the website's booking page (provider, capacity, bookable resources) → confirm button → booking with channel whatsapp and the resource held; typed time when no hours are set",
                  svc="✓ journeys book_*", ws="✓ Locations › Opening hours editor", test=_JR_TEST),
    "MS-12": dict(status=C, code="'Ask a question' → the customer types it → a lead with source whatsapp and the chat link, and the chat waits for a person (inbox, Needs you now, alerts); assigned from Enquiries like any website lead",
                  test=_JR_TEST),
    "MS-13": dict(status=P, code="'What do I owe' → khata balance with the statement link (UPI link and QR to the business's own UPI) and each unpaid bill with its page; payment-due templates carry the same links (P1-07). Provider payment links need a payment provider (activation); membership renewal is P2",
                  test=_JR_TEST),
    "MS-14": dict(status=C, code="'Track my order' / 'where is my order' → each open order's status in words and its tracking link", test=_JR_TEST),
    "MS-15": dict(status=C, code="'Repeat my last order' → the last order's items that are still sold, re-priced today, through the same checkout and confirm button", test=_JR_TEST),
    "MS-16": dict(status=P, code="cancel an order while it is still waiting to be accepted, and a booking outside the owner's cancellation window; anything later, and changes (reschedule, edit an order), go to a person with the reason shown",
                  test=_JR_TEST),
    "MS-17": dict(status=C, code="'Talk to a person' is on the menu and on every summary, problem and confirmation; typing 'talk to a person' / 'human' (and Tamil, Hindi) works at any step; the chat goes to the inbox and LOCAH steps back", test=_JR_TEST),
    "MS-18": dict(status=C, code="nothing is placed or booked without the customer's button; at 'Place order' the cart is priced from the catalogue again — a changed price shows the new total and asks again; stock short offers 'Make it N' or remove; a taken slot shows the other free times", test=_JR_TEST + " (§12.6)"),
    "MS-19": dict(status=A, code="a location pin or a typed address with its PIN code is matched to the owner's delivery zones (radius zones use the pin) and kept on the order's delivery job; the customer's last delivery address is offered first. Turning a pin into a street address needs a maps provider",
                  test=_JR_TEST),
    "MS-20": dict(status=C, code="LOCAH's replies only offer this business's own tasks; anything it does not recognise goes to a person ('someone will reply here soon — or send menu'), never a made-up answer", test=_JR_TEST),
    "MS-22": dict(status=P, code="chips: needs a person (with wait), LOCAH replying, topic (order, booking, enquiry, payment — set by the journeys), assignee, unread; the choices LOCAH offered show under its message (on a test number they can be tapped as the customer); side panel: customer, khata, orders, bookings, membership. The 'AI handling' chip arrives with the AI WhatsApp Manager (P3)",
                  ws="✓", test="✓ browser p1_07 + p1_08"),
    "MS-24": dict(status=C, code="§12.6: a cart is never placed at a price other than the catalogue's at that moment (price changed between summary and tap → new total, confirmed again); duplicate webhook deliveries create one message and one order; no automatic message within the pause after a person's reply; no marketing template without consent — zero model calls",
                  test=_JR_TEST + " + test_messaging"),
    "PKT-08": dict(status=C, code="done-when met: the §12.6 tests pass with zero model calls (test_journeys + test_messaging; the suite's AI guard fails any attempted model call)", test=_JR_TEST),
    "OR-02": dict(status=C, code="orders carry where they came from — website, WhatsApp, counter, phone, entered by the team, Marketplace, ChitBridge (P4) — shown on the orders list; bookings too",
                  db="✓ orders_orders.channel / bookings_bookings.channel", ws="✓ Orders › From", test=_JR_TEST),
    "CO-02": dict(status=P, code="business-task replies only, opt-in enforced, template categories carried and metered, quality rating shown when Meta reports it. On a live number these rules are exercised only after Meta activation (MS-07)"),
    "GP-01": dict(status=C, code="one WhatsApp inbox with the customer's orders, bookings and khata beside the chat, and WhatsApp journeys that create the same orders, bookings and enquiries as the website", test=_JR_TEST),
    "CN-23": dict(status=C, code="every WhatsApp message LOCAH sends — journey replies, templates, team alerts, inbox replies — is counted once (idempotent per message) with its category (service, utility, marketing) on the business's monthly meter, capped where the owner sets a limit; so a change in WhatsApp's per-message prices is absorbed by the count, not by guesswork",
                  test="✓ test_messaging (meter + cap) + test_journeys"),
})


# ---------------------------------------------------------------- P1-09A verified review invitations
done("P1-09A", {
    "RV-01": dict(status=P, code="completed orders and bookings invite exactly once per interaction, within 30 days; membership check-ins wait for P2 attendance and closed job cards for P5 jobs; reviewer write path and UI are not yet exposed", test="✓ test_review_invites (2)"),
    "RV-03": dict(status=P, code="completion event records a review invitation and My Activity prompt; a review_request WhatsApp template is sent 2 hours later only when the contact has not reviewed or declined; customer review page and My Activity link remain to build", auto="✓ review.request", test="✓ test_review_invites (2)"),
    "AU-06": dict(status=P, code="completed order or booking → one review invitation, WhatsApp request after 2 hours; replay is idempotent and declined invitations do not send; reviewer page and membership/job sources remain", auto="✓ review.request", test="✓ test_review_invites (2)"),
    "PKT-09": dict(status=P, code="P1-09 in progress: verified order/booking invitation and WhatsApp delivery tested; review APIs, customer/owner/moderator surfaces, compliance, and §17.5 security tests remain", test="✓ test_review_invites (2); §17.5 pending"),
})


# ---------------------------------------------------------------- P1-09B reviewer, owner, moderator and compliance surfaces
_RV_TEST = "✓ test_reviews + test_review_invites + browser p1_09_review_browser (local Chromium, scratch DB)"
_CP_TEST = "✓ test_compliance (local scratch DB, platform_api RLS role)"
done("P1-09B", {
    "RV-01": dict(status=P, code="one review per completed order or booking in a 30-day window; source completion is checked again at submission. Membership attendance (P2) and closed job cards (P5) do not exist yet", test=_RV_TEST),
    "RV-02": dict(status=C, code="customer review page accepts 1–5 stars, text and up to three JPEG/PNG/WebP photos; verified source label; desktop and mobile browser submission persisted", web="✓ reviewer page", test=_RV_TEST),
    "RV-03": dict(status=C, code="one completion invitation, two-hour WhatsApp review request while still open, and identity-scoped review link in My Activity; decline stops the request", auto="✓ review.request", web="✓ My Activity", test=_RV_TEST),
    "RV-04": dict(status=C, code="owner can reply publicly, report with a listed reason and feature up to six reviews in the structured tenant-site section", ws="✓ Customers › Reviews", web="✓ reviews section", test=_RV_TEST),
    "RV-05": dict(status=C, code="admin moderation queue, listed removal reason and append-only log, reviewer notice and one appeal with moderator decision; owner cannot remove a review", api="✓ admin reviews", test=_RV_TEST),
    "RV-06": dict(status=C, code="reviewer alone may update their own rating/text within the allowed window; moderator may redact only selected personal-data spans or remove a photo; business API cannot edit/delete and DB trigger refuses direct business writes", test=_RV_TEST),
    "RV-07": dict(status=C, code="public average and distribution use every published review, not just featured ones; tenant section shows true average and See all reviews; marketplace projection follows review events", web="✓ website + Marketplace", test=_RV_TEST),
    "RV-08": dict(status=C, code="1–2 star review creates owner notification and Needs you now item with contact; only reviewer token can change review facts", ws="✓ Needs you now", test=_RV_TEST),
    "RV-11": dict(status=C, code="restricted-role tests reject business editing/deletion, ineligible or duplicate review, and verify public average; moderator, appeal and reviewer-update paths covered", test=_RV_TEST),
    "CP-01": dict(status=C, code="owner/CA-entered licence and filing calendar with recurring due dates, history, renew/file/archive and no invented statutory dates", ws="✓ Licences & deadlines", test=_CP_TEST),
    "CP-02": dict(status=P, code="30/7/1-day and due-day ladder notifies authorised owner/CA and leaves overdue items in Needs you now until renewed; task creation waits for the P2 Tasks module", auto="✓ compliance.due", test=_CP_TEST),
    "CP-03": dict(status=P, code="each compliance item can hold an HTTPS document link; a managed document vault/upload and access lifecycle are not built", ws="✓ document link", test=_CP_TEST),
    "CP-04": dict(status=C, code="entered licence/accreditation number can be explicitly shown in the tenant site's footer; blank or private values are omitted", web="✓ public licences", test=_CP_TEST),
    "AU-06": dict(status=P, code="completed orders/bookings invite once and schedule WhatsApp request; membership attendance and closed jobs wait for P2/P5", test=_RV_TEST),
    "AU-08": dict(status=P, code="due-date ladder notifies and persists a Needs you now item; task creation waits for P2 Tasks", test=_CP_TEST),
    "GP-14": dict(status=P, code="verified order/booking reviews, owner replies, low-rating recovery and moderation are live locally; membership/job sources and real provider activation remain", test=_RV_TEST),
    "GP-15": dict(status=P, code="licence calendar, reminders and owner action list built; actual Tasks item and document vault are pending", test=_CP_TEST),
    "CO-11": dict(status=P, code="FSSAI number can be entered and opted in for site display; food-specific mandatory-field policy verification remains", test=_CP_TEST),
    "PKT-09": dict(status=C, code="P1-09 §17.5 security and average tests pass; reviewer, owner, moderator and compliance paths implemented locally. P2/P5 source types, Tasks and document vault remain explicit partial rows", test=_RV_TEST + "; " + _CP_TEST),
})


# ---------------------------------------------------------------- P1-10A stock depth (§15.1)
_ST_TEST = ("✓ test_stock_depth (19, platform_api RLS role) + browser p1_10a_stock (20/20) and "
            "p1_10a_counter_serials (8/8), desktop + 390 px")
_ST_UI = "✓ Stock: a view per stock profile (counter by weight, batches & expiry, serials & warranty, size × colour, ingredients, reorder) + counts, wastage, item settings"
done("P1-10A", {
    "IN-02": dict(status=C, code="stock kept in pieces, grams or millilitres (weighed goods shown in kg); an item's buying units (crate of 24, 25 kg bag) convert on receipt; selling packs convert on sale (P1-03)",
                  db="✓ offerings.buy_units", svc="✓ /stock/receipts", ws=_ST_UI, test=_ST_TEST),
    "OF-03": dict(status=C, code="buy by crate, case or bag (buying units per item) and sell per 500 g or per piece; both convert to the one stock unit",
                  db="✓", svc="✓", ws="✓ Item settings › How you buy it", test=_ST_TEST),
    "IN-03": dict(status=P, code="owner-entered yields (1 kg whole chicken → 800 g curry cut) and cutting runs: source consumed, outputs weighed, trim reported, the whole's cost carried into the cuts, actual vs usual yield per pair; procurement maths uses yield when Buying/Recipes arrive (P4)",
                  db="✓ inventory_yields, inventory_conversions", svc="✓ /stock/yields, /stock/conversions", ws="✓ Cut and portion, live trim", test=_ST_TEST),
    "IN-05": dict(status=C, code="batches with batch number and expiry; every sale (counter, Workspace bill, online and WhatsApp orders) picks first-expiry-first-out, then unbatched stock, then expired stock (reported); cancellations and returns go back to the same batch at the value they left with; expiry alerts 30/7/0 days before through the automation kernel; write-off of an expiring or expired batch",
                  db="✓ inventory_batches + line batch_allocations", svc="✓", perm="✓ RLS + location scope", ws="✓ Batches & expiry", auto="✓ inventory.expiry", test=_ST_TEST),
    "IN-06": dict(status=C, code="serial / IMEI per unit received; captured at sale — required on a Workspace bill, scanned into the counter bill (scanning the IMEI on the box adds that phone), recorded on an online order's line before it completes; returns put the serial back; warranty from the sale date and item's warranty months; lookup by serial shows sale, bill and warranty",
                  db="✓ inventory_serials", svc="✓ /stock/serials/{serial}", ws="✓ Serials & warranty", role="✓ counter", test=_ST_TEST),
    "IN-08": dict(status=C, code="stock counts by location (and category): the counter counts blind, submits; differences change stock only when someone with inventory.approve approves, applied against current stock so sales during the count are kept; store keepers cannot approve",
                  db="✓ inventory_counts, inventory_count_lines", svc="✓", perm="✓ inventory.approve", ws="✓ Counts", test=_ST_TEST),
    "IN-09": dict(status=C, code="wastage with reasons (expired, damaged, trim loss, spoiled, missing, sample, other) in the order each business uses them; batch write-offs; cutting trim; 30-day wastage by reason with cost for those who may see it",
                  db="✓ movements.reason_code", svc="✓ /stock/wastage", ws="✓ Wastage", test=_ST_TEST),
    "IN-10": dict(status=P, code="reorder level and fill-up-to level per stock line and location; low-stock alert (P1-02 ladder); suggested quantity to the fill-up level; turning it into a requisition draft arrives with Buying (P4)",
                  db="✓ reorder_max", svc="✓", ws="✓ Reorder", auto="✓ stock.low", test=_ST_TEST),
    "IN-12": dict(status=C, code="weighted-average value on every stock line: receipts at what they cost, sales, wastage and counts at the average, returns at the value they left with, cutting runs carry value into the cuts; value visible only with inventory.cost; goods receipts from purchase orders (P4) post through the same receive",
                  db="✓ stock_value_paise, movements.value_delta_paise", svc="✓", perm="✓ inventory.cost", test=_ST_TEST),
    "IN-13": dict(status=C, code="online orders, WhatsApp orders (same order service, test_journeys reserves the same stock), counter bills and Workspace bills all move the one stock record with its batches, serials and value",
                  test=_ST_TEST + "; test_journeys"),
    "RL-07": dict(status=P, code="store keeper: stock, receiving (with batch, expiry, serials and cost from the supplier's bill), wastage, blind counts at chosen locations — cannot approve counts or see stock value; transfers (P2) and requisitions (P4) not built",
                  test=_ST_TEST),
    "GP-06": dict(status=P, code="yields, cutting trim, wastage reasons and approved counts make leakage visible; linking sales to ingredients waits for Recipes (P4)",
                  test=_ST_TEST),
    "TS-01": dict(status=P, code="[P1-10A] stock-profile fixtures per subcategory (meat → by weight with yield; pharmacy → batches; mobile store → serials; clothing → sizes; restaurant → ingredients); yield, FEFO and valuation arithmetic tested; tax/BOM fixtures come with their packets",
                  test="◐"),
    "PB-102": dict(status=P, code="Core built — counter billing, GST bills, stock with batches and expiry, khata, orders, payments; Rec fulfilment built, dispatch (P2), loyalty (P3), procurement and connectors (P4) not yet", test="✓ fixture"),
    "PB-202": dict(status=P, code="Core built — serialised items with IMEI at the counter and warranty lookup, GST bills, payments; Rec bookings/leads built, repair job cards (P5) not yet", test="✓ fixture + browser p1_10a_counter_serials"),
    "PB-201": dict(status=P, code="Core built — size × colour variants with a stock grid, counter, orders, fulfilment, GST bills; Rec reviews built, loyalty/marketing (P3) and connectors (P4) not yet", test="✓ fixture + browser p1_10a_stock"),
    "PB-206": dict(status=P, code="Core built for cosmetics — batches and expiry at the counter, orders, bills; optical lens orders as jobs (P5) not yet", test="✓ fixture"),
    "PB-404": dict(status=P, code="Core built — batch/expiry counter billing (earliest expiry sold first, expiry alerts), orders, GST bills, payments; prescription verification, refills (memberships P2), dispatch (P2) and distributor POs (P4) not yet", test="✓ fixture + browser p1_10a_stock"),
})


# ---------------------------------------------------------------- P1-10B one customer identity
_ID_TEST = ("✓ test_customer_identity (3, platform_api RLS role) + browser p1_10b_identity (14/14), desktop + 390 px, "
            "local worker draining events")
done("P1-10B", {
    "FD-01": dict(status=C, code="one LOCAH sign-in across businesses: each tenant site has My account (orders with track/bill/order-again, upcoming and past bookings with the manage link, bills, khata with statement, quotes, memberships) in the business's own colours; signed-in checkout and booking join the customer's own record; guests still check out; earlier guest records join only through the account's verified email (Doc 12), never name or unverified phone",
                  db="✓ link_verified_customer_contacts(), my_contacts_in_business()", svc="✓ /v1/me/businesses/{slug}/account, /reorder",
                  perm="✓ identity-checked SECURITY DEFINER functions; account for another identity is empty; reorder of another's order 404",
                  cust="✓ /{slug}/account + /activity", web="✓ header My account, footer link, signed-in checkout/booking", test=_ID_TEST),
    "FD-02": dict(status=P, code="My Activity across businesses: orders (with tracking), bills (open the bill), quotes, memberships, bookings, review invitations — each linking back to that business's account page; written by the customer_activity subscriber from order/invoice/quote/membership/fulfilment/payment events; guardian/student portal items join with Academics (P5)",
                  db="✓", svc="✓ customer_activity subscriber", cust="✓ /activity", test=_ID_TEST),
    "SF-05": dict(status=C, code="My Activity lists the customer's own orders, bookings, bills, quotes, memberships and review invitations across businesses", test=_ID_TEST),
    "OR-08": dict(status=C, code="Order again on the business's website refills the cart from an earlier order at today's catalogue price and names what is no longer sold; WhatsApp 'repeat last order' since P1-08", web="✓ /{slug}/checkout?reorder=", test=_ID_TEST),
    "FR-BK-06": dict(status=P, code="customer account shows upcoming and past bookings with the manage link; front-desk and provider surfaces arrive in P2"),
})


# ---------------------------------------------------------------- P1-10C module-aware website + Marketplace
_MA_TEST = ("✓ test_module_aware_site (11, platform_api RLS role) + test_journeys/test_marketplace_* + browser "
            "p1_10c_site (21/21), desktop + 390 px, local worker reindexing")
done("P1-10C", {
    "FD-03": dict(status=P, code="one capability answer (website/capabilities.py) from module readiness, offering kinds and traits feeds the website, its header button, the Marketplace listing and WhatsApp; a ready tool adds its section to the home page when the design has none (Orders → shop, Memberships → Plans, Bookings → classes / rooms / book band, Reviews → verified reviews, Enquiries → enquiry or quote form), above the contact details, each hideable by the owner; placing those sections by the design strategy (CreativeDirector) rather than above contact, and P2+ tools' sections, remain",
                  db="✓ websites.auto_sections_hidden", svc="✓ website/capabilities.py", ws="✓ Website › What customers can do / Sections your tools add",
                  web="✓ auto sections, readiness-gated controls", test=_MA_TEST),
    "FD-04": dict(status=C, code="switching a tool on and setting it up changes the live site with no rebuild (within the one-minute page cache): a gym that publishes a plan gains Plans with Ask to join, a 'See plans' header button and My account; bookable classes or rooms add their section, other bookable services a Book band; archiving the last plan or hiding the section takes them away again",
                  web="✓", test=_MA_TEST),
    "FD-05": dict(status=C, code="Marketplace actions (Order, Book, See plans, Get a quote, Book a site visit, Donate, Enquire, Call, WhatsApp, Visit) come from the same readiness answer and land where the site has that section (including a tool's own section); the business's way of trading (booking-, subscription-, quote-, donation-led) picks the first action on the card; reindexed when plans, providers, pickup/delivery, stock, traits or tool sections change",
                  svc="✓ listing_actions + marketplace.index triggers", cust="✓ card honours the business's lead action", test=_MA_TEST),
    "FD-10": dict(status=C, code="a module's customer actions appear only when it is built, switched on and set up (module_readiness) on the website, the Marketplace listing, WhatsApp menus and the owner's home; the Workspace website page says what is still missing for each tool that is on but not ready",
                  ws="✓ 'Not yet: Publish at least one plan'", web="✓", test=_MA_TEST),
    "OM-06": dict(status=C, code="booking-led businesses (trait) lead with Book on their site header and Marketplace card once Bookings is ready", test=_MA_TEST),
    "OM-07": dict(status=C, code="quote-led businesses lead with 'Get a quote' (Quotes + Enquiries ready): header button, a quote form on the home page and a Marketplace action; the request lands in Enquiries as a 'Quote request' lead the team quotes from",
                  web="✓", test=_MA_TEST),
    "OM-18": dict(status=P, code="digital-only businesses publish no address or map anywhere on the site (location list removed, contact address stripped); digital product delivery and meeting links are not built yet",
                  web="✓", test=_MA_TEST),
    "OM-19": dict(status=C, code="a business with no online selling gets an information site whose main button is Call or WhatsApp, WhatsApp journeys and the counter (P1-04, P1-07/08); switching ordering on later adds the shop, basket and Order button without a rebuild",
                  test=_MA_TEST),
})


# ---------------------------------------------------------------- P1-10D1 collect what is due (Founder refinement — Payments)
_PY_TEST = ("✓ test_payment_collect (15, platform_api RLS role) + browser p1_10d1_payments (83/83, Playwright Chromium), "
            "desktop + 390 px, local worker, sandbox WhatsApp number, fixture provider webhooks")
_PY_ONLINE = "online payment on a link needs the provider adapter (Cashfree, PY-10) — not offered, never a button that cannot work"
done("P1-10D1", {
    "PY-02": dict(status=A, code="a payment link for all or part of what is due on an order, booking, membership, bill or khata balance (7 days; the token is stored only as a hash): shared from the owner's phone or sent from the business's own WhatsApp number (payment_due template; sandbox-verified, a live number needs Meta activation MS-07); the customer pays by UPI straight to the business and says so, the business confirms it arrived; retry, withdraw, cancel and expiry on the same transaction. " + _PY_ONLINE + "; renewal reminders that carry a link come with the Memberships lifecycle (FR-MB-02, P2)",
                  db="✓ payments_requests + RLS", svc="✓ /collect/requests, /whatsapp, public /pay/{token}", perm="✓ payments.collect; store keeper 403; other business 404",
                  ws="✓ Money panel on order, booking, membership, bill, khata", cust="✓ /{slug}/pay/{token} in the business's colours", test=_PY_TEST),
    "PY-04": dict(status=C, code="advances and deposits on orders, bookings and memberships by link or recorded at the desk; total, paid and balance always shown; booking deposits as before; a quote's deposit is collected on the order it converts into (project milestone payments are P5, OM-08)",
                  ws="✓", test=_PY_TEST),
    "PY-05": dict(status=C, code="split tender at the counter — cash, UPI, card on the business's terminal and khata in one bill that sees the combined settlement (₹400 cash + ₹600 UPI in the browser); several recorded payments settle one order, booking or membership",
                  ws="✓ counter + Money panel", test=_PY_TEST + "; test_pos"),
    "PY-06": dict(status=C, code="cash, UPI, card on the business's own terminal and bank transfer recorded with a reference against counter bills, orders, bookings and memberships — never more than is due; cash collected on delivery settles only the balance left after an advance",
                  ws="✓", test=_PY_TEST),
    "PY-07": dict(status=C, code="paying on delivery or at pickup on/off with a cap for a customer's first order: one rule for the website and WhatsApp, kept with pickup and delivery (Deliveries & pickup › Zones & charges, and the WhatsApp page edits the same rule); the checkout states the cap and refuses a first COD order above it; pay at pickup is not COD",
                  db="✓ fulfilment_settings.cod_allowed / first_order_cod_cap (moved from messaging_settings)", ws="✓ Zones & charges", web="✓ checkout", test=_PY_TEST),
    "PS-03": dict(status=A, code="cash with change, UPI QR for the exact amount (cashier confirms, or 'UPI to verify'), card with reference, khata with limit and manager's PIN, split tenders (browser-verified); change only from cash. Automatic UPI confirmation by a payment webhook needs the provider (Cashfree, activation required)",
                  ws="✓", test="✓ test_pos + test_khata + browser p1_05, p1_06, p1_10d1"),
    "FR-PY-01": dict(status=A, code="payment state is separate from the transaction's own state (unpaid, being confirmed, paid, failed, part paid, refunded, part refunded, cancelled, expired); a failed try never undoes money already taken; retry is a new attempt on the same transaction — never a new order; nothing new is offered while a try is being confirmed; a replayed success pays once and a late success on an older try is kept and flagged 'paid twice' (fixture webhooks). Checking a pending online payment with the provider before another try needs the provider adapter (Cashfree)",
                     svc="✓", test=_PY_TEST),
    "FR-PY-02": dict(status=P, code="full, advance, deposit, balance and pay-later collection chosen by the owner per transaction; total, paid and balance on every surface; the balance collected later by link, at the counter, in cash or by UPI. A business-set rule that asks for an advance at checkout (fixed or % — custom cakes, pre-orders) arrives with dated pre-orders (P1-10D2)",
                     test=_PY_TEST),
    "FR-PY-03": dict(status=A, code="the link is tied to the real order, booking, membership, bill or khata balance and can go on WhatsApp from the business's number or the owner's phone; UPI to the business is confirmed by the business, and a verified provider webhook would mark the same record paid exactly once (fixture). " + _PY_ONLINE,
                     test=_PY_TEST),
    "FR-PY-04": dict(status=C, code="refunds link to a prior payment (full or part) and keep the original and the net; a refund never reopens a balance to chase; a bill issued from an order shows what was paid on the order and takes money only through the order (one money book); owner Payments: paid today (verified money only, each rupee once), waiting for you to confirm, needs attention (failed, paid twice), still owed, refunds",
                     ws="✓ Payments", test=_PY_TEST),
    "CR-02": dict(status=P, code="the customer page timeline reads as sentences and now includes each verified payment ('Paid ₹800 (advance) by UPI · Order …') beside orders, bookings and memberships; counter bills, messages, reviews and jobs join as those modules write to it",
                  ws="✓ Customer › Activity", test=_PY_TEST),
    "FR-OR-10": dict(status=P, code="the counter does the whole workflow (P1-05/06, serials and batches P1-10A, split tender browser-verified in P1-10D1); a counter bill for a named customer reaches their My Activity and khata, but counter bills do not yet write the owner's customer timeline (CR-02)",
                     test="✓ test_pos + browser p1_05_pos, p1_10a_counter_serials, p1_10d1_payments"),
    "FR-OR-07": dict(status=P, code="pickup, delivery zones with charges, paying on delivery on/off with a first-order cap (now one rule for website and WhatsApp, P1-10D1), GST treatment and readiness-driven channels exist; minimum order, free-delivery threshold, preorder rules, cutoff, lead time, cancellation/return policy, packing charge, auto-accept and dine-in are absent, shipping needs an aggregator (FU-02), and settings are not yet filtered to what the business uses"),
})


# ---------------------------------------------------------------- P1-10D2a dated pre-orders (MD §6.1, §21.1; Founder: Orders)
_PO_TEST = ("✓ test_preorders (10, platform_api RLS role) + browser p1_10d2_preorders (31/31, Playwright Chromium), "
            "desktop + 390 px; website flows p1_03/p1_10b/p1_10d1 re-run on the new checkout")
done("P1-10D2", {
    "OR-04": dict(status=C, code="dated pre-orders on the one order: per-item rules (needs a day or may take one, notice, next-day cutoff, ready times, festival window, days ahead, daily limit, % or ₹ advance, cancel window) checked in one place for the website, WhatsApp and a phone order; the order keeps the day and a snapshot of the terms; the advance becomes a payment link on the same order; the owner works them by day wanted (overdue · prepare now · today · tomorrow · later) with a production list per day",
                  db="✓ offerings.preorder, orders.due_at/preorder/advance_amount/preorder_terms", svc="✓ orders/preorder.py, orders/board.py, /checkout/price, /orders/board, /orders/production",
                  perm="✓ orders.read; same RLS as orders", ws="✓ Item › Order ahead; Orders › By day wanted; Production list", cust="✓ checkout day picker, confirmation, account, tracking",
                  web="✓", test=_PO_TEST),
    "FR-OR-16": dict(status=C, code="bakery cakes, festival boxes, home-kitchen batches, meat/fresh orders for a day: required day and time, notice, cutoff, window, daily limit (two orders never both take the last one — advisory lock), advance with the customer's confirmation, cancel window enforced for customer self-cancel on WhatsApp; operational board distinguishes overdue, prepare now, today, tomorrow and later; production list adds up what to make with each written message; website, WhatsApp and phone orders use the same check",
                     test=_PO_TEST),
    "FR-PY-02": dict(status=C, code="full, advance, deposit, balance and pay-later: an item's own advance rule (% or ₹ per piece) is asked at checkout and on WhatsApp and becomes a link on the order; booking deposits as before; the owner can ask any part by link or record it; total, paid and balance on every surface",
                     test=_PO_TEST + "; test_payment_collect"),
    "OR-09": dict(status=C, code="the website checkout shows only the server's prices (POST /checkout/price: lines with choices, tax, delivery, pre-order days, advance) and places at the catalogue's price; WhatsApp re-prices at the confirm button (MS-24); a sent unit price is never used",
                  svc="✓", web="✓", test="✓ test_checkout_flow + test_preorders + test_journeys + browser p1_10d2"),
    "FR-OR-04": dict(status=P, code="a real checkout in the business's colours: basket priced by the server with choices and written messages, pickup or delivery with address and zone charge, the day and time for made-to-order items, paying (COD cap stated), GST and total from the server, the advance and the balance, confirmation with the advance link, tracking and My Activity; dine-in (P2), shipping (aggregator), charges other than delivery (packing) and online payment (Cashfree) are missing",
                     web="✓ /{slug}/checkout", cust="✓ /track + /account + /activity", test=_PO_TEST),
    "FR-OR-06": dict(status=P, code="price, option prices, tax, delivery charge, stock (problems shown before placing) and pre-order availability (notice, cutoff, window, daily limit) come from the server and are checked again at placement; there are no customer discount codes yet, and ordinary orders are not checked against opening hours",
                     svc="✓ /checkout/price", test=_PO_TEST),
    "FR-OR-07": dict(status=P, code="pickup, delivery zones with charges, paying on delivery with a first-order cap (one rule for website and WhatsApp), GST treatment, readiness-driven channels, and per-item pre-order rules (notice, cutoff, ready times, window, daily limit, advance, cancel window — shown only for items sold through a basket); minimum order, free-delivery threshold, packing charge, auto-accept, a business-wide return policy and dine-in are absent, shipping needs an aggregator (FU-02)"),
    "FR-OR-17": dict(status=P, code="WhatsApp offers 'Make it N' or remove and asks again (MS-18); the website checkout shows 'only N left — change the quantity or remove it' before placing and a full pre-order day cannot be picked; alternatives and a reconfirmation flow when the business finds a line short after accepting are not built",
                     test=_PO_TEST + "; test_journeys"),
    "FR-OR-19": dict(status=P, code="cancel releases the reservation, cancels the delivery job and writes My Activity; customers cancel on WhatsApp while waiting, or a pre-order until its cancel window; money already taken shows as 'refund due' in Payments until refunded; there is no cancellation message to the customer and no rule by preparation stage for ordinary orders",
                     test="✓ test_orders_kernel + test_fulfilment_kernel + test_preorders"),
    "FR-OR-22": dict(status=C, code="one Orders list for every channel; channel is a filter (Website, WhatsApp, Counter, Phone, Entered by team, Marketplace) and provenance on each order — never a separate book",
                     ws="✓ Orders › Any channel", svc="✓ ?channel=", test=_PO_TEST),
    "FR-OR-23": dict(status=P, code="a business that sells made-to-order items or takes dated orders (bakery, home kitchen, festival boxes) opens Orders on the board by day wanted with its production list, chosen from its own data; others keep the plain list. The kirana picking, meat cut-prep/weight-exception, QSR/restaurant KDS and retail shipping/returns workflows are not built",
                     ws="◐", test=_PO_TEST),
    "FR-OR-27": dict(status=P, code="website checkout (p1_03, p1_04, p1_10d2), WhatsApp ordering (p1_08), POS sale (p1_05, p1_10d1 split), meat by weight (p1_03, p1_10a), bakery pre-order (p1_10d2) and reorder (p1_10b) exist as browser flows; human phone order, partial availability on the website, cancel and the combined owner view are not yet flows"),
    "MS-16": dict(status=P, code="cancel an order while it waits to be accepted, a pre-order until its cancel window (P1-10D2), and a booking outside the owner's window; changes (reschedule, edit an order) go to a person with the reason shown",
                  test="✓ test_journeys + test_preorders"),
})


# ---------------------------------------------------------------- P1-10D2b formula pricing (MD §21.2; Business OS Guide p.22)
_FP_TEST = ("✓ test_formula_pricing (7, platform_api RLS role: isolation of both tables, append-only rate history) "
            "+ browser p1_10d2_formula (28/28, Playwright Chromium), desktop + 390 px")
done("P1-10D2", {
    "OK-15": dict(status=C, code="any basket/counter item can be priced from a rate the owner enters (22K gold per g, silver, a metal or commodity by weight): rate × quantity + making (% of the metal value, ₹ per unit or ₹ per piece) + other charges, rounded to the rupee or paisa; GST stays the item's HSN/rate on the bill. Entering today's rate keeps the history (append-only) and re-prices the items using it for the next sale; each order line keeps the working at confirmation and each bill line keeps it as price_basis, so a later rate never rewrites a sale; the website card, the order, the bill (screen and PDF) and the customer's bill link show the working; Home asks for rates not entered today",
                  db="✓ pricing_rates, pricing_rate_values, offerings.price_formula, invoicing_document_lines.price_basis",
                  svc="✓ pricing/formula.py; /pricing/rates, /pricing/rates/{id}/values", perm="✓ offerings.read / offerings.update; RLS on both tables",
                  ws="✓ Products & services › Today's rates; Item › Price › From a rate; Home › rates to enter for today",
                  cust="✓ card shows today's working; bill link shows it", web="✓", test=_FP_TEST),
    "PB-203": dict(status=P, code="Core built — formula-priced items from a daily rate board, counter billing at today's rate, GST tax invoices that keep weight × rate + making, orders (custom orders can ask an advance, P1-10D2a), stock per piece; Rec leads and bookings built. Hallmark HUID per piece can be kept as the piece's serial number but is not yet named or checked as a HUID",
                   test="✓ fixture + browser p1_10d2_formula"),
})


# ---------------------------------------------------------------- P1-10E1 basic insights (MD §26.3 P1-10; First Launch §12.1)
done("P1-10E", {
    "IS-01": dict(status=C, code="Insights › Your numbers: sales (issued bills less credit notes, counter share), orders (value, by channel, cancelled apart), bookings (held, came in, waiting, did not come, cancelled) and money received (the same count as Payments, split by bills/counter, orders·bookings·plans, khata) for today, the last 7 days and this month; each number opens its page; a tool that is off is named, never a zero; no permission and location scope are respected (a location-limited manager sees their locations and is not shown business-wide money); Home's Today band links to it. Trends and comparisons are the later Analytics module (First Launch §12.2)",
                  svc="✓ insights/basic.py; GET /insights?period=", perm="✓ per-card permission + module; ORM location scope",
                  ws="✓ Insights › Your numbers; Home › Today link",
                  test="✓ test_basic_insights (5, platform_api RLS role) + browser p1_10e_insights (14/14, Playwright Chromium), desktop + 390 px"),
})


# ---------------------------------------------------------------- P1-10E2 tags and rule-built segments (MD §6.1, §18.2)
_SEG_TEST = ("✓ test_customer_segments (5, platform_api RLS role: rules, counts, consent, tags, branch scope, "
             "isolation) + browser p1_10e_segments (13/13, Playwright Chromium), desktop + 390 px")
done("P1-10E", {
    "CR-03": dict(status=C, code="tags on a customer are added (from the business's existing tags or new) and removed on the customer page; stored cleaned (spaces collapsed, lower case, no duplicates, at most 20); the customer list shows tags, a tag bar with counts, and filters by a tag",
                  svc="✓ GET /customers/tags, /customers?tag=", ws="✓ Customer › Tags; Customers › tag bar", test=_SEG_TEST),
    "CR-04": dict(status=C, code="rule-built segments: bought an item N+ times in D days (orders and counter bills, an order's bill never counted twice, cancelled orders excluded), spent ₹X+ in D days, no purchase or visit for D days, became a customer in D days, booked N+ times, membership ended A–B days ago and not renewed, owes on khata, has a tag — all must hold; a rule is offered only when its tool is on; members are worked out from the records every time (never a stale list); each segment shows its count, its rules in words and how many said yes to WhatsApp offers (consent store); the viewer's location scope applies to the orders, bills and bookings read. §18.2's 'within 5 km' and 'birthday this month' need a customer location and birthday the record does not keep; broadcasting to a segment is MK-01/P3",
                  db="✓ customer_relationships_segments (RLS)", svc="✓ customers/segments.py; /customers/segments(/preview)",
                  perm="✓ customers.read to view, customers.update to save", ws="✓ Customers › Segments (builder, list, members)",
                  test=_SEG_TEST),
})


# ---------------------------------------------------------------- P1-10E3 per-customer export and erasure (MD §25.1 DPDP)
_DPDP_TEST = ("✓ test_customer_privacy (3, platform_api RLS role: export, request, blockers, erasure, kept bill, "
              "permissions, location scope, isolation) + browser p1_10e_privacy (17/17, Playwright Chromium), desktop + 390 px")
done("P1-10E", {
    "CR-08": dict(status=C, code="per-customer export (their record, consents, notes, activity, orders with lines and delivery address, bookings, bills, payments, khata with entries, memberships, quotes, enquiries, reviews, WhatsApp messages) as one file — by the owner on the customer page and by the customer from 'My account' on the business's site; erasure removes name, phone, email, tags, notes, enquiry text, WhatsApp chat, delivery addresses and their My Activity entries, withdraws consents, and keeps issued bills (buyer as billed, CGST Act s.36) and khata entries on an anonymous record; it waits while an order is in progress, a booking is upcoming, a membership runs or a khata balance stands, and needs the name typed; the customer's erasure request reaches the owner (Home + notification), who erases or declines with a reason the customer sees. Export and erasure need a whole-business viewer; erasure needs the new customers.erase (owner by default); the audit records who and when, never the erased details",
                  db="✓ contacts.erased_at, customer_relationships_privacy_requests (RLS)",
                  svc="✓ customers/privacy.py; /customers/{id}/export|erase|privacy, /customers/privacy-requests, /me/businesses/{slug}/my-data|erasure-request",
                  perm="✓ customers.export, customers.erase (new), whole-business only", ws="✓ Customer › Their data; Home request",
                  cust="✓ My account › Your details (download, ask to delete, status)", web="✓", test=_DPDP_TEST),
    "CO-01": dict(status=P, code="consent store (PM-08), per-customer export and erasure (CR-08) and the retention defaults stated at erasure (bills 72 months, khata entries 8 years, sales records kept without name) are built; automatic purging on those periods is not, and guardian-first flows arrive with Academics (§20.4, P5). DPDP Rules commencement dates were not verified online in this build (no network lookups made)",
                  test=_DPDP_TEST),
})


# ---------------------------------------------------------------- P1-10E4 solo businesses (MD §22)
done("P1-10E", {
    "OM-21": dict(status=P, code="a business whose organisation shape is solo (chosen, or its family's default) and that has one active member gets no team menus (People, Roles, Staff & rota), a Calendar under Home — bookings, orders wanted for a day, follow-ups, memberships ending and licences due in one list, each opening its record, within the viewer's permissions — and 'Invite someone' under Settings; a second person joining brings the team menus back. 'AI employees act as the staff' waits for the AI employee runtime (P3)",
                  svc="✓ /me/context solo; GET /calendar (services/one_calendar.py)", ws="✓ solo navigation; Home › Calendar",
                  test="✓ test_solo_calendar (2) + browser p1_10e_solo (10/10, Playwright Chromium), desktop + 390 px"),
})


# ---------------------------------------------------------------- P1-10E5 phone orders and order changes (Founder: Orders)
_OC_TEST = ("✓ test_order_changes (5, platform_api RLS role) + browser p1_10e_phone (17/17, Playwright Chromium), "
            "desktop + 390 px")
done("P1-10E", {
    "FR-OR-13": dict(status=C, code="Orders › Take a phone order: the caller's name and number (matched to their customer record by number), items with their pack, option, choices and written message, pickup or delivery with the address, the day a made-to-order item can be ready — priced by the server exactly as the website prices it (/orders/phone/price → price_cart) and placed through the website's own path (place_for_contact: stock reservation, delivery zone and charge, pay-on-delivery rule, pre-order day and advance link, fulfilment job, payment attempt) with channel 'phone' and the staff member as the actor; the advance link can be sent on WhatsApp or read out",
                     svc="✓ orders/phone.py; /orders/phone, /orders/phone/price", perm="✓ orders.create",
                     ws="✓ Orders › Take a phone order", test=_OC_TEST),
    "FR-OR-18": dict(status=C, code="Change order on an open, unbilled order: quantities, lines removed, items added (with their choices); the server re-prices added lines from today's catalogue (agreed lines keep their price), reserves or releases stock for the difference (refusing more than is in stock), re-works tax and total with the billing engine, re-checks a delivered order's charge under today's zones and a dated order's day/limit/advance, and compares the money already taken with the new total (still to collect, or a refund due flagged in Payments; the cash expected on delivery follows the balance); a preview runs the same code in a rolled-back savepoint; saving needs the customer's agreement and records before/after in the order's history and the audit. A billed order is changed with a credit note instead. Changing the address or pickup/delivery is not part of the edit, and the customer confirms by phone/in person (recorded by staff) — no self-confirm link",
                     svc="✓ orders/edit.py; /orders/{id}/change?preview=", perm="✓ orders.create",
                     ws="✓ Order › Change order", test=_OC_TEST),
    "FR-OR-27": dict(status=P, code="website checkout (p1_03, p1_04, p1_10d2), WhatsApp ordering (p1_08), POS sale (p1_05, p1_10d1 split), meat by weight (p1_03, p1_10a), bakery pre-order (p1_10d2), reorder (p1_10b), human phone order and an order changed after the call (p1_10e_phone) exist as browser flows; the AI phone order fixture (P3), restaurant table order and kitchen (P2), partial availability on the website, return/exchange and the combined owner view are not yet flows"),
})


# ---------------------------------------------------------------- P1-10E6 English, Tamil and Hindi (MD §2 r10, §12, §23 #22)
_LANG_TEST = ("✓ test_customer_language (5), test_site_words (5), test_workspace_words (6) — platform_api RLS role and "
              "source checks — + browser p1_10e_language (23/23) and p1_10e_workspace_language (15/15), Playwright "
              "Chromium, desktop + 390 px")
_LANG_SCOPE = ("WhatsApp: every journey phrase, the person hand-off and STOP answer in the customer's language — "
               "detected from Tamil/Devanagari script, or chosen from the menu's Language row (then it sticks); "
               "templates go in the customer's language when that version is approved; links sent carry ?lang=. "
               "Website: the owner ticks the site's languages (first shown first); visitors switch above the header or "
               "in the footer; the site's own words — buttons, basket, checkout, booking, headings LOCAH supplies, "
               "tracking, bills, payment links, khata, reviews, booking management — follow; the owner's words stay as "
               "written; Tamil and Devanagari faces behind every site font. Workspace: a per-person language saved on "
               "the account (sidebar picker; a new browser adopts it) for the navigation, Home, Orders, an order, "
               "phone orders, changes, the production list and the money panel; the rest of the Workspace, the "
               "counter (POS), the inbox chrome and numbers-with-words the API composes (e.g. '1 order') are still "
               "English. All Tamil and Hindi wording is LOCAH's first draft and needs a native speaker's review "
               "(VB-22) before a pilot")
done("P1-10E6", {
    "PR-10": dict(status=P, code="INR, GST (invoicing), UPI (POS/collect), WhatsApp-first, DPDP consent records and per-customer export/erasure exist. " + _LANG_SCOPE,
                  db="✓ contacts.language/language_source, websites.languages, consumer_profiles.preferences.workspace_language",
                  svc="✓ messaging/words.py; PUT /website/languages; PUT /me/workspace-language",
                  web="✓ tenant site EN/TA/HI", ws="✓ Website › Languages; sidebar language", test=_LANG_TEST),
    "PKT-10": dict(status=P, code="basic insights from real data are complete (IS-01). Strings: " + _LANG_SCOPE, test=_LANG_TEST),
    "GP-22": dict(status=P, code=_LANG_SCOPE, test=_LANG_TEST),
})


# ---------------------------------------------------------------- P1 gate review — stale notes brought up to date (no status raised)
done("P1-gate", {
    "FR-OR-01": dict(status=P, code="website checkout, Marketplace (card → the business's own site), WhatsApp journeys, the counter, reorder and a staff phone order in the Workspace (FR-OR-13, P1-10E5) all place the one Order; AI phone ordering (P3), QR/table ordering (P2) and connector orders (P4) are not built"),
    "OM-09": dict(status=P, code="a portfolio_item kind (client, year, type of work) is sold as an enquiry and renders on the site with its details and 'Enquire' (P1-03); gallery sections and portfolio design families exist. A dedicated 'Our work' section chosen for portfolio-led businesses, and case-study pages, are not built"),
})


# ---------------------------------------------------------------- P2-01 assignment scope + stage engine (MD §7.2–§7.3, §24 #10–#11)
_AS_TEST = ("✓ test_assignment_scope (5), test_actor_matrix::test_assignment_matrix (2 roles × 8 record types), "
            "test_roles_and_scope — platform_api RLS role, incl. the RLS-only check with app.current_assignee — + "
            "browser p2_01_stages_and_assignment (20/20, Playwright Chromium), desktop + 390 px")
_ST_TEST = ("✓ test_stage_engine (7, platform_api RLS role) + browser p2_01_stages_and_assignment (20/20, Playwright "
            "Chromium), desktop + 390 px")
_AS_CODE = ("a member whose role's scope is `assignment` sees and changes only what is assigned to them: bookings where "
            "they are the provider, enquiries assigned to them, project tasks assigned to them, quotes they wrote or for "
            "the customer of their enquiry, and of the customer book only the customers on those bookings and "
            "enquiries. Enforced server-side for every ORM read and write in the request (authorization/"
            "assignment_scope.py: loader criteria + a flush guard that refuses creating or handing a record to someone "
            "else), repeated by RESTRICTIVE RLS policies keyed on app.current_assignee; enquiries they add are theirs; "
            "counts on Home and Insights follow the same rule")
done("P2-01", {
    "RL-17": dict(status=P, code=_AS_CODE + ". The arm exists for bookings, enquiries, project tasks and quotes; dispatch jobs, job cards and the Tasks module add theirs when they ship (P2 dispatch, P5 jobs)",
                  db="✓ assignment_scope_allows_identity/member/quote() + 4 RESTRICTIVE policies", svc="✓ authorization/assignment_scope.py",
                  perm="✓ scope 'assignment' enforced; custom assignment roles limited to ASSIGNMENT_PERMISSIONS", test=_AS_TEST),
    "PM-11": dict(status=P, code=_AS_CODE + ". Actor-matrix rows cover provider and sales executive × bookings, customers, enquiries, quotes, orders, stock, payments, projects; delivery partner, technician and housekeeping rows join with their surfaces",
                  db="✓", svc="✓", perm="✓", test=_AS_TEST),
    "RL-18": dict(status=P, code="test_actor_matrix has one row per assignment-scoped role × record type for the two roles offered today (provider, sales executive; 8 record types each: own records only, or refused). Delivery partner, technician and housekeeping rows are added with dispatch, job cards and housekeeping, before their crew surfaces ship",
                  test="✓ test_assignment_matrix (2 × 8)"),
    "RL-04": dict(status=P, code="Provider is offered wherever Bookings runs: assignment scope; Home 'My day' (today's appointments, the next one marked); Bookings lists only their appointments, which they confirm and move along and add notes to; only the customers on them; the business's booking policy is neither shown nor changeable (PATCH /bookings-policy now needs bookings.manage_availability). Editing their own working hours and the crew app surface are not built",
                  svc="✓ role_home my_day", perm="✓ bookings.read/update, customers.read — assignment", ws="✓ Home › My day; Bookings",
                  test=_AS_TEST),
    "RL-12": dict(status=P, code="Sales executive is offered wherever Enquiries or Quotes run: assignment scope; Home 'Follow-ups due today' (their open enquiries due by tonight, and new ones); enquiries assigned to them (new ones they add are theirs, they cannot hand one to someone else); quotes they wrote or for their enquiries' customers; winning an enquiry makes the customer theirs to quote. Site visits are not built",
                  svc="✓ role_home follow_ups", perm="✓ leads.*, quotes.read/create/update, customers.read — assignment",
                  ws="✓ Home › Follow-ups", test=_AS_TEST),
    "PM-10": dict(status=P, code="a business adds its own steps inside the open statuses of orders, enquiries and projects (up to 20), renames any stage, marks one as needing a note (Settings › Stages); the module's own statuses cannot be removed and no step sits inside an ending. Moving a record to a step of another status runs the module's own service (a cancelled order releases stock, a won enquiry becomes a customer, a project's own transition rules), with the module's permission; each move is kept (platform_stage_events), audited and published (stage.changed). The order, enquiry and project pages show the steps and move along them; the order board card shows the step. Dispatch jobs and job cards join when they are built",
                  db="✓ platform_stage_sets, platform_stage_events, stage on orders/leads/projects", svc="✓ stages/engine.py; /v1/b/{id}/stages/…",
                  perm="✓ settings.update to edit; module permission per move", ws="✓ Settings › Stages; order/enquiry/project Steps; board card",
                  test=_ST_TEST),
    "FR-OR-23": dict(status=P, code="a business that sells made-to-order items or takes dated orders (bakery, home kitchen, festival boxes) opens Orders on the board by day wanted with its production list, chosen from its own data; others keep the plain list. Any business can now add its own order steps (a kirana's Picking/Packed, a meat shop's Cutting) with the stage engine (P2-01, PM-10). The prebuilt kirana, meat weight-exception, QSR/restaurant KDS and retail shipping/returns workflows are not built"),
})


# ================================================================ Phase B (packets A–K merged on
# claude/phase-b-final-integration, then integrated). Audited 2026-09-30 against code + tests on a
# fresh local stack: full API/worker suite on the RLS role, browser suites named per row.
_MB_TEST = "✓ test_p2_memberships (17) + browser p2_02_memberships 24/24"
done("P2-02", {
    "MB-01": dict(status=C, code="plans + enrolments; money through Payment Collect (collect/due, links, recorded)",
                  db="✓", svc="✓", perm="✓", ws="✓", test=_MB_TEST),
    "MB-02": dict(status=C, code="plan_kind access: valid until the last paid period ends; front-desk check-in", db="✓", svc="✓",
                  ws="✓", test=_MB_TEST),
    "MB-03": dict(status=C, code="session_pack: sessions left within validity; counted when a class is booked, used once, "
                                 "given back on cancel", db="✓", svc="✓", ws="✓", integ="✓ Bookings", test=_MB_TEST),
    "MB-04": dict(status=C, code="recurring_delivery: cutoff turns tomorrow into real orders (channel subscription) once",
                  db="✓", svc="✓", ws="✓", integ="✓ Orders, Kitchen, Fulfilment", test=_MB_TEST),
    "MB-05": dict(status=C, code="service_contract: covered visits spread over the period, each asked of Jobs once; covers a "
                                 "real customer asset of this customer", db="✓", svc="✓", integ="✓ Jobs", test=_MB_TEST),
    "MB-06": dict(status=P, code="fee_plan: instalments, paid/outstanding/next due, guardian payer, never auto-removed, "
                                 "follows a real academic enrolment of the student. Late fee is not built",
                  db="✓", svc="✓", ws="✓", integ="✓ Academics reference", test=_MB_TEST),
    "MB-07": dict(status=C, code="member_dues: good standing from paid dues", db="✓", svc="✓", ws="✓", test=_MB_TEST),
    "MB-08": dict(status=C, code="pending/active/paused/grace/expired/cancelled/completed computed from what happened "
                                 "(memberships/lifecycle.py); expiring soon derived; a freeze moves the end by exactly its days",
                  svc="✓", test=_MB_TEST),
    "MB-09": dict(status=P, code="periods (one per paid period, never overlapping), freezes, session uses, instalments, "
                                 "payment applications, delivery overrides, generated deliveries, service visits. The plan "
                                 "has grace days and freeze allowance; a joining fee is not built",
                  db="✓ 20260930120000_p2_memberships", test=_MB_TEST),
    "MB-10": dict(status=C, code="ladder T−7, T−2, T0, T+1 grace, grace end → expired, T+15 win-back only with marketing "
                                 "consent, through the automation engine and Messaging. The T0 autopay attempt waits for MB-21",
                  auto="✓", test="✓ test_renewal_ladder_sends_once_waits_for_quiet_hours_and_stops_on_payment, "
                                  "test_unrenewed_goes_to_grace_then_expires_and_winback_needs_marketing_consent"),
    "MB-11": dict(status=P, code="a payment applies its period exactly once (payment applications, replay-safe) and the "
                                 "pending ladder steps for the old end are cancelled, in one transaction. A membership "
                                 "invoice and a receipt message are not issued", svc="✓", test=_MB_TEST),
    "MB-12": dict(status=C, code="quiet hours respected; steps anchored to the business timezone (location zone, else "
                                 "primary, else Asia/Kolkata); the member page's today/tomorrow too", auto="✓", test=_MB_TEST),
    "MB-13": dict(status=P, code="mode-aware Members board: counts per state (active, ending this week, grace, payment "
                                 "pending, expired, frozen, renewed today), Needs you / running / frozen-ended lists; "
                                 "send link, record cash, freeze and renew on the member page. No per-state tab filter",
                  ws="✓ /b/…/memberships", test="✓ browser p2_02 + p1_10d1 (board)"),
    "MB-14": dict(status=S, code="no renewal calendar (renewals due per day with amounts)"),
    "MB-15": dict(status=P, code="member page: periods, freezes, instalments, visits, session uses, history, Money panel. "
                                 "Period bars / check-in dots are not drawn", ws="✓"),
    "MB-16": dict(status=C, code="front desk: card code or QR → green / amber (grace if the plan allows) / red with the "
                                 "reason; Attendance records the visit under the member's name; unpaid refused, nothing kept",
                  ws="✓ memberships/checkin", integ="✓ Attendance", test="✓ test_integration_membership_attendance + demo gate 17/17"),
    "MB-17": dict(status=P, code="the customer's 'My …' card on the business's own site: plan, state, renew, pay, skip / "
                                 "restore tomorrow before cutoff. No check-in QR on the card and no freeze request",
                  cust="✓ [slug]/account", test="✓ browser p2_02 (skip/restore)"),
    "MB-18": dict(status=P, code="cutoff generates tomorrow's orders and fulfilment jobs once; skip/pause/one-day quantity "
                                 "by owner and customer site; postpaid billed on the khata at month end once. Skip/pause "
                                 "by WhatsApp buttons is not built", svc="✓", integ="✓ Orders, Kitchen, Fulfilment, Ledger",
                  test=_MB_TEST),
    "MB-19": dict(status=P, code="preventive visits become Jobs job cards once (membership keeps job_ref). Parts covered vs "
                                 "chargeable under the contract are not modelled", integ="✓ Jobs", test=_MB_TEST),
    "MB-20": dict(status=C, code="replayed payment never extends twice; 10-day freeze = exactly 10 days; no reminder after "
                                 "renewal or in quiet hours; ladder steps once", test=_MB_TEST),
    "OM-03": dict(status=P, code="all six plan kinds exist and the board follows the business's plans; a default plan "
                                 "kind per subcategory is not proposed"),
    "GP-04": dict(status=P, code="renewal ladder live (MB-10); autopay is activation-required (MB-21)"),
    "FR-MB-01": dict(status=C, code="one engine, six kinds, per-kind words (Membership, Subscription, Fees & Enrolment, "
                                    "Service plan, Dues); periods never overlap", test=_MB_TEST),
    "FR-MB-02": dict(status=C, code="state recalculated from rows on every read and by the business-timezone sweep; the "
                                    "ladder stops on payment", test=_MB_TEST),
    "FR-MB-03": dict(status=C, code="gym: members board, check-in green/amber/red, freeze with history, session packs",
                     test=_MB_TEST),
    "FR-MB-04": dict(status=P, code="subscriptions: item, quantity, days, slot, window, address, prepaid/postpaid; cutoff "
                                    "makes tomorrow's orders; skip/restore/one-day change/pause. WhatsApp buttons not built",
                     test=_MB_TEST),
    "FR-MB-05": dict(status=P, code="fee plans (instalments, guardian payer, no auto-removal), AMC visits via Jobs, club "
                                    "dues with good standing. Late fee not built", test=_MB_TEST),
    "FR-MB-06": dict(status=A, code="early renewal queues the next period (built, tested); autopay needs Cashfree mandates"),
    "FR-MB-07": dict(status=P, code="owner homes per kind and the customer 'My …' card per kind are built; WhatsApp "
                                    "renew/skip/pause buttons are not", ws="✓", cust="✓"),
    "FR-MB-08": dict(status=P, code="browser covers gym (enrol, pay, freeze, early renew, check-in), milk (tomorrow, skip, "
                                    "customer skip/restore), coaching (fee plan). Not yet: tiffin counts, postpaid bill, AMC, "
                                    "club, autopay failure", test="✓ p2_02_memberships 24/24"),
})

# ---------------------------------------------------------------- G · Kitchen (parallel/cursor-kitchen, 839b465)
_KT_TEST = "✓ test_kitchen 6/6, test_integration_restaurant; browser p2_kitchen_kds 10/10 (integrated stack)"
done("P2-kitchen", {
    "SF-04": dict(status=C, code="kitchen display surface /kds: one pass per location, station filter", ws="✓ /kds",
                  test=_KT_TEST),
    "KT-01": dict(status=C, code="order.accepted → exactly one KOT, lines routed to stations (General fallback for menu "
                                 "items; packaged goods skipped); replay-safe via kitchen_intakes; subscription orders too",
                  db="✓", svc="✓", perm="✓ kitchen.read/advance", integ="✓ Orders, Recipes", test=_KT_TEST),
    "KT-02": dict(status=C, code="bump new → preparing → ready → served with elapsed time on each card; changes after "
                                 "start stay visible", ws="✓", test=_KT_TEST),
    "KT-03": dict(status=S, code="printer fallback not built (screen pass only)"),
    "KT-04": dict(status=C, code="the kitchen role sees preparation only: no price, no customer phone",
                  perm="✓ kitchen template has no orders.read", test=_KT_TEST),
})

# ---------------------------------------------------------------- F · Queue + Tasks (parallel/cursor-queue-tasks, 472a0ea)
done("P2-queue-tasks", {
    "QU-01": dict(status=C, code="tokens waiting / called / serving / served / missed; priority then arrival; requeue when "
                                 "the lane allows", db="✓", svc="✓", ws="✓ /b/…/queue", test="✓ test_queue; browser p2_queue_board 5/5"),
    "QU-02": dict(status=P, code="board columns Waiting / Called / Serving / Done-Missed with estimated wait; refreshed on "
                                 "each action, no self-updating TV display", ws="✓", test="✓ browser p2_queue_board 5/5"),
    "QU-03": dict(status=C, code="queue.turn_soon → one notice per visit and one WhatsApp to the customer on the token "
                                 "(queue_turn_soon template, idempotent, owner switch); a walk-in without a number is "
                                 "called at the desk", auto="✓", integ="✓ Messaging",
                  test="✓ test_your_turn_soon_goes_out_on_whatsapp_once_per_visit"),
    "QU-04": dict(status=C, code="a booking joins the provider/department lane by booking_id — no second booking",
                  integ="✓ Bookings", test="✓ test_booking_joins_the_queue_without_a_second_booking"),
    "OM-12": dict(status=P, code="POS sells products; queue tokens serve walk-ins; they are separate screens"),
    "TK-01": dict(status=C, code="one Tasks domain (tasks_tasks) for housekeeping, maintenance, prep, checklists, "
                                 "compliance; related_type/related_id; views mine/due today/overdue/unassigned",
                  db="✓", svc="✓", ws="✓ /b/…/tasks", test="✓ test_tasks; browser p2_tasks_board 4/4"),
    "TK-02": dict(status=C, code="templates spawn once per occurrence key; required steps; a step can require a photo",
                  test="✓ test_tasks"),
    "TK-03": dict(status=S, code="no stay-checkout → housekeeping task hook (stays are not built as a mode)"),
    "TK-04": dict(status=S, code="no rental handover/return checklist flow"),
})

# ---------------------------------------------------------------- H · Dispatch (parallel/cursor-dispatch, c111ce6)
_DP_TEST = "✓ test_dispatch, test_integration_dispatch_messaging; browser p2_dispatch 9/9 (integrated stack)"
done("P2-dispatch", {
    "DP-01": dict(status=P, code="dispatch_jobs: unassigned → assigned → picked_up → out_for_delivery → delivered | failed; "
                                 "a delivery cannot skip out-for-delivery; delivered needs proof note, failed a reason. "
                                 "No READY or RETURNED state", db="✓", svc="✓", test=_DP_TEST),
    "DP-02": dict(status=P, code="the tracking page carries the dispatch state; the five-step stepper follows fulfilment "
                                 "statuses", web="✓"),
    "DP-03": dict(status=P, code="dispatch_job + append-only dispatch_events built; crew_shift, location_ping, "
                                 "proof_of_delivery rows and cod_settlement are not", db="✓"),
    "DP-04": dict(status=P, code="crew /b/…/crew: next stop, pickup, drop-off, customer phone only while the job is "
                                 "active, status actions, Maps search link. No duty toggle or location sharing",
                  ws="✓ crew", test=_DP_TEST),
    "DP-09": dict(status=P, code="board Unassigned / Assigned / Out now / Delivered / Failed; assign by action. No drag, "
                                 "no auto-assign", ws="✓", test=_DP_TEST),
    "DP-12": dict(status=P, code="tracking shows the dispatch state with live_location null and location_mode "
                                 "status_only until a real fix exists — never a fabricated dot", web="✓", test=_DP_TEST),
    "DP-15": dict(status=P, code="partner reads only assigned jobs (ORM filter + RLS) is tested; ping/COD tests wait for "
                                 "those features", test=_DP_TEST),
    "SF-02": dict(status=P, code="crew route for delivery partners (dispatch); technicians use the Workspace job card; "
                                 "housekeeping/provider crew screens not built", ws="✓ /b/…/crew"),
    "GP-12": dict(status=P, code="tracking page + dispatch state + messages that follow the real delivery state once "
                                 "(952f9c2)", integ="✓ Messaging"),
})

# ---------------------------------------------------------------- J · Attendance (parallel/codex-attendance, 8ff25d7) + integration
done("P2-attendance", {
    "AT-01": dict(status=C, code="front desk by card code or QR/enrolment id: Memberships decides, Attendance records "
                                 "once under the member's name; denied visits keep nothing", db="✓", svc="✓", ws="✓",
                  integ="✓ Memberships (1fc8684, 145c75f)", test="✓ test_integration_membership_attendance; demo gate 17/17"),
    "AT-02": dict(status=C, code="teacher roster per session, default present, one save, explicit exceptions, owner "
                                 "correction with reason; on the real P5 schema", integ="✓ Academics",
                  test="✓ test_attendance_postgres 5/5"),
    "AT-03": dict(status=P, code="staff self check-in / check-out at an assigned location. Not geo-verified "
                                 "(geo_verified can never be true without a real verifier); no shifts", test="✓ test_attendance_postgres"),
    "AT-05": dict(status=S, code="no authorised pick-up list"),
    "GP-11": dict(status=P, code="attendance events, assignment scope and task photo proof exist; no single 'who "
                                 "worked' view"),
})

# ---------------------------------------------------------------- E · Quotes (parallel/cursor-quotes, d7ed1a2) + integration
_QT_TEST = "✓ test_quotes, test_quotes_finish, test_integration_quote_conversion; browser p2_quotes 15/15"
done("P2-quotes", {
    "QT-02": dict(status=P, code="website quote request opens one draft (lead kept); POST …/quotes/intake is idempotent "
                                 "per channel key. WhatsApp inbound is not wired to the intake", test=_QT_TEST),
    "QT-03": dict(status=C, code="discount above the business limit stays pending until quotes.approve (owner); a sales "
                                 "executive sends within the limit", perm="✓", test=_QT_TEST),
    "QT-04": dict(status=C, code="each open of an issued version is recorded (quotes_views, open_count, quote.viewed) "
                                 "and shown to the owner", ws="✓", test=_QT_TEST),
    "QT-05": dict(status=C, code="accept with name + 6-digit code delivered on WhatsApp (quote_acceptance_code); no code "
                                 "is promised when WhatsApp cannot reach the customer; accepting locks every money "
                                 "column by trigger", integ="✓ Messaging", test=_QT_TEST),
    "QT-06": dict(status=P, code="order (one order at accepted prices; token = advance) and project (one per quote) "
                                 "consumers exist; target invoice has no consumer", integ="✓ Orders, Projects",
                  test=_QT_TEST),
    "QT-07": dict(status=P, code="payment plan resolved against the locked total; the token is collected on the "
                                 "converted order through Payment Collect. Plan stages are not scheduled as reminders; "
                                 "project/invoice targets have no collectable transaction yet", integ="✓ Payments (order)"),
    "QT-08": dict(status=C, code="lines carry quantity breaks, MOQ, lead time, BOQ section and a size matrix; under-MOQ "
                                 "refused", test=_QT_TEST),
    "GP-13": dict(status=P, code="validity + view tracking live; follow-up nudges (QT-09) not built"),
})

# ---------------------------------------------------------------- I · Growth (parallel/cursor-growth-hardening, 7550111) + 06ef456
_GR_TEST = "✓ test_growth_db, test_loyalty_lane, test_marketing_lane; browser p3 growth 14/14 (integrated stack)"
done("P3-growth", {
    "LY-01": dict(status=P, code="points per ₹ with a points ledger, redeem with discount calculation; a completed sale "
                                 "earns once (06ef456). Expiry sweep and the website loyalty card are not built",
                  db="✓", svc="✓", ws="✓", integ="✓ Orders", test=_GR_TEST),
    "LY-02": dict(status=C, code="stamp cards and rewards; idempotent stamp awards", db="✓", svc="✓", ws="✓", test=_GR_TEST),
    "LY-03": dict(status=C, code="referral codes; the friend's first eligible purchase qualifies once (06ef456)",
                  integ="✓ Orders", test=_GR_TEST),
    "LY-04": dict(status=P, code="gift vouchers with validation; Payments does not fund a voucher yet", svc="✓", test=_GR_TEST),
    "MK-01": dict(status=C, code="rule-built segments shown as counts; only marketing-consented contacts for WhatsApp; "
                                 "no export", perm="✓", test=_GR_TEST),
    "MK-02": dict(status=P, code="offers (codes, first-order, win-back, limits, expiry, per-customer caps) evaluated by "
                                 "OfferService; website checkout does not apply them yet", svc="✓", test=_GR_TEST),
    "MK-03": dict(status=P, code="broadcast to opted-in customers with cost before approval; delivery goes to the fixture "
                                 "transport, not through Messaging — live send is activation-required", test=_GR_TEST),
    "MK-07": dict(status=P, code="attribution labelled 'Approximate · last touch' from real conversions; UTM/CTWA intake "
                                 "partial", test=_GR_TEST),
    "MK-08": dict(status=P, code="campaign goal → audience → offer → approve → results in the Workspace; Meta channels "
                                 "activation-required", ws="✓", test=_GR_TEST),
    "MK-09": dict(status=C, code="no marketing template without consent; over-cap spend blocked before any provider call; "
                                 "results never estimated", test=_GR_TEST),
    "MK-10": dict(status=C, code="lawyers: marketing off; finance restricted; minors: prohibited — by taxonomy key / trait",
                  test=_GR_TEST),
    "CO-08": dict(status=C, code="lawyer subcategory: marketing off by default, no owner bypass", test=_GR_TEST),
    "MS-26": dict(status=P, code="consented audience, approved templates, owner approves; live WhatsApp send is "
                                 "activation-required and replies/frequency are local defaults"),
})

# ---------------------------------------------------------------- B · Supply / B2B / recipes (parallel/cursor-supply-b2b, 229a396)
_SP_TEST = "✓ test_supply_lane 11/11; browser supply_buying 6/6 (integrated stack)"
done("P4-supply", {
    "PC-01": dict(status=C, code="suppliers and supplier items (code, unit, pack, MOQ, lead time)", db="✓", svc="✓",
                  ws="✓ Buying", test=_SP_TEST),
    "PC-02": dict(status=C, code="price agreements; a historical PO keeps its pinned price", test=_SP_TEST),
    "PC-03": dict(status=P, code="requisitions from demand with the arithmetic on the row; from BOM / reorder point not "
                                 "automatic (low stock alerts only)", test=_SP_TEST),
    "PC-04": dict(status=P, code="PO approve → send → counter → receive → bill; a bill is not marked paid by Buying "
                                 "(ledger posting pending)", test=_SP_TEST),
    "PC-05": dict(status=C, code="goods receipt raises stock by the good quantity only (damaged kept out), partial and "
                                 "idempotent", integ="✓ Inventory", test=_SP_TEST),
    "PC-06": dict(status=P, code="supplier bills stay open with a ledger posting intent; payables not posted to the "
                                 "shared ledger", test=_SP_TEST),
    "PC-08": dict(status=C, code="a counter-offer is its own row until the buyer accepts", test=_SP_TEST),
    "RC-01": dict(status=P, code="BOM components with quantity and yield ratio (Recipes page); wastage and unit "
                                 "conversion not modelled", ws="✓ /b/…/recipes", test="✓ demo gate (recipe from the Workspace)"),
    "RC-03": dict(status=P, code="ingredients leave stock once when the kitchen completes preparation (9ea0d73: 1000 g → "
                                 "700 g); a counter sale without the kitchen does not consume", integ="✓ Kitchen, Inventory",
                  test="✓ test_integration_restaurant; demo gate 17/17"),
    "RC-04": dict(status=P, code="net = demand + safety − usable − inbound, rounded to pack and minimum (explained on the "
                                 "row); the biryani fixture is not reproduced", test=_SP_TEST),
    "RC-05": dict(status=P, code="incoming B2B demand as a sealed copy; bookings/subscriptions/forecast as demand "
                                 "sources not wired"),
    "FR-IN-05": dict(status=P, code="through Kitchen → Recipe/BOM (restaurant); direct sale path not wired"),
    "FR-OR-30": dict(status=C, code="restaurant: recipe saved in the Workspace → order → one KOT → cooked → 1000 g → "
                                    "700 g once, 0.7 kg on the stock page", test="✓ demo gate 17/17 (live worker)"),
    "EX-01": dict(status=C, code="expenses with totals", db="✓", svc="✓", ws="✓ /b/…/expenses", test=_SP_TEST),
    "DN-01": dict(status=P, code="causes (open, list) and gifts on the Donations page; campaigns/updates not built",
                  ws="✓ /b/…/donations", test=_SP_TEST),
    "DN-02": dict(status=P, code="one-off gift linked to a payment id (money stays in Payments); recurring gifts not built"),
    "PM-15": dict(status=P, code="connector pairing, mapping, fixture sync; bidirectional sync refused without a conflict "
                                 "policy. Module not marked built; no production connector", test=_SP_TEST),
    "CN-01": dict(status=P, code="connector families/direction with a refusal for two-way sync without a conflict policy"),
    "CN-04": dict(status=P, code="external id mapping for fixture sync"),
    "GP-06": dict(status=P, code="recipes, yields, wastage, counts: recipes + kitchen consumption live; wastage in BOM "
                                 "not modelled"),
})

# ---------------------------------------------------------------- C · Inventory field (parallel/cursor-inventory-field, 2c4bfc9) + 8fc4e76
_IF_TEST = "✓ test_inventory_field, test_p5_operations (job parts)"
done("P4-inventory-field", {
    "IN-07": dict(status=C, code="transfers requested → approved where required → in transit → received; transit stock "
                                 "free at neither end; replay-safe", db="✓", svc="✓", ws="✓ transfers board", test=_IF_TEST),
    "FR-IN-03": dict(status=C, code="as IN-07", test=_IF_TEST),
    "IN-11": dict(status=C, code="a van is a location (stock_role van); van board; loaded by transfer", ws="✓", test=_IF_TEST),
    "FR-IN-04": dict(status=C, code="central → van by transfer; a technician uses parts from the job's location and their "
                                    "own vans through Jobs (one Inventory contract); unused parts go back, never more than "
                                    "the job has out", integ="✓ Jobs",
                     test="✓ test_job_parts_come_from_the_job_and_the_technicians_van_and_go_back_once; browser P5 13/13"),
    "IN-14": dict(status=P, code="client-owned stock on its own records (never in the business balance), moves logged; "
                                 "no Workspace client-stock view", svc="✓", test=_IF_TEST),
    "FR-IN-13": dict(status=P, code="technician sees only the job's location and their vans (no stock book); store keeper "
                                    "receive/count/transfer; kitchen and pharmacy views not specialised"),
})

# ---------------------------------------------------------------- D · Projects / Jobs / Academics (parallel/codex-projects-jobs-academics, c40f853)
_P5_TEST = "✓ test_p5_operations, test_p5_domain_guards; browser p5_projects_jobs_academics 13/13"
done("P5-projects-jobs-academics", {
    "JB-01": dict(status=P, code="job card new → assigned → inspecting → awaiting approval → approved → in progress → "
                                 "waiting parts → quality check → completed; parts from stock/van; completion needs work "
                                 "performed. Invoicing from the job is not built (invoice_id only)", db="✓", svc="✓",
                  perm="✓ technician assignment scope", ws="✓", integ="✓ Inventory, Memberships (AMC)", test=_P5_TEST),
    "JB-02": dict(status=P, code="asset described on the job (text + serial); not linked to the customer-asset record",
                  test=_P5_TEST),
    "JB-03": dict(status=P, code="approval recorded by staff with how the customer approved; no customer approval link"),
    "JB-04": dict(status=P, code="parts from the job's location and the technician's vans, returns bounded; inspection "
                                 "photos not built", test=_P5_TEST),
    "PJ-02": dict(status=P, code="phases can be payment milestones; a payment schedule with reminders is not built"),
    "OM-08": dict(status=P, code="projects with phases and milestones; payment schedules not built"),
    "AC-01": dict(status=C, code="course → batch (teacher, schedule, capacity, room/link) → session → enrolment "
                                 "(student, guardian); a fee plan follows the enrolment (Memberships)",
                  db="✓", svc="✓", ws="✓", integ="✓ Memberships, Attendance", test=_P5_TEST),
    "AC-02": dict(status=P, code="enquiry, bookings, forms, fee plan and batch exist as separate steps; no connected "
                                 "admissions flow"),
    "AC-03": dict(status=P, code="daily session attendance (AT-02); the guardian absence note is not sent"),
    "AC-04": dict(status=P, code="fee plan instalments with reminders (Memberships ladder); concessions/sibling discounts "
                                 "with approval not built"),
    "AC-05": dict(status=P, code="assessments and marks shown to the guardian; report card PDF not built", test=_P5_TEST),
    "AC-07": dict(status=P, code="announcements on the guardian portal; not sent on WhatsApp"),
    "AC-08": dict(status=P, code="session scheduling checks teacher and room clashes; no timetable grid"),
    "AC-09": dict(status=P, code="meeting link on the batch (https only); not per session"),
    "AC-11": dict(status=P, code="My Academics: each child's classes, marks and announcements, guardian-scoped, 390 px; "
                                 "attendance %, fees + Pay and homework not on it", cust="✓", test=_P5_TEST),
    "AC-12": dict(status=P, code="guardian is contact of record under 18; teachers cannot open the customer book; no "
                                 "marketing to minors (Growth); photo consent and DPDP child consent not built"),
    "AC-14": dict(status=P, code="guardian sees only own children and another teacher's batch is not found (tested); "
                                 "absence-note-once not built", test=_P5_TEST),
    "SF-06": dict(status=P, code="phone-web My Academics for guardian/adult student (as AC-11)", cust="✓"),
})

# ---------------------------------------------------------------- K · Documents / forms / signatures (parallel/codex-documents-forms, 74d7b26)
_DC_TEST = "✓ test_document_workflows_postgres (3/3); browser p2_documents_forms 6/6 (integrated stack)"
done("P5-documents", {
    "DC-01": dict(status=C, code="document templates (agreement, consent, intake, certificate, report, generic)",
                  db="✓", svc="✓", ws="✓ /b/…/documents", test=_DC_TEST),
    "DC-02": dict(status=C, code="versioned intake/consent forms pinned per request; consent text and guardian required "
                                 "where set", cust="✓ document-request page", test=_DC_TEST),
    "DC-03": dict(status=C, code="private document files (never public), short-lived access links, immutability triggers, "
                                 "RLS", perm="✓", test=_DC_TEST),
    "DC-04": dict(status=C, code="typed and drawn signatures", test=_DC_TEST),
    "DC-05": dict(status=P, code="one-time upload/form link created and shown to share ('Share this private link once'); "
                                 "not sent on WhatsApp"),
})

# ---------------------------------------------------------------- Wrap: bookings depth, workforce schedules, WhatsApp + calling (claude/phase-b-final-integration, 2026-09-30)
_BKR_TEST = ("✓ test_booking_final_slot (5: four concurrent requests for the last place, each on its own "
             "connection through the API - class seat, instructor vs none, pooled seat, unnamed table, provider; "
             "mutation-checked) + test_bookings_kernel + test_booking_resources")
_BKS_TEST = "✓ test_booking_schedules (3: provider hours/leave/breaks on every path; guest opening hours)"
_BKD_TEST = ("✓ test_booking_depth (5: hold release / paid kept / replay; waitlist offer once, claim, spent link, "
             "expiry; weekly series create / edit one / change later all-or-nothing / end; no-show follow-up once); "
             "browser: cancel → WhatsApp offer (sandbox) → customer takes it on the site → Workspace series + Arrived")
_WA_TEST = ("✓ test_whatsapp_connection_calling (6: every connection state; Embedded Signup → registration with "
            "PIN against a mock of Graph; template/quality WABA webhooks; OTP preset; sandbox calls; permission gate)")
done("WRAP-bookings-whatsapp", {
    "FR-BK-02": dict(status=P, code="availability from the location's opening hours (guests; the desk may override), "
                                    "the provider's own schedule (weekly hours, dated leave or one-off hours, breaks), "
                                    "resource buffers, capacity (a class's places per session bind), existing "
                                    "bookings; re-checked at commit under one lock per location+mode, with the "
                                    "check and the claim committing together. Booking horizon / minimum notice rules "
                                    "not built", svc="✓", test=f"{_BKR_TEST}; {_BKS_TEST}"),
    "BK-05": dict(status=P, code="class capacity is the class's own 'places per session', enforced for guests and "
                                 "staff alike; full → waitlist; no timetable grid", test=_BKR_TEST),
    "BK-09": dict(status=C, code="waitlist (owner switch): join only when full; a freed place (cancel, decline, move, "
                                 "no-show before start) is offered to the first person waiting, one offer at a time, "
                                 "on WhatsApp with a link to the business's site; taken only by the customer through "
                                 "the booking path; runs out and passes on", db="✓", svc="✓", perm="✓ tenant/location/"
                                 "assignment RLS", ws="✓ Bookings › Waitlist (offer links)", cust="✓ /{slug}/waitlist",
                  integ="✓ Messaging, Automation", auto="✓", test=_BKD_TEST),
    "BK-10": dict(status=C, code="repeat a booking every 1–4 weeks for 2–52; each occurrence checked on its own "
                                 "(collisions reported, never double-booked); edit/cancel one; move this-and-later "
                                 "all-or-nothing; end the series; past/finished never rewritten. Workspace: Repeat, "
                                 "Move this and later (by days/minutes), End", db="✓", svc="✓", ws="✓",
                  test=_BKD_TEST + "; browser: Repeat → 4, Move +60 min moved all four"),
    "BK-12": dict(status=P, code="final-slot lock at commit on every path (exclusion constraints + advisory locks); "
                                 "a slot waiting on an online deposit is held for the owner's hold time and released "
                                 "unpaid. The website offers only pay-at-business today (online deposits need the "
                                 "payment provider), and there is no explicit hold tool yet for an AI receptionist",
                  svc="✓", test=f"{_BKR_TEST}; {_BKD_TEST}"),
    "BK-13": dict(status=P, code="a booking can hold a room/chair and a provider together (both allocated, provider "
                                 "on duty checked); no customer-facing picker for the pair", test=_BKS_TEST),
    "BK-14": dict(status=P, code="a class mapped to plans needs an active membership or a session-pack session "
                                 "(Memberships answers, P2-02); an owner override is not built"),
    "FR-BK-04": dict(status=P, code="recurring series, waitlist with customer acceptance, unpaid holds released - see "
                                    "BK-09/10/12", test=_BKD_TEST),
    "FR-BK-05": dict(status=C, code="deposit via Payments; reschedule releases the old slot, keeps history, re-checks "
                                    "provider duty and (for guests) opening hours; cancellation frees the slot and wakes "
                                    "the waitlist; Workspace moves only as the state allows (Confirm → Arrived / "
                                    "No-show → Done); no-show gets one 'we missed you'", ws="✓", auto="✓",
                     test=_BKD_TEST),
    "FR-BK-07": dict(status=P, code="two simultaneous customers → exactly one: proven through the API with real "
                                    "concurrent requests (not yet a browser script); other scenarios partly covered"),
    "WF-02": dict(status=P, code="per-person weekly hours, dated leave / one-off hours and breaks, managed on the "
                                 "member page (day names) and enforced by Bookings on every path; shift rota planning "
                                 "for crew/teachers not built", ws="✓", integ="✓ Bookings", test=_BKS_TEST),
    "WF-03": dict(status=P, code="service associations are the bookable skills (checked at booking); assignment rules "
                                 "absent"),
    "MS-07": dict(status=A, code="built, not exercised against Meta (docs checked 2026-09-30): Embedded Signup → code "
                                 "exchange → WABA webhook subscription → number registration with the two-step PIN "
                                 "(never stored); honest states ACTIVATION_REQUIRED / META_REVIEW_REQUIRED / "
                                 "NOT_CONNECTED / SETUP_REQUIRED / PHONE_VERIFICATION_REQUIRED / "
                                 "TEMPLATE_SETUP_REQUIRED / ACTIVE / DEGRADED / DISCONNECTED with a checklist; sandbox "
                                 "labelled TEST / SANDBOX; one-time codes in Meta's authentication preset. Needs "
                                 "LOCAH's Meta app, Tech Provider enrolment and App Review "
                                 "(docs/current-build/WHATSAPP-CALLING-SETUP.md)", ws="✓", test=_WA_TEST),
    "CN-06": dict(status=A, code="as MS-07", test=_WA_TEST),
    "MS-08": dict(status=C, code="webhooks also handle WABA-level template decisions (approved / rejected with reason "
                                 "/ paused) and quality/limit updates, routed by WABA id; another account's events "
                                 "touch nothing", test=_WA_TEST),
    "CN-07": dict(status=A, code="WhatsApp Calling built to Meta's documented signalling: settings with call hours from "
                                 "the location, call actions, `calls` webhook → one call record (no SDP/media/tokens), "
                                 "call permissions (reply, 7-day temporary on calling in), business-initiated calls "
                                 "only with permission, requests inside the window at most 1/day 2/week. Answering "
                                 "needs a WebRTC call runtime LOCAH does not have: CALLING_ACTIVATION_REQUIRED",
                  test=_WA_TEST),
    "RC-20": dict(status=A, code="as CN-07 - calls are recorded and the team alerted; nobody pretends one was "
                                 "answered", test=_WA_TEST),
    "CN-08": dict(status=A, code="provider-neutral VoiceProvider boundary (place, answer/route, transfer, hang up, "
                                 "webhook → CallEvent) writing the same call record; no vendor chosen (founder "
                                 "decision); fixture provider for tests only"),
    "IN-10": dict(status=P, code="reorder point per item and location → low-stock alert once a day → optionally (owner "
                                 "switch on the Low-stock automation) a DRAFT requisition sized by the buying planner, "
                                 "one open per item, never a purchase order; min/max not built", auto="✓",
                  test="✓ test_low_stock_drafts_a_requisition_only_when_the_owner_asks"),
})
