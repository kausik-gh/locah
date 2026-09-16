-- Stage 1E: Platform foundation — business, locations, team, entitlements, modules, outbox, audit, RLS

-- Session context helpers (Doc 12 §7.2)
CREATE OR REPLACE FUNCTION current_business_id() RETURNS uuid AS $$
    SELECT NULLIF(current_setting('app.current_business_id', true), '')::uuid;
$$ LANGUAGE sql STABLE;

CREATE OR REPLACE FUNCTION current_identity_id() RETURNS uuid AS $$
    SELECT NULLIF(current_setting('app.current_identity_id', true), '')::uuid;
$$ LANGUAGE sql STABLE;

CREATE OR REPLACE FUNCTION set_updated_at() RETURNS trigger AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Businesses (core-business-identity)
CREATE TABLE businesses (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    slug TEXT NOT NULL,
    display_name TEXT NOT NULL,
    state TEXT NOT NULL DEFAULT 'draft'
        CHECK (state IN ('draft', 'onboarding', 'active', 'dormant', 'closed')),
    status TEXT NOT NULL DEFAULT 'in_good_standing'
        CHECK (status IN ('in_good_standing', 'under_review', 'suspended')),
    visibility TEXT NOT NULL DEFAULT 'private'
        CHECK (visibility IN ('private', 'unlisted', 'discoverable')),
    primary_owner_identity_id UUID NOT NULL REFERENCES platform_identities(id),
    business_type TEXT,
    characteristics JSONB NOT NULL DEFAULT '[]'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    deleted_at TIMESTAMPTZ,
    version INTEGER NOT NULL DEFAULT 1,
    UNIQUE (slug)
);

CREATE INDEX idx_businesses_primary_owner ON businesses(primary_owner_identity_id);
CREATE INDEX idx_businesses_active ON businesses(id) WHERE deleted_at IS NULL;

-- Locations (core-locations)
CREATE TABLE business_locations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    business_id UUID NOT NULL REFERENCES businesses(id),
    name TEXT NOT NULL,
    address JSONB,
    timezone TEXT NOT NULL DEFAULT 'UTC',
    hours JSONB,
    is_primary BOOLEAN NOT NULL DEFAULT false,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    deleted_at TIMESTAMPTZ,
    version INTEGER NOT NULL DEFAULT 1
);

CREATE INDEX idx_business_locations_business_id ON business_locations(business_id);
CREATE INDEX idx_business_locations_active ON business_locations(business_id) WHERE deleted_at IS NULL;

-- Team & Access (core-team-access)
CREATE TABLE business_memberships (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    business_id UUID NOT NULL REFERENCES businesses(id),
    identity_id UUID NOT NULL REFERENCES platform_identities(id),
    role TEXT NOT NULL CHECK (role IN ('primary_owner', 'manager', 'member')),
    status TEXT NOT NULL DEFAULT 'pending'
        CHECK (status IN ('pending', 'active', 'suspended', 'removed')),
    location_scope UUID[],
    invited_at TIMESTAMPTZ,
    activated_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    deleted_at TIMESTAMPTZ,
    version INTEGER NOT NULL DEFAULT 1,
    UNIQUE (business_id, identity_id)
);

CREATE INDEX idx_business_memberships_business_id ON business_memberships(business_id);
CREATE INDEX idx_business_memberships_identity_id ON business_memberships(identity_id);

