# LOCAH Supabase and Database Audit — 2026-09

Audit snapshot: 2026-09-23, Supabase project `pmwyaqmwxfbnfulqbqmk` (`ap-south-1`, PostgreSQL 17.6.1).

This was an audit-first pass. No users, tenants, rows, buckets, files, tables, indexes, policies, or extensions were deleted. Counts are a point-in-time snapshot; another test process was still adding rows during the audit.

## Executive Summary

The LOCAH data model is structurally recognizable and mostly aligned with the canonical architecture. All 79 application tables can be traced to repository migrations and either ORM models, server services, worker SQL, or the implementation blueprint. Business is consistently the tenant key and Location remains subordinate. An automated check of 81 same-tenant foreign-key relationships found zero cross-Business rows.

The live project was not safe at the start of the audit. Eight internal queue/audit/idempotency tables had RLS disabled while Supabase default grants gave both `anon` and `authenticated` every table privilege. Anonymous REST reads returned real rows from seven of the eight tables. Five `SECURITY DEFINER` functions were also executable by browser-facing roles. The affected audit/event JSON includes PII-bearing fields and token-like keys, so this was a real exposure rather than a linter-only warning.

The other dominant problem is test pollution. The generic `DATABASE_URL` was accepted by integration tests, allowing the deployed database to become the test database. Of 12,759 Auth users, 12,752 match explicit automation/test patterns. There are 9,802 Businesses, 9,770 soft-deleted, and 588,237 rows across 64 Business-scoped tables still linked to those deleted tenants. This is data pollution, not evidence that the schema objects are obsolete.

Summary counts:

| Item | Count / state |
|---|---:|
| Project base tables, all inspected schemas | 119 |
| Application tables in `public` | 79 |
| Public views/materialized views | 0 / 0 |
| App-defined public functions | 10 |
| Extension-owned public functions | 188 (`btree_gist`) |
| Public table policies | 146 |
| RLS-enabled public tables | 71 |
| RLS-disabled public tables | 8 |
| Actually exposed internal tables before remediation | 8 |
| Externally executable `SECURITY DEFINER` functions before remediation | 5 |
| Proven legacy/deletion candidates | 0 |
| Review candidates (no deletion approved) | 3 |
| Storage objects without a `media_assets` row | 4 |
| Ready media rows without a real object | 62 (all point at the test host `example.supabase.co`) |
| Cross-Business relationship mismatches | 0 across 81 checked relationships |
| Unresolved dead-letter rows | 179 |

## Critical Findings

### 1. Internal platform tables were anonymously reachable

The following server-only tables had RLS disabled and direct `anon`/`authenticated` privileges for `SELECT`, `INSERT`, `UPDATE`, `DELETE`, `TRUNCATE`, `REFERENCES`, and `TRIGGER`:

- `idempotency_records`
- `platform_async_jobs`
- `platform_audit_events`
- `platform_dead_letter_events`
- `platform_event_deliveries`
- `platform_outbox_events`
- `platform_processed_events`
- `platform_scheduled_jobs`

Anonymous REST verification returned HTTP 200/206 and these exact totals at the time of testing: 12,480 async jobs, 83,771 audit events, 179 dead letters, 4,066 event deliveries, 68,960 outbox events, 12,394 processed-event rows, and 30 scheduled jobs. `idempotency_records` was reachable but empty.

Root cause: migrations intentionally disabled RLS for cross-tenant server infrastructure, but project-level default privileges separately granted browser roles full access. RLS being disabled is not itself the defect; combining that design with Data API grants is.

### 2. Five privileged functions were public RPC endpoints

`handle_new_auth_user`, `resolve_activity_business_names`, `resolve_muted_identities`, `resolve_order_business_id`, and `rls_auto_enable` are `SECURITY DEFINER`. They were executable by `anon` and `authenticated`; four also inherited `EXECUTE` from `PUBLIC`. The three resolver functions bypass RLS intentionally for narrow server operations, which makes direct browser execution inappropriate.

