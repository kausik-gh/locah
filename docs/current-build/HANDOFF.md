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
| P1-10B one customer identity | this commit | test_customer_identity (3) + browser p1_10b_identity 14/14; suite 1048 |

P1 gate after P1-10B: **TOTAL 240 · COMPLETE 116 · PARTIAL 94 · NOT_STARTED 14 ·
ACTIVATION_REQUIRED 16 · FUTURE 0.** Whole ledger: 763 rows (P1 total grew by the
founder-refinement rows in section A2).

### Founder refinements (authority 1) — read before touching these modules

`Documentations/# FOUNDER REFINEMENT — INVENTORY / BOOKINGS / MEMBERSHIPS /
PAYMENTS.txt` and `Documentations/B2B.txt` (added 2026-09-28/29). Ledger section
A2 (`tools/ledger/rows_refinements.py`) lists each requirement with its status;
each document ends with a browser acceptance list that the module's flow must mirror.

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

P1 NOT_STARTED (14): FD-04 (website recomposes when modules change), OK-15
(formula-priced jewellery), OR-04 (dated pre-orders), OR-08 (reorder), PY-02
(payment links), PY-05/PY-06 (split tender / cash-card records as payment
domain — POS already does both; audit and close), CR-04 (segments), CR-08 +
CO-01 (DPDP export/erase), OM-18 (digital-only), OM-21 (solo navigation),
IS-01 (basic insights), PKT-10 (P1-10 packet).
P1 PARTIAL groups: FD-01/02 (customer identity + My Activity), FD-03/05/10 +
OM-06/07/09/19 (module-aware website + Marketplace readiness actions), GP-22 +
PR-10 (English/Tamil/Hindi), payments provider (Cashfree = ACTIVATION),
playbook rows waiting on P2–P5 modules.

Planned next packets (dependency order):
1. **P1-10B** customer identity on tenant sites + My Activity across modules
   (FD-01, FD-02, SF-05), reorder (OR-08).
2. **P1-10C** module-aware website + Marketplace actions from real readiness
   (FD-03/04/05/10, OM-06/07/09/18/19) — use `module_readiness.readiness()`,
   not `activation_state == 'active'` (today's `marketplace/eligibility.capability_flags`).
3. **P1-10D** payment links (provider-neutral; Cashfree edge ACTIVATION),
   COD first-order cap, dated pre-orders, formula pricing, PY-05/06 audit.
4. **P1-10E** EN/TA/HI UI strings, basic insights from real data, solo
   navigation, tags/segments, DPDP export/erase; then the P1 gate.
5. P2 → P5 per MD §26.2 / ledger sections W–AL, then E2E flows (section BG).

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
  background (drains events so My Activity/automations run). Sessions expire
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
