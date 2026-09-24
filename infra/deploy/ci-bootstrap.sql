-- CI-only Supabase shim.
--
-- This file exists ONLY so CI can apply infra/supabase/migrations/*.sql
-- against a plain `postgres:16` service container. It is never applied to
-- any real environment (local dev, staging, production all run on actual
-- Supabase, which already provides everything below). Do not add anything
-- here beyond what the two Supabase-dependent migrations require:
--   - 20260713020000_stage1f_auth_identity_trigger.sql
--       needs: `extensions` schema, `auth.users` to attach a trigger to.
--   - 20260901020000_media_storage.sql
--       needs: `storage.buckets` / `storage.objects`, `auth.uid()`,
--       `storage.foldername()`, and the `anon`/`authenticated`/
--       `service_role` roles the policies reference.
-- 20260730000000_stage5_workforce_booking_providers.sql also references
-- `auth.uid()` in a policy.
--   - 20260923113433_restrict_internal_platform_objects.sql
--       needs: `public.rls_auto_enable()` to exist, so its
--       `REVOKE EXECUTE ON FUNCTION ...` has something to reference. Real
--       Supabase projects install this trigger function themselves; a
--       plain postgres:16 container has never heard of it. This was the
--       first CI run to ever reach this migration — every earlier run
--       died at an unrelated step first — so the gap went unnoticed.
-- Every other migration is plain PostgreSQL and needs nothing from this
-- file.

-- ============================================================
-- 1. SCHEMAS
-- ============================================================
CREATE SCHEMA IF NOT EXISTS extensions;
CREATE SCHEMA IF NOT EXISTS auth;
CREATE SCHEMA IF NOT EXISTS storage;

-- Real Supabase projects carry `extra_search_path = ["public", "extensions"]`
-- (infra/supabase/config.toml [api]), so unqualified calls to extension
-- functions installed in `extensions` (e.g. pgcrypto's `crypt()`, used by
-- platform_testing.db_helpers.ensure_auth_user) resolve without a schema
-- prefix. Match that here.
ALTER DATABASE postgres SET search_path TO public, extensions;
SET search_path TO public, extensions;

-- `crypt()` (used by platform_testing.db_helpers.ensure_auth_user to stand in
-- for Supabase Auth's password hashing) is pgcrypto, not core Postgres —
-- unlike gen_random_uuid(), which has been built in since PG13 and needs no
-- extension. Real Supabase projects have pgcrypto installed already.
CREATE EXTENSION IF NOT EXISTS pgcrypto WITH SCHEMA extensions;

-- ============================================================
-- 2. ROLES
-- ============================================================
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'anon') THEN
        CREATE ROLE anon NOLOGIN;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'authenticated') THEN
        CREATE ROLE authenticated NOLOGIN;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'service_role') THEN
        CREATE ROLE service_role NOLOGIN;
    END IF;
END
$$;

-- ============================================================
-- 3. auth.users + auth.uid()
-- ============================================================
-- Columns match what platform_testing.db_helpers.ensure_auth_user (and the
-- suite's fixtures more broadly) insert against a real Supabase auth.users.
CREATE TABLE IF NOT EXISTS auth.users (
    id uuid PRIMARY KEY,
    instance_id uuid,
    aud text,
    role text,
    email text,
    encrypted_password text,
    email_confirmed_at timestamptz,
    raw_user_meta_data jsonb,
    created_at timestamptz,
    updated_at timestamptz
);

-- Real Supabase resolves this from the request's verified JWT (the `sub`
-- claim via a GUC set per-connection by PostgREST/Auth). Nothing in the test
-- suite issues a request through that path — tests talk to Postgres
-- directly with the `postgres` (migrations/worker) or `platform_api` (API)
-- roles, never as `authenticated` acting on its own JWT — so this stub only
-- needs to let `CREATE POLICY ... auth.uid() ...` resolve the function name;
-- it is never evaluated with a real caller identity in CI.
CREATE OR REPLACE FUNCTION auth.uid() RETURNS uuid
LANGUAGE sql STABLE
AS $$
    SELECT NULLIF(current_setting('request.jwt.claim.sub', true), '')::uuid;
$$;

-- ============================================================
-- 4. storage.buckets / storage.objects + storage.foldername()
-- ============================================================
CREATE TABLE IF NOT EXISTS storage.buckets (
    id text PRIMARY KEY,
    name text NOT NULL,
    public boolean NOT NULL DEFAULT false,
    file_size_limit bigint,
    allowed_mime_types text[]
);

CREATE TABLE IF NOT EXISTS storage.objects (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    bucket_id text REFERENCES storage.buckets(id),
    name text,
    owner uuid
);
ALTER TABLE storage.objects ENABLE ROW LEVEL SECURITY;

-- Real Supabase Storage splits the object key on '/' and drops the final
-- segment (the filename), leaving the folder path. Same behaviour here.
CREATE OR REPLACE FUNCTION storage.foldername(name text) RETURNS text[]
LANGUAGE sql IMMUTABLE
AS $$
    SELECT (string_to_array(name, '/'))[1 : array_length(string_to_array(name, '/'), 1) - 1];
$$;

-- ============================================================
-- 5. public.rls_auto_enable()
-- ============================================================
-- A Supabase-platform trigger function (the dashboard's "auto-enable RLS on
-- new tables" behaviour), not something this repo defines or calls. Nothing
-- here needs it to DO anything — 20260923113433 only revokes EXECUTE on it —
-- so the body is a placeholder; only the name, argument list and return type
-- need to match closely enough for that REVOKE to resolve.
CREATE OR REPLACE FUNCTION public.rls_auto_enable() RETURNS event_trigger
LANGUAGE plpgsql
AS $$
BEGIN
END;
$$;
