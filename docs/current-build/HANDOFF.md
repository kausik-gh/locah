# Handoff — Phase B (Business OS), canonical resume point

Read first: `CLAUDE.md`, both canonical sources (`Documentations/LOCAH — Business
Capability Universe.md`, `Documentations/LOCAH_Business_OS_Guide.pdf` — read in
full), this file, the generated ledger
(`docs/current-build/business-os-implementation-ledger.md`, rendered from
`tools/ledger/rows_*.py` + `tools/ledger/progress.py`), and
`docs/current-build/specialization-matrix.md`.

Authority: founder instructions → PDF (Cashfree is the payment direction) → MD
→ accepted implementation → repository. FUTURE/P6 stays FUTURE.

## Where things stand

Branch `main`. Packets done, newest last:

| Packet | Commit | Proof |
| --- | --- | --- |
| P1-01 … P1-09B | see git log | per-packet tests + browser flows (history in git) |
| P1-10A stock depth | cb8ecc3 | test_stock_depth (19) + browser p1_10a_stock 20/20, p1_10a_counter_serials 8/8 |
| P1-10B one customer identity | 4eea4b4 | test_customer_identity (3) + browser p1_10b_identity 14/14; suite 1048 |
| P1-10C module-aware website + Marketplace | 366ad71 | test_module_aware_site (11) + browser p1_10c_site 21/21; suite 1059 |
| P1-10D1 collect what is due (payments) | see git log ("feat(p1-10d1)… browser-verified") | test_payment_collect (15) + browser p1_10d1_payments 83/83 (Playwright Chromium, desktop + 390 px); suite 1073 |
| P1-10D2a dated pre-orders | see git log ("feat(p1-10d2a)") | test_preorders (10) + browser p1_10d2_preorders 31/31; p1_03, p1_08, p1_10b, p1_10d1 re-run green on the new checkout; suite 1083 |
| P1-10E4 solo navigation + calendar | see git log ("feat(p1-10e3, p1-10e4)") | test_solo_calendar (2) + browser p1_10e_solo 10/10 (desktop + 390 px) |
| P1-10E3 DPDP export + erasure | see git log ("feat(p1-10e3, p1-10e4)") | test_customer_privacy (3) + browser p1_10e_privacy 17/17 (desktop + 390 px) |
| P1-10E2 tags + segments | see git log ("feat(p1-10e2)") | test_customer_segments (5) + browser p1_10e_segments 13/13 (desktop + 390 px) |
| P1-10E1 basic insights | see git log ("feat(p1-10e1)") | test_basic_insights (5) + browser p1_10e_insights 14/14 (desktop + 390 px); payments-collect, role-home tests re-run |
| P1-10D2b formula pricing | see git log ("feat(p1-10d2b)") | test_formula_pricing (7) + browser p1_10d2_formula 28/28 (Playwright Chromium, desktop + 390 px); suite 1090 |

P1 gate after P1-10C: **TOTAL 240 · COMPLETE 122 · PARTIAL 90 · NOT_STARTED 12 ·
ACTIVATION_REQUIRED 16 · FUTURE 0.** Whole ledger: 763 rows (P1 total grew by the
founder-refinement rows in section A2).

P1 gate after the Orders & Customer Transactions refinement was added (no code
change, P1-10D1 rows not yet reconciled): **TOTAL 261 · COMPLETE 126 · PARTIAL
102 · NOT_STARTED 15 · ACTIVATION_REQUIRED 18 · FUTURE 0.** Whole ledger: 793 rows.

P1 gate after P1-10D1: **TOTAL 261 · COMPLETE 131 · PARTIAL 97 · NOT_STARTED 11 ·
ACTIVATION_REQUIRED 22 · FUTURE 0.**

P1 gate after P1-10D2a: **TOTAL 261 · COMPLETE 136 · PARTIAL 95 · NOT_STARTED 8 ·
ACTIVATION_REQUIRED 22 · FUTURE 0.**

P1 gate after P1-10D2b: **TOTAL 261 · COMPLETE 137 · PARTIAL 95 · NOT_STARTED 7 ·
ACTIVATION_REQUIRED 22 · FUTURE 0.**

