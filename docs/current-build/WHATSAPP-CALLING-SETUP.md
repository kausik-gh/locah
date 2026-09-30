# WhatsApp messaging & calling — setup guide

Status of this guide: written 2026-09-30 against the code at
`claude/phase-b-final-integration` and **Meta's documentation as fetched on
2026-09-30** (sources at the end). Meta changes these rules; re-check the
sources before activating production. No secrets appear here — only the
names of the settings that hold them.

LOCAH uses only the **official WhatsApp Business Platform (Cloud API, hosted
by Meta)**. No WhatsApp Web automation, unofficial libraries, QR-login or
personal-account sessions — ever.

---

## 1. What LOCAH has today (honest summary)

| Area | State |
| --- | --- |
| Internal automation (confirmations, reminders, renewals, queue, dispatch, invoices, waitlist offers, no-show follow-up, quote codes) | **Built and tested** through the Messaging service and the sandbox transport |
| Cloud API adapter (send template/text/interactive, submit templates, Embedded Signup code exchange, subscribe WABA webhooks, **register number with PIN**) | **Built**, request shapes tested against a mock of Graph. **Never exercised against Meta from this repository.** |
| Webhooks (messages, statuses, coexistence echoes, `calls`, `call_permission_reply`, `message_template_status_update`, `phone_number_quality_update`) | **Built**: signature-checked (X-Hub-Signature-256 / app secret), verify-token handshake, idempotent, tenant-routed by phone number ID or WABA ID |
| Embedded Signup in the owner's browser | **Built** (Workspace → WhatsApp → Connect with WhatsApp). **ACTIVATION_REQUIRED**: needs LOCAH's Meta app |
| Meta App Review / Tech Provider onboarding | **ACTIVATION_REQUIRED** (a business action with Meta, not code) |
| WhatsApp Calling — signalling contract, settings, permissions, call records | **Built**, fixture/protocol tested |
| WhatsApp Calling — actually answering a call | **ACTIVATION_REQUIRED**: needs a WebRTC call runtime (see §5) |
| Phone line (PSTN/SIP) | **ACTIVATION_REQUIRED**: provider-neutral boundary only; no vendor chosen |
| AI receptionist on calls | **Not built** — deliberately, until a real call transport exists (§6) |

The owner sees the true state on **Workspace → WhatsApp → Connection**:
`ACTIVATION_REQUIRED`, `META_REVIEW_REQUIRED`, `NOT_CONNECTED`,
`SETUP_REQUIRED`, `PHONE_VERIFICATION_REQUIRED`, `TEMPLATE_SETUP_REQUIRED`,
`ACTIVE`, `DEGRADED`, `DISCONNECTED` — with a checklist of what is actually
true — and for calls `CALLING_NOT_AVAILABLE`, `CALLING_ACTIVATION_REQUIRED`,
`CALLING_ELIGIBLE`, `CALLING_SETUP_REQUIRED`, `CALLING_ACTIVE`,
`CALLING_DEGRADED`. A sandbox number is always labelled **TEST / SANDBOX**
and never ticks the Meta steps. (Code: `python/core/platform_core/messaging/connection.py`.)

---

## 2. Settings (names only)

| Setting | Holds | Where used |
| --- | --- | --- |
| `META_APP_ID` | LOCAH's Meta app ID (public) | Embedded Signup, token exchange |
| `META_APP_SECRET` | App secret | Code exchange; **webhook signature check** |
| `META_GRAPH_VERSION` | Graph API version, e.g. the current `vNN.0` | Every Graph call — the only place the version lives |
| `META_ES_CONFIG_ID` | Embedded Signup configuration ID | Owner's browser flow |
| `META_ADVANCED_ACCESS` | `1` once Meta has approved App Review for the WhatsApp permissions | Moves owners out of `META_REVIEW_REQUIRED` |
| `WHATSAPP_VERIFY_TOKEN` | Webhook verify token | `GET /v1/webhooks/whatsapp` handshake |
| `PAYMENT_CREDENTIAL_KEY` (Fernet) | Key that encrypts each business's WhatsApp access token at rest (falls back to a key derived from the JWT secret) | `messaging_channels.encrypted_token` |
| `MESSAGING_SANDBOX` | `1` on local/test stacks only (ignored in production) | Test number |
| `WHATSAPP_CALLING_RUNTIME` | Name of the WebRTC call runtime, once one exists | Calling states |
| `TELEPHONY_PROVIDER` | PSTN adapter name (`fixture` only on dev stacks today) | Phone line state |

