"""Compliance, roadmap gates, testing, end-to-end flows, open decisions and
verify-at-build (MD §25–§28; PDF §19–§20; Founder §61–§64)."""

from __future__ import annotations

from tools.ledger.model import Decision, Section, Verify, r

S, P, C, A, F = "NOT_STARTED", "PARTIAL", "COMPLETE", "ACTIVATION_REQUIRED", "FUTURE"

compliance = Section(
    "BD. Compliance by design and what LOCAH will not build (MD §25)",
    "",
    [
        r("CO-01", "P1", "MD §25.1", "DPDP: consent store, per-customer export/delete, retention defaults, guardian-first flows", "platform", "NEW", S, "see PM-08/CR-08"),
        r("CO-02", "P1", "MD §25.1", "WhatsApp Business policy: business-task bots only; opt-in; template categories; quality rating", "messaging", "NEW", S, "see MS-*"),
        r("CO-03", "P1", "MD §25.1", "GST: invoice content, numbering, e-invoice above threshold (P4), e-way bills", "invoicing", "NEW", S, "see IV-*"),
        r("CO-04", "X", "MD §25.1 · PDF §12", "Payments: the provider is the payment aggregator; LOCAH never holds, escrows or wallets customer funds", "payments", "EXISTING", C, "no wallet/escrow tables; money moves only through provider"),
        r("CO-05", "P1", "MD §25.1", "SMS only as fallback with DLT-registered templates", "messaging", "NEW", A, "DLT registration"),
        r("CO-06", "P1", "MD §25.1", "Marketplace obligations: seller details, policies, grievance contact on LOCAH pages", "marketplace", "EXTEND", P, "policy pages exist; seller-details/grievance block to verify"),
        r("CO-07", "P2", "MD §25.1", "Health: front-desk only; encrypted reports with expiring links; AI guardrails", "platform", "NEW", S, "absent"),
        r("CO-08", "P3", "MD §25.1", "Legal profession: marketing module off by default for lawyers", "marketing", "NEW", S, "absent"),
        r("CO-09", "P3", "MD §25.1", "Finance/insurance: no product selling or advice through LOCAH or its AI", "ai-employees", "NEW", S, "absent"),
        r("CO-10", "P2", "MD §25.1", "Real estate: RERA field displayed when entered", "projects", "NEW", S, "absent"),
        r("CO-11", "P1", "MD §25.1", "Food: FSSAI field shown on food businesses' sites (verify requirement)", "compliance", "NEW", S, "absent"),
        r("CO-12", "P5", "MD §25.1", "Donations from abroad blocked unless FCRA declared", "donations", "NEW", S, "absent"),
        r("CO-13", "P2", "MD §25.1", "Staff location: on-duty only, consent at onboarding, 7-day raw retention", "dispatch", "NEW", S, "absent"),
        r("CO-14", "P3", "MD §25.1", "Call recording announcement before any recorded AI call", "ai-employees", "NEW", S, "absent"),
        r("CO-15", "X", "MD §25.1", "Accessibility: 44 px targets, focus rings, 390 px mobile, reduced motion", "platform", "EXISTING", P, "Phase A surfaces comply; new surfaces must"),
        r("CO-16", "X", "MD §25.2", "Will not build: clinical records, diagnosis, e-prescriptions, HIS", "—", "EXISTING", C, "none built"),
        r("CO-17", "X", "MD §25.2", "Will not build: lending, BNPL, insurance underwriting, investment products, wallets, escrow, holding customer money", "—", "EXISTING", C, "none built"),
        r("CO-18", "X", "MD §25.2", "Will not build: tenant-hosted multi-vendor marketplace or food-aggregator clone", "—", "EXISTING", C, "none built"),
        r("CO-19", "X", "MD §25.2", "Will not build: scraping or unofficial-API integrations", "—", "EXISTING", C, "none built"),
        r("CO-20", "X", "MD §25.2", "Will not build: full ERP/MRP/shop-floor scheduling, full school ERP, statutory payroll filing", "—", "EXISTING", C, "none built"),
        r("CO-21", "X", "MD §25.2", "Will not build: general-purpose AI chatbot on WhatsApp", "—", "EXISTING", C, "none built"),
        r("CO-22", "X", "MD §25.2", "Will not build: fake reviews, invented metrics, 'Coming soon' decoration", "—", "EXISTING", C, "none built"),
        r("CO-23", "X", "MD §25.2", "Will not build: staff tracking outside shifts", "—", "EXISTING", C, "none built"),
        r("CO-24", "P3", "MD §25.3", "External pen-test before P3 GA; short sessions, device binding for crew devices", "platform", "NEW", A, "external engagement"),
    ],
)

