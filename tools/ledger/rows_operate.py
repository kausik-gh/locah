"""Run-the-day rows: bookings, memberships, attendance, queue, tasks, kitchen,
dispatch/crew, workforce, quotes, projects, real estate, jobs, academics,
documents, donations, insights, expenses, procurement, recipes, trade network
(MD §6, §10, §13, §16, §19, §20; PDF §9, §10, §14–§16)."""

from __future__ import annotations

from tools.ledger.model import Section, r

S, P, C, A, F = "NOT_STARTED", "PARTIAL", "COMPLETE", "ACTIVATION_REQUIRED", "FUTURE"

bookings = Section(
    "W. Bookings — seven distinct modes (MD §6.1; Founder §25)",
    "",
    [
        r("BK-01", "P0", "MD §6.1", "Bookings kernel: resources (exclusive/pooled, buffers, slot/date_range), allocation, policies (deposit, cancel window), guest management link, public booking page", "bookings", "EXISTING", C,
          "bookings kernel + allocation + /[slug]/book + /[slug]/bookings/[id]", db="✓", svc="✓", ws="✓ /bookings", cust="✓", web="✓ /book", test="✓ test_bookings_kernel, test_booking_resources"),
        r("BK-02", "P2", "MD §6.1", "Mode appointment (provider/department)", "bookings", "EXISTING", P, "appointment mode + provider_id; department grouping absent"),
        r("BK-03", "P2", "MD §6.1", "Mode table (party size)", "bookings", "EXISTING", P, "table mode + party_size"),
        r("BK-04", "P2", "MD §6.1", "Mode stay (date range, rooms, check-in/out)", "bookings", "EXTEND", P, "accommodation mode + date_range resources; no check-in/out operations"),
        r("BK-05", "P2", "MD §6.1", "Mode class (capacity, timetable)", "bookings", "EXTEND", P, "class_session mode + capacity"),
        r("BK-06", "P2", "MD §6.1", "Mode rental (handover checklist, return, damage/late fees)", "bookings", "EXTEND", P, "rental mode only"),
        r("BK-07", "P2", "MD §6.1", "Mode site_visit (with assigned sales executive)", "bookings", "NEW", S, "absent"),
        r("BK-08", "P2", "MD §6.1", "Mode event_date (halls, photographers, catering; guest count)", "bookings", "NEW", S, "absent"),
        r("BK-09", "P2", "MD §6.1", "Waitlist (fill cancellations)", "bookings", "NEW", S, "absent"),
        r("BK-10", "P2", "MD §6.1", "Recurring bookings", "bookings", "NEW", S, "absent"),
        r("BK-11", "P2", "MD §6.1", "Reschedule policy", "bookings", "EXTEND", P, "cancel window policy; reschedule rules absent"),
        r("BK-12", "P2", "MD §11.4", "Slot holds that auto-release after the owner's hold time (default 15 min); slot lock at commit", "bookings", "NEW", S, "absent"),
        r("BK-13", "P2", "MD §21.3", "Provider + room booked together (spa)", "bookings", "NEW", S, "absent"),
        r("BK-14", "P2", "MD §10.7", "Expired member cannot book a class unless owner allows", "bookings", "NEW", S, "absent"),
        r("BK-15", "P2", "MD §21.4", "Private mode (therapy): minimal data, discreet reminders, reviews off by default", "bookings", "NEW", S, "absent"),
    ],
)

