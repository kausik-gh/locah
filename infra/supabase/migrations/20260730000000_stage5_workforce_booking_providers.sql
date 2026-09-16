-- Stage 5 completion: Workforce providers + Booking.provider_id cutover
-- Doc 10 §4.8 WorkforceMember · Doc 11 §10.5 / §17.5
-- Pre-launch clean forward migration: backfill then drop employee_id

-- ============================================================
-- Workforce domain
-- ============================================================

CREATE TABLE workforce_members (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    business_id UUID NOT NULL REFERENCES businesses(id),
    display_name TEXT NOT NULL,
    email TEXT,
    phone TEXT,
    designation TEXT,
    -- Optional Platform Identity linkage — NEVER grants Workspace access (Doc 11 §10.5)
    identity_id UUID REFERENCES platform_identities(id),
    status TEXT NOT NULL DEFAULT 'active'
        CHECK (status IN ('active', 'inactive')),
    notes TEXT,
    source_employee_id UUID,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    deleted_at TIMESTAMPTZ,
    version INTEGER NOT NULL DEFAULT 1
);

CREATE INDEX idx_workforce_members_business
    ON workforce_members (business_id)
    WHERE deleted_at IS NULL;
CREATE INDEX idx_workforce_members_identity
    ON workforce_members (business_id, identity_id)
    WHERE deleted_at IS NULL AND identity_id IS NOT NULL;

CREATE TABLE workforce_location_assignments (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    business_id UUID NOT NULL REFERENCES businesses(id),
    member_id UUID NOT NULL REFERENCES workforce_members(id),
    location_id UUID NOT NULL REFERENCES business_locations(id),
    is_primary BOOLEAN NOT NULL DEFAULT false,
    assigned_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    assigned_by UUID REFERENCES platform_identities(id),
    UNIQUE (member_id, location_id)
);

CREATE INDEX idx_workforce_location_assignments_business
    ON workforce_location_assignments (business_id, location_id);

CREATE TABLE workforce_service_associations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    business_id UUID NOT NULL REFERENCES businesses(id),
    member_id UUID NOT NULL REFERENCES workforce_members(id),
    offering_id UUID NOT NULL REFERENCES offerings_catalog_offerings(id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    created_by UUID REFERENCES platform_identities(id),
    UNIQUE (member_id, offering_id)
);

CREATE INDEX idx_workforce_service_assoc_business
    ON workforce_service_associations (business_id, offering_id);

CREATE TABLE workforce_availability (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    business_id UUID NOT NULL REFERENCES businesses(id),
    member_id UUID NOT NULL REFERENCES workforce_members(id),
    location_id UUID REFERENCES business_locations(id),
    weekday INTEGER CHECK (weekday IS NULL OR (weekday >= 0 AND weekday <= 6)),
    exception_date DATE,
    start_time TIME NOT NULL,
    end_time TIME NOT NULL,
    is_available BOOLEAN NOT NULL DEFAULT true,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CHECK (end_time > start_time),
    CHECK (
        (weekday IS NOT NULL AND exception_date IS NULL)
        OR (weekday IS NULL AND exception_date IS NOT NULL)
    )
);

CREATE INDEX idx_workforce_availability_member
    ON workforce_availability (business_id, member_id);

CREATE TABLE bookings_policies (
    business_id UUID PRIMARY KEY REFERENCES businesses(id),
    require_deposit BOOLEAN NOT NULL DEFAULT false,
    deposit_amount NUMERIC(12, 2) CHECK (deposit_amount IS NULL OR deposit_amount >= 0),
    deposit_percent NUMERIC(5, 2) CHECK (deposit_percent IS NULL OR (deposit_percent >= 0 AND deposit_percent <= 100)),
    cancel_window_hours INTEGER NOT NULL DEFAULT 24 CHECK (cancel_window_hours >= 0),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    version INTEGER NOT NULL DEFAULT 1
);

-- ============================================================
-- Booking: provider_id + deposits + management token
-- ============================================================

ALTER TABLE bookings_bookings
    ADD COLUMN provider_id UUID REFERENCES workforce_members(id),
    ADD COLUMN deposit_required BOOLEAN NOT NULL DEFAULT false,
    ADD COLUMN deposit_amount NUMERIC(12, 2) NOT NULL DEFAULT 0 CHECK (deposit_amount >= 0),
    ADD COLUMN management_token TEXT,
    ADD COLUMN management_token_expires_at TIMESTAMPTZ;

-- Expand payment_status for deposit_paid
ALTER TABLE bookings_bookings DROP CONSTRAINT IF EXISTS bookings_bookings_payment_status_check;
ALTER TABLE bookings_bookings
    ADD CONSTRAINT bookings_bookings_payment_status_check
    CHECK (payment_status IN ('pending', 'pending_offline', 'deposit_paid', 'paid', 'refunded'));

