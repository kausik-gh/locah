# Railway deployment checklist

Project: **locah-staging** (Railway), environment `production`. Every service
builds from GitHub `kausik-gh/locah`, branch **`main`**, root `/`, with its own
Dockerfile. Nothing is uploaded from a laptop; nothing is patched on Railway
outside Git. Supabase (project **Locah**, `ap-south-1`) is the database and
auth provider. General background: `infra/deploy/README.md`.

Order for every release:

1. Hosted migrations are reconciled and applied **before** the code that needs
   them (see "Database first").
2. `main` points at the tested release commit.
3. The four services build that commit (API and worker first, then web and
   Workspace).
4. Post-deploy smoke (below) on the deployed URLs.

## Database first (Supabase)

- Migrations: `infra/supabase/migrations/*.sql`, forward-only, keyed by the
  version prefix. Apply only what the hosted history does not have, after a
  schema comparison — never re-run a migration whose objects already exist.
- Known history gap: `20260930130000_procurement_supply_lane.sql` was applied
  without a history row. Reconcile with `supabase migration repair --status
  applied <version>` only after the objects are proven equal; record it in
  `FINAL-RELEASE-HANDOFF.md`.
- Seed (idempotent): `infra/supabase/seed/00_platform.sql` — module and section
  registries. A deploy without it starts but fails at runtime.
- `platform_api` role password is set outside Git (see `infra/deploy/README.md` §4).
- Storage buckets used by the product: `media` (public pictures, Gemini drafts),
  `business-assets` (logos, profile assets)
  and the private `owner-documents` bucket (menus / catalogues). All three are
  created by migrations.

## Services

### locah-api

| | |
|---|---|
| Dockerfile | `infra/docker/Dockerfile.api` |
| Build | `uv sync --frozen --no-group dev` (no dev tools in the image) |
| Start | `uv run uvicorn platform_api.main:app --host 0.0.0.0 --port $PORT` with `UV_NO_SYNC=1` (nothing is downloaded at boot) |
| Health check | `/health/ready` (database connected); liveness `/health/live` |
| Watch paths | `apps/api/**`, `python/**`, `infra/docker/Dockerfile.api`, `pyproject.toml`, `uv.lock` |
| Domain | `locah-api-production.up.railway.app` (custom: `api.<platform-domain>`) |
| Depends on | Supabase Postgres (pooler), Supabase Auth JWKS, Supabase Storage, Google Gemini |

Secrets: `DATABASE_URL`, `API_DATABASE_URL` (the RLS `platform_api` role),
`SUPABASE_SERVICE_ROLE_KEY`, `SUPABASE_JWT_SECRET` (legacy HS256 only),
`WEBSITE_PREVIEW_SECRET`, `PAYMENT_WEBHOOK_SECRET`, `GEMINI_API_KEY`
(a Google project **with prepaid credit**), and later `CASHFREE_*`, `META_*`
when activated.

Config: `ENVIRONMENT=production` (never a development value on Railway — it
would allow development default signing secrets), `SUPABASE_URL`,
`SUPABASE_ANON_KEY`, `CORS_ALLOWED_ORIGINS=https://locah-web-production.up.railway.app,https://locah-workspace-production.up.railway.app`,
`RATE_LIMIT_TRUST_XFF=1`, `AI_PROVIDER=gemini`, `IMAGE_PROVIDER=gemini`,
`VOICE_PROVIDER=gemini`. Optional pins of today's defaults:
`GEMINI_INTERVIEW_MODEL=gemini-3.8-flash`, `GEMINI_WEBSITE_MODEL=gemini-3.8-flash`,
`GEMINI_DOCUMENT_MODEL=gemini-3.8-flash`, `GEMINI_IMAGE_MODEL=gemini-3.1-flash-image`,
`GEMINI_FALLBACK_MODEL=gemini-3.5-flash,gemini-3.1-flash-lite`.
`PLATFORM_DOMAIN` only once a custom registrable domain exists.

Must be **absent**: `LOCAH_TEST_NO_EXTERNAL_AI`, `AUTO_GENERATE_WEBSITE_IMAGES`
(Website v4 draws pictures in its own job), `MESSAGING_SANDBOX`, and every
`XAI_*` / `AI_PROVIDER=grok` / `IMAGE_PROVIDER=xai` (no longer read).

### locah-worker

| | |
|---|---|
| Dockerfile | `infra/docker/Dockerfile.worker` |
| Build | as the API |
| Start | `uv run python -m platform_worker.main` (`UV_NO_SYNC=1`) |
| Health check | none on Railway (no HTTP port); healthy = logs show `worker.polling` then regular `worker.*_processed`; `API/health/worker` returns 503 when the outbox lags |
| Watch paths | `apps/worker/**`, `python/**`, `infra/docker/Dockerfile.worker`, `pyproject.toml`, `uv.lock` |
| Domain | none |
| Depends on | Supabase Postgres (direct `postgres` role — cross-tenant jobs), Storage, Gemini |