memberships = Section(
    "X. Memberships and subscriptions (MD §6.1, §10; PDF §9)",
    "",
    [
        r("MB-01", "P0", "MD §10", "Plans and enrolments with payment", "memberships", "EXISTING", P,
          "plans (fixed_duration/recurring) + enrolments (pending/active/paused/expired/cancelled/completed)", db="✓", svc="✓", ws="✓ /memberships", test="✓ test_memberships_kernel"),
        r("MB-02", "P2", "MD §10.1", "Plan kind access (check in until end date)", "memberships", "EXTEND", S, "no plan kind"),
        r("MB-03", "P2", "MD §10.1", "Plan kind session_pack (sessions left > 0 and before expiry)", "memberships", "EXTEND", S, "absent"),
        r("MB-04", "P2", "MD §10.1", "Plan kind recurring_delivery (deliveries generated on schedule)", "memberships", "EXTEND", S, "absent"),
        r("MB-05", "P2", "MD §10.1", "Plan kind service_contract (covered visits within period; AMC)", "memberships", "EXTEND", S, "absent"),
        r("MB-06", "P2", "MD §10.1", "Plan kind fee_plan (instalments, late fee, guardian payer)", "memberships", "EXTEND", S, "absent"),
        r("MB-07", "P2", "MD §10.1", "Plan kind member_dues (good standing, annual)", "memberships", "EXTEND", S, "absent"),
        r("MB-08", "P2", "MD §10.2", "States PENDING_PAYMENT → ACTIVE ⇄ PAUSED; ACTIVE → GRACE → EXPIRED; EXPIRED → ACTIVE; CANCELLED; 'expiring soon' derived", "memberships", "EXTEND", P, "no GRACE state; pause does not extend end date"),
        r("MB-09", "P2", "MD §10.3", "Entities: plan (joining fee, grace days, freeze allowance, channels, ladder), member_subscription, subscription_period (one row per paid period), subscription_freeze", "memberships", "EXTEND", S, "no periods/freezes"),
        r("MB-10", "P2", "MD §10.4", "Renewal ladder T−7, T−2, T0 (autopay attempt), T+1 grace, end of grace expired, T+15 win-back (marketing opt-in only)", "memberships", "NEW", S, "absent"),
        r("MB-11", "P2", "MD §10.4", "Payment webhook → extend period, issue invoice, send receipt, cancel pending ladder steps — one transaction; idempotency key subscription+period+step", "memberships", "NEW", S, "absent"),
        r("MB-12", "P2", "MD §10.4", "Quiet hours (9 pm–8 am) and Asia/Kolkata date boundary for every step", "memberships", "NEW", S, "absent"),
        r("MB-13", "P2", "MD §10.5", "Members board tabs: Active · Expiring in 7 days · In grace · Expired · Paused · Payment pending; row actions send link, record cash, freeze, renew", "memberships", "EXTEND", S, "basic list only"),
        r("MB-14", "P2", "MD §10.5", "Renewal calendar: renewals due per day with amounts", "memberships", "NEW", S, "absent"),
        r("MB-15", "P2", "MD §10.5", "Member profile: period bars, freezes shaded, check-ins as dots, payments", "memberships", "NEW", S, "absent"),
        r("MB-16", "P2", "MD §10.5", "Front desk check-in by QR: green active, amber grace (if permitted), red expired + Collect renewal", "memberships", "NEW", S, "absent"),
        r("MB-17", "P2", "MD §10.5", "My Activity membership card: date bar, days left, check-in QR, Renew, Request freeze", "memberships", "NEW", S, "absent"),
        r("MB-18", "P2", "MD §10.6", "Recurring delivery: cutoff (default 9 pm) generates tomorrow's orders and delivery jobs; skip/pause by WhatsApp; postpaid → ledger month-end bill", "memberships", "NEW", S, "absent"),
        r("MB-19", "P2", "MD §10.6", "Service contract schedules preventive visits as jobs; parts covered or chargeable", "memberships", "NEW", S, "absent"),
        r("MB-20", "P2", "MD §10.7", "Tests: replayed webhook no double-extend; 10-day freeze moves end by exactly 10 days; no reminder after renewal or in quiet hours; ladder steps in activity log", "memberships", "NEW", S, "absent"),
        r("MB-21", "P2", "MD §6.1", "Autopay mandates", "memberships", "EXTEND", A, "provider (Cashfree) + RBI rules verify"),
    ],
)