P1 gate after P1-10E1: **TOTAL 261 · COMPLETE 138 · PARTIAL 95 · NOT_STARTED 6 ·
ACTIVATION_REQUIRED 22 · FUTURE 0.**

P1 gate after P1-10E2: **TOTAL 261 · COMPLETE 140 · PARTIAL 94 · NOT_STARTED 5 ·
ACTIVATION_REQUIRED 22 · FUTURE 0.**

P1 gate after P1-10E3: **TOTAL 261 · COMPLETE 141 · PARTIAL 95 · NOT_STARTED 3 ·
ACTIVATION_REQUIRED 22 · FUTURE 0.**

P1 gate after P1-10E4: **TOTAL 261 · COMPLETE 141 · PARTIAL 96 · NOT_STARTED 2 ·
ACTIVATION_REQUIRED 22 · FUTURE 0.** Full suite before E4: 1102 passed + the
permission-registry parity test fixed (TS `CUSTOMERS_ERASE` added).

### Founder refinements (authority 1) — read before touching these modules

`Documentations/# FOUNDER REFINEMENT — INVENTORY / BOOKINGS / MEMBERSHIPS /
PAYMENTS.txt`, `Documentations/B2B.txt` (B2B / ChitBridge) and
`Documentations/# FOUNDER REFINEMENT — ORDERS & CUSTOMER TRANSACTIONS.txt`
(added 2026-09-28/29). Ledger section A2 (`tools/ledger/rows_refinements.py`)
lists each requirement with its status (FR-IN, FR-BK, FR-MB, FR-PY, FR-OR,
FR-B2B); each document ends with a browser acceptance list that the module's
flow must mirror.

Orders & Customer Transactions (FR-OR-01..30, baseline after P1-10D1 was
committed): one Orders service for every channel (no per-channel order
copies), routing that sends bookings/plans/bills/RFQs/site visits/donations/
repairs to their own modules, a real website checkout with the server
authoritative for price/tax/stock/availability/charges, only the relevant
owner order settings, POS/WhatsApp/human-phone/AI-phone (P3, when enabled)
on the same service, pre-orders with today/tomorrow/future/overdue views,
partial availability and edits that reconfirm, cancellation/returns through
Payments/Inventory/Invoicing, reorder at today's truth, and an Orders
Workspace whose workflow adapts to the business (channel is a filter, never a
tab; never one generic CRUD table). B2B stays its own experience. Baseline:
5 COMPLETE · 15 PARTIAL · 8 NOT_STARTED · 2 ACTIVATION_REQUIRED (21 of the 30
are P1). Pre-orders (FR-OR-16) are part of P1-10D2 and must follow this
document; FR-OR-18 (order edits) and FR-OR-23 (adaptive Orders workspace) are
new P1 NOT_STARTED rows.

SOURCE_CONFLICT SC-01 (resolved by authority order, ledger decisions table):
MD §11.2 closes the AI Receptionist's tool list ("Nothing else") and §11.3
sends restaurant phone orders to a WhatsApp link; the Orders refinement
authorises AI phone ordering for simple orders where enabled. The founder
wins; the WhatsApp-link/human path remains for long, custom or risky orders.

### P1-10E4 — solo businesses: no team menus, one calendar (DONE, browser-verified; OM-21 PARTIAL)

- `business_classification.run_solo(session, business_id)`: org shape (chosen
  or family default) is `solo` AND one active member. `/v1/me/context` returns
  `solo`; the Workspace layout passes it to `AppSidebar` → `visibleAreas(...,
  solo)`; nav children carry `shape: 'solo' | 'team'` (Team area items are
  `team`; Home › Calendar and Settings › Invite someone are `solo`). The
  sidebar now renders extra Home-area children after Notifications.
- `services/one_calendar.py` + `GET /v1/platform/businesses/{id}/calendar?days=7|30`
  (any member; each kind gated by permission + tool); page `/b/{id}/calendar`.
- Fixed in passing: Home's "licences or filings" link pointed to `/licences`
  (no such page) — now `/compliance`.
- Open: "AI employees act as the staff" (P3 AI runtime).

### P1-10E3 — per-customer export and erasure (DONE, browser-verified)

