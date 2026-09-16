-- Stage 7 — RLS: exempt the platform-operational tables (follow-up to
-- 20260802000000).
--
-- These tables are queues, ledgers, and idempotency keys — not tenant
-- resources. Their access control is entirely at the application layer:
--   * platform_audit_events / platform_outbox_events — append-only, written by
--     every service; read only by Super Admin endpoints (which run on the
--     service-role connection);
--   * platform_async_jobs / platform_scheduled_jobs — the API enqueues jobs
--     (e.g. website generation) as part of normal request handling;
--   * platform_dead_letter_events / platform_processed_events — worker-owned;
--   * idempotency_records — checkout de-dup.
--
-- A per-business RLS predicate does not model any of these correctly (audit is
-- deliberately cross-tenant for admins; the outbox is a single queue). The
-- first RLS migration gave them permissive `USING (true)` policies; simpler and
-- clearer to turn RLS off for them outright and rely on the GRANTs + the
-- application gates. The `postgres` (worker) path is unaffected either way.

ALTER TABLE platform_audit_events       DISABLE ROW LEVEL SECURITY;
ALTER TABLE platform_outbox_events      DISABLE ROW LEVEL SECURITY;
ALTER TABLE platform_async_jobs         DISABLE ROW LEVEL SECURITY;
ALTER TABLE platform_scheduled_jobs     DISABLE ROW LEVEL SECURITY;
ALTER TABLE platform_dead_letter_events DISABLE ROW LEVEL SECURITY;
ALTER TABLE platform_processed_events   DISABLE ROW LEVEL SECURITY;
ALTER TABLE idempotency_records         DISABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS audit_events_api    ON platform_audit_events;
DROP POLICY IF EXISTS outbox_events_api   ON platform_outbox_events;
DROP POLICY IF EXISTS async_jobs_api      ON platform_async_jobs;
DROP POLICY IF EXISTS scheduled_jobs_api  ON platform_scheduled_jobs;
DROP POLICY IF EXISTS dead_letter_api     ON platform_dead_letter_events;
DROP POLICY IF EXISTS processed_events_api ON platform_processed_events;
DROP POLICY IF EXISTS idempotency_api     ON idempotency_records;
