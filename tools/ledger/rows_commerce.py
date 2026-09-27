"""Commerce rows: offerings, orders, payments, inventory, fulfilment, invoicing,
POS, khata, Tally (MD §6.1–§6.3, §14, §15; PDF §4, §11, §12)."""

from __future__ import annotations

from tools.ledger.model import Section, r

S, P, C, A, F = "NOT_STARTED", "PARTIAL", "COMPLETE", "ACTIVATION_REQUIRED", "FUTURE"

offerings = Section(
    "G. Offerings catalogue and offering kinds (MD §6.1, §6.3)",
    "One catalogue, many kinds; the kind decides fields, website section and transaction flow.",
    [
        r("OF-01", "P1", "MD §6.1", "Offering kinds on one catalogue (13 kinds below) with kind-specific fields", "offerings-catalog", "EXTEND", P,
          "offering_type has 8 values (product, menu_item, service, accommodation, membership_plan, class_session, rental, listing)",
          db="◐", svc="✓ offering", perm="✓", ws="✓ /offerings", web="◐", test="✓ test_inventory_kernel"),
        r("OF-02", "P1", "MD §6.1 · §14.3", "GTIN / HSN / SAC codes on offerings", "offerings-catalog", "EXTEND", S, "barcode column only"),
        r("OF-03", "P1", "MD §6.1 · §15.1", "Units and conversions (buy by crate/kg, sell per 500 g or piece)", "offerings-catalog", "EXTEND", S, "unit_of_measure text only"),
        r("OF-04", "P1", "MD §6.1 · §15.1", "Variants: size × colour matrix, stock per SKU", "offerings-catalog", "EXTEND", P, "variants table (name/sku/barcode/price) + inventory per variant; no attribute matrix", db="◐", svc="✓"),
        r("OF-05", "P4", "MD §6.1 · §22", "B2B price lists (customer-specific; two price lists for hybrid; price visibility shown/logged-in/on request)", "offerings-catalog", "NEW", S, "absent"),
        r("OK-01", "P1", "MD §6.3", "product (variants optional) → cart → order / POS", "offerings-catalog", "EXISTING", P, "product kind + cart/checkout; POS absent", web="✓ product_showcase + /checkout"),
        r("OK-02", "P1", "MD §6.3", "weighed_product (per kg, cut, pack size) → cart → order / POS weighed label", "offerings-catalog", "NEW", S, "absent; inventory quantities are integers"),
        r("OK-03", "P1", "MD §6.3", "menu_item (modifiers, add-ons) → cart → order / table / KOT", "offerings-catalog", "EXTEND", P, "menu_item kind + menu_section; no modifiers", web="◐ menu_section"),
        r("OK-04", "P1", "MD §6.3", "service (duration, provider) → booking", "offerings-catalog", "EXISTING", P, "service kind + workforce_service_associations + /book; duration field to verify", web="✓ /book"),
        r("OK-05", "P1", "MD §6.3", "class / course → booking or enrolment", "offerings-catalog", "EXTEND", P, "class_session kind + classes_section; no course/enrolment", web="◐"),
        r("OK-06", "P1", "MD §6.3", "room_type / rental_resource → date-range booking + deposit", "offerings-catalog", "EXTEND", P, "accommodation/rental kinds + date_range resources + deposits", web="◐ rooms_section"),
        r("OK-07", "P1", "MD §6.3", "plan → membership", "offerings-catalog", "EXISTING", P, "membership_plan kind + memberships_plans", web="◐ plans_section"),
        r("OK-08", "P1", "MD §6.3", "package (bundle of sessions or items) → order, then redeemed", "offerings-catalog", "NEW", S, "absent"),
        r("OK-09", "P1", "MD §6.3", "property_project / unit → enquiry → site visit → quote", "offerings-catalog", "NEW", S, "'listing' kind only"),
        r("OK-10", "P1", "MD §6.3", "vehicle → enquiry → test drive → quote", "offerings-catalog", "NEW", S, "absent"),
        r("OK-11", "P1", "MD §6.3", "portfolio_item → showcase → enquiry", "offerings-catalog", "NEW", S, "gallery sections only"),
        r("OK-12", "P1", "MD §6.3", "digital_product → order → download link", "offerings-catalog", "NEW", S, "absent"),
        r("OK-13", "P1", "MD §6.3", "cause → donation", "offerings-catalog", "NEW", S, "absent"),
        r("OK-14", "P1", "MD §26.3 P1-03", "New kinds render on the tenant site; existing catalogue tests still pass", "website", "NEW", S, "absent"),
        r("OK-15", "P1", "MD §21.2", "Formula-priced offerings (jewellery: metal rate × weight + making + GST from a daily rate board)", "offerings-catalog", "NEW", S, "absent"),
    ],
)