attendance = Section(
    "Y. Attendance / check-ins (MD §6.2)",
    "",
    [
        r("AT-01", "P2", "MD §6.2", "Member check-in by QR or manual (attendance_event)", "attendance", "NEW", S, "absent"),
        r("AT-02", "P5", "MD §6.2 · §20.2", "Student attendance per session (teacher one-tap, default present)", "attendance", "NEW", S, "absent"),
        r("AT-03", "P2", "MD §6.2 · §21.8", "Staff check-in / site attendance (geo-verified for guards)", "attendance", "NEW", S, "absent"),
        r("AT-04", "P6", "MD §6.2", "Hardware adapters (turnstiles, biometric)", "attendance", "FUTURE", F, "later by source"),
        r("AT-05", "P2", "MD §21.4", "Authorised pick-up list for daycare", "attendance", "NEW", S, "absent"),
    ],
)

queue = Section(
    "Z. Walk-in queue (MD §6.2)",
    "",
    [
        r("QU-01", "P2", "MD §6.2", "Tokens: issue, waiting, called, served, missed", "queue", "NEW", S, "absent"),
        r("QU-02", "P2", "MD §6.2", "Live queue board", "queue", "NEW", S, "absent"),
        r("QU-03", "P2", "MD §6.2", "'Your turn soon' WhatsApp", "queue", "NEW", S, "absent"),
        r("QU-04", "P2", "MD §21.4", "Booked appointments and walk-ins in one queue per provider/department", "queue", "NEW", S, "absent"),
    ],
)

tasks = Section(
    "AA. Tasks & checklists (MD §6.2)",
    "",
    [
        r("TK-01", "P2", "MD §6.2", "Tasks: housekeeping, maintenance, prep, opening/closing checklists", "tasks", "NEW", S, "projects_tasks exist inside projects only"),
        r("TK-02", "P2", "MD §6.2", "Checklist templates with photo proof", "tasks", "NEW", S, "absent"),
        r("TK-03", "P2", "MD §4.3", "Stay checkout → housekeeping task automatically", "tasks", "NEW", S, "absent"),
        r("TK-04", "P2", "MD §4.3 · §21.6", "Rental handover and return checklists (photos, damage)", "tasks", "NEW", S, "absent"),
    ],
)

kitchen = Section(
    "AB. Kitchen display (MD §6.2)",
    "",
    [
        r("KT-01", "P2", "MD §6.2", "Kitchen order tickets by station", "kitchen", "NEW", S, "absent"),
        r("KT-02", "P2", "MD §6.2", "Bump screen and prep timers", "kitchen", "NEW", S, "absent"),
        r("KT-03", "P2", "MD §6.2", "Printer fallback", "kitchen", "NEW", S, "absent"),
        r("KT-04", "P2", "MD §7.2", "Kitchen users see no prices or phone numbers", "kitchen", "NEW", S, "absent"),
    ],
)

