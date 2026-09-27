"""AI employees, receptionist, automation ladders and connectors
(MD §8, §9, §11, §24; PDF §6, §8)."""

from __future__ import annotations

from tools.ledger.model import Section, r

S, P, C, A, F = "NOT_STARTED", "PARTIAL", "COMPLETE", "ACTIVATION_REQUIRED", "FUTURE"

automation = Section(
    "AM. Automations (PDF §6; MD §2 r11, §24 #4)",
    "One generic ladder engine on the outbox/jobs kernel; every automation idempotent, visible, auditable, switchable off; no secret money movement.",
    [
        r("AU-01", "P2", "PDF §6", "Membership nearing expiry → reminder + payment link; stops on payment, pause, or owner disable", "automation", "NEW", S, "absent"),
        r("AU-02", "P2", "PDF §6", "Booking tomorrow → confirmation/reminder; stops on cancel/reschedule", "automation", "NEW", S, "absent"),
        r("AU-03", "P1", "PDF §6", "Stock below threshold → alert or draft purchase request; stops when restored", "automation", "NEW", S, "absent"),
        r("AU-04", "P1", "PDF §6", "Invoice/khata overdue → statement/payment link; stops when paid or paused", "automation", "NEW", S, "absent"),
        r("AU-05", "P2", "PDF §6", "Order picked up → tracking update; stops delivered/failed", "automation", "NEW", S, "absent"),
        r("AU-06", "P1", "PDF §6 · MD §17.1", "Completed order/booking → review request; stops if reviewed or opted out", "automation", "NEW", S, "absent"),
        r("AU-07", "P2", "PDF §6", "Lead follow-up due → task/nudge; stops when lead moves or closes", "automation", "NEW", S, "absent"),
        r("AU-08", "P1", "PDF §6", "Licence expiry approaching → notify owner and create task; stops when renewal date updated", "automation", "NEW", S, "absent"),
        r("AU-09", "P1", "MD §2 r11", "Owner activity log shows every automation step with delivery status; per-automation off switch", "automation", "NEW", S, "absent"),
        r("AU-10", "P5", "MD §21.4", "Recall reminders (6-month dental), vaccination due, seasonal service reminders (AC before summer)", "automation", "NEW", S, "absent"),
    ],
)

