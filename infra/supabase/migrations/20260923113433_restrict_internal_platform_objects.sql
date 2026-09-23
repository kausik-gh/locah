-- Server-only platform infrastructure lives in public today because the API
-- and worker already depend on those qualified names.  RLS is intentionally
-- disabled for these cross-tenant queues/audit tables; the platform_api and
-- service roles are the authorization boundary.  Supabase's default public
-- schema grants also gave anon/authenticated direct access, however.  Remove
-- only those browser-facing grants without changing the server contract.

REVOKE ALL PRIVILEGES ON TABLE
    public.idempotency_records,
    public.platform_async_jobs,
    public.platform_audit_events,
    public.platform_dead_letter_events,
    public.platform_event_deliveries,
    public.platform_outbox_events,
    public.platform_processed_events,
    public.platform_scheduled_jobs
FROM PUBLIC, anon, authenticated;

-- These SECURITY DEFINER functions are trigger/server helpers, not public RPC
-- endpoints.  Explicit role grants survive a revoke from PUBLIC, so the three
-- resolver functions remain executable by platform_api as established by
-- their defining migrations.
REVOKE EXECUTE ON FUNCTION public.handle_new_auth_user()
FROM PUBLIC, anon, authenticated;
REVOKE EXECUTE ON FUNCTION public.resolve_activity_business_names(uuid[])
FROM PUBLIC, anon, authenticated;
REVOKE EXECUTE ON FUNCTION public.resolve_muted_identities(uuid, text, uuid[])
FROM PUBLIC, anon, authenticated;
REVOKE EXECUTE ON FUNCTION public.resolve_order_business_id(uuid)
FROM PUBLIC, anon, authenticated;
REVOKE EXECUTE ON FUNCTION public.rls_auto_enable()
FROM PUBLIC, anon, authenticated;
