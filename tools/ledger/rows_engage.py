"""Customer and reach rows: CRM, leads, messaging/WhatsApp, reviews, compliance,
marketing, loyalty (MD §6.1–§6.2, §12, §17, §18; PDF §7, §13)."""

from __future__ import annotations

from tools.ledger.model import Section, r

S, P, C, A, F = "NOT_STARTED", "PARTIAL", "COMPLETE", "ACTIVATION_REQUIRED", "FUTURE"

crm = Section(
    "P. Customer relationships (MD §6.1, §24; Founder §29)",
    "",
    [
        r("CR-01", "P0", "MD §6.1", "Customer contacts, notes, timeline entries", "customer-relationships", "EXISTING", C,
          "contacts/notes/timeline", db="✓", svc="✓", ws="✓ /customers", test="✓ test_customer_kernel"),
        r("CR-02", "P1", "MD §6.1", "Unified timeline across orders, bookings, memberships, invoices, messages, reviews, jobs", "customer-relationships", "EXTEND", P, "timeline entries exist; not every module writes to it"),
        r("CR-03", "P1", "MD §6.1", "Tags", "customer-relationships", "EXISTING", P, "tags array on contacts; no tag management UI", db="✓"),
        r("CR-04", "P1", "MD §6.1 · §18.2", "Segments (rule-built)", "customer-relationships", "NEW", S, "absent"),
        r("CR-05", "P1", "MD §6.1 · §24 #8", "Consent flags (see PM-08) with timestamp and source", "customer-relationships", "NEW", S, "absent"),
        r("CR-06", "P5", "MD §6.1 · §20.4", "Guardians (guardian is contact of record for minors; one guardian, many children)", "customer-relationships", "NEW", S, "absent"),
        r("CR-07", "P2", "MD §6.1 · §24", "Customer assets: vehicle, pet, AC unit, device, policy, property, installed machine", "customer-relationships", "NEW", S, "absent"),
        r("CR-08", "P1", "MD §25.1", "Per-customer export and delete (DPDP access/erasure)", "customer-relationships", "NEW", S, "customers.export permission only"),
        r("CR-09", "P2", "MD §21.2", "Measurement profiles (tailors) stored on the customer", "customer-relationships", "NEW", S, "absent"),
    ],
)

leads = Section(
    "Q. Leads (MD §6.1; Founder §29)",
    "Website, Marketplace, WhatsApp and Meta leads become the same LOCAH lead.",
    [
        r("LD-01", "P0", "MD §6.1", "Lead capture (website enquiry, marketplace, manual, import), assignment, follow-up date, notes, history", "leads", "EXISTING", C,
          "leads kernel", db="✓", svc="✓", ws="✓ /leads", web="✓ enquiry_form", test="✓ test_leads_kernel"),
        r("LD-02", "P2", "MD §6.1 · §19.3", "Configurable stages (e.g. real estate New→Contacted→Site visit booked→Visited→Quote sent→Negotiation→Token paid→Agreement→Won/Lost)", "leads", "EXTEND", S, "fixed statuses"),
        r("LD-03", "P2", "MD §6.1", "Sources: web, WhatsApp, call, Meta lead ads, walk-in, channel partner", "leads", "EXTEND", P, "web/marketplace/manual/import only"),
        r("LD-04", "P2", "MD §6.1", "Follow-up SLA with nudges (task / 'Needs you now')", "leads", "EXTEND", P, "next_follow_up_at only"),
        r("LD-05", "P2", "MD §7.2", "Assignment-scoped view for sales executives / channel partners", "leads", "EXTEND", S, "absent"),
        r("LD-06", "P2", "MD §19.2", "Brochure download = phone + consent → lead", "leads", "NEW", S, "absent"),
    ],
)