dispatch = Section(
    "AC. Delivery, dispatch and crew app (MD §6.2, §13; PDF §10)",
    "",
    [
        r("DP-01", "P2", "MD §13.1", "Job states CREATED→READY→ASSIGNED→PICKED_UP→EN_ROUTE→DELIVERED | FAILED→(ASSIGNED|RETURNED)", "dispatch", "NEW", S, "fulfilment has simpler statuses"),
        r("DP-02", "P2", "MD §13.1", "Customer sees five steps: Placed · Preparing · Picked up · On the way · Delivered", "dispatch", "EXTEND", P, "tracking page stepper exists for fulfilment statuses"),
        r("DP-03", "P2", "MD §13.2", "Entities dispatch_job, crew_shift, location_ping, proof_of_delivery, cod_settlement", "dispatch", "NEW", S, "absent"),
        r("DP-04", "P2", "MD §13.3", "Crew: go on duty (location only while on duty banner), my jobs in suggested order, navigate via Maps URL, call customer only on active job, picked up/arrived/delivered (OTP or photo)/failed (reason)", "dispatch", "NEW", S, "absent"),
        r("DP-05", "P2", "MD §13.3", "Collect COD (cash or UPI QR); end-shift settlement expected vs collected confirmed by manager", "dispatch", "NEW", S, "absent"),
        r("DP-06", "P2", "MD §13.3", "Status taps and pings queue offline and sync", "dispatch", "NEW", S, "absent"),
        r("DP-07", "P2", "MD §13.4", "P2a PWA with wake-lock; ping ~15 s moving / 60 s stopped; nothing off duty; raw pings 7 days (≤30) retention; consent at onboarding", "dispatch", "NEW", S, "absent"),
        r("DP-08", "P2", "MD §13.4 · §26.2", "P2b native wrapper with background location", "dispatch", "NEW", A, "needs Flutter/Capacitor build (§28.1)"),
        r("DP-09", "P2", "MD §13.5", "Dispatch board columns Unassigned · Assigned · Picked up · On the way · Delivered today · Failed; assign by drag or auto (nearest on-duty with capacity, then round-robin); group area runs", "dispatch", "NEW", S, "absent"),
        r("DP-10", "P2", "MD §13.5", "Map view with crew dots and ping age; job pins", "dispatch", "NEW", A, "map renderer decision (§28.1)"),
        r("DP-11", "P2", "MD §13.5", "Alerts: late vs window, ping older than 5 min while on the way, COD not settled at shift end", "dispatch", "NEW", S, "absent"),
        r("DP-12", "P2", "MD §13.6", "Tracking page: live dot only between pickup and delivery, ETA, partner first name, call dials the business, link expires 24 h after delivery, post-delivery review prompt", "dispatch", "EXTEND", P, "tracking page exists without live location"),
        r("DP-13", "P2", "MD §13.7", "ETA via Routes API at pickup and on drift/5 min", "dispatch", "NEW", A, "Google Routes key"),
        r("DP-14", "P3", "MD §13.8", "Overflow: Delivery Coordinator suggests third-party courier; owner approves paid booking; partner tracking link stored", "dispatch", "NEW", A, "partner APIs"),
        r("DP-15", "P2", "MD §13.9", "Tests: partner reads only assigned jobs (RLS); no ping off duty; no location before pickup/after delivery; COD expected = sum delivered COD", "dispatch", "NEW", S, "absent"),
        r("DP-16", "P2", "MD §21.8", "Field jobs share dispatch (technicians, phlebotomists, caregivers, walkers)", "dispatch", "NEW", S, "absent"),
    ],
)

workforce = Section(
    "AD. Workforce (MD §6.1)",
    "",
    [
        r("WF-01", "P0", "MD §6.1", "Staff/provider records, availability, service associations, location assignments", "workforce", "EXISTING", C,
          "workforce kernel", db="✓", svc="✓", ws="✓ /workforce", test="✓ test_workforce_kernel"),
        r("WF-02", "P2", "MD §6.1", "Provider schedules and shifts (rota)", "workforce", "EXTEND", P, "availability windows only"),
        r("WF-03", "P2", "MD §6.1", "Skills and assignment rules", "workforce", "EXTEND", S, "absent"),
        r("WF-04", "P6", "MD §6.1", "Commission rules", "workforce", "FUTURE", F, "FUTURE by source"),
        r("WF-05", "P2", "MD §21.11", "Volunteers rosters (community)", "workforce", "EXTEND", S, "absent"),
    ],
)