### 3. Production was used as an integration-test database

`apps/api/tests/conftest.py` deliberately disabled paid providers and made jobs inert, but did not restrict database selection. More than one hundred DB-writing tests use `DATABASE_URL` directly. That explains the observed sequence of test-shaped Auth users, soft-deleted Businesses, module/entitlement fan-out, generated website rows, audit events, outbox events, and background jobs.

The data itself corroborates the code finding:

- 12,752 / 12,759 Auth users match test/automation naming patterns.
- 12,691 Auth users were created in the preceding seven days; 1,621 in the preceding 24 hours.
- 9,744 Businesses were created in seven days; 1,296 in 24 hours.
- 9,770 / 9,802 Businesses are soft-deleted.
- 116,688 module-state rows and 97,700 entitlement rows belong to deleted Businesses.
- 68,131 outbox events and 83,004 audit events belong to deleted Businesses.

## Database Inventory

The machine-readable master inventory is [supabase-object-inventory.csv](./supabase-object-inventory.csv). It records every public application table, all ten app-defined public functions, the public-schema extension, and the media bucket.

Domain coverage is consistent with the staged LOCAH plan: identity, Business and membership, Location/people, website, marketplace projections, offerings/inventory, CRM/leads, orders/checkout, fulfilment, workforce/bookings, memberships, payments, quotations/projects, notifications, and platform infrastructure.

No public view or materialized view exists. There are 36 distinct application trigger names, no application sequence, and no application enum. Supabase-managed schemas contain another 40 base tables: Auth 27, Storage 8, Realtime 3, migrations 1, and Vault 1.

## RLS / Grants Audit

All 79 public tables had direct grants to `anon`, `authenticated`, and `service_role`. Each of those roles had all seven table privileges on every table. `platform_api` had CRUD on all 79.

For the 71 RLS-enabled tables:

- 146 policies exist.
- 64 tables have a policy applicable to `PUBLIC` (therefore both anonymous and authenticated roles).
- 63 policies are `SELECT TO public`.
- 58 policies are `ALL TO platform_api`.
- Eight legacy website/profile/media policies are `ALL TO public` and tenant-scope with `current_business_id()`.
- `FORCE ROW LEVEL SECURITY` is enabled on the 71 protected tables.

The broad browser grants are unnecessary for the current frontend architecture: repository search found Supabase clients used for Auth, while business data goes through the FastAPI server. They are not immediately revoked project-wide because that is a broad contract change. A dedicated non-exposed API schema or explicit least-privilege grants should be designed and tested first.

Supabase advisor results after the read-only audit:

- 8 `rls_disabled_in_public` errors (the internal tables above).
- 5 mutable-function-search-path warnings.
- 1 extension-in-public warning.
- 5 anonymous and 5 authenticated `SECURITY DEFINER` execution warnings.
- leaked-password protection disabled.
- 3 RLS init-plan warnings.
- 103 multiple-permissive-policy warnings.

The migration in this pass revokes browser table/RPC grants. It deliberately does not invent tenant RLS policies for cross-tenant worker tables.

Live remediation verification:

- migration `20260923113433_restrict_internal_platform_objects` applied successfully;
- `anon` and `authenticated` now have no CRUD privilege on any of the eight internal tables;
- `platform_api` and `service_role` retain CRUD on all eight;
- `anon` and `authenticated` can no longer execute any of the five privileged functions;
- the three resolver functions retain `platform_api` execution;
- row totals for async jobs, audit events, outbox events, and deliveries were unchanged by the migration;
- the post-migration Security Advisor no longer reports RLS-disabled/exposed-table or public `SECURITY DEFINER` findings. Remaining advisor categories are five mutable search paths, one extension in public, and leaked-password protection disabled.

## Unrestricted Objects

Before remediation there were exactly eight unrestricted private tables and five unrestricted privileged functions. The tables are active server infrastructure, not cleanup candidates. Runtime references exist in:

