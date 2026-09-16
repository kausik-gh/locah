-- Stage 7 — RLS role separation (AUD-02)
-- Authority: Doc 11 §21.1 gate 2 ("RLS is enabled and tested wherever the
-- execution context supports it"), Doc 12 §7.2 (session context helpers).
--
-- Today the API connects as `postgres` (rolbypassrls=true), so all 70 RLS
-- policies are inert. This migration:
--   1. creates a dedicated NOBYPASSRLS login role `platform_api` for the API
--      connection ONLY — worker + migrations keep the `postgres` connection;
--   2. grants it exactly the DML it needs;
--   3. adds write (FOR ALL) policies to the 41 business-scoped tables that had
--      only a SELECT policy, plus hand-written policies for the ~15 tables with
--      non-trivial scoping (identity-scoped, recipient-scoped, member-of,
--      registry, app-managed infra);
--   4. FORCE ROW LEVEL SECURITY on every business-scoped table so a
--      non-superuser owner is still subject to policy.
--
-- The role's PASSWORD is NOT set here (migrations are committed to git). It is
-- set out-of-band by the apply step and stored only in .env as
-- API_DATABASE_URL. See infra/deploy/README.md.
--
-- `postgres` keeps rolbypassrls=true, so FORCE does not affect the worker or
-- migrations — verified: pg_roles.rolbypassrls wins over FORCE.

-- ============================================================
-- 1. ROLE
-- ============================================================
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'platform_api') THEN
        CREATE ROLE platform_api LOGIN NOBYPASSRLS;
    END IF;
END
$$;

GRANT USAGE ON SCHEMA public TO platform_api;
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO platform_api;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO platform_api;
GRANT EXECUTE ON FUNCTION current_business_id() TO platform_api;
GRANT EXECUTE ON FUNCTION current_identity_id() TO platform_api;
-- Future tables created by later migrations inherit the grant.
ALTER DEFAULT PRIVILEGES IN SCHEMA public
    GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO platform_api;
ALTER DEFAULT PRIVILEGES IN SCHEMA public
    GRANT USAGE, SELECT ON SEQUENCES TO platform_api;

-- ============================================================
-- 2. WRITE POLICIES — simple business-scoped tables (41)
--    Each already has a `<t>_read` SELECT policy; this adds FOR ALL so the
--    same tenant predicate governs INSERT/UPDATE/DELETE. Scoped TO platform_api
--    so the worker/postgres path is unaffected even if it ever stops bypassing.
-- ============================================================
CREATE POLICY bookings_booking_notes_api_write ON bookings_booking_notes FOR ALL TO platform_api
    USING (business_id = current_business_id()) WITH CHECK (business_id = current_business_id());
CREATE POLICY bookings_booking_status_history_api_write ON bookings_booking_status_history FOR ALL TO platform_api
    USING (business_id = current_business_id()) WITH CHECK (business_id = current_business_id());
CREATE POLICY bookings_bookings_api_write ON bookings_bookings FOR ALL TO platform_api
    USING (business_id = current_business_id()) WITH CHECK (business_id = current_business_id());
CREATE POLICY bookings_policies_api_write ON bookings_policies FOR ALL TO platform_api
    USING (business_id = current_business_id()) WITH CHECK (business_id = current_business_id());
CREATE POLICY business_employee_location_assignments_api_write ON business_employee_location_assignments FOR ALL TO platform_api
    USING (business_id = current_business_id()) WITH CHECK (business_id = current_business_id());
CREATE POLICY business_employees_api_write ON business_employees FOR ALL TO platform_api
    USING (business_id = current_business_id()) WITH CHECK (business_id = current_business_id());
CREATE POLICY business_locations_api_write ON business_locations FOR ALL TO platform_api
    USING (business_id = current_business_id()) WITH CHECK (business_id = current_business_id());
CREATE POLICY business_module_states_api_write ON business_module_states FOR ALL TO platform_api
    USING (business_id = current_business_id()) WITH CHECK (business_id = current_business_id());
CREATE POLICY commercial_entitlements_api_write ON commercial_entitlements FOR ALL TO platform_api
    USING (business_id = current_business_id()) WITH CHECK (business_id = current_business_id());
CREATE POLICY customer_relationships_contacts_api_write ON customer_relationships_contacts FOR ALL TO platform_api
    USING (business_id = current_business_id()) WITH CHECK (business_id = current_business_id());
CREATE POLICY customer_relationships_notes_api_write ON customer_relationships_notes FOR ALL TO platform_api
    USING (business_id = current_business_id()) WITH CHECK (business_id = current_business_id());
