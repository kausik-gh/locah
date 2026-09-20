# Deploy runbook

Everything a real (hosted / production-like) deploy needs beyond `git pull`.
Local dev setup is in the repo root `README` / `.env.example`; this file is the
things that bite you on a fresh environment.

## 1. Migrations

```
npx supabase db push        # applies infra/supabase/migrations/* in order
```

`supabase db push` does **not** run the seed. See step 2.

## 2. Seed (separate step — NOT part of db push or db reset)

```
psql "$DATABASE_URL" -f infra/supabase/seed/00_platform.sql
```

`00_platform.sql` is idempotent (`ON CONFLICT DO NOTHING`). It populates:

| table | rows | what |
|---|---|---|
| `module_definitions` | 21 | the full optional-module registry |
| `website_section_types` | 13 | website section schemas |

A deploy that skips this has an empty module catalog and website rendering
fails. `db reset` locally *does* run it (it's wired into the Supabase local
flow); hosted/prod deploys do not — run it by hand.

## 3. RLS role provisioning (AUD-02) — required for §21.1 gate 2

Migration `20260802000000_stage7_rls_role_separation.sql` creates the
`platform_api` login role (NOBYPASSRLS) but does **not** set its password
(migrations are in git). After `db push`:

```sql
ALTER ROLE platform_api PASSWORD '<generate a strong one>';
```

Then set, in the API process environment only (never the worker, never a
client bundle):

```
API_DATABASE_URL=postgresql://platform_api.<project-ref>:<password>@<pooler-host>:5432/postgres
```

- The **API** connects with this (`create_worker_session_factory(role="user")`).
  Every query is subject to the row-level policies.
- The **worker** and **migrations** keep `DATABASE_URL` (the `postgres` role,
  which bypasses RLS) — they legitimately cross tenant boundaries.
- If `API_DATABASE_URL` is unset, the API falls back to `DATABASE_URL` and RLS
  is inert (the pre-AUD-02 behaviour). The app still runs; it is just not
  enforcing. `/health/ready` does not distinguish these — check
  `SELECT rolbypassrls FROM pg_roles WHERE rolname = current_user` on the API's
  connection if in doubt.

## 4. Worker process

```
PYTHONPATH=apps/worker/src python -m platform_worker.main
```

Needed for: outbox event processing, notification fan-out, website generation
jobs, scheduled job materialisation.

> **Not currently deployed.** `render.yaml` declares `locah-worker`, but the
> Render account has only `locah-api`. Nothing drains the outbox in production:
> as of 2026-09-20 the backlog was ~9,900 pending events with nothing older than
> 2026-09-18 07:52 ever processed. Most of that is test-suite residue, but the
> consequence for a real signup is the same — the AI website generation job
> never runs, so every new business keeps the deterministic fallback site, and
> notification fan-out and marketplace re-indexing never fire either. Creating
> the service is a founder step: Render does not offer background workers on the
> free plan the API currently runs on.

`/health/worker` returns 503 while the outbox backlog age exceeds
`WORKER_LAG_THRESHOLD_SECONDS` (default 300) — that is the gate working, not a
fault; it clears once the worker catches up.

## 5. Platform domain (FL-DEC-016)

One registrable domain, surfaces on subdomains of it. Document 10 §12 fixes this
shape; the only open part was ever the name.

| Host | Serves |
|---|---|
| `<domain>` | public platform: marketing, Marketplace, auth |
| `app.<domain>` | Business Workspace |
| `admin.<domain>` | Platform Super Admin |
| `api.<domain>` | FastAPI |
| `{slug}.<domain>` | each Business's own website |

### Why it is not optional

The session cookie is scoped by registrable domain. With every surface under one
domain, a cookie carrying `Domain=.<domain>` covers all of them and a person
signs in once. Three separate `*.vercel.app` hostnames cannot do this at all:
`vercel.app` is on the Public Suffix List, so the browser refuses a cookie
scoped to it. That is not a limitation to work around — it is the reason
Workspace is unreachable after signing in on the public app today.

`resolvePlatformOrigins()` (`packages/config/src/platform-origins.ts`) refuses a
domain that cannot carry a shared cookie rather than setting one the browser
will discard, because a discarded cookie fails silently and looks like a
sign-in that did not work.