- `apps/worker/src/platform_worker/claiming.py`
- `apps/worker/src/platform_worker/job_runner.py`
- `apps/worker/src/platform_worker/outbox_consumer.py`
- `apps/worker/src/platform_worker/scheduler.py`
- `python/core/platform_core/services/async_jobs.py`
- `apps/api/src/platform_api/routers/v1_admin.py`

`idempotency_records` is canonical in Document 12 and its migration but is empty and has no current table-level runtime reference. It remains in place pending a product/architecture decision.

## Tenant Isolation

Business is the tenant throughout the application schema. Sixty-nine non-Business tables carry `business_id`; Location-scoped records also retain Business ownership. A dynamic audit checked every foreign-key relationship where both child and parent expose `business_id`: 81 relationships, zero mismatched rows.

Additional integrity results:

- zero platform identities without an Auth user;
- zero Locations without a Business;
- zero Websites without a Business;
- zero active Businesses without an active `primary_owner` membership;
- zero Business/primary-owner identity mismatches;
- zero duplicate active slugs;
- zero duplicate Business profiles or Websites.

One duplicate slug exists only across soft-deleted rows. This is expected because `businesses_slug_active_key` is intentionally unique only where `deleted_at IS NULL`, permitting slug reuse after deletion.

Tenant isolation in stored data looks sound. Database enforcement is incomplete for some same-tenant foreign-key pairs because they use independent single-column foreign keys rather than composite `(business_id, id)` constraints; application services currently enforce the invariant. No automatic constraint rewrite is recommended without staged migration and load testing.

## Service Role Usage

Privileged database access is intentionally split:

- `DATABASE_URL`: service/Postgres connection, `BYPASSRLS`; worker, migrations, payment webhook, and gated super-admin support.
- `API_DATABASE_URL`: `platform_api`, no `BYPASSRLS`; normal API requests bind `app.current_business_id` and `app.current_identity_id` GUCs.
- `SUPABASE_SERVICE_ROLE_KEY`: server-side Storage operations in `supabase_storage.py`.

This split matches the canonical server-authoritative design. The principal defect was allowing Data API browser roles to share privileges intended for server roles.

The fallback from `API_DATABASE_URL` to `DATABASE_URL` keeps deployments running but silently disables the intended RLS enforcement if the API-specific connection is absent. Deployment configuration should treat `API_DATABASE_URL` as required in production and fail readiness when missing.

## Functions / RPC

There are ten application-owned public functions. Five are `SECURITY DEFINER`; all five use a fixed search path. The five invoker functions flagged for mutable search path are `current_business_id`, `current_identity_id`, `set_updated_at`, `update_business_search_vector`, and `update_offering_search_vector`.

`btree_gist` is installed in `public` and owns 188 additional functions there. This is why the raw public-routine count is much higher than the application-function count. Moving the extension to `extensions` is desirable but not safe to do casually because GiST indexes and operator-class dependencies must be preserved.

## Storage

One bucket exists:

| Bucket | Public | Objects | Recorded bytes | Limit | MIME allowlist |
|---|---:|---:|---:|---:|---|
| `media` | yes | 88 | 208,085,198 | 10 MiB/object | JPEG, PNG, WebP, GIF |

Policies allow public reads and authenticated insert/update/delete only when the first path segment equals `auth.uid()`. Service-generated media uses the `generated/` prefix via the service role.

Integrity findings:

- 4 Storage objects have no `media_assets` record.
- 62 `ready` media rows have no Storage object; all point to `example.supabase.co` and are proven test fixtures/placeholders.
- 67 pending and 31 failed media rows have no object, which is compatible with incomplete/failed generation states.
- 189 media rows belong to soft-deleted Businesses; 89 of those are `ready`.

No object or media row was removed. Cleanup must first partition records by proven test tenant and verify published website references.

## Auth / Test Accounts

Auth contains 12,759 users. The audit did not output email addresses, tokens, password hashes, or credentials. Pattern-only analysis identified 12,752 test/automation-like accounts and seven accounts outside those patterns.