- Migration `20260929150000_p1_customer_privacy.sql`: `contacts.erased_at`,
  `customer_relationships_privacy_requests` (access/erasure, open/done/declined,
  one open erasure per contact; RLS; no DELETE). Applied to local DBs only.
- New permission `customers.erase` (in `permissions.py`; owner gets it through
  ALL_PERMISSIONS, no template grants it).
- `platform_core/customers/privacy.py`: `export`, `blockers`, `erase`
  (explicit per-table SQL, business-scoped), `KEPT` (retention defaults shown
  and returned), `PrivacyRequests`. Staff routes in `v1_platform_customers.py`
  (`/privacy-requests` declared before `/{customer_id}`); customer routes in
  `v1_me.py` (`/businesses/{slug}/my-data`, `/erasure-request`).
- Workspace: customer page "Their data" (request + decline, download, erase
  with blockers / what stays / type-the-name); Home "customers asked you to
  delete their details". Tenant site: My account › Your details (download via
  `/{slug}/account/my-data` route handler, ask to delete, status/decline reason).
- Open (CO-01 PARTIAL): no automatic purge on the retention periods; guardian
  flows are P5; the customer is not messaged when erased/declined (they see it
  in their account).

### P1-10E2 — customer tags and rule-built segments (DONE, browser-verified)

- Migration `20260929140000_p1_customer_segments.sql`: `customer_relationships_segments`
  (rules only, RLS, no DELETE for the API role — archive instead) and a GIN
  index on contact tags. Applied to local DBs only.
- `platform_core/customers/segments.py`: `available(live)`, `clean_rules`,
  `words`, `evaluate` (ORM selects → location scope applies inside the
  union subqueries; consent count from `customer_consents`), `SegmentService`
  (all/create/update/archive/tags). Routes in `v1_platform_customers.py`
  are declared before `/customers/{customer_id}` (that path is UUID-typed —
  FastAPI would otherwise answer 422 for `/customers/tags`).
- Workspace: customer page Tags editor; Customers list tag bar + Tags column +
  "Segments"; `/customers/segments` (builder with "See who is in it", saved
  list) and `/customers/segments/{id}` (members, remove).
- Not offered (honest): "within 5 km" and "birthday this month" (no customer
  location/birthday on the record); sending to a segment is MK-01 (P3).
- New flow check worth reusing: at 390 px compare every input/select/button's
  right edge with the viewport — `fits()` alone missed a clipped field.

### P1-10E1 — basic insights from real data (DONE, browser-verified)

- `platform_core/insights/basic.py` (`summary`, `window`, `rupees`) and
  `GET /v1/platform/businesses/{id}/insights?period=today|7d|month` (in
  `v1_workspace_home.py`; any member, each card gated by its permission and
  whether the tool is on). Sales = issued bills less credit notes; orders =
  placed in the period, cancelled/declined apart, by channel; bookings =
  starting in the period by outcome; money received =
  `PaymentCollectService.received(first, until)` — the same function the
  Payments page now uses for "paid today", so the two never disagree.
- Location scope: ORM filter on orders/bookings/bills; money received is
  business-wide, so a location-limited viewer gets "whole_business_only".
- Workspace: Insights › Your numbers (`/b/{id}/insights`), period tabs, a card
  per number linking to its page, "Not counted here because the tool is off";
  Home's Today band links to it.

### P1-10D2b — formula pricing (DONE, browser-verified)

- Migration `20260929130000_p1_formula_pricing.sql`: `pricing_rates` (per
  business, unique key), `pricing_rate_values` (append-only: the API role has
  no UPDATE/DELETE — a correction is a new value), `offerings.price_formula`,
  `invoicing_document_lines.price_basis`; RLS on both new tables. Applied to
  local DBs only.
- `platform_core/pricing/formula.py`: `clean_formula` (rate key, quantity,
  making % / ₹ per unit / ₹ per piece, other charges, rupee or paisa
  rounding; basket/counter items only), `compute` (pure), `basis_words`,
  `RateService` (board, create, `set_value` → history + re-price every item on
  that rate + audit + `pricing.rate.updated`; `apply_to` on item save;
  `not_entered_since` for Home). An item priced from a rate keeps
  `price_amount` = today's price, so website, WhatsApp, checkout and the
  counter read one catalogue price; a typed price is ignored for such items.
