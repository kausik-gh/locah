-- Phase B P1 · Roles (Capability Universe §7.2–§7.3; Business OS Guide §5).
-- "A role is not just a sidebar label. It is permissions + scope + default
-- surface." Memberships now record which role template they hold and their
-- scope; owners can clone a template into a custom role; location scope is
-- enforced for the operational records that carry a location.

-- ---------------------------------------------------------------------------
-- 1. The role a member holds and its scope.
-- ---------------------------------------------------------------------------
ALTER TABLE business_memberships
    ADD COLUMN role_template TEXT,
    ADD COLUMN access_scope TEXT NOT NULL DEFAULT 'business'
        CHECK (access_scope IN ('business', 'location', 'assignment', 'self'));

-- Existing location-scoped members keep the scope they were given.
UPDATE business_memberships
   SET access_scope = 'location'
 WHERE location_scope IS NOT NULL AND cardinality(location_scope) > 0;

ALTER TABLE business_invitations
    ADD COLUMN role_template TEXT,
    ADD COLUMN access_scope TEXT NOT NULL DEFAULT 'business'
        CHECK (access_scope IN ('business', 'location', 'assignment', 'self'));

-- ---------------------------------------------------------------------------
-- 2. Custom roles: an owner clones a template and adjusts it; never more than
--    the person creating it holds (checked in the service).
-- ---------------------------------------------------------------------------
CREATE TABLE business_custom_roles (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    business_id UUID NOT NULL REFERENCES businesses(id),
    name TEXT NOT NULL CHECK (char_length(name) BETWEEN 2 AND 60),
    based_on TEXT,
    permissions TEXT[] NOT NULL DEFAULT '{}',
    access_scope TEXT NOT NULL DEFAULT 'business'
        CHECK (access_scope IN ('business', 'location', 'assignment', 'self')),
    created_by UUID REFERENCES platform_identities(id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    archived_at TIMESTAMPTZ
);
CREATE UNIQUE INDEX business_custom_roles_name
    ON business_custom_roles (business_id, lower(name)) WHERE archived_at IS NULL;

ALTER TABLE business_custom_roles ENABLE ROW LEVEL SECURITY;
ALTER TABLE business_custom_roles FORCE ROW LEVEL SECURITY;
CREATE POLICY business_custom_roles_read ON business_custom_roles FOR SELECT
    USING (business_id = current_business_id());
CREATE POLICY business_custom_roles_api_write ON business_custom_roles FOR ALL TO platform_api
    USING (business_id = current_business_id()) WITH CHECK (business_id = current_business_id());
GRANT SELECT, INSERT, UPDATE, DELETE ON business_custom_roles TO platform_api;
REVOKE ALL ON business_custom_roles FROM anon;

-- ---------------------------------------------------------------------------
-- 3. Location scope as defence in depth. The API binds
--    app.current_location_scope (comma-separated location ids) for a member
--    whose membership is limited to some locations; unset means no location
--    limit. The server filters the same records first — these RESTRICTIVE
--    policies are ANDed with the existing ones, so they can only narrow what
--    a request sees, never widen it.
-- ---------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION location_scope_allows(loc uuid) RETURNS boolean
    LANGUAGE sql STABLE AS $$
    SELECT CASE
        WHEN COALESCE(current_setting('app.current_location_scope', true), '') = '' THEN true
        WHEN loc IS NULL THEN true
        ELSE loc = ANY (string_to_array(current_setting('app.current_location_scope', true), ',')::uuid[])
    END;
$$;
GRANT EXECUTE ON FUNCTION location_scope_allows(uuid) TO platform_api;

DO $$
DECLARE t TEXT;
BEGIN
    FOREACH t IN ARRAY ARRAY[
        'orders_orders', 'bookings_bookings', 'fulfilment_jobs', 'inventory_records',
        'inventory_movements', 'quotes_quotes', 'projects_projects'
    ] LOOP
        EXECUTE format(
            'CREATE POLICY %I ON %I AS RESTRICTIVE FOR ALL TO platform_api '
            'USING (location_scope_allows(location_id)) WITH CHECK (location_scope_allows(location_id))',
            t || '_location_scope', t);
    END LOOP;
END $$;
