# LOCAH — final release handoff

Release lane `claude/final-release-candidate`, worked in the existing worktree
`/Users/user25/gowtham/Personal_Projects/locah-release` (macOS, local stack).
Every "tested" below was executed; what could not be run says so.
Updated after the deploy (same day).

## Identity

| Field | Value |
|---|---|
| FINAL MAIN SHA | **`0fe502674f6a868e533e3cace0cdfe445c6d6ddd`** — the tested release (promoted by fast-forward `9c21d46..dfe2995..0fe5026`, no force, tree = tested tree). `main` may carry later docs-only commits (this file's updates); the code is `0fe5026`. |
| RELEASE TAG | **`locah-demo-2026-09-30-r2`** → `0fe5026` (tag object `52dc4da`). `locah-demo-2026-09-30` → `dfe2995` is superseded: correct code, but its migration set could not be deployed to hosted (see SUPABASE). |
| Release lane start | `d0fb04f` (fast-forwarded from local `42ff0e9`; tree clean) |
| WEBSITE-V4 SOURCE SHA | `f2c6353a7ede027eb01350cb5eac97c69b03aff3` (`origin/claude/compassionate-allen-hlpq6p`), merged in `9a5248b` |
| GEMINI AUDIT SHA | `e27dfe99d8897ed48bf77086667c6adaa992a6f0` (`origin/cursor/gemini-activation-audit`, docs only), cherry-picked as `747a4d4` → `docs/current-build/GEMINI-ACTIVATION-AUDIT.md` |
| Old main | `9c21d4689033ed0539035cbfa8d39efb6efacf89` (already inside the release lineage via `2b34513`) |
| MIGRATION COUNT | **95** (`infra/supabase/migrations`), no duplicate versions; hosted history = 95 |

## What this pass changed (commits on top of `d0fb04f`)

| Commit | What |
|---|---|
| `9a5248b` | Website-v4 merged. No textual conflicts; two files touched by both sides (`job_runner.py`, `models.py`) had independent hunks, both kept. Receptionist's use of `get_ai_provider()` / `generate_structured(..., timeout_seconds=)` / `model_name` checked against v4. No Grok/xAI code returned (only tests asserting it is gone). |
| `747a4d4` | Gemini activation audit document (cherry-pick of the doc-only commit). |
| `a526424` | Audit **B1** (HTTP 402 → `AIProviderBillingError`: one call, no fallback model, no generator retry; log `ai.gemini.billing_refused`), **B5** (no brand names / trademarks / manufacturer markings / branded logos, clothing, packaging in any picture prompt; prompt version `media-v4.2`), **B6** (unsure digits → confidence low). Tests mutation-checked for B1. |
| `e4462f6` | Audit **B2** (verifier compares price amounts and name±unit; 32 px test menu), **B3** (verifier restores the Gemini hero before re-publishing), **B4** (`owner_sites.mjs` waits for the hero `<img>`/background to load and decode; caption derived from `report.json`). |
| `708553b` | **WhatsApp routing fix**: "how much is personal training?" matched "person" and went to a person. A lone word counts only as the whole message; otherwise whole phrases. Steering attempts go to a person deterministically. |
| `533408e` | Hosted-only migration `20260929115750_location_list_places` brought into Git (exact hosted statement; seed row aligned). |
| `e3b4085` | `DEMO-RUNBOOK.md`, `RAILWAY-DEPLOYMENT-CHECKLIST.md`; two browser suites made runnable off Windows (harness only). |
| `dfe2995` | This handoff (first version). Promoted to main and tagged `locah-demo-2026-09-30`. |
| `0fe5026` | **Hosted history collision fixed**: hosted versions `20260929110000` / `20260929120000` held two never-committed `REVOKE`s while the repo used them for the COD-rules and dated pre-orders migrations (Supabase would have skipped both → 7 missing columns → every order failing). Hosted statements committed under their versions; the two repo migrations moved to `20260929110100` / `20260929120100` (same relative order). Found by rehearsal. Promoted and tagged `-r2`. |

## Gates (executed)

**API/WORKER TESTS** — full suite, fresh database, RLS role `platform_api`
(`TEST_API_DATABASE_URL`), `-n 8`:
- at `708553b` (92 migrations): **1355 passed, 0 failed**.
- at `dfe2995` (93 migrations): **1355 passed, 0 failed**.
- **at the release `0fe5026` (95 migrations): 1355 passed, 0 failed** (78 s).

**STATIC CHECKS** (at `708553b`; no application source changed after it —
only docs, harness `.mjs`, one migration, one seed row):
ruff clean · mypy **0 issues in 603 files** · contracts typecheck + lint +
build · web typecheck + lint · Workspace typecheck + lint · **web production
build** · **Workspace production build** (warnings only: supabase-js Edge
note, one autoprefixer hint — pre-existing). Permission parity Python = TS =
**160** (`test_python_permissions_match_typescript_registry`; +2 AI-employee
permissions over the previous 158).

**BROWSER TESTS** — Chromium (Playwright 1.49 / Chromium 1148), one local
stack on a fresh DB (API :8040, web :3400, Workspace :3401, live worker), final
code:

| Suite | Result |
|---|---|
| Demo gate (gym, restaurant, field service; desktop + 390 px; live worker) | **17/17** |
| P1-10D1 Payments | **84/84** |
| P1-10B Identity / My Activity (incl. 390 px) | **14/14** |
| P1-08 WhatsApp journeys | **30/30** (one earlier run 29/30: the harness read the last bubble before it rendered; re-run 30/30, order was created both times) |
| P1-07 WhatsApp setup / staff alerts | **21/21** |
| P2-02 Memberships | **24/24** |
| P2 Quotes | **15/15** |
| P2 Queue board | **5/5** |
| P2 Kitchen / KDS | **10/10** |
| P2 Dispatch | **9/9** |
| P2 Tasks board | **4/4** |
| P2 Documents / forms | **6/6** |
| P3 Growth Workspace UI (loyalty desk, campaign builder) | **14/14** |
| P5 Projects / Jobs / Academics | **13/13** |
| P1-10A Stock | **20/20** |
| P1-10E Language | **23/23** |
| Website-v4 interview flows (`flows.mjs`) | **13/13 desktop, 13/13 phone** |
| Workspace priority-route survey (19 routes × 1440/390) | **38/38**, no error text, no horizontal overflow; screenshots inspected |
| Website-v4 owner flow + `owner_sites.mjs` (5 sites, stand-in pixels) | 5/5 shot; hero waits resolved (`img` ×3, `background` ×2), no timeouts |
| `gemini_verify_v4.py --self-test` | 5 sites 10/11 (the 11th, `returned_by_gemini`, is never set in self-test), hero restored 5/5, manual controls 7/7, upload wins |

Not a product failure, not run as a gate: `p3_growth_loyalty_marketing.mjs`
(first-pass growth suite, `e48fd60`) creates a business without enabling the
Loyalty module and gets the correct `403 ENTITLEMENT_REQUIRED`; it was
superseded by the hardened growth suites above.

**DOCKER BUILDS** — this Mac has **no Docker engine**; the four images were
not built locally. What was executed instead:
- API/worker: a clean environment built exactly as the image does
  (`uv sync --frozen --no-group dev` → no pytest/ruff/mypy), started exactly as
  the image does (`uv run`, `UV_NO_SYNC=1`, the image `PYTHONPATH`,
  `ENVIRONMENT=production`): API `/health/live` 200, `/health/ready` 200
  `database: connected`, **0 packages fetched at boot**; worker
  `worker.starting → worker.db_connected → worker.polling`, processing outbox,
  deliveries and async jobs.
- Web/Workspace: `pnpm install --frozen-lockfile` (lockfile in sync) and the
  Dockerfiles' own `pnpm --filter @platform/<app>... build`: both pass.
- The real image builds are Railway's builds of `main` (see RAILWAY).

**DEMO GATE** — 17/17 (above). **Demo seed** (`tools/demo/seed.py`, API only)
run twice on the final tree: 3 businesses created, then "already there" ×3;
no duplicate offerings, plans, quotes or contacts.

## Product areas

- **TALK TO LOCAH**: interview flows 13/13 desktop + phone (replayed model
  readings, model-down path included); real-Gemini text verified by the audit
  (36 real turns, no fallback).
- **MODULE RECOMMENDATIONS**: Essential / Recommended / Optional with a plain
  why (`ec5e440`); survey screenshot checked at 390 px.
- **WEBSITE**: Website-v4 merged; unit/API suites green; real Gemini verified
  by the audit (creative-v2 path, MediaPlan, draw_missing, 19 real pictures,
  desktop 1440 + mobile 390, manual Generate / new / Keep / Remove / upload
  wins, menu PDF read); B1–B6 applied.
- **AI EMPLOYEES**: Receptionist / Collections / Procurement on one runtime —
  verified by `test_ai_employees.py` (10 tests) and code reading: writes only
  its own tables (`ai_employees`, `ai_actions`, controls); acts through the
  same services staff use (`LeadService`, `MessagingService`, booking journey,
  `SupplyService`); tool allowlist, T0–T3, kill switch and global pause;
  every action an `ai_actions` row with model and tokens; a PO send is T3 and
  its approval needs `procurement.approve`; Collections has no refund,
  write-off or invoice-editing tool. No new employees added.
- **WHATSAPP**: routing fixed (above); journeys 30/30, setup 21/21; Receptionist
  answers price (from the Offering), hours (from the location), services,
  starts bookings; discount / refund / injection → a person. Deployed:
  ACTIVATION_REQUIRED (no Meta number; the sandbox is development-only by
  design — `ENVIRONMENT` must stay production on Railway).
- **AUTOMATIONS**: dedicated tests, all in the green full suite — booking
  confirm/remind/reschedule/cancel (`test_messaging`), renewal ladder
  (`test_p2_memberships::test_renewal_ladder_sends_once_waits_for_quiet_hours_and_stops_on_payment`),
  queue turn-soon (`test_queue`), dispatch message
  (`test_integration_dispatch_messaging`), invoice/collections
  (`test_invoicing_gst`, `test_ai_employees`), low stock → alert / draft
  requisition (`test_platform_primitives`), compliance → task
  (`test_integration_compliance_tasks`, `test_tasks`), review request
  (`test_review_invites`). Each asserts trigger → worker → service → side
  effect → once only.
- **WORKFORCE**: sufficient for the demo, not expanded — provider schedules
  bind bookings, technician assignment (Jobs), teacher (Academics), crew
  (Dispatch), attendance presence: suites green (full suite; P5 13/13;
  dispatch 9/9; demo gate check-in). Payroll: FUTURE.
- **CALLING**: call records, permission rules, staff alert, audit, capability
  states — `test_whatsapp_connection_calling` green. CALL_AUDIO =
  ACTIVATION_REQUIRED (no Meta voice transport; no AI phone call).
- **CASHFREE** (`cashfree-sandbox` `8b495b8`, never merged):
  - ALREADY_PRESENT / PORTED: refund over-refund guard → kernel row lock (`6fec540`).
  - OBSOLETE: checkout / payment_attempt / webhook / merchant-routing rewrites,
    CashfreeConnect UI and payments page, `.gitignore` entry, event names.
  - UNSAFE (not ported): `payments_platform_fee_rules` + `commission.py` +
    admin fee-rule route (platform billing inside merchant checkout — breaks
    the payments separation), `test_payments_kernel` reductions.
  - ACTIVATION_REQUIRED: `CashfreePaymentProvider` client (untested WIP, never
    run against the sandbox) and the migration's `cashfree` provider value.
  - NOT PORTED, known gap: the refund `idempotency_key` column. The kernel's
    row lock means refunds can never exceed what was paid, but the refund
    route takes no idempotency key, so a double-submitted partial refund can
    be recorded twice (still capped at the amount paid). Port with Cashfree
    activation.
  - DEFERRED WITH ACTIVATION: the provider-neutral fulfilment guard ("online
    order cannot be fulfilled before verified payment") — correct once online
    collection is live; changes a staff rule today, so it ships with Cashfree
    activation, not in this release.
- **TALLY**: connector hub foundation only; ACTIVATION_REQUIRED.

## Final gate (release `0fe5026`)

Fresh database from all 95 migrations + seed (`ON_ERROR_STOP`): clean.
Full API + worker suite on it (RLS role, `-n 8`): **1355 passed, 0 failed**.
Ruff clean. No application source changed since the static checks and
production builds at `708553b` (only docs, harness, migrations/seed, one code
comment). Browser suites and the demo gate above ran on the same code.

## SUPABASE

Hosted project `Locah` (`pmwyaqmwxfbnfulqbqmk`, ap-south-1, Postgres 17),
read-only analysis done in this pass:
- History: 64 rows, newest `20260929120000`. One row had no file in Git
  (`20260929115750_location_list_places`) — now committed (`533408e`), its
  statement verified to reproduce the hosted value exactly.
- `20260930130000_procurement_supply_lane.sql`: objects present without a
  history row. Compared against a local replay stopped at that version: all
  25 tables, the function `procurement_post_trade` and the 6 module rows —
  columns (type, nullability, default), indexes, policies, RLS/force-RLS and
  149 constraints — identical (the only raw difference was Postgres 18's
  catalogued NOT NULL constraints, absent on PG17; excluding those, the
  constraint fingerprints are equal). → safe for `supabase migration repair
  --status applied 20260930130000`.
- Genuinely pending: 28 migrations (20 create tables absent on hosted; 8
  column/data-only ones whose sentinel objects are absent) — plus 2 more found
  by the rehearsal below.

**Rehearsal (local, on real data)**: the hosted backup restored into a local
database, then exactly the commands used on hosted. It showed that after
`db push` seven columns the release reads were still missing: hosted history
versions `20260929110000` / `20260929120000` were two hot-fix `REVOKE`s never
committed, and the repo reused those versions for the COD-rules and dated
pre-orders migrations, so Supabase counted them as applied. Fixed in
`0fe5026`; re-rehearsed: 30 applied, history 95, and the result equal to a
fresh replay of the release in tables (235), columns with defaults (2961),
indexes (677), constraints (1671), policies (512), function bodies (34),
triggers (84) and `platform_api` grants (600 = 600).

**Applied to hosted** (official Supabase CLI 2.109.1, session pooler):
1. Backups (custom format, `public` + `supabase_migrations`, 150 tables):
   `/Users/user25/gowtham/Personal_Projects/locah-backups/hosted-before-release-20260930T062526Z.dump`
   and, immediately before applying, `hosted-pre-apply-20260930T063938Z.dump`
   (43.6 MB each). Supabase's managed backups are separate.
2. `supabase migration repair --status applied 20260930130000` → "Migration
   history repaired" (the objects were proven equal first — above).
3. `supabase db push --include-all --dry-run` → exactly the rehearsed 30.
4. `supabase db push --include-all` → 30 applied, no errors; history 64 → **95**.
5. Seed `00_platform.sql` in one transaction → ok (no-op: the module and
   section registries already matched).
6. Verified read-only: hosted schema vs. the fresh replay of the release —
   structurally identical except a Supabase-provided platform function body
   (`rls_auto_enable`) and a pre-existing no-op FORCE-RLS flag on six platform
   tables whose RLS is off; `platform_api` grants and function EXECUTE
   identical (901 = 901).

SUPABASE REPAIR STATUS: DONE (`20260930130000` repaired as applied; hosted-only
`20260929115750`, `20260929110000`, `20260929120000` brought into Git).
MIGRATION STATUS: hosted = repository = 95.
SUPABASE STORAGE: published tenant pictures are served from
`pmwyaqmwxfbnfulqbqmk.supabase.co/storage/.../media/…` through the deployed
API and render on the deployed sites (existing pictures; a new generation on
the deployed stack was not run — needs a signed-in owner).

## RAILWAY

Project `locah-staging`, environment `production`; services `locah-api`,
`locah-worker`, `locah-web`, `locah-workspace`, all from `kausik-gh/locah`
with their Dockerfiles. Found before deploying: only `locah-workspace` tracks
`main` in its live config; an un-applied staged patch (web → `main`, worker
variable changes); `XAI_*` still on API/worker; `GEMINI_API_KEY` present on
API and worker; web/Workspace carry only `NEXT_PUBLIC_*`.

**Configured and deployed** (one staged patch, reviewed, non-destructive,
committed once): all four services' source pinned to `kausik-gh/locah` @
`main`; API + worker `AI_PROVIDER` / `IMAGE_PROVIDER` / `VOICE_PROVIDER` =
`gemini` and the `GEMINI_*_MODEL` pins; `RATE_LIMIT_TRUST_XFF=1` on the API;
`XAI_API_KEY`, `XAI_MODEL`, `XAI_VOICE`, `XAI_VOICE_MODEL` removed from the
API and `XAI_API_KEY`, `XAI_MODEL` from the worker; the worker given
`SUPABASE_JWT_SECRET=${{locah-api.SUPABASE_JWT_SECRET}}` (a Railway reference
— the worker signs bill / khata links for collections and reminders, and had
no signing secret; no value was copied). Confirmed absent on both:
`LOCAH_TEST_NO_EXTERNAL_AI`, `AUTO_GENERATE_WEBSITE_IMAGES`,
`MESSAGING_SANDBOX`. `ENVIRONMENT` is set on both; its value is not readable
through the tools used and was left unchanged. No secret value was printed.

Deployments, all from `main` @ `0fe5026`, all SUCCESS:
`locah-api` 16230927…, `locah-worker` 25c47950…, `locah-web` c6f3e8b6…,
`locah-workspace` 203f8879…. **DOCKER BUILDS**: all four images built on
Railway from their Dockerfiles (worker log: `uv sync --frozen --no-group dev`,
32 runtime packages).

RAILWAY DEPLOYMENT URLS:
- Web: https://locah-web-production.up.railway.app
- Workspace: https://locah-workspace-production.up.railway.app
- API: https://locah-api-production.up.railway.app
- Worker: no public URL (health via `API/health/worker`).

**Deployed smoke — executed (deployed URLs, not localhost):**
- API HEALTH: `/health/live` 200 · `/health/ready` 200 `database: connected` ·
  new build confirmed (`/v1/b/…/ai-employees`, a route only this release has, → 401 unauthenticated) · startup log
  `external_ai_disabled: false`.
- WORKER STATUS: `worker.starting → worker.db_connected → worker.polling`
  (interval 2 s); `/health/worker` 200 `healthy, lag_seconds 0, pending 0`.
- Web `/`, `/marketplace`, `/signup`, `/login` → 200; home, login and
  Marketplace render styled at 1440 and 390, no horizontal overflow, no
  console errors (headless Chromium).
- Workspace → 307 to the web login when signed out (by design).
- Public tenant websites `/nalla-veedu-kitchen-1`, `/grit-barbell-club-1` →
  200; styled; hero picture loaded (1376 px) from Supabase Storage; 1440 and
  390; no overflow; no broken images in view; no console errors.

**Deployed smoke — NOT executed (needs a signed-in account):** Supabase
sign-in, Create Business, Talk to LOCAH, recommendations, enable module,
Build Website with real Gemini personalization and hero, manual Generate
picture, menu/catalogue read, Booking, Membership, Order, Payment, Kitchen,
Automation + Automation Activity, AI Receptionist answer, escalation, My
Activity. Creating accounts or entering passwords on a non-local site is not
something this session may do; these run once the founder signs in (web and
Workspace tabs), and every one of them passed on the local stack on the same
code (Gates). WhatsApp on the deployed stack is activation-required by
design (no Meta number; sandbox is development-only). GEMINI on Railway:
key present on API and worker, providers set; not exercised on the deployed
stack yet (the audit proved the same key and models locally).

## ACTIVATION_REQUIRED

Meta WhatsApp production number, App Review, Tech Provider, Embedded Signup ·
Meta Calling live audio · PSTN telephony · Cashfree live merchant credentials
and review · real Tally environment · optional Maps provider · custom platform
domain (shared sign-in across web/Workspace).

## KNOWN NON-BLOCKERS

- Railway generated domains: web and Workspace keep separate sessions (no
  shared cookie across `*.up.railway.app`).
- `draw_missing` runs picture slots concurrently: on a 402 every slot of that
  build fails at once (each a single call); text calls are one call (B1).
- B7 (audit) diagnostics not done: generated MediaAssets carry no
  width/height; 401/404 image errors map to the generic owner reason (the log
  keeps the status).
- Refunds: no idempotency key on the refund route — a double-submitted
  partial refund can be recorded twice, never more than was paid (see CASHFREE).
- Quote number wraps onto three lines in the Quotes table at 390 px (readable,
  no overflow).
- Website-v4 open items from its handoff: removing a picture does not mark the
  MediaPlan slot removed; model-down reader is coarse.
- Earlier open items still open: quote → invoice target has no consumer;
  offers not applied at website checkout; some screens compute "today" in UTC;
  two document stores (supply `documents_records`, Documents `document_files`).

## Branches

DELETED (18, each re-checked immediately before, details in
`BRANCH-CLEANUP-MANIFEST.md`): `claude/p2-02-memberships-wip`,
`claude/phase-b-final-integration`, `claude/sleepy-gauss-ou1t3i`,
`claude/wonderful-newton-eiw7jn`, `claude/compassionate-allen-hlpq6p`, the
eleven `parallel/*` branches — all ancestors of main — and
`cursor/gemini-activation-audit`, `cashfree-sandbox` after archive tags
`archive/gemini-activation-audit` (`e27dfe9`) and `archive/cashfree-sandbox`
(`8b495b8`).
KEPT: `main`; `claude/final-release-candidate` (= `0fe5026` + these docs; the
release worktree's branch); local-only `backup-before-reset`,
`web-builder-lovable` (founder's decision); local branches in the `/locah` and
`/locah-gemini-audit` worktrees.

## Verdicts

- **DEPLOYED = YES** — all four services on Railway from `main` @ `0fe5026`,
  healthy; hosted database at the release schema.
- **RAILWAY_READY = YES** — four Dockerfile builds on Railway, health checks
  green, configuration per `RAILWAY-DEPLOYMENT-CHECKLIST.md`.
- **DEMO_READY = NO — one step short**: the whole workflow passed on the
  local stack on this exact code (demo gate 17/17 and every suite above), and
  the deployed services are healthy, but the signed-in walk-through on the
  deployed URLs (including a live Gemini build there) has not been executed.
  It becomes YES when the founder signs in and that walk-through passes.
- **PRODUCTION_READY = NO** — ACTIVATION_REQUIRED items (Meta WhatsApp /
  Calling, Cashfree live, Tally, custom domain for one sign-in) and the known
  non-blockers above.