roadmap = Section(
    "BE. Roadmap gates and build packets (MD §26)",
    "",
    [
        r("GT-01", "P1", "MD §26.1", "Gate: backup/restore drill against a disposable staging database", "platform", "EXISTING", A, "needs a staging project; not doable in this container"),
        r("GT-02", "P1", "MD §26.1", "Gate: pnpm typecheck and frontend build green with dependencies installed", "platform", "EXISTING", C, "typecheck green 2026-09-27 in this session", test="✓"),
        r("GT-03", "P1", "MD §26.1", "Gate: 302/303 reproduced against the real Supabase project", "platform", "EXISTING", A, "needs hosted project access; not repeated (founder: do not redo DB audit)"),
        r("GT-04", "P1", "MD §26.1", "Gate: Build Spec P0 frontend spine shipped", "platform", "EXISTING", C, "Phase A accepted by founder"),
        r("PKT-01", "P1", "MD §26.3", "P1-01 Taxonomy and traits — done when every subcategory fixture returns its expected module set", "catalog", "NEW", S, "see TX-*"),
        r("PKT-02", "P1", "MD §26.3", "P1-02 Platform primitives — each primitive has isolation + idempotency tests", "platform", "NEW", S, "see PM-*"),
        r("PKT-03", "P1", "MD §26.3", "P1-03 Offering kinds — existing catalogue tests pass; new kinds render on tenant site", "offerings-catalog", "NEW", S, "see OK-*"),
        r("PKT-04", "P1", "MD §26.3", "P1-04 GST invoicing — §14.6 tests pass", "invoicing", "NEW", S, "see IV-*"),
        r("PKT-05", "P1", "MD §26.3", "P1-05 POS — two-register offline sync test passes", "pos", "NEW", S, "see PS-*"),
        r("PKT-06", "P1", "MD §26.3", "P1-06 Khata — balance equals sum of entries under concurrent writes", "ledger", "NEW", S, "see LG-*"),
        r("PKT-07", "P1", "MD §26.3", "P1-07 WhatsApp foundation — owner connects a number and receives order notifications", "messaging", "NEW", S, "internal parts buildable; number connection ACTIVATION"),
        r("PKT-08", "P1", "MD §26.3", "P1-08 WhatsApp journeys — §12.6 tests pass with zero model calls", "messaging", "NEW", S, "see MS-*"),
        r("PKT-09", "P1", "MD §26.3", "P1-09 Reviews + compliance — §17.5 tests pass", "reviews", "NEW", S, "see RV-*/CP-*"),
        r("PKT-10", "P1", "MD §26.3", "P1-10 Pilot hardening — English/Tamil/Hindi strings, basic insights from real data", "platform", "NEW", S, "see IS-01, GP-22"),
        r("PH-01", "P1", "MD §26.2", "P1 exit: pilots bill all counter sales in LOCAH for 2 weeks; WhatsApp orders end to end; zero numbering gaps", "platform", "NEW", A, "real pilots required"),
        r("PH-02", "P2", "MD §26.2", "P2 exit: a full renewal cycle collects without manual chasing; deliveries tracked live end to end", "platform", "NEW", A, "real pilots required"),
        r("PH-03", "P3", "MD §26.2", "P3 exit: Receptionist books real appointments, zero medical-advice incidents in red-team fixtures; AI spend within caps", "platform", "NEW", A, "real pilots required"),
        r("PH-04", "P4", "MD §26.2", "P4 exit: one requisition restaurant → wholesaler → delivered → GRN → Tally without manual re-entry", "platform", "NEW", A, "real pilots required"),
        r("PH-05", "P5", "MD §26.2", "P5 exit: each pilot runs its core loop only in LOCAH for a month; 16 new website templates", "platform", "NEW", A, "real pilots required"),
        r("PH-06", "P6", "MD §26.2", "P6 ecosystem: payroll via partner, channel manager, access control, card terminals, ONDC, Brand HQ, forecasting ML, supplier discovery, ticketing, native customer apps", "platform", "FUTURE", F, "FUTURE by source"),
        r("PH-07", "P5", "MD §4.2 · §26.2", "Website target templates (fresh_store, boutique, clinic, practice, portfolio_projects, service_business, automotive, logistics, events, portfolio, personal_brand, b2b_catalogue, farm, pets, rentals, organisation)", "website", "NEW", P,
          "Phase A replaced fixed templates with design families chosen from dimensions (founder-accepted); module sections still needed per target"),
    ],
)