orders = Section(
    "H. Orders and commerce loop (MD §6.1, §22, §23; Founder §22)",
    "Website, Marketplace, POS and WhatsApp converge on one order and stock truth.",
    [
        r("OR-01", "P0", "MD §6.1", "Order lifecycle with reservation, idempotent creation, status history", "orders", "EXISTING", C,
          "orders kernel + status history + inventory reservation + idempotency key", db="✓", svc="✓", perm="✓", ws="✓ /orders", cust="✓ /checkout", test="✓ test_orders_kernel"),
        r("OR-02", "P1", "MD §6.1", "Channel field: web, WhatsApp, POS, phone, ChitBridge", "orders", "EXTEND", S, "no channel column"),
        r("OR-03", "P2", "MD §6.1 · §21.1", "Dine-in / table orders (QR dine-in ordering)", "orders", "EXTEND", S, "absent"),
        r("OR-04", "P1", "MD §6.1 · §21.1", "Pre-orders with a date (cakes, catering, festival windows)", "orders", "EXTEND", S, "absent"),
        r("OR-05", "P2", "MD §6.1 · §14.1", "Returns and exchanges → credit note + stock back", "orders", "EXTEND", S, "absent"),
        r("OR-06", "P2", "MD §21.2 · §22", "Order stages for made-to-order (tailoring cutting→stitching→trial; laundry; print job tickets) via stage engine", "orders", "NEW", S, "fixed statuses"),
        r("OR-07", "P1", "Founder §22", "End-to-end commerce loop: catalogue → cart → order → payment → invoice → inventory → preparation → pickup/delivery → tracking → review → timeline", "orders", "EXTEND", P,
          "catalogue→cart→order→payment→inventory→fulfilment→tracking exist; invoice/review/timeline links absent", test="✓ test_checkout_flow"),
        r("OR-08", "P1", "MD §12.3", "Reorder ('repeat last order')", "orders", "NEW", S, "absent"),
        r("OR-09", "P1", "MD §12.4", "Cart price always equals catalogue price at that moment (re-checked at confirm)", "orders", "EXISTING", P, "order_calculation prices from catalogue server-side", svc="✓"),
    ],
)

payments = Section(
    "I. Payments (MD §6.1, §9.1, §25; PDF §12 — Cashfree direction)",
    "Provider-neutral payment domain; provider activation is separate.",
    [
        r("PY-01", "P0", "MD §6.1", "Payment attempts, refunds, webhook receipts; COD / pay at business / online", "payments", "EXISTING", C,
          "payments kernel", db="✓", svc="✓", perm="✓", ws="✓ /payments", test="✓ test_payments_kernel"),
        r("PY-02", "P1", "MD §6.1 · §12.4", "Payment links (renewals, deposits, invoices, WhatsApp)", "payments", "EXTEND", S, "absent"),
        r("PY-03", "P1", "MD §6.1 · §14.1", "UPI dynamic QR with exact amount, confirmed by webhook", "payments", "EXTEND", A, "needs provider (Cashfree) activation"),
        r("PY-04", "P1", "MD §6.1", "Deposits", "payments", "EXTEND", P, "booking deposits exist; quote deposits computed", db="◐"),
        r("PY-05", "P1", "MD §6.1 · §14.1", "Split tender (cash + UPI + card + khata)", "payments", "EXTEND", S, "absent"),
        r("PY-06", "P1", "MD §6.1", "Cash / card records (card recorded against an external terminal)", "payments", "EXTEND", S, "pay_at_business only"),
        r("PY-07", "P1", "MD §6.1 · §12.4", "COD with a first-order COD cap", "payments", "EXTEND", P, "COD exists; no cap"),
        r("PY-08", "P0", "MD §6.1", "Refunds from authorized workflow, reconciled to the originating payment", "payments", "EXISTING", C, "refund service", test="✓"),
        r("PY-09", "P2", "MD §6.1 · §10.4", "Subscriptions / autopay mandate", "payments", "EXTEND", A, "provider capability must be verified (RBI e-mandate)"),
        r("PY-10", "P1", "PDF §12", "Cashfree provider adapter (checkout, webhooks, settlement/split)", "payments", "EXTEND", A, "deferred to the Cashfree pass by founder decision"),
        r("PY-11", "P1", "PDF §12", "Platform billing (business → LOCAH) as separate transactions", "payments", "NEW", A, "needs Cashfree platform account; commercial_entitlements exists"),
        r("PY-12", "P6", "MD §9.1", "Payouts", "payments", "FUTURE", F, "FUTURE by source"),
    ],
)

