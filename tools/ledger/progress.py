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
