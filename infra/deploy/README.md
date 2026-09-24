# Railway deployment runbook

LOCAH's hosted runtime is Railway. Supabase remains the managed database and
authentication provider. GitHub `main` is the only source Railway should build.

## 1. Current service shape

| Railway service | Purpose |
| --- | --- |
| `locah-web` | Public platform, Marketplace, auth and tenant websites |
| `locah-workspace` | Business Workspace |
| `locah-api` | FastAPI application |
| `locah-worker` | Outbox, notifications, generation jobs and scheduled work |

The Admin app remains a distinct application in the monorepo but is not exposed
as a public Railway service yet.

Do not upload an arbitrary local build to Railway. Push a reviewed commit to
GitHub and let each linked Railway service build that commit. This keeps the
deployed source reproducible for every collaborator.

## 2. Local development

The three frontend applications are separate product surfaces, not three copies
of the public website:

| Command | URL |
| --- | --- |
| `pnpm dev` or `pnpm dev:web` | Public web at `http://localhost:3000` |
| `pnpm dev:workspace` | Workspace at `http://localhost:3001` |
| `pnpm dev:admin` | Admin at `http://localhost:3002` |
| `pnpm dev:all` | All three surfaces |

Stop an existing server before switching branches or worktrees. A running
`next start` process keeps serving the build from the directory where it was
launched, even after another checkout is pulled.

## 3. Database migrations and seed

Apply forward-only migrations before deploying code that requires them:

```sh
npx supabase db push
```

The seed is separate and idempotent:

```sh
psql "$DATABASE_URL" -f infra/supabase/seed/00_platform.sql
```

It populates the module and website-section registries. A deployment that skips
the seed can start successfully while still failing at runtime.

## 4. RLS role provisioning

Migration `20260802000000_stage7_rls_role_separation.sql` creates the
`platform_api` login role without a password. Set a strong password outside
Git, then configure only `locah-api` with:

```
API_DATABASE_URL=postgresql://platform_api.<project-ref>:<password>@<pooler-host>:5432/postgres
```

The API uses the RLS-enforcing role. The worker and migrations keep
`DATABASE_URL` because they legitimately perform cross-tenant work.

## 5. Railway variables

Server secrets belong only on `locah-api` and, when provider jobs run there,
`locah-worker`. Never expose server secrets through `NEXT_PUBLIC_*`.

Each frontend uses Railway-injected public origins. For the current generated
domains, configure the API allowlist with the web and Workspace origins. When a
custom registrable domain is available, set:

```
PLATFORM_DOMAIN=<domain>
NEXT_PUBLIC_PLATFORM_DOMAIN=<domain>
```

and remove per-surface URL overrides where the derived origins are correct.

`RATE_LIMIT_TRUST_XFF=1` is required on `locah-api` because Railway is the
trusted reverse proxy.

## 6. Platform domain

The canonical production shape remains:

| Host | Serves |
| --- | --- |
| `<domain>` | Public platform |
| `app.<domain>` | Workspace |
| `admin.<domain>` | Super Admin |
| `api.<domain>` | API |
| `{slug}.<domain>` | Tenant website |

A shared login across surfaces requires one registrable domain. Railway's
generated per-service domains are useful for staging, but a browser cannot use
one parent session cookie across unrelated customer service hosts.

Configure all custom domains and DNS in Railway, then update Supabase
Authentication URL Configuration and regenerate the email templates:

```sh
PLATFORM_DOMAIN=<domain> pnpm email:templates
```

## 7. API authentication

The API verifies hosted Supabase ES256 tokens through the project's JWKS URL, so
`SUPABASE_URL` is required and outbound HTTPS must be available. The optional
`SUPABASE_JWT_SECRET` supports legacy HS256 tokens still within their TTL.

## 8. Worker health

`locah-worker` must run continuously. `/health/worker` returns 503 when the
oldest pending outbox event exceeds `WORKER_LAG_THRESHOLD_SECONDS`; that is an
operational alarm, not a reason to bypass the queue.

## 9. Backup and restore

Supabase provides managed backups, but LOCAH still needs a documented restore
drill, recovery-time objective and named owner before the launch gate is closed.