- Snapshot, never rewrite: order lines copy `price_formula.last` into
  `options.formula` at confirmation (when the server priced them); bill lines
  keep it as `price_basis` (order bills from the order line; counter/Workspace
  bills when sold at today's price — a changed price keeps none). The bill
  screen shows the working on its own row, the PDF lists it in notes, and the
  customer's bill link shows it.
- API: `GET/POST /v1/platform/businesses/{id}/pricing/rates`,
  `POST …/pricing/rates/{rateId}/values` (offerings.read / offerings.update).
- Workspace: Products & services › Today's rates (enter the day's rate, items
  priced from it with their working, history); item editor Price › "From a
  rate" (offered once a rate exists; goods items without rates get a pointer
  to add rates); Home "rates to enter for today" when a rate pricing a live item
  has no value since the start of the day. Website card: "Today's price: 10 g ×
  ₹6,450 (22K gold) + making ₹7,740 (12%)" in the tenant's own muted colour.
- Honest gaps: HUID per piece is a serial number, not a named/checked HUID
  (PB-203 PARTIAL); the Workspace bill table scrolls sideways a few px on
  nine-column intra-state GST bills at 1440 px (pre-existing layout).

### P1-10D2a — dated pre-orders (DONE, browser-verified)

- Migration `20260929120000_p1_dated_preorders.sql`: `offerings.preorder`
  (JSONB rules; "no rules" is SQL NULL — the model uses `JSONB(none_as_null=True)`),
  `orders.due_at / preorder / advance_amount / preorder_terms`, index on
  (business_id, due_at), attention value `refund_due`.
- `platform_core/orders/preorder.py`: `clean_rules`, `Rules`, `plan()` (the one
  check — notice, next-day cutoff, ready times, festival window, days ahead,
  open days from location hours, daily limit under an advisory lock, advance,
  terms), `bucket()`; `orders/board.py`: board by day wanted + production list.
  `OrderService._apply_preorder` runs for every channel.
- Checkout: `POST /v1/public/websites/{slug}/checkout/price` (server-priced
  basket: lines with choices, tax, delivery, pre-order days, advance; nothing
  created); placing an order with an advance creates the payment link on it.
  The website checkout page was rebuilt on it (tenant colours, words, day
  picker, advance/balance, confirmation with "Pay advance").
- Text-box choices (`option_groups` entry `{name, text: true, max_length}`):
  catalogue, pricing (`options.notes`), WhatsApp (typed step), website card,
  Workspace editor.
- WhatsApp: "When do you need it?" day/time lists, summary with ready time and
  advance, advance link after placing; customer self-cancel honours a pre-order's
  cancel window. Cancelling an order with money taken flags "refund due".
- Workspace: item editor "Order ahead"; Orders opens "By day wanted" (overdue /
  prepare now / today / tomorrow / later) when the business has dated items or
  orders; channel filter on the list; production list page with print; order
  page shows "Wanted for" and "Advance asked"; action buttons in words.
- Still open (ledger): photo reference on a custom cake (needs public upload),
  order edits (FR-OR-18), a Workspace "take a phone order" screen (FR-OR-13),
  other businesses' adaptive boards (FR-OR-23).

### P1-10D1 — collect what is due (DONE, browser-verified in the cloud session)

- Migrations `20260929100000_p1_payment_requests.sql` (links, attempt purposes,
  part-paid states) and `20260929110000_p1_cod_rules_with_fulfilment.sql`
  (paying on delivery / first-order cap moved from messaging_settings to
  fulfilment_settings — one rule for website and WhatsApp; the WhatsApp page
  edits it through `FulfilmentService.set_payment_rules`). Applied to local DBs
  only.
- `services/payment_collect.py`: money view, links, customer "I have paid" =
  claim until the business confirms, withdraw, confirm/not received, record
  cash/UPI/card/bank, settle exactly once, paid-twice flag, owner overview,
  `send_on_whatsapp` (token proven by hash, `payment_due` template),
  `close_intents` (a pay-on-delivery/at-pickup choice closes "Paid another way"
  once the transaction is paid in full), `net_paid`.