CREATE TABLE business_membership_permission_grants (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    business_id UUID NOT NULL REFERENCES businesses(id),
    membership_id UUID NOT NULL REFERENCES business_memberships(id) ON DELETE CASCADE,
    permission TEXT NOT NULL,
    location_ids UUID[],
    granted_by UUID NOT NULL REFERENCES platform_identities(id),
    granted_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_membership_permission_grants_membership ON business_membership_permission_grants(membership_id);

CREATE TABLE business_membership_applied_templates (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    membership_id UUID NOT NULL REFERENCES business_memberships(id) ON DELETE CASCADE,
    template_id TEXT NOT NULL,
    applied_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    applied_by UUID NOT NULL REFERENCES platform_identities(id),
    customized BOOLEAN NOT NULL DEFAULT false
);

-- Entitlements (svc-entitlement-billing)
CREATE TABLE commercial_entitlements (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    business_id UUID NOT NULL REFERENCES businesses(id),
    subject_type TEXT NOT NULL CHECK (subject_type IN ('module', 'capability', 'allowance')),
    subject_id TEXT NOT NULL,
    source TEXT NOT NULL CHECK (source IN ('platform_core', 'plan', 'addon', 'trial', 'promo', 'manual')),
    status TEXT NOT NULL DEFAULT 'active'
        CHECK (status IN ('active', 'suspended', 'expired', 'revoked')),
    starts_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    expires_at TIMESTAMPTZ,
    quantity_limit INTEGER,
    granted_by UUID REFERENCES platform_identities(id),
    reason TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_commercial_entitlements_business ON commercial_entitlements(business_id);
CREATE INDEX idx_commercial_entitlements_active ON commercial_entitlements(business_id, subject_id)
    WHERE status = 'active';

-- Module registry & lifecycle (core-module-management)
CREATE TABLE module_definitions (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    module_class TEXT NOT NULL CHECK (module_class IN ('platform_core', 'optional', 'ai_employee', 'service')),
    description TEXT,
    dependencies TEXT[] NOT NULL DEFAULT '{}',
    config_schema JSONB,
    is_available BOOLEAN NOT NULL DEFAULT true,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE business_module_states (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    business_id UUID NOT NULL REFERENCES businesses(id),
    module_id TEXT NOT NULL REFERENCES module_definitions(id),
    activation_state TEXT NOT NULL DEFAULT 'not_enabled'
        CHECK (activation_state IN (
            'not_enabled', 'enabled', 'configuring', 'ready',
            'active', 'deactivated', 'entitlement_suspended', 'degraded'
        )),
    configuration JSONB,
    enabled_at TIMESTAMPTZ,
    activated_at TIMESTAMPTZ,
    deactivated_at TIMESTAMPTZ,
    deactivated_reason TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    version INTEGER NOT NULL DEFAULT 1,
    UNIQUE (business_id, module_id)
);

CREATE INDEX idx_business_module_states_business ON business_module_states(business_id);

-- Outbox / jobs (Doc 12 §18)
CREATE TABLE platform_outbox_events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    business_id UUID,
    event_type TEXT NOT NULL,
    event_version TEXT NOT NULL DEFAULT '1.0',
    payload JSONB NOT NULL,
    correlation_id UUID,
    causation_id UUID,
    status TEXT NOT NULL DEFAULT 'pending'
        CHECK (status IN ('pending', 'processing', 'completed', 'failed', 'dead_letter')),
    attempt_count INTEGER NOT NULL DEFAULT 0,
    max_attempts INTEGER NOT NULL DEFAULT 5,
    next_attempt_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    leased_until TIMESTAMPTZ,
    leased_by TEXT,
    last_error TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    processed_at TIMESTAMPTZ
);

CREATE INDEX idx_outbox_pending ON platform_outbox_events(status, next_attempt_at)
    WHERE status IN ('pending', 'failed');

CREATE TABLE platform_async_jobs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    business_id UUID,
    job_type TEXT NOT NULL,
    payload JSONB NOT NULL,
    correlation_id UUID,
    causation_id UUID,
    status TEXT NOT NULL DEFAULT 'pending'
        CHECK (status IN ('pending', 'processing', 'completed', 'failed', 'dead_letter')),
    attempt_count INTEGER NOT NULL DEFAULT 0,
    max_attempts INTEGER NOT NULL DEFAULT 5,
    next_attempt_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    leased_until TIMESTAMPTZ,
    leased_by TEXT,
    last_error TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    completed_at TIMESTAMPTZ
);

CREATE INDEX idx_async_jobs_pending ON platform_async_jobs(status, next_attempt_at)
    WHERE status IN ('pending', 'failed');

CREATE TABLE platform_scheduled_jobs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    business_id UUID,
    schedule_type TEXT NOT NULL,
    payload JSONB NOT NULL,
    run_at TIMESTAMPTZ NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending'
        CHECK (status IN ('pending', 'materialized', 'cancelled')),
    materialized_job_id UUID REFERENCES platform_async_jobs(id),
    recurrence_key TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_scheduled_jobs_due ON platform_scheduled_jobs(run_at) WHERE status = 'pending';

CREATE TABLE platform_processed_events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    event_id UUID NOT NULL,
    handler TEXT NOT NULL,
    processed_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (event_id, handler)
);

