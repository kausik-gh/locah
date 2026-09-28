"""Founder refinements (authority 1), added to Documentations/ on 2026-09-28/29:
`# FOUNDER REFINEMENT — INVENTORY / BOOKINGS / MEMBERSHIPS / PAYMENTS.txt` and
`B2B.txt`. They refine the MD/PDF scope of those modules; statuses here are the
baseline when they arrived (after P1-10A) and move through progress.py."""

from __future__ import annotations

from tools.ledger.model import Section, r

S = "NOT_STARTED"
P = "PARTIAL"
C = "COMPLETE"
A = "ACTIVATION_REQUIRED"

_INV_T = "✓ test_stock_depth + browser p1_10a_stock, p1_10a_counter_serials"

refinements = Section(
    "A2. Founder refinements — Inventory, Bookings, Memberships, Payments, B2B (2026-09-28/29)",
    "Founder documents that sharpen how each module must behave; each ends with a browser acceptance list. "
    "They rank with the founder prompt, above the PDF and the MD.",
    [
        # ---------------------------------------------------------------- inventory
        r("FR-IN-01", "P1", "FR-Inventory §1, §26", "One stock truth: POS, website, WhatsApp and bills move the same stock through one service; no channel stock copies", "inventory", "EXTEND", C,
          "[P1-10A] every path (counter, Workspace bill, online/WhatsApp order, count, cut, wastage) is a movement on the one record under its lock", test=_INV_T),
        r("FR-IN-02", "P1", "FR-Inventory §2", "Stock modes composed from real characteristics: simple, weight, yield/transformation, variant, batch/expiry (FEFO), serialised", "inventory", "EXTEND", C,
          "[P1-10A] modes from traits + §21 hints + configuration; FEFO on every sale path; serial per unit; yields and cutting runs", test=_INV_T),
        r("FR-IN-03", "P2", "FR-Inventory §2, §19", "Multi-location transfers: requested → approved where required → in transit → received; transit stock not free at either end", "inventory", "NEW", S,
          "per-location stock exists; transfers not built (IN-07)"),
        r("FR-IN-04", "P5", "FR-Inventory §2, §17", "Van / mobile stock: central → van; technician consumes parts against a job; unused parts returned", "inventory", "NEW", S,
          "needs van locations and Jobs (P5)"),
        r("FR-IN-05", "P4", "FR-Inventory §2, §10", "Ingredient/material consumption through Recipe/BOM when a finished item sells (shawarma, restaurant, manufacturer)", "recipes", "NEW", S,
          "Recipes & BOM is P4"),
        r("FR-IN-06", "P1", "FR-Inventory §4", "Receive stock: simple (qty + cost), batch (batch, expiry), serial (IMEI list), weight (kg + cost/kg); stock rises only on actual receipt", "inventory", "EXTEND", P,
          "[P1-10A] all four receive paths with total cost and buying units; cost-per-kg / per-unit entry not offered yet", test=_INV_T),
        r("FR-IN-07", "P1", "FR-Inventory §5", "Reserve on confirmed online/WhatsApp order, release on cancel, deduct on fulfil; returns restore the same serial and batch", "inventory", "EXTEND", C,
          "[P1-10A] reservations (First Launch + P1-08) with FEFO on deduction; returns and cancellations go back to the original batch and serial", test=_INV_T),
        r("FR-IN-08", "P1", "FR-Inventory §6", "Stock counts: expected/counted/variance with approval; by category/aisle for supermarkets; per location", "inventory", "EXTEND", P,
          "[P1-10A] blind counts, approval, applied against current stock, per location; category scope exists in the API but the Workspace start form offers no category picker yet", test=_INV_T),
        r("FR-IN-09", "P1", "FR-Inventory §7", "Wastage/write-off with reasons; prominent for food/fresh, not the main screen for electronics", "inventory", "EXTEND", C,
          "[P1-10A] reasons ordered per lens; wastage leads only on fresh/food views", test=_INV_T),
        r("FR-IN-10", "P1", "FR-Inventory §8, §9", "Reorder: minimum, target, safety stock → suggested replenish quantity as an input to Procurement (not a second purchasing system)", "inventory", "EXTEND", P,
          "[P1-10A] min and fill-up-to with suggested quantity; safety stock and the Procurement hand-off arrive with Buying (P4)", test=_INV_T),
        r("FR-IN-11", "P1", "FR-Inventory §3; B2B §4", "Available-to-promise excludes reserved and expired/unusable stock; confirmed inbound shown where Procurement exists", "inventory", "EXTEND", P,
          "[P1-10A] free = on hand − reserved; expired batches flagged and sold last; inbound needs Procurement (P4)", test=_INV_T),
        r("FR-IN-12", "P1", "FR-Inventory §11–§18, §21", "Inventory home adapts by trait/configuration: kirana, supermarket, meat, restaurant, pharmacy, fashion, electronics, field service, industrial", "inventory", "EXTEND", P,
          "[P1-10A] counter-by-weight, batches, serials, size grid, ingredients and reorder homes; restaurant recipe consumption (P4), field van (P5), industrial lots/raw-material homes (P4) not yet", test=_INV_T),
        r("FR-IN-13", "P2", "FR-Inventory §22", "Role views: store keeper (receive/count/transfer), cashier (sale-time stock, serial capture), kitchen (ingredients), technician (own van/job parts), picker (order items)", "inventory", "EXTEND", P,
          "[P1-10A] store keeper and cashier done; kitchen, technician and picker surfaces arrive with Kitchen (P2), Jobs (P5), Dispatch (P2)"),
        r("FR-IN-14", "P1", "FR-Inventory §23", "Inventory automations: low stock, expiring stock, count variance awaiting approval, transfer awaiting receipt, reorder suggestion", "inventory", "EXTEND", P,
          "[P1-10A] low-stock and expiry ladders; count-awaiting-approval notice, transfers and reorder suggestion not yet", auto="◐"),
        r("FR-IN-15", "P1", "FR-Inventory §24", "Inventory insights only from real data: on hand, value, low, near-expiry, wastage, count variance, movement, yield variance", "insights", "EXTEND", P,
          "[P1-10A] value, low, expiring, wastage and yield accuracy shown on the stock views; no Insights page yet (IS-01)"),
        r("FR-IN-16", "P1", "FR-Inventory §27", "Browser acceptance: 14 inventory scenarios (small shop, online reserve/release, kirana count, meat, restaurant recipe, pharmacy, fashion sale, electronics return, transfer, van, reorder, RLS, 390 px, regression)", "inventory", "EXTEND", P,
          "[P1-10A] meat cut + wastage, pharmacy expiry + write-off, fashion grid, electronics IMEI at the counter + lookup, count approval, 390 px; small-shop POS 24→22, online reserve/release, fashion variant sale, electronics return in the browser, transfer, van, restaurant and reorder→procurement not yet"),
        # ---------------------------------------------------------------- bookings
        r("FR-BK-01", "P2", "FR-Bookings §1", "One booking record from every channel (website, Marketplace, WhatsApp, phone/AI, front desk, Workspace) with the channel stored", "bookings", "EXTEND", P,
          "website, WhatsApp (P1-08) and Workspace create the same booking; phone/AI (P3) and front-desk surface (P2) not yet"),
        r("FR-BK-02", "P2", "FR-Bookings §2–§3", "Real availability from hours, provider/resource schedule, duration, buffers, bookings, blocks, capacity; re-checked with a slot lock at confirm", "bookings", "EXTEND", P,
          "availability engine + exclusive-resource constraint exist; buffers, horizon/notice rules and a commit-time slot hold per mode not complete"),
        r("FR-BK-03", "P2", "FR-Bookings §4–§14, §28", "Mode-specific flows and settings: appointment (service→provider/any→date→slot), table (date→time→party), stay (date range→room type), class (capacity/waitlist), rental (asset→range), site visit (→assigned salesperson), event date", "bookings", "EXTEND", S,
          "the website booking page is one generic start/end form for everyone"),
        r("FR-BK-04", "P2", "FR-Bookings §15–§17", "Recurring bookings (edit one / future), waitlist with customer acceptance, temporary holds that release when unpaid", "bookings", "NEW", S, "absent"),
        r("FR-BK-05", "P2", "FR-Bookings §18–§21", "Deposit/full payment via Payments; reschedule releases old slot and keeps history; cancellation by policy frees slot and triggers waitlist; arrival/no-show states", "bookings", "EXTEND", P,
          "deposits, cancel window and reschedule exist; waitlist reaction and mode-specific states not"),
        r("FR-BK-06", "P2", "FR-Bookings §24–§27", "Front desk calendar (today, next available, arrivals, no-shows), provider 'my schedule', owner utilisation; reminders; My Activity upcoming/past with reschedule/cancel/pay balance", "bookings", "EXTEND", P,
          "[P1-10B] customer account shows upcoming and past bookings with the manage link; front-desk and provider surfaces (P2)"),
        r("FR-BK-07", "P2", "FR-Bookings §30", "Browser acceptance: 15 booking scenarios incl. two simultaneous customers → exactly one succeeds", "bookings", "EXTEND", S, "not yet"),
        # ---------------------------------------------------------------- memberships
        r("FR-MB-01", "P2", "FR-Memberships §1–§3", "One recurring-relationship engine with plan kinds; per-kind language (Membership, Subscription, Fees/Enrolment, Service plan, Dues); periods never overwritten; deterministic states", "memberships", "EXTEND", S,
          "plans + enrolments with fixed statuses; no plan kinds, periods or per-kind language"),
        r("FR-MB-02", "P2", "FR-Memberships §4–§5", "Lifecycle recalculated on every event and by a daily business-timezone job; owner sees active/expiring/due/pending/grace/expired/paused; ladder stops after renewal", "memberships", "NEW", S, "absent"),
        r("FR-MB-03", "P2", "FR-Memberships §6–§8", "Gym: members board, QR check-in eligibility green/amber/red, freeze extends end by exactly the frozen days with history; session packs track remaining uses as the truth Bookings asks", "memberships", "NEW", S, "absent"),
        r("FR-MB-04", "P2", "FR-Memberships §9–§15", "Recurring delivery subscriptions: items, quantity, days, meal slots, window, address, prepaid/postpaid; cutoff generates tomorrow's orders; skip, pause, one-day quantity override, change future; any suitable product", "memberships", "NEW", S, "absent"),
        r("FR-MB-05", "P2", "FR-Memberships §16–§19", "Fee plans with instalments (paid/outstanding/next due, guardian payer, no auto-removal), AMC contracts with visits via Jobs, club dues with good standing", "memberships", "NEW", S, "absent"),
        r("FR-MB-06", "P2", "FR-Memberships §20–§21", "Autopay renews exactly once; failure follows retry → grace → expiry; early renewal queues the next period", "memberships", "NEW", S, "autopay needs Cashfree (activation)"),
        r("FR-MB-07", "P2", "FR-Memberships §22–§25", "Owner homes per kind (gym, milk/food, coaching, AMC, club); customer 'My …' per kind; WhatsApp renew/skip/pause buttons on the same service; Needs you now summaries", "memberships", "NEW", S, "absent"),
        r("FR-MB-08", "P2", "FR-Memberships §28", "Browser acceptance: gym renewal, freeze, session pack, milk skip/override/pause, tiffin counts, postpaid bill, coaching instalments, AMC, club, failure/grace, early renewal, RLS, 390 px", "memberships", "NEW", S, "not yet"),
        # ---------------------------------------------------------------- payments
        r("FR-PY-01", "P1", "FR-Payments §2–§4", "Payment states separate from the transaction (unpaid, pending, paid, failed, part-paid, refunded, part-refunded, expired); retry creates a new attempt, never a new order; pending checks the provider before another attempt", "payments", "EXTEND", P,
          "payment_attempts with statuses and webhook receipts exist; retry/pending-recheck flow for customers not built; provider is Cashfree (activation)"),
        r("FR-PY-02", "P1", "FR-Payments §5, §10", "Business chooses full / advance / % advance / deposit / pay later; total, paid and balance always shown; balance collectable later by link, counter, cash, UPI", "payments", "EXTEND", P,
          "booking deposits and counter split tender exist; order advances and a general balance view not"),
        r("FR-PY-03", "P1", "FR-Payments §7", "Secure payment link tied to the real order/booking/membership/invoice/balance for WhatsApp; webhook marks the same record paid", "payments", "EXTEND", S,
          "khata statement carries the business's own UPI link; provider payment links need Cashfree (PY-02)"),
        r("FR-PY-04", "P1", "FR-Payments §9, §12, §14", "Refunds linked to a prior payment (full/partial) keeping history; receipts through Invoicing; owner sees paid today, pending, failed, balances, refunds — verified payments only", "payments", "EXTEND", P,
          "refund records and invoice payments exist; owner payment overview incomplete"),
        # ---------------------------------------------------------------- B2B
        r("FR-B2B-01", "P4", "B2B §1, §10", "Supplier relationships (on or off LOCAH): item mapping, supplier code, unit, pack, MOQ, price and history, lead time, delivery days, terms, preferred/fallback, connection state", "procurement", "NEW", S, "absent"),
        r("FR-B2B-02", "P4", "B2B §2, §13", "Three purchase origins: standing/recurring (edit one occurrence, skip, pause, change future), ad-hoc, demand-driven", "procurement", "NEW", S, "absent"),
        r("FR-B2B-03", "P4", "B2B §3–§5, §9", "Demand & Supply planning: aggregate all buyer demand (orders, bookings, subscriptions, forecast, par) with drill-down; BOM/yield conversion; net = demand + safety − ATP − inbound; pack/MOQ rounding", "procurement", "NEW", S, "absent"),
        r("FR-B2B-04", "P4", "B2B §6–§7", "Suggested requisition → review/edit → approve & send; owner-set auto-approval limits only; supplier counter (qty/price/date) with diff → accept/counter/decline", "procurement", "NEW", S, "absent"),
        r("FR-B2B-05", "P4", "B2B §8, §11", "A PO received by a LOCAH supplier becomes their incoming B2B sales order; their planning repeats upstream; buyer and supplier records stay distinct (sales order ≠ requisition ≠ PO ≠ GRN ≠ bill)", "trade-network", "NEW", S,
          "needs ChitBridge dependency gate"),
        r("FR-B2B-06", "P4", "B2B §12", "Goods receipt with actual quantity/weight, batch, cost, shortage and quality issue → inventory up by actual, payable linked, dispute path", "procurement", "NEW", S,
          "the P1-10A receive function is the stock half of a GRN"),
        r("FR-B2B-07", "P4", "B2B acceptance", "Browser acceptance: 15 B2B scenarios (3-node chain, 100 buyers → 30 net, safety/inbound, standing order, counter, GRN, idempotent webhooks, off-network supplier, isolation, recursive upstream)", "procurement", "NEW", S, "not yet"),
    ],
)

SECTIONS = [refinements]