CREATE POLICY customer_relationships_timeline_entries_api_write ON customer_relationships_timeline_entries FOR ALL TO platform_api
    USING (business_id = current_business_id()) WITH CHECK (business_id = current_business_id());
CREATE POLICY fulfilment_jobs_api_write ON fulfilment_jobs FOR ALL TO platform_api
    USING (business_id = current_business_id()) WITH CHECK (business_id = current_business_id());
CREATE POLICY fulfilment_settings_api_write ON fulfilment_settings FOR ALL TO platform_api
    USING (business_id = current_business_id()) WITH CHECK (business_id = current_business_id());
CREATE POLICY fulfilment_zones_api_write ON fulfilment_zones FOR ALL TO platform_api
    USING (business_id = current_business_id()) WITH CHECK (business_id = current_business_id());
CREATE POLICY inventory_movements_api_write ON inventory_movements FOR ALL TO platform_api
    USING (business_id = current_business_id()) WITH CHECK (business_id = current_business_id());
CREATE POLICY inventory_records_api_write ON inventory_records FOR ALL TO platform_api
    USING (business_id = current_business_id()) WITH CHECK (business_id = current_business_id());
CREATE POLICY leads_lead_notes_api_write ON leads_lead_notes FOR ALL TO platform_api
    USING (business_id = current_business_id()) WITH CHECK (business_id = current_business_id());
CREATE POLICY leads_lead_status_history_api_write ON leads_lead_status_history FOR ALL TO platform_api
    USING (business_id = current_business_id()) WITH CHECK (business_id = current_business_id());
CREATE POLICY leads_leads_api_write ON leads_leads FOR ALL TO platform_api
    USING (business_id = current_business_id()) WITH CHECK (business_id = current_business_id());
CREATE POLICY marketplace_business_projections_api_write ON marketplace_business_projections FOR ALL TO platform_api
    USING (business_id = current_business_id()) WITH CHECK (business_id = current_business_id());
CREATE POLICY marketplace_index_health_api_write ON marketplace_index_health FOR ALL TO platform_api
    USING (business_id = current_business_id()) WITH CHECK (business_id = current_business_id());
CREATE POLICY marketplace_offering_projections_api_write ON marketplace_offering_projections FOR ALL TO platform_api
    USING (business_id = current_business_id()) WITH CHECK (business_id = current_business_id());
CREATE POLICY memberships_enrolment_status_history_api_write ON memberships_enrolment_status_history FOR ALL TO platform_api
    USING (business_id = current_business_id()) WITH CHECK (business_id = current_business_id());
CREATE POLICY memberships_enrolments_api_write ON memberships_enrolments FOR ALL TO platform_api
    USING (business_id = current_business_id()) WITH CHECK (business_id = current_business_id());
CREATE POLICY memberships_plan_offering_access_api_write ON memberships_plan_offering_access FOR ALL TO platform_api
    USING (business_id = current_business_id()) WITH CHECK (business_id = current_business_id());
CREATE POLICY memberships_plans_api_write ON memberships_plans FOR ALL TO platform_api
    USING (business_id = current_business_id()) WITH CHECK (business_id = current_business_id());
CREATE POLICY offerings_catalog_categories_api_write ON offerings_catalog_categories FOR ALL TO platform_api
    USING (business_id = current_business_id()) WITH CHECK (business_id = current_business_id());
CREATE POLICY offerings_catalog_offerings_api_write ON offerings_catalog_offerings FOR ALL TO platform_api
    USING (business_id = current_business_id()) WITH CHECK (business_id = current_business_id());
CREATE POLICY offerings_catalog_variants_api_write ON offerings_catalog_variants FOR ALL TO platform_api
    USING (business_id = current_business_id()) WITH CHECK (business_id = current_business_id());
CREATE POLICY orders_order_line_items_api_write ON orders_order_line_items FOR ALL TO platform_api
    USING (business_id = current_business_id()) WITH CHECK (business_id = current_business_id());
CREATE POLICY orders_order_notes_api_write ON orders_order_notes FOR ALL TO platform_api
    USING (business_id = current_business_id()) WITH CHECK (business_id = current_business_id());
CREATE POLICY orders_order_status_history_api_write ON orders_order_status_history FOR ALL TO platform_api
    USING (business_id = current_business_id()) WITH CHECK (business_id = current_business_id());
CREATE POLICY orders_orders_api_write ON orders_orders FOR ALL TO platform_api
    USING (business_id = current_business_id()) WITH CHECK (business_id = current_business_id());
CREATE POLICY payments_merchant_connections_api_write ON payments_merchant_connections FOR ALL TO platform_api
    USING (business_id = current_business_id()) WITH CHECK (business_id = current_business_id());