CREATE TABLE platform_dead_letter_events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    source_table TEXT NOT NULL,
    source_id UUID NOT NULL,
    event_type TEXT NOT NULL,
    payload JSONB NOT NULL,
    final_error TEXT NOT NULL,
    attempt_count INTEGER NOT NULL,
    resolved_at TIMESTAMPTZ,
    resolved_by UUID REFERENCES platform_identities(id),
    resolution_note TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE idempotency_records (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    idempotency_key TEXT NOT NULL,
    business_id UUID NOT NULL,
    endpoint TEXT NOT NULL,
    response_code INTEGER NOT NULL,
    response_body JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    expires_at TIMESTAMPTZ NOT NULL,
    UNIQUE (idempotency_key, business_id, endpoint)
);

-- Audit (Doc 12 §22.3)
CREATE TABLE platform_audit_events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    event_type TEXT NOT NULL,
    actor_identity_id UUID NOT NULL REFERENCES platform_identities(id),
    actor_context TEXT NOT NULL,
    business_id UUID,
    resource_type TEXT,
    resource_id UUID,
    action TEXT NOT NULL,
    before_state JSONB,
    after_state JSONB,
    reason TEXT,
    ip_address INET,
    user_agent TEXT,
    occurred_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_audit_business ON platform_audit_events(business_id);
CREATE INDEX idx_audit_actor ON platform_audit_events(actor_identity_id);

-- updated_at triggers
CREATE TRIGGER trg_businesses_updated_at BEFORE UPDATE ON businesses
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();
CREATE TRIGGER trg_business_locations_updated_at BEFORE UPDATE ON business_locations
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();
CREATE TRIGGER trg_business_memberships_updated_at BEFORE UPDATE ON business_memberships
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();
CREATE TRIGGER trg_commercial_entitlements_updated_at BEFORE UPDATE ON commercial_entitlements
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();
CREATE TRIGGER trg_business_module_states_updated_at BEFORE UPDATE ON business_module_states
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();
CREATE TRIGGER trg_platform_identities_updated_at BEFORE UPDATE ON platform_identities
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();
CREATE TRIGGER trg_consumer_profiles_updated_at BEFORE UPDATE ON consumer_profiles
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

-- RLS (defense-in-depth; FastAPI authorization is primary)
ALTER TABLE businesses ENABLE ROW LEVEL SECURITY;
ALTER TABLE business_locations ENABLE ROW LEVEL SECURITY;
ALTER TABLE business_memberships ENABLE ROW LEVEL SECURITY;
ALTER TABLE business_membership_permission_grants ENABLE ROW LEVEL SECURITY;
ALTER TABLE business_membership_applied_templates ENABLE ROW LEVEL SECURITY;
ALTER TABLE commercial_entitlements ENABLE ROW LEVEL SECURITY;
ALTER TABLE module_definitions ENABLE ROW LEVEL SECURITY;
ALTER TABLE business_module_states ENABLE ROW LEVEL SECURITY;
ALTER TABLE platform_audit_events ENABLE ROW LEVEL SECURITY;

CREATE POLICY businesses_member_read ON businesses FOR SELECT USING (
    deleted_at IS NULL AND (
        id = current_business_id()
        OR id IN (
            SELECT business_id FROM business_memberships
            WHERE identity_id = current_identity_id() AND status = 'active' AND deleted_at IS NULL
        )
    )
);

CREATE POLICY business_locations_member_read ON business_locations FOR SELECT USING (
    deleted_at IS NULL AND business_id = current_business_id()
);

CREATE POLICY business_memberships_member_read ON business_memberships FOR SELECT USING (
    deleted_at IS NULL AND business_id = current_business_id()
);

CREATE POLICY module_definitions_authenticated_read ON module_definitions
    FOR SELECT USING (true);

CREATE POLICY commercial_entitlements_member_read ON commercial_entitlements FOR SELECT USING (
    business_id = current_business_id()
);

CREATE POLICY business_module_states_member_read ON business_module_states FOR SELECT USING (
    business_id = current_business_id()
);

CREATE POLICY consumer_profiles_self ON consumer_profiles
    FOR ALL USING (identity_id = current_identity_id());