ai = Section(
    "AN. AI employees (MD §8; PDF §6)",
    "Tool-using agents with a role, allowlist, tiers, budget and audit; they call the same services humans call.",
    [
        r("AI-01", "P3", "MD §8.1", "WhatsApp Manager: FAQs, carts from catalogue, free slots, list-price payment links, order status; asks for discounts/custom prices/refunds/off-catalogue", "ai-employees", "NEW", S, "P1 structured journeys first (MS-*)"),
        r("AI-02", "P3", "MD §8.1 · §11", "Receptionist (voice): answers, books, reschedules, messages, confirmations; hands medical/complaints/refunds to a human", "ai-employees", "NEW", S, "absent"),
        r("AI-03", "P3", "MD §8.1", "Appointment Manager: waitlist fill, reminders, no-show follow-ups; asks for overbooking/fee waivers", "ai-employees", "NEW", S, "absent"),
        r("AI-04", "P3", "MD §8.1", "Collections Assistant: renewal/dues reminders on owner's schedule, payment links; asks for waivers/extensions/credit-limit changes (P2 rules, P3 AI)", "ai-employees", "NEW", S, "absent"),
        r("AI-05", "P3", "MD §8.1", "Delivery Coordinator: suggests/auto-assigns within rules, ETA updates, reschedules failed drops; asks for paid courier", "ai-employees", "NEW", S, "absent"),
        r("AI-06", "P3", "MD §8.1", "Inventory Manager: low-stock alerts, wastage anomalies, reorder suggestions; asks for every stock adjustment", "ai-employees", "NEW", S, "absent"),
        r("AI-07", "P4", "MD §8.1", "Procurement Planner: drafts requisitions from demand and BOM; asks before sending any PO (auto-send only under owner limit to approved supplier)", "ai-employees", "NEW", S, "absent"),
        r("AI-08", "P4", "MD §8.1", "Bookkeeper: bill photos into drafts, matches payments, flags sync errors; asks before posting to books/Tally", "ai-employees", "NEW", S, "absent"),
        r("AI-09", "P3", "MD §8.1", "Sales Executive: qualifies leads, schedules site visits, nudges, quote drafts; asks before sending a quote or price change", "ai-employees", "NEW", S, "absent"),
        r("AI-10", "P3", "MD §8.1", "Marketing Manager: audience/campaign/creative drafts, weekly summary; asks for any spend/broadcast", "ai-employees", "NEW", S, "absent"),
        r("AI-11", "P3", "MD §8.1", "Review Responder: drafts; auto-posts 4–5 star if enabled; asks for 1–3 star and reports", "ai-employees", "NEW", S, "absent"),
        r("AI-12", "P0", "MD §8.1", "Website Editor: rewrites a section's content fields; asks for publishing", "ai-employees", "EXISTING", C,
          "talk_to_website edits as structured state; publish is owner action", test="✓ test_website_edits"),
        r("AI-13", "P3", "MD §8.2", "Autonomy tiers T0 read, T1 draft, T2 act within limits, T3 approval always (spend, refunds, discounts above limit, deletions, POs above limit)", "ai-employees", "NEW", S, "absent"),
        r("AI-14", "P3", "MD §8.3", "Identity: actor_type=ai_employee + employee id + business_id; RLS and authorization unchanged", "ai-employees", "NEW", S, "absent"),
        r("AI-15", "P3", "MD §8.3", "Audit: ai_action row per action (tool, inputs, result, reason, conversation, tokens, cost) shown as a readable feed", "ai-employees", "NEW", S, "absent"),
        r("AI-16", "P3", "MD §8.3", "Limits live in services (max discount, max PO, hours, channels); a prompt cannot raise them", "ai-employees", "NEW", S, "absent"),
        r("AI-17", "P3", "MD §8.3", "Injection-safe: customer text is data; no tool changes prices, permissions, payouts or AI limits", "ai-employees", "NEW", S, "absent"),
        r("AI-18", "P3", "MD §8.3", "Kill switch per employee + global pause; paused → buttons and human handoff", "ai-employees", "NEW", S, "absent"),
        r("AI-19", "P3", "MD §8.3", "Discloses itself (voice opening line; chat when asked); replies in customer's language (EN/TA/HI, code-mixed)", "ai-employees", "NEW", S, "absent"),
        r("AI-20", "P3", "MD §8.4", "Cost ladder: buttons/Flows → deterministic intent → small model extraction → larger model generation", "ai-employees", "NEW", S, "absent"),
        r("AI-21", "P3", "MD §8.4", "Monthly AI credit meter with hard cap; at cap flows drop to steps 1–2 and owner is told; provider-agnostic model interface", "ai-employees", "EXTEND", P, "provider-agnostic AI interface + replay exist (Phase A); no per-business cap"),
        r("AI-22", "P3", "MD §6.2", "One entitlement per AI employee; approvals ('Needs you now'); meters", "ai-employees", "NEW", S, "absent"),
        r("AI-23", "P3", "MD §26.2", "Free-text business-task AI on WhatsApp (never a general-purpose chatbot)", "ai-employees", "NEW", S, "absent"),
    ],
)

receptionist = Section(
    "AO. AI Receptionist (MD §11; PDF §8)",
    "",
    [
        r("RC-10", "P3", "MD §11.2", "Tool layer exactly: business_info, list_services, check_availability, hold_slot, create_booking, reschedule, cancel, order_status, capture_lead, take_message, transfer_to_human, send_whatsapp", "ai-employees", "NEW", S, "absent"),
        r("RC-11", "P3", "MD §11.3", "Per-business behaviour: clinic, hotel, salon, restaurant, real estate, education, home services/garage, gym (and handoff rules)", "ai-employees", "NEW", S, "absent"),
        r("RC-12", "P3", "MD §11.4", "Healthcare: never medical advice/triage; emergency phrases → '108 or 112' message + immediate transfer attempt", "ai-employees", "NEW", S, "absent"),
        r("RC-13", "P3", "MD §11.4", "Disclosure + recording announcement; no payment details by voice (links on WhatsApp); holds expire (15 min)", "ai-employees", "NEW", S, "absent"),
        r("RC-14", "P3", "MD §11.4", "Fallback when AI/provider down: voicemail, 'we'll call you back' WhatsApp, owner callback task", "ai-employees", "NEW", S, "absent"),
        r("RC-15", "P3", "MD §11.5", "Workspace Calls page (outcome, 2-line summary, transcript, Call back); setup (hours, forwarding steps, transfer number, T2 limits, voice, languages); knowledge from website/offerings/policies/FAQ", "ai-employees", "NEW", S, "absent"),
        r("RC-16", "P3", "MD §11.5", "Transcripts retained 90 days default, owner-configurable, card-like numbers redacted", "ai-employees", "NEW", S, "absent"),
        r("RC-17", "P3", "MD §11.6", "Minutes metered per business with monthly cap; at cap → voicemail mode", "ai-employees", "NEW", S, "absent"),
        r("RC-18", "P3", "MD §11.6", "Tests: slot lock (two parallel calls cannot take one slot); red-team medical fixtures never advise; AI bookings show actor_type=ai_employee linked to call", "ai-employees", "NEW", S, "absent"),
        r("RC-19", "P3", "MD §11.1 · §9.1", "Forwarded phone calls to a LOCAH virtual number with media streaming", "ai-employees", "NEW", A, "telephony + STT/TTS providers (§28.1)"),
        r("RC-20", "P3", "MD §11.1 · §9.1", "WhatsApp calls via Calling API (WebRTC/SIP)", "ai-employees", "NEW", A, "Meta Calling prerequisites"),
    ],
)