testing = Section(
    "BF. Testing strategy with near-zero AI spend (MD §27; PDF §20)",
    "",
    [
        r("TS-01", "X", "MD §27", "Deterministic fixtures: subcategory → module set; trait rules; GST split; BOM net; ladder schedules; number series; stock/yield maths", "testing", "EXTEND", P, "interview/discovery fixtures exist"),
        r("TS-02", "X", "MD §27", "Service integration on fresh Postgres in RLS-enforcing and bypass modes, isolation and actor-matrix rows", "testing", "EXISTING", P, "832 tests pass on platform_api role; new modules to add"),
        r("TS-03", "X", "MD §27", "Provider contracts: recorded WhatsApp, payment, ChitBridge, Meta payloads; Tally pairs; Maps stubs", "testing", "EXTEND", P, "payment webhook stubs exist"),
        r("TS-04", "X", "MD §27", "AI record-replay keyed by prompt hash; CI fails if a test reaches an AI provider without a recording", "testing", "EXISTING", C, "LOCAH_TEST_NO_EXTERNAL_AI + replay provider", test="✓ test_ai_guard"),
        r("TS-05", "X", "MD §27", "AI evaluation set (EN/TA/HI/code-mixed) — only when a prompt/model changes", "testing", "EXTEND", P, "interview eval exists"),
        r("TS-06", "P3", "MD §27", "Red-team fixtures (medical questions, '90% off', off-topic, injected tool args)", "testing", "NEW", S, "absent"),
        r("TS-07", "X", "MD §27", "Live smoke ≈5 calls once per release", "testing", "NEW", A, "not in routine development by founder rule"),
        r("TS-08", "X", "MD §27", "Devices: POS offline on entry-level Android tablet, crew GPS on Android/iPhone, printers", "testing", "NEW", A, "physical devices"),
        r("TS-09", "X", "Founder §62", "Browser workflows incl. mobile and offline", "testing", "EXTEND", P, "Phase A CDP harness flows A–L"),
    ],
)

e2e = Section(
    "BG. End-to-end business flows (PDF §19; Founder §64)",
    "Each must run through real shared services and the real UI.",
    [
        r("E2E-01", "P2", "Founder §64 · PDF §19", "Meat shop: setup → weighted offerings → website → cart/order → Workspace order → inventory → fulfilment → dispatch/tracking → customer activity", "e2e", "NEW", S, "weighted offerings/dispatch absent"),
        r("E2E-02", "P2", "Founder §64", "Restaurant: menu → website/table/order → POS → kitchen → payment/invoice → inventory/recipes where enabled", "e2e", "NEW", S, "absent"),
        r("E2E-03", "P2", "Founder §64 · PDF §19", "Gym: plans → website → join → membership → booking/class → attendance → renewal lifecycle → customer membership view", "e2e", "NEW", S, "absent"),
        r("E2E-04", "P2", "Founder §64 · PDF §19", "Clinic front desk: services/providers → website booking → appointment → queue → front desk → payment state → customer appointment view", "e2e", "NEW", S, "absent"),
        r("E2E-05", "P5", "Founder §64 · PDF §19", "Hotel: room type → availability → reservation → deposit → front desk/stay op → housekeeping", "e2e", "NEW", S, "absent"),
        r("E2E-06", "P5", "Founder §64 · PDF §19", "Education: course → enquiry/demo → enrolment → fee plan → batch/session → attendance → guardian/student view", "e2e", "NEW", S, "absent"),
        r("E2E-07", "P2", "Founder §64 · PDF §19", "Real estate: project → website listing → lead → site visit → quote → sales Workspace", "e2e", "NEW", S, "absent"),
        r("E2E-08", "P5", "Founder §64", "Field service: request → estimate → job → assigned technician → parts → completion → invoice", "e2e", "NEW", S, "absent"),
        r("E2E-09", "P4", "Founder §64 · PDF §19", "Industrial/B2B: technical catalogue → RFQ → quote → acceptance → order → dispatch → invoice/ledger", "e2e", "NEW", S, "absent"),
        r("E2E-10", "P4", "PDF §19", "Small retail shop already using billing software: catalogue/stock brought online through a controlled connector without duplicate entry", "e2e", "NEW", S, "absent"),
        r("E2E-11", "P5", "Founder §52", "Community/nonprofit: cause → website donate → donation → receipt → donor timeline", "e2e", "NEW", S, "absent"),
        r("E2E-12", "P5", "Founder §51", "Whole product loop: create → talk → website → marketplace → recommend → enable/configure → workspace adapts → site gains functionality → customer uses → records → role surfaces → My Activity → automations → insights → AI tools → connectors", "e2e", "NEW", S, "first half shipped in Phase A"),
    ],
)