The repository ignores environment files and tracks only `.env.example`. A format-based scan of tracked files found three intentionally synthetic voice-test secret fixtures and no deployable credentials. A commit-history `-G` scan found no matching provider-key formats. `gitleaks` is not installed, so this is strong targeted evidence, not a claim of a complete entropy-based secret scan.

Supabase Auth leaked-password protection is disabled. Enable it in project Auth settings. Backup/PITR status could not be read through the available Supabase connector and remains a manual dashboard verification item.

## Data Model vs Canonical LOCAH Architecture

Aligned:

- Business is the tenant; Location is subordinate.
- Website content is structured as Websites → Versions → Pages → Sections.
- Platform billing/entitlements and merchant payment connections/attempts are separate.
- Server API and worker communicate through contracts/events and shared core packages.
- RLS is defense in depth for request-path tables; the server remains authoritative.
- BusinessBlueprint is embedded at `businesses.metadata.interview`, versioned with `schema_version = 1` and tenant-bound by `business_id`.

BusinessBlueprint live-state audit:

- 47 Businesses contain an interview Blueprint; 15 are active and 32 soft-deleted.
- all 47 use schema version 1;
- zero embedded Business IDs mismatch the owning row;
- completion: 18 collecting, 13 review, 16 built;
- average serialized size 7,037 bytes; maximum 21,891 bytes;
- zero unknown top-level keys relative to the current Pydantic model.

Divergences/risks:

- internal worker tables remain in the Data API-exposed `public` schema;
- default grants are broader than the server-authoritative frontend requires;
- `API_DATABASE_URL` has a bypass-role fallback;
- both `business_employees*` and `workforce_*` are live. The former remains referenced by employee services while newer booking/project/provider paths use workforce, so this is an overlap to resolve—not a safe duplicate to drop.

## Code Usage Mapping

DB → code:

- 74 tables have SQLAlchemy models in `python/core/platform_core/models.py`.
- Four worker infrastructure tables are consumed through explicit SQL in the worker and platform services.
- `idempotency_records` is migration/blueprint-defined but currently dormant.
- all public tables originate in `infra/supabase/migrations`.

Code → DB:

- Web/Workspace business-data calls use the API; repository search found no browser `.from(...)`/RPC access to application tables.
- Supabase browser/server clients are used for Auth flows.
- Storage writes use the service-role adapter.
- Resolver `SECURITY DEFINER` functions are called by server services over `platform_api`, not by browser code.

## Duplicate / Legacy / Unused Candidates

No table is proven safe to delete.

Review candidates:

1. `idempotency_records` — canonical but empty and without a current runtime table reference. Decide whether upcoming checkout idempotency still requires it.
2. `business_employees` — active service/model references but overlapping concepts with `workforce_members`.
3. `business_employee_location_assignments` — active service/model references but overlapping concepts with `workforce_location_assignments`.

The two employee pairs cannot be merged or dropped until routes, consumers, migration/backfill semantics, and historical IDs are reconciled.

## Test Data Pollution

The polluted graph is large but well-bounded by test accounts and soft-deleted Businesses:

- 9,770 soft-deleted Businesses;
- 588,237 rows in 64 Business-scoped tables linked to deleted Businesses;
- 116,688 module states;
- 97,700 commercial entitlements;
- 83,004 audit events;
- 77,567 website sections;
- 68,131 outbox events;
- 37,665 website pages;
- 16,988 website versions;
- 12,246 async jobs;
- 11,383 memberships;
- 9,937 Locations;
- 9,770 profiles and 9,770 Websites.

The correct cleanup unit is the proven test tenant graph, not table-by-table truncation. Before deletion, export IDs, exclude the seven non-pattern Auth accounts and all 32 active Businesses unless independently proven test-owned, validate Storage references, then delete through a reviewed migration/runbook in dependency order.

## Orphans