- Fixes the browser run found (all now tested): a bill issued from an order
  shows what was paid on the order and refuses its own payments (one money
  book); a failed or withdrawn try no longer resets a part-paid order/booking/
  membership to "pending"; a part refund keeps the paid state and never
  reopens a balance; cash settled on a COD attempt takes only the remaining
  balance; verified payments write the owner's customer timeline; order,
  bill, tracking and membership pages show words, never stored states
  (`orders/labels.ts`); whole-rupee amounts without paise outside bills;
  counter UPI tab hides "Paid ₹0" once nothing is left; new membership detail
  page `/b/{id}/memberships/{enrolmentId}` with the Money panel.
- Browser flow `tools/acceptance/phase_b/p1_10d1_payments.mjs` (Playwright,
  helper `pw.mjs`): custom-cake advance → UPI claim → owner confirms from
  Payments → part paid → bill agrees → balance: not received → retry →
  withdraw → paid; recorded cash/UPI/card/bank; refund; fixture provider
  replay + late success ("paid twice"); full link at 390 px; membership part
  paid; counter split ₹400 cash + ₹600 UPI; COD first-order cap from Zones &
  charges; store keeper 403, other business 403/404, wrong slug 404.
- Honest remainder: online payment on links / provider status checks =
  ACTIVATION_REQUIRED (`ONLINE_LINKS_ACTIVE = False`, Cashfree); a
  business-set advance rule at checkout (fixed/% for cakes and pre-orders,
  FR-PY-02) is part of P1-10D2; booking Money panel is covered by backend
  tests, not by this browser flow; the website checkout page is still plain
  (raw "INR", lower-case mode names) — rebuild with P1-10D2 (FR-OR-04).

### P1-10C — the site and the Marketplace follow the tools (Founder §14–16; Guide §4)

- `platform_core/website/capabilities.py`: one answer from module readiness +
  live offering kinds + traits — `decide` (actions incl. request_quote,
  site_visit, test_drive, donate, show_address), `pick_primary` (the business's
  way of trading leads; an action whose section is hidden is skipped),
  `auto_sections` (a ready tool's section on the home page when the design has
  none), `published_auto_paths` (Marketplace landing places).
- Read by `website_publish.load_public_page` (sections above contact;
  digital-only strips address/map/location list), `marketplace/eligibility`
  (projection flags), `marketplace_search.listing_actions`, WhatsApp journeys
  (`messaging/journeys._ctx` drops orders/bookings/leads that are not ready).
- Migration `20260928120000_p1_module_aware_site.sql`: `websites.auto_sections_hidden`.
- API: `GET /v1/b/{id}/website/capabilities`, `PATCH /v1/b/{id}/website/auto-sections`
  (event `website.auto_sections.changed`), public `GET /v1/public/websites/{slug}/plans`;
  enquiry purposes `quote_request`, `membership` (+ `plan_id`).
- Marketplace reindexes on plan/provider/fulfilment/stock/traits/tool-section
  events; `_ensure_health` is insert-if-absent (a worker reindex racing an
  opt-in used to 500).
- Web: Plans section reads real membership plans (period shown, "Ask to join"),
  quote form, header button from `primary_path`, My account for plan sellers;
  the Marketplace card leads with the business's own primary action.
- Workspace `/b/{id}/website`: "What customers can do on your site" (live
  actions, "Not yet: <missing step>") and "Sections your tools add" (show/hide).
- Honest partials: tool sections are placed above contact, not by the design
  strategy; digital product delivery / meeting links not built; buying a plan
  online with payment is the Memberships packet (P2).

### P1-10B — one customer identity (Founder §12–13; Doc 12 l.848)

- Migration `20260928110000_p1_customer_identity.sql`:
  `link_verified_customer_contacts()` (links only the calling identity, only on its
  verified email, only unclaimed contacts) and `my_contacts_in_business()`.
- `services/customer_account.py`: linking + backfill, per-business account view,
  reorder at today's price, `contact_for_identity` (signed-in checkout/booking).
- `events/subscribers/customer_activity.py`: My Activity rows from order, invoice,
  quote, membership, fulfilment and payment events.
- API: `optional_customer_identity` on public checkout/booking (invalid token → 401,
  never guest); `/v1/me/businesses/{slug}/account`, `/orders/{id}/reorder`;
  `/v1/me/activity` links verified history first and adds action/account links.