quotes = Section(
    "AE. Quotes & proposals (MD §6.2, §19.4; P2)",
    "",
    [
        r("QT-01", "P0", "MD §6.2", "Versioned quotes (revision rows), validity, share link, online accept/reject, conversion target fields, print-ready document", "quotes", "EXISTING", P,
          "quotes kernel + public view/accept; document is HTML not PDF", db="✓", svc="✓", ws="✓ /quotes", cust="✓ /q", test="✓ test_quotes"),
        r("QT-02", "P2", "MD §6.2", "RFQ intake from website/WhatsApp (request quote → draft quote)", "quotes", "NEW", S, "absent"),
        r("QT-03", "P2", "MD §19.4", "Discounts above the executive's limit go to owner approval", "quotes", "NEW", S, "absent"),
        r("QT-04", "P2", "MD §19.4", "Owner sees when the customer opened each version", "quotes", "NEW", S, "absent"),
        r("QT-05", "P2", "MD §19.4", "Accept with name + OTP; accepted version locks every price component", "quotes", "EXTEND", P, "accept by name; OTP absent"),
        r("QT-06", "P2", "MD §6.2", "Convert accepted quote to order / project / invoice", "quotes", "EXTEND", P, "fields exist; project conversion via source_quote_id"),
        r("QT-07", "P2", "MD §19.4", "Payment plan + token payment link after acceptance", "quotes", "NEW", S, "absent"),
        r("QT-08", "P2", "MD §21.10", "Quantity breaks, MOQ, lead time, size-matrix and BOQ line templates", "quotes", "NEW", S, "absent"),
        r("QT-09", "P3", "MD §23 #13", "Quote-view tracking and follow-up nudges (Sales Executive)", "quotes", "NEW", S, "absent"),
    ],
)

projects = Section(
    "AF. Projects and real estate (MD §6.2, §19; PDF §14)",
    "",
    [
        r("PJ-01", "P0", "MD §6.2", "Projects with phases, tasks, assignments, lifecycle, source quote", "projects", "EXISTING", P,
          "projects kernel", db="✓", svc="✓", ws="✓ /projects", test="✓ test_projects"),
        r("PJ-02", "P5", "MD §6.2", "Milestones and payment schedule with reminders", "projects", "EXTEND", S, "absent"),
        r("PJ-03", "P5", "MD §6.2", "Client approvals (drawings, artwork, deliverables with version history)", "projects", "EXTEND", S, "absent"),
        r("PJ-04", "P5", "MD §6.2", "File room / media per project with customer visibility", "projects", "EXTEND", S, "absent"),
        r("PJ-05", "P2", "MD §19.1", "Property project entity: status upcoming/launching/live/sold_out/completed/on_hold, map pin, RERA field, possession date, amenities, gallery, video, brochure, floor plans", "projects", "NEW", S, "absent"),
        r("PJ-06", "P2", "MD §19.1", "unit_type (e.g. 2 BHK, carpet area, starting price) and unit (tower/floor/number, facing, area, base price, status available/held/booked/sold/blocked)", "projects", "NEW", S, "absent"),
        r("PJ-07", "P2", "MD §19.1", "price_component (base, floor rise, PLC, parking, club, GST, owner-entered estimates)", "projects", "NEW", S, "absent"),
        r("PJ-08", "P2", "MD §19.2", "Owner upload flow: create project, bulk images, video, brochure, floor plans, unit grid/CSV, publish", "projects", "NEW", S, "absent"),
        r("PJ-09", "P2", "MD §19.2", "Website Projects section with tabs Upcoming · Live · Completed; project page with gallery, map, amenities, unit types, live availability chart from real unit statuses, Download brochure (lead), Book site visit", "website", "NEW", S, "absent"),
        r("PJ-10", "P2", "MD §19.4", "Quote builder: pick unit → components auto-filled → role-limited discount → payment plan → validity 7 d → PDF + link on WhatsApp → accept name+OTP → token link → unit HELD → BOOKED", "projects", "NEW", S, "absent"),
        r("PJ-11", "P2", "MD §19.4", "Valid quote soft-holds a unit only if owner enables holds; else first token wins", "projects", "NEW", S, "absent"),
        r("PJ-12", "P5", "MD §19.5", "After booking: schedule reminders (Collections), document checklist, construction progress photos to buyer portal", "projects", "NEW", S, "absent"),
        r("PJ-13", "P5", "MD §19.5", "Channel partners get an assignment-scoped view of own leads; commission tracking FUTURE", "projects", "NEW", S, "absent"),
        r("PJ-14", "P2", "MD §19.6", "Tests: two customers cannot both reach BOOKED on one unit; availability chart = count by status; accepted quote total never changes", "projects", "NEW", S, "absent"),
        r("PJ-15", "P5", "MD §21.9", "Matters (lawyers) with hearing dates and strict per-matter access", "projects", "NEW", S, "absent"),
        r("PJ-16", "P5", "MD §21.7", "Running-account bills, retention money, site logs, daily labour attendance (contractors)", "projects", "NEW", S, "absent"),
    ],
)