Per business, LOCAH stores: WABA ID, phone number ID, display number and
name, quality rating, messaging limit tier, **encrypted** business token,
registration time/error, calling status, last webhook time. Nothing else;
the two-step PIN is never stored or logged.

Until `META_APP_SECRET` and `WHATSAPP_VERIFY_TOKEN` are set, both webhook
routes answer 404 and nothing is accepted.

---

## 3. Developer / demo setup

**What works locally with no Meta account:**

1. Local stack (`tools/acceptance/README.md`): `MESSAGING_SANDBOX=1` is set by
   `tools/acceptance/stack/api.sh` and `worker.sh`.
2. Workspace → WhatsApp → *Connect a test number* (any `+91…` number). State
   becomes `ACTIVE` with the **TEST / SANDBOX** label; templates are
   "approved" instantly by the sandbox (Meta would review them).
3. Every automatic message is recorded in `messaging_messages` and shows in
   the inbox; nothing leaves the machine.
4. Simulate a customer: `POST /v1/platform/businesses/{id}/messaging/sandbox/inbound`
   (a message) or `…/messaging/sandbox/call` (a WhatsApp call ringing /
   ending) — both go through the same webhook code path as a real delivery.

**What is simulated:** delivery, template approval, calls (no audio).
**What is real:** every rule — templates-only outside the 24-hour window,
marketing consent, quiet hours, metering, idempotency, per-business routing.

**With a Meta developer test number** (optional, before App Review): create a
Meta app with the WhatsApp product, use Meta's test WABA and test number,
set the settings in §2 on a non-production stack, expose
`/v1/webhooks/whatsapp` over HTTPS, subscribe the webhook fields `messages`,
`message_template_status_update`, `phone_number_quality_update` (and `calls`
for calling), and connect through Embedded Signup as one of the app's test
users. This has **not** been done from this repository yet.

---

## 4. Production merchant setup

### 4.1 One-time, for LOCAH (the Tech Provider)

1. **Meta business portfolio** for LOCAH, **Business Verification** completed.
2. **Meta app** (Business type) with the WhatsApp product; register as a
   **Tech Provider** (or work through a Solution Partner). Tech Providers:
   each business adds its own payment method in WhatsApp Manager; Solution
   Partners share a credit line (needs `business_management` too).
3. Permissions with **Advanced Access** via App Review:
   `whatsapp_business_management` (templates, account settings) and
   `whatsapp_business_messaging` (phone number settings, sending/receiving).
   Meta: *"You will not be able to onboard business customers until your app
   has been approved for advanced access for each of the permissions it
   requires."* Onboarding is limited (10 new customers/week, 200 after
   Business Verification, App Review and Access Verification).
   → set `META_ADVANCED_ACCESS=1` only after approval.
4. **Embedded Signup configuration** → `META_ES_CONFIG_ID`.
5. **Webhook**: callback `https://<api>/v1/webhooks/whatsapp`, verify token →
   `WHATSAPP_VERIFY_TOKEN`; subscribe `messages`,
   `message_template_status_update`, `phone_number_quality_update`, and
   `calls` when calling is used.
6. Set the §2 settings on the production API and worker.

### 4.2 Per business (the owner, in LOCAH)

1. Workspace → WhatsApp → **Connect with WhatsApp** → Meta's Embedded Signup
   opens; the owner signs in to Meta, picks/creates the business portfolio and
   WABA, and picks/verifies the number (or keeps it on the WhatsApp Business
   app — *coexistence*).
