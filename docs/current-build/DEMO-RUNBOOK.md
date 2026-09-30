# LOCAH demo runbook

One product, shown end to end in 8–10 minutes: an owner describes the business,
LOCAH understands it, recommends modules, builds a website and a Workspace; a
customer acts on the website; staff handle it; the system records, automates
and reports. Everything shown is the real product on the deployed stack. What
is sandboxed is **said out loud** (see "Say it honestly").

URLs are in `FINAL-RELEASE-HANDOFF.md` (RAILWAY DEPLOYMENT URLS). Below:
`WEB` = public web, `WS` = Workspace, `API` = API.

## Before the demo (15 minutes, once)

1. `API/health/ready` answers `{"status":"ok","database":"connected"}`.
2. Sign in to `WEB` and to `WS` with the demo owner account. On Railway's
   generated domains each surface keeps its own session (a browser cannot share
   one cookie across `*.up.railway.app` hosts) — sign in on both tabs before
   starting. With a custom platform domain this becomes one sign-in.
3. Prepared businesses (idempotent; run again any time — it skips what exists):

   ```bash
   LOCAH_API=<API> LOCAH_DEMO_TOKEN=<demo owner access token> uv run python tools/demo/seed.py --yes
   ```

   Creates, through the public API only (no database access, no service key):
   - **Demo · Iron Temple Strength** (gym) — plans, members (one paid, one
     not), personal training, hours, AI receptionist;
   - **Demo · Saffron Table** (restaurant) — menu, a recipe that takes paneer
     off stock, low-stock threshold, table bookings;
   - **Demo · Cool Fix Services** (field service) — customer, technician, an
     enquiry, a quote sent for acceptance.

   Modules the plan does not allow are reported, never forced (on a fresh
   plan the gym's Loyalty reports `ENTITLEMENT_REQUIRED`). WhatsApp gets the
   TEST / SANDBOX number only on a local/development stack (`MESSAGING_SANDBOX=1`
   and a development `ENVIRONMENT`); on Railway the step is skipped and reported.
   Local stack: `LOCAH_API=http://localhost:8010 uv run python tools/demo/seed.py
   --session acceptance-out/session.json --yes` (see `tools/acceptance/README.md`).
4. Open the three prepared businesses once in `WS` so first loads are warm.
5. Gemini is live only if the Google project has credit. A quick check:
   start a throwaway business and send one sentence in Talk to LOCAH. If the
   API log shows `ai.gemini.billing_refused` (HTTP 402), top up the Google
   project — do not debug website code. Without Gemini the product still
   works (LOCAH asks its own questions, the site is composed deterministically
   and text-led), but say so.

## The main flow (8–10 minutes)

Pick the story that fits the audience: **Gym**, **Restaurant** or
**Industrial / field service**. Steps 1–11 are done live with a new business;
steps 12–20 use the matching prepared business so nothing waits on timing.

| # | Show | Where | What to say / point at |
|---|---|---|---|
| 1 | Sign up | `WEB/signup` | A real Supabase account. |
| 2 | Create business | `WEB/start` | Name optional — LOCAH can ask later. |
| 3 | Talk to LOCAH | `WEB/start/<id>/interview` | Type or speak naturally: "I run a strength gym in Anna Nagar, memberships and personal training, open 6 to 10". |
| 4 | Adaptive questions | same | The next question depends on the answer; it never re-asks what was said. Tamil/Hindi work too. |
| 5 | Understanding | same (summary card) | What LOCAH understood: trade, offerings, hours, prices only where a number was said. Correct one thing live. |
| 6 | Module recommendations | `WEB/start/<id>/modules` | **Essential / Recommended / Optional**, each with a plain "why". |
| 7 | Enable modules | same | Accept the recommended ones, reject one to show the owner decides. |
| 8 | Workspace adapts | `WS/b/<id>` | The navigation now has exactly those modules. |
| 9 | Build website | `WEB/start/<id>/website` | One Build: a MediaPlan and a creative direction chosen for this business, not a template. |
| 10 | Real Gemini pictures | preview, then `WS/b/<id>/website` | With no uploads, the hero and story pictures are Gemini drafts, labelled "Draft picture by LOCAH". Show *Generate a new picture*, *Keep*, *Replace with my photo*. Factual slots (a builder's projects, a photographer's work) are never drawn — only uploaded. |
| 11 | Desktop and phone | `WEB/<slug>` at full width and at phone width | Publish, then show both. |
| 12 | Customer action | prepared business's site | Gym: join / book a trial on `/<slug>/book`. Restaurant: order on `/<slug>/checkout` or book a table. Field service: request a quote on `/<slug>/enquire`. |
| 13 | The Workspace record | `WS/b/<id>/bookings` · `/orders` · `/leads` | The same record, immediately. |
| 14 | Staff handling | Restaurant `WS/b/<id>/kitchen` (KDS) · gym `/attendance` (check-in by card code) · field `/jobs` (technician) | Accept → cooking → ready; or check the member in (an unpaid member is refused with Memberships' reason). |
| 15 | Automation trigger | the action in 12–14 | Booking confirmation / order update goes out. |
| 16 | Automation Activity | `WS/b/<id>/settings/automations` | Each automation says where it lands, last run, next run, and the log of what was really sent. |
| 17 | WhatsApp, honestly | `WS/b/<id>/whatsapp` and `/inbox` | On the deployed stack WhatsApp says **activation required** — no Meta number is connected, and the sandbox is deliberately off outside development. Show the connection checklist and the automations that will use it. The sandbox conversation (number labelled **TEST / SANDBOX**) is shown from a local stack: "how much is personal training?" → the AI Receptionist answers with the catalogue price; "give me 40% discount" → a person. |
| 18 | Payment / inventory consequence | Restaurant `WS/b/<id>/inventory` · `/payments` | The recipe took the paneer off stock once; a payment request link and its status. |
| 19 | My Activity (customer) | `WEB/activity` | The customer's own bookings, orders and bills across businesses. |
| 20 | Insights / AI staff | `WS/b/<id>/insights` · `/ai-employees` | AI staff: Receptionist, Collections, Procurement — autonomy tier, allowed tools, kill switch, "Needs your approval", every action recorded. A purchase order is never sent without the owner. |

## The three prepared flows (steps 12–20)

**Gym — Demo · Iron Temple Strength**
- Site: `/book` for a trial or PT session; the booking shows in `WS › Bookings`.
- Door: `WS › Attendance` — the paid member's card code checks in; the unpaid
  member is refused with the membership reason; nothing is recorded for them.
- Renewal ladder: `WS › Settings › Automations` (renewal reminders, quiet hours,
  stops on payment).
- WhatsApp sandbox: the Receptionist answers price / hours / "do you have yoga?"
  from records; discounts and refunds go to a person.

**Restaurant — Demo · Saffron Table**
- Site: order from the menu at `/checkout`, or book a table (party size).
- Kitchen: `WS › Kitchen` — one KOT per order; accept → cooking → ready.
- Inventory: the recipe deducts paneer once (worker); low stock → alert, and a
  **draft** requisition only if the owner switched that on (never a PO).
- Customer: `/track/<order>` and My Activity.

**Industrial / field service — Demo · Cool Fix Services**
- Site: `/enquire` → a lead in `WS › Leads`.
- Quote: the prepared quote is sent for acceptance; accepted → a project /
  job; technician assigned in `WS › Jobs`; dispatch message to the customer.
- Collections: an overdue bill gets one reminder with its own pay link; it
  stops when paid.

Optional (if asked): Education (Academics: teacher, roster, attendance), NGO
(Donations), Hotel (stay bookings by date range) — each is a business created
live in step 2 with its own category; do not promise depth beyond what the
Workspace shows.

## Say it honestly

- **WhatsApp**: on the deployed stack, activation required (no Meta number).
  The sandbox (TEST / SANDBOX, messages recorded, never delivered) runs only
  on a local/development stack — never switch a deployed service to a
  development `ENVIRONMENT` to get it. Meta production number, App Review and
  Embedded Signup are ACTIVATION_REQUIRED.
- **Calls**: call records, permission rules and staff alerts exist; live call
  audio is ACTIVATION_REQUIRED. There is no AI phone call.
- **Online payments**: Cashfree live merchant collection is
  ACTIVATION_REQUIRED; the demo shows payment requests, pay-at-business and the
  ledger.
- **Tally**: connector foundation only; ACTIVATION_REQUIRED.
- **Pictures**: Gemini drafts are illustrative and labelled as drafts; the
  owner's own photo always wins.
- **Payroll**: not built (future).

## If something goes wrong

| Symptom | Do |
|---|---|
| Talk to LOCAH answers generically / site has no pictures | Check API/worker logs for `ai.gemini.billing_refused` (402) → Google billing; `no_image_provider_key` → `GEMINI_API_KEY` missing on the **worker**. Carry on — the deterministic path is the product's own fallback. |
| Website build never finishes | The worker is down: `locah-worker` logs must show `worker.polling`. |
| Workspace says signed out | Sign in on the Workspace tab (separate cookie on Railway domains). |
| A prepared business is missing | Re-run the seed; it only adds what is missing. |