jobs = Section(
    "AG. Job cards / field service (MD §6.2; P5)",
    "",
    [
        r("JB-01", "P5", "MD §6.2", "Job card flow request → inspect → estimate → approve → work → parts → QC → invoice → complete", "jobs", "NEW", S, "absent"),
        r("JB-02", "P5", "MD §6.2", "Linked to a customer asset with service history", "jobs", "NEW", S, "absent"),
        r("JB-03", "P5", "MD §21.8", "Customer approves estimate on WhatsApp/link", "jobs", "NEW", S, "absent"),
        r("JB-04", "P5", "MD §21.8", "Inspection photos, parts from stock / van stock", "jobs", "NEW", S, "absent"),
        r("JB-05", "P5", "MD §21.8", "Ready alert, reminders by date or km, repair warranty", "jobs", "NEW", S, "absent"),
        r("JB-06", "P5", "MD §21.4", "Lab sample → test job → results → certificate PDF with QR verification link", "jobs", "NEW", S, "absent"),
    ],
)

academics = Section(
    "AH. Education (MD §6.2, §20; PDF §15; P5)",
    "A full school ERP (transport, exams board, HR) is FUTURE.",
    [
        r("AC-01", "P5", "MD §20.1", "course → batch (teacher, schedule, capacity, room/link) → session → enrolment (student, guardian, batch, fee plan)", "academics", "NEW", S, "absent"),
        r("AC-02", "P5", "MD §20.2", "Admissions: enquiry → demo class booking → counselling → enrolment form with documents → fee plan → payment → batch allocation → welcome", "academics", "NEW", S, "absent"),
        r("AC-03", "P5", "MD §20.2", "Daily attendance + absence note to guardian (once per missed session, never for cancelled)", "academics", "NEW", S, "absent"),
        r("AC-04", "P5", "MD §20.2", "Fees via fee_plan ladder; concessions/sibling discounts need approval", "academics", "NEW", S, "absent"),
        r("AC-05", "P5", "MD §20.2", "Tests and marks → report card PDF → guardian; progress chart from real marks", "academics", "NEW", S, "absent"),
        r("AC-06", "P5", "MD §20.2", "Homework with a file (submissions by upload later P5b)", "academics", "NEW", S, "absent"),
        r("AC-07", "P5", "MD §20.2", "Announcements to a batch or everyone over WhatsApp and portal", "academics", "NEW", S, "absent"),
        r("AC-08", "P5", "MD §20.2", "Timetable with teacher and room clash detection", "academics", "NEW", S, "absent"),
        r("AC-09", "P5", "MD §20.2", "Online classes: meeting link per session", "academics", "NEW", S, "absent"),
        r("AC-10", "P5", "MD §20.2", "Certificates PDF with verification link", "academics", "NEW", S, "absent"),
        r("AC-11", "P5", "MD §20.3", "Guardian portal (each child's classes, attendance %, fees + Pay, marks, homework, announcements); student portal without payments; teacher view own batches", "academics", "NEW", S, "absent"),
        r("AC-12", "P5", "MD §20.4", "Safeguarding: guardian is contact of record under 18; no marketing to minors; teachers cannot export contacts; photo consent flag; DPDP children's consent verify", "academics", "NEW", S, "absent"),
        r("AC-13", "P5", "MD §20.5", "Variants: preschool pick-up list + daily note; driving school instructor+vehicle slots and learner dates; music/dance grade tracking", "academics", "NEW", S, "absent"),
        r("AC-14", "P5", "MD §20.6", "Tests: guardian sees only own children; absence note once; overdue changes status only by owner rule", "academics", "NEW", S, "absent"),
        r("AC-15", "P6", "MD §20", "Full school ERP (transport, exams board, HR); LMS", "academics", "FUTURE", F, "FUTURE by source"),
    ],
)