messaging = Section(
    "R. Messaging & WhatsApp (MD §6.2, §9.1, §12; PDF §7; P1-07/P1-08)",
    "Every WhatsApp path ends in the same order/booking/lead the website would create. Provider activation is separate from the internal inbox and journeys.",
    [
        r("MS-01", "P1", "MD §6.2", "Business inbox: conversations and messages per channel", "messaging", "NEW", S, "absent"),
        r("MS-02", "P1", "MD §6.2 · §12.4", "Template library (order confirmed, out for delivery, delivered, booking reminder, renewal, payment due) in English/Tamil/Hindi", "messaging", "NEW", S, "absent"),
        r("MS-03", "P1", "MD §6.2 · §12.4", "Opt-ins via consent store; marketing needs explicit opt-in", "messaging", "NEW", S, "absent"),
        r("MS-04", "P1", "MD §12.1", "Router: button/list reply or menu word → deterministic step; free text → AI (P3) ; human asked/low confidence → inbox", "messaging", "NEW", S, "absent"),
        r("MS-05", "P1", "MD §12.1", "A human reply pauses AI in that thread for 12 h", "messaging", "NEW", S, "absent"),
        r("MS-06", "P1", "MD §6.2", "SMS / email fallback", "messaging", "NEW", A, "email provider exists for auth; SMS needs DLT templates"),
        r("MS-07", "P1", "MD §9.1", "WhatsApp Cloud API: LOCAH as Tech Provider, Embedded Signup per business, coexistence", "messaging", "NEW", A, "needs Meta app + §28.1 decision"),
        r("MS-08", "P1", "MD §26.3 P1-07", "Webhooks (idempotent), notification routing to WhatsApp, meters", "messaging", "NEW", S, "absent"),
        r("MS-09", "P1", "MD §12.2", "Entry points: counter/packaging QR, website 'Order on WhatsApp', Marketplace, GBP, Click-to-WhatsApp ads", "messaging", "NEW", S, "absent"),
        r("MS-10", "P1", "MD §12.3", "Journey Order: menu → category → item → qty/cut/weight → cart → delivery/pickup → address pin → pay link or COD → orders + reservation + dispatch job", "messaging", "NEW", S, "absent"),
        r("MS-11", "P1", "MD §12.3", "Journey Book: service → date → slots → confirm → bookings", "messaging", "NEW", S, "absent"),
        r("MS-12", "P1", "MD §12.3", "Journey Enquire: lead-form flow → leads + assignment", "messaging", "NEW", S, "absent"),
        r("MS-13", "P1", "MD §12.3", "Journey Pay/renew/dues: template button → payment link", "messaging", "NEW", S, "absent"),
        r("MS-14", "P1", "MD §12.3", "Journey Track: status + live tracking link", "messaging", "NEW", S, "absent"),
        r("MS-15", "P1", "MD §12.3", "Journey Reorder: repeat last order", "messaging", "NEW", S, "absent"),
        r("MS-16", "P1", "MD §12.3", "Journey Change/cancel within owner policy", "messaging", "NEW", S, "absent"),
        r("MS-17", "P1", "MD §12.3", "Talk to a person button always visible → Workspace inbox", "messaging", "NEW", S, "absent"),
        r("MS-18", "P1", "MD §12.4", "Customer confirms every cart/booking with a button; stock and slots re-checked at confirm with alternatives", "messaging", "NEW", S, "absent"),
        r("MS-19", "P1", "MD §12.4", "Address from location pin → geocoded and saved; last address offered first", "messaging", "NEW", S, "absent"),
        r("MS-20", "P1", "MD §12.4", "Policy boundary: only this business's tasks; off-topic gets a polite redirect", "messaging", "NEW", S, "absent"),
        r("MS-21", "P3", "MD §12.4", "Optional catalogue sync to a Meta commerce catalogue (LOCAH stays source of truth)", "messaging", "NEW", A, "Meta catalogue API"),
        r("MS-22", "P1", "MD §12.5", "Inbox: status chips (AI handling, needs a person, order, booking, lead); side panel with orders/bookings/balance/membership + one-tap actions", "messaging", "NEW", S, "absent"),
        r("MS-23", "P1", "MD §12.5", "Assign to staff, quick replies, wait timer; waiting > 10 min → Needs you now", "messaging", "NEW", S, "absent"),
        r("MS-24", "P1", "MD §12.6", "Tests: cart price = catalogue price; duplicate webhooks → one order; 12 h human pause; no marketing template without consent — zero model calls", "messaging", "NEW", S, "absent"),
        r("MS-25", "P3", "MD §12.3", "Free-text path (WhatsApp Manager): '2 kg chicken curry cut…' → cart lines, asks only the missing choice", "messaging", "NEW", S, "needs AI runtime"),
        r("MS-26", "P3", "PDF §7", "Promotions/broadcasts: consented audience, approved templates, owner approves offer/audience/schedule/spend; replies return to inbox; frequency controls", "marketing", "NEW", S, "absent"),
    ],
)

reviews = Section(
    "S. Reviews and moderation (MD §6.2, §17; PDF §13; P1-09)",
    "",
    [
        r("RV-01", "P1", "MD §17.1", "One review per completed interaction (delivered order, completed booking, membership period with ≥1 check-in, closed job card); 30-day window", "reviews", "NEW", S, "absent"),
        r("RV-02", "P1", "MD §17.1", "Rating 1–5, text, up to 3 photos, Verified badge", "reviews", "NEW", S, "absent"),
        r("RV-03", "P1", "MD §17.1", "Invitation via WhatsApp after completion + prompt in My Activity", "reviews", "NEW", S, "absent"),
        r("RV-04", "P1", "MD §17.2", "Owner: reply publicly, report with a reason, choose featured reviews on own website", "reviews", "NEW", S, "absent"),
        r("RV-05", "P1", "MD §17.2", "Only a LOCAH moderator removes a Marketplace review, for a listed violation, reason logged, reviewer told, one appeal", "reviews", "NEW", S, "absent"),
        r("RV-06", "P1", "MD §17.2", "No one edits review text; moderator may only redact personal data", "reviews", "NEW", S, "absent"),
        r("RV-07", "P1", "MD §17.2", "Average always from every published review; featured strip shows true average + 'See all reviews'", "reviews", "NEW", S, "absent"),
        r("RV-08", "P1", "MD §17.3", "1–2 star review → Needs you now item with contact; only the reviewer can update", "reviews", "NEW", S, "absent"),
        r("RV-09", "P3", "MD §17.4", "Review Responder drafts; auto-posts only 4–5 star replies if owner turns it on", "reviews", "NEW", S, "needs AI runtime"),
        r("RV-10", "P3", "MD §17.4", "Google Business Profile reviews mirrored read-only with reply support, never in LOCAH average", "reviews", "NEW", A, "GBP API approval"),
        r("RV-11", "P1", "MD §17.5", "Tests: no business role/API can delete or edit a review; ineligible review rejected; average = mean of published", "reviews", "NEW", S, "absent"),
    ],
)