The worker runs `website.generate` (creative plan + Gemini pictures),
`interview.read_document` (menu / catalogue reading), `interview.generate_logo`,
automations, WhatsApp/booking/membership ladders, AI employee sweeps.

Secrets: `DATABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`, **`GEMINI_API_KEY`**
(required here too — without it every website is text-led and no document is
read), `WEBSITE_PREVIEW_SECRET`.
Config: `ENVIRONMENT=production`, `SUPABASE_URL`, `AI_PROVIDER=gemini`,
`IMAGE_PROVIDER=gemini`, `VOICE_PROVIDER=gemini`, optional `GEMINI_*` pins as
the API, `WORKER_POLL_INTERVAL_SECONDS=2`.
Absent: the same list as the API.

### locah-web

| | |
|---|---|
| Dockerfile | `infra/docker/Dockerfile.web` |
| Build | `pnpm install --frozen-lockfile` then `pnpm --filter @platform/web... build` |
| Start | `pnpm --filter @platform/web exec next start -H 0.0.0.0 -p $PORT` |
| Health check | `/` answers 200 |
| Watch paths | `apps/web/**`, `packages/**`, `infra/docker/Dockerfile.web`, `pnpm-lock.yaml`, `pnpm-workspace.yaml`, `package.json` |
| Domain | `locah-web-production.up.railway.app` (custom: `<platform-domain>` and `{slug}.<platform-domain>`) |

Public build variables only (inlined into the browser at build time — a change
needs a rebuild): `NEXT_PUBLIC_API_URL`, `NEXT_PUBLIC_WEB_URL`,
`NEXT_PUBLIC_WORKSPACE_URL`, `NEXT_PUBLIC_SUPABASE_URL`,
`NEXT_PUBLIC_SUPABASE_ANON_KEY`, `NODE_ENV=production`.
**No** `GEMINI_API_KEY`, no `SUPABASE_SERVICE_ROLE_KEY`, no `DATABASE_URL`,
nothing AI under `NEXT_PUBLIC_*`.

### locah-workspace

As `locah-web` with `infra/docker/Dockerfile.workspace`,
`pnpm --filter @platform/workspace... build`, start
`pnpm --filter @platform/workspace exec next start …`, watch
`apps/workspace/**` (+ the shared paths), domain
`locah-workspace-production.up.railway.app` (custom: `app.<platform-domain>`).
Same public-only variables; same prohibitions.

## Domains and sign-in

- Railway's generated `*.up.railway.app` hosts are **separate sites to the
  browser**: one sign-in cannot be shared between web and Workspace there. Sign
  in on each. Tenant websites are served at `WEB/<slug>`.
- With a custom registrable domain: `<domain>` web, `app.<domain>` Workspace,
  `api.<domain>` API, `{slug}.<domain>` tenant sites; set `PLATFORM_DOMAIN` and
  `NEXT_PUBLIC_PLATFORM_DOMAIN`, then Supabase Auth → URL configuration.
  Buying or wiring a domain is the owner's decision.
- Supabase Auth → URL configuration must list the web and Workspace origins as
  redirect URLs.

## Post-deploy smoke (deployed URLs, not localhost)

1. `API/health/live` 200; `API/health/ready` → `database: connected`.
2. Worker logs: `worker.starting`, `worker.db_connected`, `worker.polling`.
3. `WEB/` and `WS/` load; sign-in works on both.
4. Create a business → Talk to LOCAH (one message) → recommendations → enable →
   Build. API/worker logs show `ai.gemini.completed`; the job has
   `creative_strategy: ai`, `media_drawn > 0`.
5. The hero picture URL is a Supabase Storage URL and loads on the public site.
6. Editor → Hero → Generate a picture (manual) works.
7. One menu/catalogue upload is read (`interview.read_document`).
8. One booking, one order, one payment request / pay-at-business, one kitchen
   ticket, one automation with its Activity row, one AI Receptionist answer,
   one escalation, one customer My Activity view.

If Gemini answers **402**: `GOOGLE_BILLING_DEPLETED` — top up the Google
project; stop paid tests; do not debug website code. One refused request is
one call (no fallback loop).

## Remove / never set

`XAI_API_KEY`, `XAI_MODEL`, `XAI_IMAGE_MODEL`, `XAI_VOICE`, `XAI_VOICE_MODEL`,
`AI_PROVIDER=grok`, `IMAGE_PROVIDER=xai`, `AUTO_GENERATE_WEBSITE_IMAGES`,
`LOCAH_TEST_NO_EXTERNAL_AI`, `MESSAGING_SANDBOX`, any server secret on web or
Workspace.