documents = Section(
    "AI. Documents, forms and signatures (MD §6.2; P5)",
    "",
    [
        r("DC-01", "P5", "MD §6.2", "Document templates", "documents", "NEW", S, "absent"),
        r("DC-02", "P5", "MD §6.2", "Intake and consent forms (18+ / guardian check where required)", "documents", "NEW", S, "absent"),
        r("DC-03", "P5", "MD §6.2", "Uploads with encrypted storage and expiring links for sensitive documents", "documents", "EXTEND", P, "media_assets storage exists; no document records"),
        r("DC-04", "P5", "MD §6.2", "Typed / drawn signatures", "documents", "NEW", S, "absent"),
        r("DC-05", "P5", "MD §21.9", "WhatsApp document requests with an upload link", "documents", "NEW", S, "absent"),
        r("DC-06", "P6", "MD §5", "E-sign provider", "documents", "FUTURE", F, "FUTURE by source"),
    ],
)

donations = Section(
    "AJ. Donations (MD §6.2, §21.11; P5)",
    "",
    [
        r("DN-01", "P5", "MD §6.2", "Causes and campaigns", "donations", "NEW", S, "absent"),
        r("DN-02", "P5", "MD §6.2", "One-off and recurring gifts", "donations", "NEW", S, "absent"),
        r("DN-03", "P5", "MD §6.2 · §21.11", "80G receipts only when the organisation is registered for it", "donations", "NEW", S, "absent"),
        r("DN-04", "P5", "MD §6.2", "Donor timeline and updates; donor/CSR reports", "donations", "NEW", S, "absent"),
        r("DN-05", "P5", "MD §21.11 · §25", "Foreign-currency donations blocked unless FCRA registration declared", "donations", "NEW", S, "absent"),
        r("DN-06", "P5", "MD §21.11", "Seva/pooja dated bookings and sponsorships (temples)", "donations", "NEW", S, "absent"),
    ],
)

insights = Section(
    "AK. Insights (MD §6.2 P1→P5; PDF §3)",
    "Computed from real data only.",
    [
        r("IS-01", "P1", "MD §26.3 P1-10", "Basic insights from real data only (sales, orders, bookings, collections)", "insights", "NEW", S, "absent"),
        r("IS-02", "P5", "MD §26.2", "Advanced insights per role (owner, manager, accountant, marketer)", "insights", "NEW", S, "absent"),
        r("IS-03", "P4", "MD §16.6", "Supplier scorecard (private to buyer): on-time, fill rate, short-weight, price history with jump alerts", "insights", "NEW", S, "absent"),
    ],
)