compliance = Section(
    "T. Compliance calendar (MD §6.2, §23 #15; P1-09)",
    "Records, reminds and links — no legal/tax advice.",
    [
        r("CP-01", "P1", "MD §6.2", "Licence and filing calendar (FSSAI, trade, drug, fire, bar, GST/IT filings)", "compliance", "NEW", S, "absent"),
        r("CP-02", "P1", "MD §6.2", "Expiry reminders via automation ladder; owner notified + task created", "compliance", "NEW", S, "absent"),
        r("CP-03", "P1", "MD §6.2", "Document vault link per compliance item", "compliance", "NEW", S, "absent"),
        r("CP-04", "P1", "MD §25.1", "Regulated fields shown on site where entered: RERA number, FSSAI number, accreditation number", "compliance", "NEW", S, "absent"),
        r("CP-05", "P4", "MD §21.9", "Per-client compliance calendar for CA firms turned into tasks", "compliance", "NEW", S, "absent"),
    ],
)

marketing = Section(
    "U. Marketing, Meta and local presence (MD §6.2, §18; PDF §13)",
    "The owner approves every broadcast and every rupee.",
    [
        r("MK-01", "P3", "MD §18.2", "Audiences: rule-built segments shown as counts; only consented contacts for WhatsApp; marketer cannot export numbers", "marketing", "NEW", S, "absent"),
        r("MK-02", "P3", "MD §18.2", "Offers: coupon codes, auto-applied, first-order, win-back; usage limits, expiry, per-customer caps", "marketing", "NEW", S, "absent"),
        r("MK-03", "P3", "MD §18.2", "WhatsApp broadcasts to opted-in customers with per-message cost shown before send", "marketing", "NEW", S, "absent"),
        r("MK-04", "P3", "MD §18.2", "Meta ads via the owner's ad account; monthly cap enforced before any API call", "marketing", "NEW", A, "Meta app review"),
        r("MK-05", "P3", "MD §18.2", "Conversions API: hashed server-side Purchase/Lead events with consent", "marketing", "NEW", A, "Meta"),
        r("MK-06", "P3", "MD §18.2 · §9.1", "Google Business Profile: hours, posts, photos, review replies, links to order/book pages", "marketing", "NEW", A, "GBP API approval"),
        r("MK-07", "P3", "MD §18.2", "Attribution: UTM links, CTWA ad ids, coupon use → leads/orders/bookings/revenue/cost per order, labelled 'approximate, last touch'", "marketing", "NEW", S, "absent"),
        r("MK-08", "P3", "MD §18.1", "Campaign flow goal → audience → offer → creative → channel+budget → owner approves → live → results", "marketing", "NEW", S, "absent"),
        r("MK-09", "P3", "MD §18.4", "Tests: no marketing template without consent; campaign over cap blocked before Meta call; results never estimated", "marketing", "NEW", S, "absent"),
        r("MK-10", "P3", "MD §25.1 · §21.9", "Regulated categories: marketing off by default for lawyers; restricted for finance; no marketing to minors", "marketing", "NEW", S, "absent"),
    ],
)

loyalty = Section(
    "V. Loyalty & referrals (MD §6.2, §18.2)",
    "",
    [
        r("LY-01", "P3", "MD §18.2", "Points per ₹ with a points ledger and expiry", "loyalty", "NEW", S, "absent"),
        r("LY-02", "P3", "MD §18.2", "Stamp cards ('10th coffee free') and rewards", "loyalty", "NEW", S, "absent"),
        r("LY-03", "P3", "MD §18.2", "Referral codes rewarded on the friend's first order", "loyalty", "NEW", S, "absent"),
        r("LY-04", "P3", "MD §21.3", "Gift vouchers as prepaid balance", "loyalty", "NEW", S, "absent"),
    ],
)

SECTIONS = [crm, leads, messaging, reviews, compliance, marketing, loyalty]