CREATE POLICY payments_payment_attempts_api_write ON payments_payment_attempts FOR ALL TO platform_api
    USING (business_id = current_business_id()) WITH CHECK (business_id = current_business_id());
CREATE POLICY payments_refunds_api_write ON payments_refunds FOR ALL TO platform_api
    USING (business_id = current_business_id()) WITH CHECK (business_id = current_business_id());
CREATE POLICY workforce_availability_api_write ON workforce_availability FOR ALL TO platform_api
    USING (business_id = current_business_id()) WITH CHECK (business_id = current_business_id());
CREATE POLICY workforce_location_assignments_api_write ON workforce_location_assignments FOR ALL TO platform_api
    USING (business_id = current_business_id()) WITH CHECK (business_id = current_business_id());
CREATE POLICY workforce_members_api_write ON workforce_members FOR ALL TO platform_api
    USING (business_id = current_business_id()) WITH CHECK (business_id = current_business_id());
CREATE POLICY workforce_service_associations_api_write ON workforce_service_associations FOR ALL TO platform_api
    USING (business_id = current_business_id()) WITH CHECK (business_id = current_business_id());

-- ============================================================
-- 3. HAND-WRITTEN POLICIES — non-trivial scoping
-- ============================================================

-- Businesses: visible to a member, the owner, or the active context.
-- Created by the owner; updated only from within its own context.
CREATE POLICY businesses_api_select ON businesses FOR SELECT TO platform_api USING (
    id = current_business_id()
    OR primary_owner_identity_id = current_identity_id()
    OR EXISTS (
        SELECT 1 FROM business_memberships m
        WHERE m.business_id = businesses.id
          AND m.identity_id = current_identity_id()
          AND m.status = 'active' AND m.deleted_at IS NULL
    )
    -- Public slug resolution: an unlisted or discoverable business in good
    -- standing has a public website, so a guest (no identity, no context) must
    -- be able to resolve it by slug before `bind_public_context` can run.
    OR (visibility IN ('unlisted', 'discoverable') AND status = 'in_good_standing')
);
CREATE POLICY businesses_api_insert ON businesses FOR INSERT TO platform_api
    WITH CHECK (primary_owner_identity_id = current_identity_id());
CREATE POLICY businesses_api_update ON businesses FOR UPDATE TO platform_api
    USING (id = current_business_id() OR primary_owner_identity_id = current_identity_id());

-- Memberships: your own rows anywhere, plus every row in the active business.
CREATE POLICY business_memberships_api_select ON business_memberships FOR SELECT TO platform_api USING (
    identity_id = current_identity_id() OR business_id = current_business_id()
);
CREATE POLICY business_memberships_api_write ON business_memberships FOR ALL TO platform_api
    USING (business_id = current_business_id())
    WITH CHECK (business_id = current_business_id() OR identity_id = current_identity_id());

-- Invitations: the one tenant table with no policy at all (the §21.1 gap).
-- Scoped to the active business; also readable by the invited identity so the
-- accept flow works before a membership exists.
CREATE POLICY business_invitations_api_select ON business_invitations FOR SELECT TO platform_api USING (
    business_id = current_business_id() OR invited_identity_id = current_identity_id()
);
CREATE POLICY business_invitations_api_write ON business_invitations FOR ALL TO platform_api
    USING (business_id = current_business_id() OR invited_identity_id = current_identity_id())
    WITH CHECK (business_id = current_business_id() OR invited_identity_id = current_identity_id());

-- Permission grants / denials / applied templates: keyed by membership, which
-- is keyed by business. Scope through the membership.
CREATE POLICY perm_grants_api_write ON business_membership_permission_grants FOR ALL TO platform_api
    USING (EXISTS (SELECT 1 FROM business_memberships m WHERE m.id = membership_id AND m.business_id = current_business_id()))
    WITH CHECK (EXISTS (SELECT 1 FROM business_memberships m WHERE m.id = membership_id AND m.business_id = current_business_id()));
CREATE POLICY perm_denials_api_write ON business_membership_permission_denials FOR ALL TO platform_api
    USING (EXISTS (SELECT 1 FROM business_memberships m WHERE m.id = membership_id AND m.business_id = current_business_id()))
    WITH CHECK (EXISTS (SELECT 1 FROM business_memberships m WHERE m.id = membership_id AND m.business_id = current_business_id()));
CREATE POLICY applied_templates_api_write ON business_membership_applied_templates FOR ALL TO platform_api
    USING (EXISTS (SELECT 1 FROM business_memberships m WHERE m.id = membership_id AND m.business_id = current_business_id()))
    WITH CHECK (EXISTS (SELECT 1 FROM business_memberships m WHERE m.id = membership_id AND m.business_id = current_business_id()));