### What must be done outside the repository

1. **Register the domain.** Nothing else here can proceed without it.
2. **Add it to each Vercel project** (`locah-web` → apex + `www`,
   `locah-workspace` → `app`, `locah-admin` → `admin`) and create the DNS
   records Vercel shows for each.
3. **Wildcard for Business websites.** Add `*.<domain>` to the `locah-web`
   project and a `CNAME *` record. Without it, Business sites stay on the
   `/{slug}` path form — which still works, just not at the canonical address.
4. **API.** Point `api.<domain>` at the Render service and add the custom domain
   there.
5. **Supabase → Authentication → URL Configuration.** Site URL `https://<domain>`,
   and add `https://<domain>/**`, `https://app.<domain>/**`,
   `https://admin.<domain>/**` to Redirect URLs. Email confirmation does not
   depend on this (the templates carry absolute links), but password reset and
   any future OAuth do.
6. **Re-render the email templates** for the new origin and paste them in:

   ```
   PLATFORM_DOMAIN=<domain> pnpm email:templates
   ```

   Output lands in `infra/supabase/email-templates/dist/` (gitignored).

### What to set in each environment

Set on all three Vercel projects **and** the API/worker:

```
PLATFORM_DOMAIN=<domain>
NEXT_PUBLIC_PLATFORM_DOMAIN=<domain>
```

Then **remove** `NEXT_PUBLIC_WEB_URL`, `NEXT_PUBLIC_WORKSPACE_URL`,
`NEXT_PUBLIC_ADMIN_URL` and `NEXT_PUBLIC_API_URL` from those projects. They are
per-surface overrides and they win over the derived values — left in place
pointing at `*.vercel.app`, they keep the old split-session behaviour even after
the domain is live. `CORS_ALLOWED_ORIGINS` also becomes unnecessary: the API
derives its allowlist, including `{slug}.<domain>`, from `PLATFORM_DOMAIN`.

Local development needs no change. `localhost` is not a registrable domain, so
no cookie domain is issued, and `localhost:3000` / `:3001` / `:3002` already
share cookies because a cookie's scope ignores the port.

### Verifying it worked

Sign in on `https://<domain>/login`, then open `https://app.<domain>`. It must
show the Workspace, not a sign-in form. If it shows a sign-in form, check the
`Set-Cookie` on the sign-in response: it should carry `Domain=.<domain>`. No
domain attribute means `NEXT_PUBLIC_PLATFORM_DOMAIN` did not reach the build, or
a per-surface override above is still set.

## 6. Frontend env

Each Next app (`apps/web`, `apps/workspace`, `apps/admin`) loads `.env` from
**its own directory**, not the repo root. Provide `NEXT_PUBLIC_API_URL`,
`NEXT_PUBLIC_WEB_URL`, `NEXT_PUBLIC_SUPABASE_URL`,
`NEXT_PUBLIC_SUPABASE_ANON_KEY` per app (or via your platform's env injection).

## 7. API auth / JWT verification

The API verifies Supabase access tokens in dual mode (`platform_api.jwt_verify`):

- **ES256 / asymmetric** (the hosted project's current signing key) — verified
  against the JWKS public keys at `<SUPABASE_URL>/auth/v1/.well-known/jwks.json`.
  **`SUPABASE_URL` must be set** in the API environment, and the API process
  needs outbound HTTPS to `*.supabase.co`. Keys are cached in-process
  (300s) and warmed at startup.
- **HS256 / legacy** — verified with `SUPABASE_JWT_SECRET` (the *Legacy JWT
  Secret* from the dashboard, not the Key ID). Covers pre-migration tokens still
  in their TTL. Optional if the project has fully migrated.

A token whose `alg` has no configured verifier → 401 plus a
`jwt.verifier_misconfigured` WARN log.

## 8. Backup / restore

**Not yet documented — blocked on a founder decision** (recovery-time
objective, who owns running the restore drill). Supabase provides managed
backups at the platform level; a *tested* restoration procedure with an RTO
does not exist and is a Doc 11 §21.1 gate that stays open until that decision
is made.