| Check | Result |
|---|---:|
| Identity without Auth user | 0 |
| Location without Business | 0 |
| Website without Business | 0 |
| Active Business without primary owner | 0 |
| Cross-Business FK mismatch | 0 |
| Storage object without media row | 4 |
| Ready media row without object | 62 test placeholders |
| Unresolved dead-letter event | 179 |
| Website job stuck `running` | 26, all linked to deleted Businesses |
| Website job pending | 3, all linked to deleted Businesses |

Rows linked to soft-deleted Businesses are retained dependents, not referential orphans.

## Index / Performance Findings

Supabase reports:

- 256 public indexes;
- zero invalid indexes;
- 104 foreign keys without a covering index;
- 40 currently unused indexes;
- 103 multiple-permissive-policy warnings;
- 3 Auth/RLS init-plan warnings.

Do not bulk-add or drop indexes from advisor counts alone. Most tables are test-polluted and statistics reflect synthetic workload. Prioritize real hot paths after cleanup. `pg_stat_statements` shows the worker claim updates as the dominant workload: approximately 82,691 outbox-claim calls and 85,300 async-job-claim calls. Database cache hit was 99.99%; current connections were 22/60 (14 idle, 1 active at snapshot).

The application schema occupies roughly 341 MB when the earlier aggregate double-counts index relations; `pg_database_size` was about 291 MB and is the reliable whole-database figure. The largest individual tables including indexes were outbox (~42 MB), audit (~40 MB), entitlements (~32 MB), module states (~31 MB), and website sections (~29 MB).

## Schema Drift / Migration Problems

Repository/live migration history is not aligned:

- repository before this pass: 40 SQL migrations;
- live history: 36 entries;
- four live migrations have deployment-time versions that differ from repository filenames (`generation_provider_usage`, `booking_management_token_rls`, `projects_and_work_orders`, `website_expressive_sections`);
- four repository migrations have no matching history row (`event_subscription_registry`, `bookable_resource_foundation`, `quotations`, `quote_share_token_rls`) although their objects/columns exist live.

This indicates DDL was applied through tooling that generated different history timestamps and/or bundled changes outside the repository filename sequence. Do not repair history blindly: first dump live schema, diff against a clean replay, then use `migration repair` only with a reviewed mapping.

The configured Supabase CLI is 2.90.0 while 2.117.0 is available. Upgrade in a dedicated tooling change after validating command behavior.

## Cleanup Plan

### SAFE NOW

- Revoked browser-facing privileges from the eight internal tables while preserving `platform_api` and `service_role`.
- Revoked public/browser execution from the five `SECURITY DEFINER` helpers while preserving explicit server grants.
- Added a fail-closed guard when tests see a remote generic `DATABASE_URL`; remote suites now require `TEST_DATABASE_URL`.
- Keep paid AI providers disabled in automated tests.
- Produce and preserve this audit/inventory snapshot.

### REQUIRES MIGRATION

- Build a reviewed test-tenant purge migration/runbook with export, dry-run counts, FK order, and rollback plan.
- Reconcile migration history against a fresh schema replay.
- Add only high-value missing FK indexes supported by production query plans.
- Fix RLS init-plan patterns and consolidate permissive policies table by table.
- Move server-only infrastructure to a non-exposed schema if repository SQL and worker deployment are migrated together.
- Hash public access/management/tracking tokens at rest where equality lookup is sufficient; preserve one-time plaintext delivery semantics.

### REQUIRES PRODUCT DECISION

- Retention period for audit/outbox/processed/dead-letter data.
- Whether soft-deleted tenant data is retained, archived, or purged.
- Whether `business_employees*` is deprecated in favor of `workforce_*`.
- Whether `idempotency_records` remains part of Stage 1 checkout design.
- Whether tenant media remains globally public or moves to signed URLs.

### DO NOT TOUCH

- the seven non-pattern Auth accounts;
- the 32 active Businesses without explicit test provenance;
- BusinessBlueprint JSON;
- published website rows and referenced media;
- payment/audit records subject to retention requirements;
- `btree_gist` or any dependent index;
- RLS policy semantics without endpoint-by-endpoint authorization tests.