DECISIONS = [
    Decision("OD-01", "P1", "Map the 11 Doc 11 module keys not confirmed here against the NEW keys in §6.2", "OPEN_DECISION",
             "Reconciled in packet P1-01 (module registry) — update when done"),
    Decision("OD-02", "P1", "Meta Tech Provider directly, or through a Business Solution Provider", "OPEN_DECISION", "Blocks WhatsApp activation (MS-07, CN-06); internal inbox/journeys built provider-neutral"),
    Decision("OD-03", "P1", "Pilot businesses, by name, for each phase", "OPEN_DECISION", "Blocks phase exits PH-01..05"),
    Decision("OD-04", "P1", "Pricing and packaging of packs and AI add-ons", "OPEN_DECISION", "No prices invented; packs shown without prices"),
    Decision("OD-05", "P2", "Map renderer: Google Maps JS or open-source renderer + commercial tiles", "OPEN_DECISION", "Blocks DP-10 map view; list board + Maps URLs built"),
    Decision("OD-06", "P2", "Crew app wrapper: Flutter or Capacitor", "OPEN_DECISION", "Blocks DP-08; PWA (P2a) built"),
    Decision("OD-07", "P2", "Shipping aggregator and hyperlocal delivery partner", "OPEN_DECISION", "Blocks FU-02, CN-11"),
    Decision("OD-08", "P3", "Telephony provider for Indian inbound numbers with audio streaming", "OPEN_DECISION", "Blocks RC-19"),
    Decision("OD-09", "P3", "Speech-to-text and text-to-speech providers for Tamil and Hindi", "OPEN_DECISION", "Blocks RC-19/20"),
    Decision("OD-10", "P4", "GST Suvidha Provider for e-invoice and e-way bill", "OPEN_DECISION", "Blocks IV-12, CN-14"),
    Decision("OD-11", "P4", "Owner of the LOCAH ↔ ChitBridge API contract", "OPEN_DECISION", "Blocks TN-02..04"),
    Decision("OD-12", "P1", "Founder: existing Razorpay code — remove, or keep frozen once Cashfree ships", "OPEN_DECISION", "Kept, frozen, not extended (founder 2026-09-27)"),
    Decision("SC-01", "P3", "SOURCE_CONFLICT: MD §11.2 gives the AI Receptionist a closed tool list ('Nothing else', no order creation) and §11.3 sends restaurant phone orders to a WhatsApp link; FR-Orders authorises AI phone ordering for simple orders where the business enables it", "RESOLVED",
             "Founder refinement (authority 1) wins: when enabled, the receptionist gets read-catalogue / build-cart / create-order tools on the same Orders service (actor_type=ai_employee, payment link only, never card details by voice); long, custom, negotiated, high-risk or low-confidence orders keep the MD's WhatsApp-link / human path (FR-OR-14)"),
]