2. LOCAH's server finishes it (Meta's documented order): exchange the code for
   a business token → subscribe LOCAH's app to the WABA's webhooks → read the
   number → **register the number** (`POST /{phone-number-id}/register` with a
   6-digit two-step PIN). Coexistence numbers are already registered.
   If the PIN is not given or is wrong, the state is
   `PHONE_VERIFICATION_REQUIRED` and the owner enters it on the Connection
   panel (sent to Meta only).
3. LOCAH submits its message templates (English, Tamil, Hindi) for review.
   Until one utility template is approved the state is
   `TEMPLATE_SETUP_REQUIRED`; Meta's decisions arrive by webhook.
4. The owner **adds a payment method in WhatsApp Manager** (required by Meta
   for Tech Provider customers).
5. The owner sends a **test message** from the Connection panel.
6. State `ACTIVE`. `DEGRADED` if a send fails or Meta flags quality;
   `DISCONNECTED` after Disconnect (automatic messages stop).

### 4.3 Message categories and the 24-hour window

* A customer's message opens the customer-service window; inside it LOCAH may
  reply freely (inbox, WhatsApp journeys). Outside it, **only approved
  templates** may be sent — enforced in `MessagingService.reply` / `bot_*`.
* **Utility**: booking confirmation/reminder, queue turn soon, dispatch
  status, payment/invoice reminders, membership renewal, document request
  (today the owner shares that link; LOCAH does not send it automatically),
  order state, waitlist offer, "we missed you".
* **Authentication**: the quote-acceptance one-time code — sent in Meta's
  **preset authentication format** (Meta's wording, code in body + copy-code
  button, 10-minute expiry). Custom text is not allowed for codes.
* **Marketing**: campaigns, offers, win-back — sent only with an explicit
  WhatsApp marketing opt-in; STOP withdraws it.
* **Meta decides the category at approval** (since 9 Apr 2025 a utility
  template Meta considers marketing is approved *as marketing*). LOCAH stores
  Meta's category per template and language and applies marketing consent
  when Meta says marketing — never a utility template to dodge policy.
* Quiet hours (21:00–08:00 business time) hold customer-facing automation;
  owners switch each automation in Automations; the monthly message meter
  stops at the owner's cap.

---

## 5. WhatsApp Calling (Business Calling API)

**What Meta provides (2026-09-30):** user-initiated calls wherever Cloud API
runs; business-initiated calls in supported countries (not US, Canada, Egypt,
Vietnam, Nigeria). Requirements: number on Cloud API (not the Business app),
app subscribed to the `calls` webhook field, `whatsapp_business_messaging`,
and a **messaging limit of at least 2,000** in production. Signalling is
Graph API + webhooks; **media is WebRTC (ICE + DTLS-SRTP, OPUS)** between Meta
and whoever answers. The business has about 30–60 s to answer a ringing call.

**What LOCAH implements:**

* Settings: `POST /{phone-number-id}/settings` with `calling.status`,
  `call_icon_visibility`, `callback_permission_status` and `call_hours`
  built from the location's opening hours (max 2 spans/day, time zone).
  Owner switch on the Connection panel — only when the state allows.
* Calls: the `calls` webhook (`connect` / `terminate`) creates one
  `calls_sessions` record per call — business, channel, direction, Meta call
  ID, caller/callee, start/answer/end, state, handler (none/human/ai_employee),
  hand-offs, what it led to, within business hours — **no SDP, media or
  tokens**. Replays create nothing new.