-- Backfill WorkforceMembers from employees referenced by bookings
INSERT INTO workforce_members (
    business_id, display_name, email, phone, designation, identity_id, status, source_employee_id
)
SELECT DISTINCT ON (b.employee_id)
    b.business_id,
    COALESCE(e.display_name, 'Provider'),
    e.email,
    e.phone,
    e.designation,
    e.identity_id,
    CASE WHEN e.status = 'active' OR e.status IS NULL THEN 'active' ELSE 'inactive' END,
    b.employee_id
FROM bookings_bookings b
LEFT JOIN business_employees e ON e.id = b.employee_id
WHERE b.employee_id IS NOT NULL
ORDER BY b.employee_id, e.created_at NULLS LAST;

-- Copy location assignments for backfilled members
INSERT INTO workforce_location_assignments (
    business_id, member_id, location_id, is_primary, assigned_at, assigned_by
)
SELECT DISTINCT
    a.business_id,
    wm.id,
    a.location_id,
    a.is_primary,
    a.assigned_at,
    a.assigned_by
FROM business_employee_location_assignments a
JOIN workforce_members wm ON wm.source_employee_id = a.employee_id
ON CONFLICT (member_id, location_id) DO NOTHING;

UPDATE bookings_bookings b
SET provider_id = wm.id
FROM workforce_members wm
WHERE b.employee_id IS NOT NULL
  AND wm.source_employee_id = b.employee_id;

-- Verify: no orphaned provider references for previous employee bookings
DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM bookings_bookings
        WHERE employee_id IS NOT NULL AND provider_id IS NULL AND deleted_at IS NULL
    ) THEN
        RAISE EXCEPTION 'Stage 5 migration failed: booking with employee_id missing provider_id after backfill';
    END IF;
END $$;

CREATE INDEX idx_bookings_provider_time
    ON bookings_bookings (business_id, provider_id, starts_at, ends_at)
    WHERE deleted_at IS NULL AND provider_id IS NOT NULL
      AND status NOT IN ('cancelled', 'rejected', 'no_show');

DROP INDEX IF EXISTS idx_bookings_employee_time;
ALTER TABLE bookings_bookings DROP COLUMN employee_id;

ALTER TABLE workforce_members DROP COLUMN source_employee_id;

CREATE UNIQUE INDEX idx_bookings_management_token
    ON bookings_bookings (management_token)
    WHERE management_token IS NOT NULL;

-- ============================================================
-- Consumer activity projections (Doc 12 §5.13) — Stage 7 UI later
-- ============================================================

CREATE TABLE consumer_activity_projections (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    identity_id UUID NOT NULL REFERENCES platform_identities(id),
    business_id UUID NOT NULL REFERENCES businesses(id),
    activity_type TEXT NOT NULL,
    resource_type TEXT NOT NULL,
    resource_id UUID NOT NULL,
    occurred_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    summary JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_consumer_activity_identity
    ON consumer_activity_projections (identity_id, occurred_at DESC);
CREATE INDEX idx_consumer_activity_business
    ON consumer_activity_projections (business_id, occurred_at DESC);
CREATE UNIQUE INDEX idx_consumer_activity_dedupe
    ON consumer_activity_projections (identity_id, resource_type, resource_id, activity_type);

ALTER TABLE workforce_members ENABLE ROW LEVEL SECURITY;
ALTER TABLE workforce_location_assignments ENABLE ROW LEVEL SECURITY;
ALTER TABLE workforce_service_associations ENABLE ROW LEVEL SECURITY;
ALTER TABLE workforce_availability ENABLE ROW LEVEL SECURITY;
ALTER TABLE bookings_policies ENABLE ROW LEVEL SECURITY;
ALTER TABLE consumer_activity_projections ENABLE ROW LEVEL SECURITY;

CREATE POLICY workforce_members_member ON workforce_members
    FOR SELECT USING (business_id = current_business_id());
CREATE POLICY workforce_locations_member ON workforce_location_assignments
    FOR SELECT USING (business_id = current_business_id());
CREATE POLICY workforce_services_member ON workforce_service_associations
    FOR SELECT USING (business_id = current_business_id());
CREATE POLICY workforce_availability_member ON workforce_availability
    FOR SELECT USING (business_id = current_business_id());
CREATE POLICY bookings_policies_member ON bookings_policies
    FOR SELECT USING (business_id = current_business_id());
CREATE POLICY consumer_activity_self ON consumer_activity_projections
    FOR SELECT USING (identity_id = auth.uid());