- Web: `/{slug}/account` (tenant theme), header/footer "My account", signed-in
  checkout (no email field, Order again) and booking, checkout/book pages now use
  the business theme instead of a stock serif/gradient; `/activity` covers orders,
  bills, quotes, memberships.
`CURRENT P1–P5 BUSINESS OS IMPLEMENTATION COMPLETE: NO`.

### P1-10A — stock depth (Capability Universe §15.1)

- Migration `20260928100000_p1_stock_depth.sql`: batches (FEFO), serials
  (warranty), yields + cutting runs, counts + lines, wastage reason codes,
  weighted-average value on every record and movement, buying units, reorder
  max; bill and order lines carry `serials` and `batch_allocations`. RLS +
  location-scope restrictive policies; the API role cannot DELETE stock history.
- `platform_core/stock/`: `ledger.py` (value, FEFO take/put-back, serial
  sell/return — called with the record row locked from every stock path:
  counter and Workspace bills in `InvoiceService._move_stock`, order deduction,
  opening stock, adjustments), `profile.py` (which stock views a business gets,
  from traits + §21 family hints + configuration), `service.py` (receive,
  wastage, write-off, yields, cutting runs, counts with approval, reorder,
  expiry, serial lookup, overview, items).
- Router `v1_platform_stock.py` (`/v1/platform/businesses/{id}/stock/...`);
  permissions `inventory.approve` (counts) and `inventory.cost` (value).
- Expiry alerts: ladder `inventory.expiry` (30/7/0 days) via subscriber
  `events/subscribers/inventory_expiry.py`.
- Workspace `/b/{id}/inventory`: a view per stock profile (counter by weight
  with live-trim cutting; batches & expiry; serials & warranty lookup; size ×
  colour grid; ingredients; reorder) plus counts (blind count sheet +
  approval), wastage, item settings; `/inventory/{recordId}` detail;
  `/inventory/counts/{countId}`. Counter (POS): serial-tracked items need one
  serial per unit before Pay; scanning an IMEI adds that unit.
- Honest partials: yield in procurement maths and requisition drafts (P4),
  transfers (P2), van stock / parts / client-owned stock lenses (P2–P5).

## Remaining work snapshot (P1 first)

P1 NOT_STARTED (2): FR-OR-18 (order edits that revalidate), PKT-10 (P1-10
packet — languages remain).
P1 PARTIAL groups: FD-02 (portal items with Academics), FD-03 (strategy
placement of tool sections), OM-09 (portfolio kind), OM-18 (digital delivery),
GP-22 + PR-10 (English/Tamil/Hindi), payments provider (Cashfree =
ACTIVATION), playbook rows waiting on P2–P5 modules.

Planned next packets (dependency order):
1. **P1-10E** (E1 insights, E2 tags + segments, E3 DPDP, E4 solo done) → E5 order edits that revalidate + phone-order screen
   (FR-OR-18, FR-OR-13) → E6 English/Tamil/Hindi strings (PKT-10, PR-10);
   then the P1 gate.
2. P2 → P5 per MD §26.2 / ledger sections W–AL, then E2E flows (section BG).

## How to run things locally (Linux / Claude Code cloud) — used since P1-10D1

- Python: `uv sync --all-packages` (needs Python 3.12; uv fetches it).
  Node: `pnpm install --frozen-lockfile`, then build the shared packages once:
  `for p in config contracts validation permissions observability auth api-client ui; do (cd packages/$p && pnpm run build); done`
  (the Next apps import their `dist/`).
- Postgres 16 (Ubuntu package, runs as the `postgres` user, not root):
  `initdb -D /var/tmp/locah-pg/data -U postgres --auth=trust`, then
  `pg_ctl -D /var/tmp/locah-pg/data -o '-p 54329 -c max_connections=300' start`.
  Fresh DBs: `PGPORT=54329 bash tools/acceptance/stack/db.sh locah_test` (and
  `locah_accept`) — every migration + seed in ~3 s. A new migration on an
  existing DB: `psql -h localhost -p 54329 -U postgres -d <db> -f <file>`.
- Backend suite from `apps/api` (as on Windows, with `../../.venv/bin/python`
  and `-n 3` on a 4-core box).