-- Notifications: fan-out INSERTs rows for OTHER recipients in the active
-- business; a recipient only reads/updates their own.
CREATE POLICY notifications_api_select ON platform_notifications FOR SELECT TO platform_api USING (
    business_id = current_business_id() AND recipient_identity_id = current_identity_id()
);
CREATE POLICY notifications_api_insert ON platform_notifications FOR INSERT TO platform_api
    WITH CHECK (business_id = current_business_id());
CREATE POLICY notifications_api_update ON platform_notifications FOR UPDATE TO platform_api
    USING (recipient_identity_id = current_identity_id());
CREATE POLICY notification_prefs_api_write ON platform_notification_preferences FOR ALL TO platform_api
    USING (identity_id = current_identity_id() AND business_id = current_business_id())
    WITH CHECK (identity_id = current_identity_id() AND business_id = current_business_id());

-- Consumer profile: strictly self.
CREATE POLICY consumer_profiles_api_write ON consumer_profiles FOR ALL TO platform_api
    USING (identity_id = current_identity_id()) WITH CHECK (identity_id = current_identity_id());

-- Consumer activity: the /v1/me/activity feed reads by identity; BookingService
-- writes by business.
CREATE POLICY consumer_activity_api_select ON consumer_activity_projections FOR SELECT TO platform_api USING (
    identity_id = current_identity_id() OR business_id = current_business_id()
);
CREATE POLICY consumer_activity_api_write ON consumer_activity_projections FOR ALL TO platform_api
    USING (business_id = current_business_id()) WITH CHECK (business_id = current_business_id());

-- Platform identities: not secret (email + display name). Cross-identity SELECT
-- is needed (notify-by-email, owner display, workforce linkage); the endpoint
-- layer is the real gate. Writes: bootstrap can INSERT (id comes from the
-- verified JWT sub), updates are self only.
CREATE POLICY identities_api_select ON platform_identities FOR SELECT TO platform_api USING (true);
CREATE POLICY identities_api_insert ON platform_identities FOR INSERT TO platform_api WITH CHECK (true);
CREATE POLICY identities_api_update ON platform_identities FOR UPDATE TO platform_api
    USING (id = current_identity_id());

-- Admin grants: the is_super_admin check filters by identity_id in the query;
-- the row set is small and non-sensitive (who is an admin, why). Read only for
-- the API; grants/revokes are done out-of-band.
CREATE POLICY admin_grants_api_select ON platform_admin_grants FOR SELECT TO platform_api USING (true);

-- Registries: global reference data the API reads constantly.
CREATE POLICY module_definitions_api_select ON module_definitions FOR SELECT TO platform_api USING (true);
CREATE POLICY website_section_types_api_select ON website_section_types FOR SELECT TO platform_api USING (true);

-- App-managed infra: not tenant-RLS-scoped. Access control for these is at the
-- application layer (admin endpoints require super_admin; audit/outbox writes
-- are app-controlled and append-only). Permissive policies keep RLS "on" while
-- making the intent explicit.
CREATE POLICY audit_events_api ON platform_audit_events FOR ALL TO platform_api USING (true) WITH CHECK (true);
CREATE POLICY outbox_events_api ON platform_outbox_events FOR ALL TO platform_api USING (true) WITH CHECK (true);
CREATE POLICY dead_letter_api ON platform_dead_letter_events FOR SELECT TO platform_api USING (true);
CREATE POLICY async_jobs_api ON platform_async_jobs FOR SELECT TO platform_api USING (true);
CREATE POLICY scheduled_jobs_api ON platform_scheduled_jobs FOR SELECT TO platform_api USING (true);
CREATE POLICY processed_events_api ON platform_processed_events FOR SELECT TO platform_api USING (true);
CREATE POLICY idempotency_api ON idempotency_records FOR ALL TO platform_api USING (true) WITH CHECK (true);
-- Webhook receipts: written by the public webhook endpoint (no business
-- context — the signature is the auth). App-controlled.
CREATE POLICY webhook_receipts_api ON payments_webhook_receipts FOR ALL TO platform_api USING (true) WITH CHECK (true);

-- ============================================================
-- 4. FORCE ROW LEVEL SECURITY
--    Applies policy to a non-superuser owner too. `postgres` still bypasses
--    via rolbypassrls, so worker + migrations are unaffected.
-- ============================================================
DO $$
DECLARE t text;
BEGIN
    FOR t IN
        SELECT c.relname FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
        WHERE n.nspname = 'public' AND c.relkind = 'r' AND c.relrowsecurity
    LOOP
        EXECUTE format('ALTER TABLE public.%I FORCE ROW LEVEL SECURITY', t);
    END LOOP;
END
$$;
