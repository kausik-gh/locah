-- Database hygiene from the 2026-09-27 database pass. Forward-only, no data
-- changes, safe to re-run.
--
-- 1. Worker claim indexes. `claim_outbox_batch` / `claim_job_batch`
--    (apps/worker/src/platform_worker/claiming.py) select
--        status IN ('pending','failed') OR (status = 'processing' AND lease expired)
--    ordered by next_attempt_at. The original partial indexes only cover
--    ('pending','failed'), so the OR arm could never use them and every poll
--    sequentially scanned the whole table: on the hosted project the outbox
--    claim had run 172k times at ~21 ms (≈62 min of database time, 8 billion
--    rows read) and was the single most expensive statement. The event
--    delivery lane already uses the right shape (idx_event_deliveries_due,
--    0.24 ms per claim); the outbox and job lanes now match it, and the old
--    indexes they supersede are dropped.
--
-- 2. Row-level policies that called current_setting()/auth.uid() once per
--    row now call it once per statement (`(select …)`), as the Supabase
--    advisor recommends. Same predicates, same roles.
--
-- 3. The three trigger functions get a fixed search_path. Their bodies only
--    use pg_catalog, so '' is exact. current_business_id() /
--    current_identity_id() are deliberately left alone: they are one-line SQL
--    functions used by nearly every RLS policy, and a SET clause would stop
--    Postgres inlining them and add a per-call GUC save/restore. Their bodies
--    only call pg_catalog functions, which are always resolved first.

-- 1 ─────────────────────────────────────────────────────────────────────────
CREATE INDEX IF NOT EXISTS idx_outbox_due ON platform_outbox_events(next_attempt_at)
    WHERE status IN ('pending', 'failed', 'processing');
DROP INDEX IF EXISTS idx_outbox_pending;

CREATE INDEX IF NOT EXISTS idx_async_jobs_due ON platform_async_jobs(next_attempt_at)
    WHERE status IN ('pending', 'failed', 'processing');
DROP INDEX IF EXISTS idx_async_jobs_pending;

-- 2 ─────────────────────────────────────────────────────────────────────────
DROP POLICY IF EXISTS consumer_activity_self ON consumer_activity_projections;
CREATE POLICY consumer_activity_self ON consumer_activity_projections
    FOR SELECT USING (identity_id = (SELECT auth.uid()));

DROP POLICY IF EXISTS quotes_share_token_read ON quotes_quotes;
CREATE POLICY quotes_share_token_read ON quotes_quotes
    FOR SELECT TO platform_api
    USING (
        deleted_at IS NULL
        AND access_token IS NOT NULL
        AND access_token = (SELECT NULLIF(current_setting('app.current_quote_token', true), ''))
    );

DROP POLICY IF EXISTS bookings_management_token_read ON bookings_bookings;
CREATE POLICY bookings_management_token_read ON bookings_bookings
    FOR SELECT TO platform_api
    USING (
        deleted_at IS NULL
        AND management_token IS NOT NULL
        AND management_token = (SELECT NULLIF(current_setting('app.current_booking_token', true), ''))
    );

-- 3 ─────────────────────────────────────────────────────────────────────────
ALTER FUNCTION public.set_updated_at() SET search_path = '';
ALTER FUNCTION public.update_business_search_vector() SET search_path = '';
ALTER FUNCTION public.update_offering_search_vector() SET search_path = '';