- Stack: `node tools/acceptance/stack/mock-auth.mjs`, `bash tools/acceptance/stack/api.sh`
  (set `PAYMENT_WEBHOOK_SECRET=local-acceptance-webhook-secret` for the fixture
  webhook steps), `web.sh`, `workspace.sh`, `worker.sh` — each backgrounded with
  `setsid nohup … &`. `uv run --no-env-file python tools/acceptance/stack/recordings.py acceptance-out`
  once; sessions: `owner.py locah_accept acceptance-out/owner2.json` (owner) and
  `… acceptance-out/session.json` (customer). Exactly one worker.
- The image has no `ss`: find a port's process through `/proc` (or `lsof -i :8010`)
  and restart by PID. Never `pkill -f <pattern>` from a shell whose own
  command line contains the pattern — it kills that shell.
- Browser flows: new flows use Playwright with the global install and
  `/opt/pw-browsers` Chromium (`tools/acceptance/phase_b/pw.mjs`):
  `node tools/acceptance/phase_b/p1_10d1_payments.mjs`. Older CDP flows run with
  `CHROME_PATH=/opt/pw-browsers/chromium CHROME_NO_SANDBOX=1`. Screenshots in
  `acceptance-out/phase_b/<flow>/` (git-ignored) — look at them.

## How to run things locally (Windows)

- Postgres 18 (scoop) cluster lives at
  `%TEMP%\claude\C--Users-KausikGH-Documents-Locah\1e393fca-…\scratchpad\pgdata`,
  port 54329, trust auth. If it wedges with "could not reserve shared memory
  region … error code 487", stop it (`pg_ctl stop -m immediate`, kill the
  postmaster) and `pg_ctl start -D <pgdata> -l <pg.log> -o "-p 54329"`.
- Fresh DBs: `PGPORT=54329 bash tools/acceptance/stack/db.sh locah_test`
  (and `locah_accept`) — replays every migration + seed (~15 s).
- Backend suite (RLS role), from `apps/api`:
  `env -u DATABASE_URL -u API_DATABASE_URL LOCAH_TEST_NO_EXTERNAL_AI=1
  TEST_DATABASE_URL=postgresql+asyncpg://postgres@localhost:54329/locah_test
  TEST_API_DATABASE_URL=postgresql+asyncpg://platform_api:localtest@localhost:54329/locah_test
  ../../.venv/Scripts/python.exe -m pytest tests ../worker/tests -c pyproject.toml --rootdir . -q -p no:cacheprovider -n 6`
- Lint/types: `.venv/Scripts/ruff.exe check <paths>`,
  `.venv/Scripts/mypy.exe --explicit-package-bases <paths>`; Workspace:
  `apps/workspace/node_modules/.bin/tsc --noEmit -p apps/workspace`, `next lint`.
- Browser stack: `.claude/launch.json` entries `accept-auth`, `accept-api`,
  `accept-workspace`, `accept-web` (local DB `locah_accept`, no provider keys,
  AI replay only); worker: `bash tools/acceptance/stack/worker.sh` in the
  background (drains events so My Activity/automations run). On Windows,
  stopping that background task leaves its Python children running old code;
  they race the new worker and write stale projections — find them with
  `Get-CimInstance Win32_Process` (command line `*platform_worker*`) and stop
  them before restarting. Restart `accept-api` after backend changes. Sessions expire
  after 12 h — re-mint with `owner.py` (customer `session.json`, owner `owner2.json`). Session: `.venv/Scripts/python.exe tools/acceptance/stack/owner.py
  locah_accept acceptance-out/session.json`. Flows:
  `node tools/acceptance/phase_b/<flow>.mjs` (local Chrome over CDP);
  screenshots in `acceptance-out/phase_b/` — look at them, a passing text
  check once hid white-on-white IMEI chips.
- Ledger: `.venv/Scripts/python.exe -m tools.ledger.render` then
  `PYTHONIOENCODING=utf-8 … --gate P1`.
- Constraints in force: zero Gemini/OpenAI/xAI/Anthropic/image/voice calls and
  zero payment-provider transactions; no Razorpay expansion; no deploys or
  hosted-Supabase migrations without an explicit go; never weaken RLS; never
  claim UI verified without a browser run.