inventory = Section(
    "J. Inventory (MD §6.1, §15.1; PDF §11)",
    "Configuration/traits decide which capabilities a business uses.",
    [
        r("IN-01", "P0", "MD §15.1", "Stock per offering/variant/location with movements and reservations (reserve on order, release on cancel)", "inventory", "EXISTING", C,
          "inventory_records/movements, reservation", db="✓", svc="✓", ws="✓ /inventory", test="✓ test_inventory_kernel"),
        r("IN-02", "P1", "MD §15.1", "Units and conversions, fractional quantities (weights)", "inventory", "EXTEND", S, "integer quantities"),
        r("IN-03", "P1", "MD §15.1", "Yield (1 kg whole chicken → 0.8 kg curry cut), used in selling and procurement maths", "inventory", "NEW", S, "absent"),
        r("IN-04", "P1", "MD §15.1", "Variants: stock per SKU", "inventory", "EXISTING", C, "inventory per variant_id", test="✓"),
        r("IN-05", "P1", "MD §15.1", "Batches and expiry, FEFO picking, expiry alerts", "inventory", "EXTEND", S, "absent"),
        r("IN-06", "P1", "MD §15.1", "Serials and warranty (serial captured at sale; warranty lookup)", "inventory", "EXTEND", S, "absent"),
        r("IN-07", "P2", "MD §15.1", "Multi-location transfers with in-transit state", "inventory", "EXTEND", S, "per-location stock exists; no transfers"),
        r("IN-08", "P1", "MD §15.1", "Stock counts (cycle counts by category; variances need approval)", "inventory", "EXTEND", S, "adjustment movement only"),
        r("IN-09", "P1", "MD §15.1", "Wastage with reasons (expired, damaged, trim loss); feeds yield accuracy", "inventory", "EXTEND", S, "absent"),
        r("IN-10", "P1", "MD §15.1", "Reorder points min/max per location → low-stock alert → requisition draft", "inventory", "EXTEND", P, "low_stock_threshold only"),
        r("IN-11", "P4", "MD §15.1", "Van stock (a vehicle is a location)", "inventory", "EXTEND", S, "absent"),
        r("IN-12", "P1", "MD §15.1", "Valuation: weighted average cost from goods receipts", "inventory", "NEW", S, "absent"),
        r("IN-13", "P1", "PDF §11", "Online orders, POS and WhatsApp orders converge on the same stock", "inventory", "EXTEND", P, "online orders reserve/deduct; POS/WhatsApp absent"),
        r("IN-14", "P4", "MD §21.6", "Client-owned stock (warehousing, cold storage): inward/outward log per client, client stock view", "inventory", "NEW", S, "absent"),
    ],
)

fulfilment = Section(
    "K. Fulfilment (MD §6.1)",
    "",
    [
        r("FU-01", "P0", "MD §6.1", "Pickup and local delivery jobs, zones, delivery charge, tracking token + customer tracking page", "fulfilment", "EXISTING", C,
          "fulfilment kernel + /[slug]/track/[orderId]", db="✓", svc="✓", ws="✓ /fulfilment", cust="✓", test="✓ test_fulfilment_kernel, test_order_tracking"),
        r("FU-02", "P2", "MD §6.1 · §9.1", "Shipping (courier aggregator) with milestones on the same tracking page", "fulfilment", "EXTEND", A, "needs aggregator (§28.1 decision)"),
        r("FU-03", "P2", "MD §6.1 · §13", "Local delivery handed to dispatch", "fulfilment", "EXTEND", S, "no dispatch module"),
    ],
)