connectors = Section(
    "AP. Connectors and integrations (MD §9; PDF §11)",
    "Every adapter declares data families, owner, direction; credentials in secrets store; sync_run per run; idempotent via sync_mapping; failures in 'Needs you now'.",
    [
        r("CN-01", "P4", "MD §9.2", "Adapter contract: data families + owner + direction (pull/push/both owner-wins)", "connectors", "NEW", S, "absent"),
        r("CN-02", "P4", "MD §9.2", "Credentials in secrets store, never plain tables", "connectors", "EXTEND", P, "platform_core.secrets exists for env secrets; merchant credentials encrypted (crypto.py)"),
        r("CN-03", "P4", "MD §9.2", "Every run writes sync_run with counts and errors", "connectors", "NEW", S, "absent"),
        r("CN-04", "P4", "MD §9.2", "Idempotent writes via external id mapping (sync_mapping)", "connectors", "NEW", S, "absent"),
        r("CN-05", "P4", "MD §9.2", "Failure in 'Needs you now' in plain words", "connectors", "NEW", S, "absent"),
        r("CN-06", "P1", "MD §9.1", "WhatsApp Business Platform (Cloud API)", "connectors", "NEW", A, "Meta Tech Provider/BSP decision + app"),
        r("CN-07", "P3", "MD §9.1", "WhatsApp Business Calling API", "connectors", "NEW", A, "Meta"),
        r("CN-08", "P3", "MD §9.1", "Telephony (forwarded calls)", "connectors", "NEW", A, "provider choice open"),
        r("CN-09", "P1", "MD §9.1 · PDF §12", "Payments provider (Cashfree per PDF; Razorpay existing, frozen)", "connectors", "EXTEND", A, "Cashfree pass later"),
        r("CN-10", "P2", "MD §9.1", "Google Maps Platform: Maps URLs (no key), Routes API ETA, Places Autocomplete", "connectors", "NEW", P, "Maps URLs need no key (buildable); Routes/Places need key"),
        r("CN-11", "P2", "MD §9.1", "Shipping + hyperlocal partners (aggregator API)", "connectors", "NEW", A, "partner decision"),
        r("CN-12", "P4", "MD §9.1", "TallyPrime (see TL-*)", "connectors", "NEW", S, "absent"),
        r("CN-13", "P4", "MD §9.1", "Other accounting/billing: Zoho Books, Vyapar, Busy, Marg (CSV/Excel first)", "connectors", "NEW", S, "absent"),
        r("CN-14", "P4", "MD §9.1", "GST IRP e-invoice + e-way bill via GSP", "connectors", "NEW", A, "GSP decision"),
        r("CN-15", "P3", "MD §9.1", "Meta Marketing API + Conversions API + Lead Ads", "connectors", "NEW", A, "Meta app review"),
        r("CN-16", "P3", "MD §9.1", "Google Business Profile", "connectors", "NEW", A, "Google approval"),
        r("CN-17", "P3", "MD §9.1", "Google Calendar provider busy/free sync", "connectors", "NEW", A, "OAuth app"),
        r("CN-18", "P1", "MD §9.1", "Email + SMS (receipts, OTP, fallback alerts)", "connectors", "EXTEND", P, "auth email templates exist; SMS needs DLT"),
        r("CN-19", "P4", "MD §9.1 · §16", "ChitBridge (REST + HMAC + Idempotency-Key; LOCAH as connector actor)", "connectors", "NEW", A, "dependency gate + API owner decision"),
        r("CN-20", "P1", "MD §9.1", "Hardware: scanners (keyboard/camera), ESC/POS receipt & kitchen printers, drawer kick, label scales — driverless on Android", "connectors", "NEW", S, "absent"),
        r("CN-21", "P6", "MD §9.1", "Access control, card terminals", "connectors", "FUTURE", F, "FUTURE by source"),
        r("CN-22", "P6", "MD §9.1", "ONDC, OTA channel managers, food aggregators", "connectors", "FUTURE", F, "FUTURE by source"),
        r("CN-23", "P1", "MD §9.3", "Meter counts every WhatsApp message so pricing changes are absorbed", "connectors", "NEW", S, "absent"),
    ],
)

SECTIONS = [automation, ai, receptionist, connectors]