VERIFY = [
    Verify("VB-01", "WhatsApp pricing", "Whether service messages and in-window utility templates become billable from 1 Oct 2026", "§9.3", "VERIFY_AT_BUILD", "Meter counts every message either way"),
    Verify("VB-02", "WhatsApp template categories", "How renewal reminders and review invites are categorised", "§10.4, §17.1", "VERIFY_AT_BUILD", ""),
    Verify("VB-03", "WhatsApp calling", "Availability on coexistence numbers; messaging-limit prerequisite", "§11.1", "VERIFY_AT_BUILD", ""),
    Verify("VB-04", "Meta 'AI Providers' pricing policy (16 Feb 2026)", "That it does not apply to LOCAH business-task use", "§9.1", "VERIFY_AT_BUILD", ""),
    Verify("VB-05", "Recurring payments", "Current RBI e-mandate limits via the provider (Cashfree per PDF)", "§10.4", "VERIFY_AT_BUILD", "Autopay marked ACTIVATION_REQUIRED"),
    Verify("VB-06", "DPDP Rules", "Commencement dates; children's-data consent mechanics", "§20.4, §25", "VERIFY_AT_BUILD", ""),
    Verify("VB-07", "E-commerce rules", "LOCAH Marketplace obligations as a marketplace", "§25", "VERIFY_AT_BUILD", ""),
    Verify("VB-08", "Legal advertising", "Rules on advocates' websites and marketing", "§21.9", "VERIFY_AT_BUILD", ""),
    Verify("VB-09", "FSSAI", "Licence-number display for online food sales", "§25", "VERIFY_AT_BUILD", ""),
    Verify("VB-10", "FCRA", "Handling of foreign donations for NGOs", "§21.11", "VERIFY_AT_BUILD", ""),
    Verify("VB-11", "Meta ad categories", "Restrictions for housing, credit, employment and health ads in India", "§18.3", "VERIFY_AT_BUILD", ""),
    Verify("VB-12", "Google Business Profile API", "Access approval process", "§9.1", "VERIFY_AT_BUILD", ""),
    Verify("VB-13", "TallyPrime", "Behaviour across versions (XML vs JSONEx), multi-company setups", "§15", "VERIFY_AT_BUILD", ""),
    Verify("VB-14", "GSTR-1 export", "Current offline-tool file format", "§14.4", "VERIFY_AT_BUILD", ""),
    Verify("VB-15", "Maps URLs", "Available travel modes (two-wheeler) in India", "§13.3", "VERIFY_AT_BUILD", ""),
    Verify("VB-16", "Label scales", "Barcode format of the pilot hardware", "§14.3", "VERIFY_AT_BUILD", "Per-business configurable format"),
    Verify("VB-17", "Listing sites", "Calendar import/export support for homestays", "§21.6", "VERIFY_AT_BUILD", ""),
    Verify("VB-18", "Partner APIs", "Shipping, hyperlocal, EMI and accounting APIs open to small merchants", "§9.1", "VERIFY_AT_BUILD", ""),
    Verify("VB-19", "GST state codes", "The state-code table used for place of supply and GSTIN checks (platform_core/invoicing/states.py)", "§14.4", "VERIFY_AT_BUILD", "Reference data, editable in one place"),
    Verify("VB-20", "Invoice number length", "The GST limit on invoice-number length (16 characters) against the source example CHN1/26-27/000123, which is 17", "§14.4", "VERIFY_AT_BUILD", "Default padding 5 keeps CHN1/26-27/00001 at 16; longer numbers are flagged to the owner, not blocked"),
    Verify("VB-21", "In-store barcodes", "GS1 restricted-circulation prefix used for in-store codes (20…)", "§14.3", "VERIFY_AT_BUILD", "One constant in platform_core/pos/barcodes.py"),
    Verify("VB-22", "Tamil and Hindi templates", "Native-speaker review of the Tamil and Hindi WhatsApp template wording before it is submitted for a real number", "§12.4", "VERIFY_AT_BUILD", "Wording lives in platform_core/messaging/templates.py; the sandbox approves it automatically, Meta will not"),
    Verify("VB-23", "WhatsApp coexistence echoes", "The webhook field and shape Meta uses for replies the owner sends from the WhatsApp Business app on a coexistence number (built as `smb_message_echoes` / `message_echoes`)", "§9.1, §12.5", "VERIFY_AT_BUILD", "One parser in MessagingService._echo; confirm against a recorded Meta delivery at activation"),
]

SECTIONS = [compliance, roadmap, testing, e2e]