invoicing = Section(
    "L. Invoicing & GST (MD §6.2, §14.4, §14.6; P1-04)",
    "Tax rates are data the owner/CA sets; LOCAH computes, it does not advise.",
    [
        r("IV-01", "P1", "MD §14.4", "Tax invoice (GSTIN, FY series, HSN/SAC, taxable value, CGST+SGST or IGST, place of supply)", "invoicing", "NEW", S, "absent"),
        r("IV-02", "P1", "MD §14.4", "Tax invoice with buyer GSTIN for B2B", "invoicing", "NEW", S, "absent"),
        r("IV-03", "P1", "MD §14.4", "Bill of supply for composition scheme (declaration, no tax line)", "invoicing", "NEW", S, "absent"),
        r("IV-04", "P1", "MD §14.4", "Bill / receipt for unregistered seller (no GST fields)", "invoicing", "NEW", S, "absent"),
        r("IV-05", "P1", "MD §14.4 · §6.2", "Credit notes / debit notes referencing the original invoice", "invoicing", "NEW", S, "absent"),
        r("IV-06", "P1", "MD §14.4", "Rates as data per offering/HSN with effective dates, never hard-coded", "invoicing", "NEW", S, "tax_rate numeric on offering only"),
        r("IV-07", "P1", "MD §14.4 · §24 #5", "Gapless series per GSTIN × FY (Apr–Mar) × register, e.g. CHN1/26-27/000123; cancelled invoices stay marked", "invoicing", "NEW", S, "absent"),
        r("IV-08", "P1", "MD §14.4", "Outputs: A4 PDF, 58/80 mm thermal, WhatsApp 'Your bill from <business>', email", "invoicing", "NEW", S, "absent"),
        r("IV-09", "P1", "MD §14.4", "For the CA: sales register, HSN summary, tax-by-rate summary, GSTR-1-ready export, Tally export", "invoicing", "NEW", S, "absent"),
        r("IV-10", "P1", "MD §14.4", "Tax-treatment questions show 'Confirm with your CA' + a setting, never an assumption", "invoicing", "NEW", S, "absent"),
        r("IV-11", "P1", "MD §14.6", "Tests: same-state CGST/SGST, other-state IGST; composition never prints tax; round-off own line never changes tax", "invoicing", "NEW", S, "absent"),
        r("IV-12", "P4", "MD §9.1 · §14", "E-invoice IRN + QR (via GST Suvidha Provider) and e-way bill", "invoicing", "NEW", A, "needs GSP (§28.1)"),
        r("IV-13", "P1", "MD §14", "Every bill (counter, website, WhatsApp, B2B) from one billing engine with a stock movement", "invoicing", "NEW", S, "absent"),
        r("IV-14", "P4", "MD §21.10", "Foreign-currency proforma/invoices (import/export)", "invoicing", "NEW", S, "absent"),
    ],
)

pos = Section(
    "M. POS counter billing (MD §6.2, §14.1–§14.3, §14.5; P1-05)",
    "",
    [
        r("PS-01", "P1", "MD §14.1", "Registers and cash-drawer shifts: open with opening cash, close counted vs expected", "pos", "NEW", S, "absent"),
        r("PS-02", "P1", "MD §14.1", "Scan or search → cart + optional customer", "pos", "NEW", S, "absent"),
        r("PS-03", "P1", "MD §14.1", "Tenders: cash, UPI QR, card (external terminal), split, khata", "pos", "NEW", S, "absent"),
        r("PS-04", "P1", "MD §14.1", "Hold and recall bills", "pos", "NEW", S, "absent"),
        r("PS-05", "P1", "MD §14.1", "Returns and exchanges create a credit note and put stock back", "pos", "NEW", S, "absent"),
        r("PS-06", "P1", "MD §14.1", "Role limits: discount cap per role; voids/returns past the window need a manager PIN", "pos", "NEW", S, "absent"),
        r("PS-07", "P1", "MD §14.1", "Receipt print (ESC/POS 58/80 mm) + WhatsApp bill", "pos", "NEW", S, "absent"),
        r("PS-08", "P2", "MD §14.1", "Restaurants: POS sends kitchen tickets by station; table bills, split and merge", "pos", "NEW", S, "absent"),
        r("PS-09", "P1", "MD §14.2", "Offline mode: catalogue/prices cached with a version stamp; bills queue on device", "pos", "NEW", S, "absent"),
        r("PS-10", "P1", "MD §14.2", "Each register reserves a block of invoice numbers (default 50) while online", "pos", "NEW", S, "absent"),
        r("PS-11", "P1", "MD §14.2", "UPI cannot be verified offline: cash or 'UPI to verify', reconciled on sync", "pos", "NEW", S, "absent"),
        r("PS-12", "P1", "MD §14.3", "Scanner as keyboard input or tablet camera; in-store codes and label printing for loose goods", "pos", "NEW", S, "absent"),
        r("PS-13", "P1", "MD §14.3", "Weighed-label barcodes (item code + weight or price) decoded with a per-business format", "pos", "NEW", S, "absent"),
        r("PS-14", "P1", "MD §14.5", "Cash closing: opening + cash sales − cash refunds − petty expenses = expected; counted and variance logged per shift", "pos", "NEW", S, "absent"),
        r("PS-15", "P1", "MD §14.6", "Two-register offline sync: no duplicate or missing numbers", "pos", "NEW", S, "absent"),
        r("PS-16", "P6", "MD §9.1", "Card-present terminal integration", "pos", "FUTURE", F, "FUTURE by source"),
    ],
)

