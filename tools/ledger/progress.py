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