## Recommended Migration Order

1. Stop recurrence with the test-database guard.
2. Restrict the eight internal tables and five privileged functions.
3. Verify API, worker, Auth bootstrap, queue processing, and anonymous denial.
4. Reconcile live/repository migration history.
5. Create a dedicated isolated test database/branch and run the full suite there.
6. Export and dry-run the proven test-tenant cleanup set.
7. Purge test data in dependency order only after approval.
8. Re-analyze tables and re-measure query/index behavior.
9. Address policy/index/extension improvements in small migrations.

## Risk Matrix

| Severity | Finding | State |
|---|---|---|
| CRITICAL | 8 server-internal tables reachable by anonymous Data API roles | Fixed live; browser CRUD privileges are now false on all eight |
| HIGH | 5 `SECURITY DEFINER` functions callable as public RPC | Fixed live; anonymous/authenticated execution is now false |
| HIGH | Tests can target deployed DB through generic `DATABASE_URL` | Fail-closed guard added and unit-tested |
| HIGH | 12,752 test-like Auth users and 588,237 deleted-tenant dependents | Not deleted; requires approved runbook |
| HIGH | Migration history differs from repository | Requires controlled reconciliation |
| MEDIUM | Audit/event data contains email/phone/token-like JSON keys | Exposure removed by grant fix; retention/redaction review remains |
| MEDIUM | 62 ready media placeholders and 4 untracked objects | Requires reference-aware cleanup |
| MEDIUM | 104 unindexed FKs; synthetic workload distorts priorities | Reassess after cleanup |
| MEDIUM | Auth leaked-password protection disabled | Dashboard configuration change |
| LOW | `btree_gist` installed in public | Move only with dependency-tested migration |

## Proposed Follow-up Work

1. Provision a dedicated Supabase test branch/project and set `TEST_DATABASE_URL` / `TEST_API_DATABASE_URL` in CI only.
2. Run a clean migration replay and schema diff against production.
3. Prepare a read-only SQL export of the exact test-user/test-Business graph for owner approval.
4. Add retention policy tables/configuration for outbox, processed events, audit, dead letters, and soft-deleted tenants.
5. Add authorization integration tests for every public endpoint and direct Data API denial tests.
6. Require `API_DATABASE_URL` in deployed API readiness.
7. Enable leaked-password protection and verify backup/PITR status in the Supabase dashboard.
8. Re-run Supabase Security and Performance Advisors after each DDL change.

## Verification Executed

- Live privilege matrix: 8/8 internal tables deny anonymous/authenticated CRUD; 8/8 preserve `platform_api` and `service_role` CRUD.
- Live function matrix: 5/5 privileged functions deny anonymous/authenticated execution; required server resolver grants remain.
- Live row-count comparison: no rows changed by the grant-only migration.
- Post-migration Supabase Security Advisor: exposure/RLS-disabled and public `SECURITY DEFINER` categories cleared.
- Ruff: all changed Python files passed.
- API suite with all remote DB variables removed: 328 passed, 335 skipped.
- Worker suite with all remote DB variables removed: 2 passed, 14 skipped.
- Test-database guard unit tests: six passing cases covering remote rejection, same-DB rejection across driver and Supabase pooler/direct URL variants, explicit test selection, and local allowance.
- The first combined root pytest invocation was discarded because the root invocation did not load the app/worker project Python paths; package-scoped reruns above used their canonical configurations and passed.

Advisor references: [RLS disabled in public](https://supabase.com/docs/guides/database/database-linter?lint=0013_rls_disabled_in_public), [public SECURITY DEFINER execution](https://supabase.com/docs/guides/database/database-linter?lint=0028_anon_security_definer_function_executable), [unindexed foreign keys](https://supabase.com/docs/guides/database/database-linter?lint=0001_unindexed_foreign_keys), [leaked-password protection](https://supabase.com/docs/guides/auth/password-security#password-strength-and-leaked-password-protection).