ledger = Section(
    "N. Khata / credit book (MD §6.2, §14.5; P1-06)",
    "",
    [
        r("LG-01", "P1", "MD §6.2", "Ledger accounts per customer and supplier with running balance from entries", "ledger", "NEW", S, "absent"),
        r("LG-02", "P1", "MD §14.5", "Credit sale posts to the customer's ledger", "ledger", "NEW", S, "absent"),
        r("LG-03", "P1", "MD §14.5", "Credit limits; at the limit POS blocks credit unless a manager overrides", "ledger", "NEW", S, "absent"),
        r("LG-04", "P1", "MD §6.2", "Ageing (receivables and payables)", "ledger", "NEW", S, "absent"),
        r("LG-05", "P1", "MD §14.5", "WhatsApp statement with a UPI/payment link; reminders", "ledger", "NEW", S, "absent"),
        r("LG-06", "P1", "MD §6.2", "Settlements (payment against balance)", "ledger", "NEW", S, "absent"),
        r("LG-07", "P1", "MD §26.3", "Balance equals sum of entries under concurrent writes", "ledger", "NEW", S, "absent"),
        r("LG-08", "P2", "MD §10.6", "Postpaid recurring delivery accrues to ledger; month-end bill (milkman model)", "ledger", "NEW", S, "absent"),
    ],
)

tally = Section(
    "O. Tally and other billing software (MD §9.1, §15.2–§15.7; PDF §11)",
    "",
    [
        r("TL-01", "P4", "MD §15.2", "LOCAH Connector Agent on the Tally PC: outbound HTTPS only, pairs with a one-time code", "connectors", "NEW", S, "absent"),
        r("TL-02", "P4", "MD §15.2", "JSONEx for TallyPrime 7.0+, XML for older; every request names svCurrentCompany", "connectors", "NEW", S, "absent"),
        r("TL-03", "P4", "MD §15.2", "Heartbeat: Workspace says in plain words when the PC/Tally is closed; changes queue", "connectors", "NEW", S, "absent"),
        r("TL-04", "P4", "MD §15.2", "Idempotency via voucher reference + sync_mapping", "connectors", "NEW", S, "absent"),
        r("TL-05", "P4", "MD §15.3 · PDF §11", "Owner picks Preset A (LOCAH runs shop, Tally keeps books) or B (Tally master) per data family", "connectors", "NEW", S, "absent"),
        r("TL-06", "P4", "MD §15.3", "Conflicts owner-wins per family; overwritten edit logged 'overridden' with both values", "connectors", "NEW", S, "absent"),
        r("TL-07", "P4", "MD §15.4", "Setup wizard: pair, preset, map tax ledgers and payment modes, match stock items, posting per invoice or daily summary", "connectors", "NEW", S, "absent"),
        r("TL-08", "P4", "MD §15.5", "Zoho Books via API; Vyapar, Busy, Marg via CSV/Excel import-export first", "connectors", "NEW", S, "absent"),
        r("TL-09", "P4", "MD §15.6", "Supplier bill photo → AI Bookkeeper draft → human confirms before GRN/payable/voucher", "connectors", "NEW", S, "absent"),
        r("TL-10", "P4", "MD §15.7", "Tests: same sync twice no duplicates; 3-day-offline agent catches up in order; request without company rejected; Preset B round-trip matches", "connectors", "NEW", S, "absent"),
        r("TL-11", "P4", "MD §15", "Real Tally installation connection", "connectors", "NEW", A, "needs a Tally PC; agent contract testable with recorded pairs"),
    ],
)

SECTIONS = [offerings, orders, payments, inventory, fulfilment, invoicing, pos, ledger, tally]
