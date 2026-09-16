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
jobs, scheduled job materialisation. `/health/worker` returns 503 while the
outbox backlog age exceeds `WORKER_LAG_THRESHOLD_SECONDS` (default 300) — that
is the gate working, not a fault; it clears once the worker catches up.

## 5. Frontend env

Each Next app (`apps/web`, `apps/workspace`, `apps/admin`) loads `.env` from
**its own directory**, not the repo root. Provide `NEXT_PUBLIC_API_URL`,
`NEXT_PUBLIC_WEB_URL`, `NEXT_PUBLIC_SUPABASE_URL`,
`NEXT_PUBLIC_SUPABASE_ANON_KEY` per app (or via your platform's env injection).

## 6. API auth / JWT verification

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

## 7. Backup / restore

**Not yet documented — blocked on a founder decision** (recovery-time
objective, who owns running the restore drill). Supabase provides managed
backups at the platform level; a *tested* restoration procedure with an RTO
does not exist and is a Doc 11 §21.1 gate that stays open until that decision
is made.