* Actions: `pre_accept` / `accept` (with the runtime's SDP answer) / `reject`
  / `terminate` bodies per Meta's docs.
* **Permission before any business-initiated call** (`assert_may_call`):
  calling must be `CALLING_ACTIVE` and the customer must have an unexpired
  permission — from `call_permission_reply` (temporary 7 days or permanent),
  or the temporary one Meta grants when the customer calls in (callback
  enabled). Requests go only inside the 24-hour window as the
  `call_permission_request` interactive message, at most **1 per day and 2
  per 7 days** per customer. **No unsolicited calls.**

**Why it is `CALLING_ACTIVATION_REQUIRED` today:** LOCAH has no WebRTC call
runtime — nothing that can produce an SDP answer and carry the audio to a
staff softphone or an AI voice agent. Without it a call is recorded, the
team is alerted ("call the customer back"), and nobody pretends it was
answered. To activate:

1. Build or choose the call runtime (a WebRTC media server / SFU, or Meta's
   SIP option to bridge into a telephony provider) and a staff answering
   surface; set `WHATSAPP_CALLING_RUNTIME`.
2. Ensure the number's messaging limit is ≥ 2,000 and it is on Cloud API.
3. Subscribe the `calls` webhook field on LOCAH's app.
4. Owner switches calls on (Connection panel) → `CALLING_ACTIVE`.
5. For business-initiated calls outside a chat window: create an approved
   template with a call-permission button (not in LOCAH's library yet).

---

## 6. Phone line (PSTN) and the AI receptionist

* WhatsApp calling and ordinary phone calls are **different channels**. PSTN
  needs a telephony provider (numbers, SIP/WebRTC media, DTMF, recordings).
  The sources name none, so LOCAH commits to none: `calling/voice.py` defines
  a provider-neutral `VoiceProvider` (place call, answer/route, transfer,
  hang up, parse webhook → `CallEvent`); calls land in the same
  `calls_sessions` record (`channel='pstn'`). State: **ACTIVATION_REQUIRED —
  choosing a provider is a founder decision.**
* **AI receptionist**: not built, on purpose, until a real transport exists.
  When built it is another actor (`actor_type=ai_employee`) using only real
  service tools and its own permissions — look up offerings, real
  availability (the booking engine's own checks), create a booking or lead,
  send a payment/booking link, take a message, hand off to a person (recorded
  in `calls_sessions.handoffs`). It may not invent availability or prices,
  change money, grant permissions, ignore consent or write to the database
  directly.

---

## 7. Activation checklist (ACTIVATION_REQUIRED items)

- [ ] LOCAH Meta business portfolio + Business Verification
- [ ] Meta app, Tech Provider (or Solution Partner) enrolment
- [ ] App Review: advanced access for `whatsapp_business_management`,
      `whatsapp_business_messaging` → `META_ADVANCED_ACCESS=1`
- [ ] Embedded Signup configuration → `META_ES_CONFIG_ID`
- [ ] Production settings in §2 on API and worker; HTTPS webhook subscribed
- [ ] First real merchant connected end to end (signup → register → templates
      approved → payment method → test message) — **not yet done**
- [ ] Native-speaker review of Tamil and Hindi template wording (VB-22)
- [ ] Calling: call runtime, `calls` webhook subscription, ≥ 2,000 limit
- [ ] Call-permission template (for requests outside the chat window)
- [ ] PSTN provider choice and adapter

## Sources (fetched 2026-09-30)

- Embedded Signup overview — developers.facebook.com/docs/whatsapp/embedded-signup
- Onboarding customers as a Tech Provider — developers.facebook.com/docs/whatsapp/embedded-signup/onboarding-customers-as-a-tech-provider
- Calling API overview — developers.facebook.com/docs/whatsapp/cloud-api/calling
- Call settings — developers.facebook.com/docs/whatsapp/cloud-api/calling/call-settings
- User-initiated calls — developers.facebook.com/docs/whatsapp/cloud-api/calling/user-initiated-calls
- User call permissions — developers.facebook.com/docs/whatsapp/cloud-api/calling/user-call-permissions
- Webhooks, getting started (signatures, verification) — developers.facebook.com/docs/graph-api/webhooks/getting-started
- Template categorization — developers.facebook.com/documentation/business-messaging/whatsapp/templates/template-categorization
- Copy-code authentication templates — developers.facebook.com/documentation/business-messaging/whatsapp/templates/authentication-templates/copy-code-button-authentication-templates
- message_template_status_update webhook — developers.facebook.com/documentation/business-messaging/whatsapp/webhooks/reference/message_template_status_update