back_office = Section(
    "AL. Expenses, procurement, recipes/BOM, trade network (MD §6.2, §16; PDF §16; P4)",
    "",
    [
        r("EX-01", "P4", "MD §6.2", "Expenses", "expenses", "NEW", S, "absent"),
        r("EX-02", "P4", "MD §6.2", "Petty cash", "expenses", "NEW", S, "absent"),
        r("EX-03", "P4", "MD §6.2 · §14.5", "Daily cash closing (cash book day)", "expenses", "NEW", S, "absent"),
        r("PC-01", "P4", "MD §6.2", "Suppliers", "procurement", "NEW", S, "absent"),
        r("PC-02", "P4", "MD §6.2", "Price agreements", "procurement", "NEW", S, "absent"),
        r("PC-03", "P4", "MD §6.2", "Requisitions (draft from demand/BOM/reorder)", "procurement", "NEW", S, "absent"),
        r("PC-04", "P4", "MD §16.4", "Purchase orders DRAFT→APPROVED (owner or auto under limit)→SENT→COUNTERED/ACKNOWLEDGED→DISPATCHED→RECEIVED→DISPUTED/BILLED→PAID", "procurement", "NEW", S, "absent"),
        r("PC-05", "P4", "MD §6.2", "Goods receipt with actual weights", "procurement", "NEW", S, "absent"),
        r("PC-06", "P4", "MD §6.2", "Supplier bills and payables", "procurement", "NEW", S, "absent"),
        r("PC-07", "P4", "MD §16.5", "Off-network supplier magic-link PO page (accept, change qty, pick slot) sent as WhatsApp template", "procurement", "NEW", S, "absent"),
        r("PC-08", "P4", "MD §16.8", "Counter-offer never changes the PO until buyer accepts", "procurement", "NEW", S, "absent"),
        r("RC-01", "P4", "MD §6.2", "Recipe/BOM components per offering with yield, wastage, unit conversions", "recipes", "NEW", S, "absent"),
        r("RC-02", "P4", "MD §6.2", "Production batches", "recipes", "NEW", S, "absent"),
        r("RC-03", "P4", "MD §6.2", "Consumption on sale", "recipes", "NEW", S, "absent"),
        r("RC-04", "P4", "MD §16.1", "Net requirement formula net = max(0, Σ q·r/y + s − h − o) rounded to pack size and MOQ; biryani fixture reproduces exactly", "recipes", "NEW", S, "absent"),
        r("RC-05", "P4", "MD §16.3", "Demand sources: confirmed future orders/pre-orders, bookings consuming stock, subscriptions at cutoff, forecast (avg last 4 same weekdays × festival multiplier), par levels", "recipes", "NEW", S, "absent"),
        r("RC-06", "P6", "MD §16.3", "ML forecasting after 6 months of data", "recipes", "FUTURE", F, "FUTURE by source"),
        r("TN-01", "P4", "MD §6.2", "ChitBridge entity binding and buyer/supplier relations", "trade-network", "NEW", S, "absent"),
        r("TN-02", "P4", "MD §16.5", "PO as chit (purchase_order keeps chit id); supplier on LOCAH gets a sales order in its own tenant", "trade-network", "NEW", A, "ChitBridge dependency gate (§16.5)"),
        r("TN-03", "P4", "MD §16.5", "Status updates via append-only state_log/HMAC webhooks update LOCAH's own copy; replay never advances twice", "trade-network", "NEW", A, "ChitBridge dependency gate"),
        r("TN-04", "P4", "MD §16.5", "Agreed price pinned to the catalogue version seen; disputes shown as outcome only", "trade-network", "NEW", A, "ChitBridge dependency gate"),
        r("TN-05", "P4", "MD §16.6", "Forward demand for suppliers (opt-in forecast sharing), standing orders, credit terms both ways", "trade-network", "NEW", S, "absent"),
        r("TN-06", "P4", "MD §16.7", "Privacy: suppliers never see buyer's customers; forecast sharing opt-in per supplier and withdrawable", "trade-network", "NEW", S, "absent"),
        r("TN-07", "P4", "MD §16.8", "Supplier-side tenant cannot query buyer's tenant under any role", "trade-network", "NEW", S, "absent"),
        r("TN-08", "P6", "MD §16.6", "Supplier discovery in Marketplace (P6); group buying FUTURE", "trade-network", "FUTURE", F, "P6/FUTURE by source"),
    ],
)

SECTIONS = [bookings, memberships, attendance, queue, tasks, kitchen, dispatch, workforce, quotes,
            projects, jobs, academics, documents, donations, insights, back_office]
