-- Stage 3: Location & People Kernel

ALTER TABLE business_locations
    ADD COLUMN IF NOT EXISTS status TEXT NOT NULL DEFAULT 'active'
        CHECK (status IN ('active', 'archived')),
    ADD COLUMN IF NOT EXISTS internal_code TEXT,
    ADD COLUMN IF NOT EXISTS phone TEXT,
    ADD COLUMN IF NOT EXISTS email TEXT,
    ADD COLUMN IF NOT EXISTS notes TEXT,
    ADD COLUMN IF NOT EXISTS latitude DOUBLE PRECISION,
    ADD COLUMN IF NOT EXISTS longitude DOUBLE PRECISION;

CREATE INDEX IF NOT EXISTS idx_business_locations_status
    ON business_locations(business_id, status)
    WHERE deleted_at IS NULL;

CREATE UNIQUE INDEX IF NOT EXISTS idx_business_locations_one_primary
    ON business_locations(business_id)
    WHERE deleted_at IS NULL AND is_primary = true AND status = 'active';

CREATE TABLE business_employees (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    business_id UUID NOT NULL REFERENCES businesses(id),
    identity_id UUID REFERENCES platform_identities(id),
    membership_id UUID REFERENCES business_memberships(id),
    display_name TEXT NOT NULL,
    email TEXT,
    phone TEXT,
    designation TEXT,
    internal_code TEXT,
    status TEXT NOT NULL DEFAULT 'active'
        CHECK (status IN ('active', 'inactive', 'archived')),
    notes TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    deleted_at TIMESTAMPTZ,
    version INTEGER NOT NULL DEFAULT 1
);

CREATE INDEX idx_business_employees_business ON business_employees(business_id);
CREATE INDEX idx_business_employees_active ON business_employees(business_id)
    WHERE deleted_at IS NULL AND status != 'archived';
CREATE INDEX idx_business_employees_display_name ON business_employees(business_id, display_name)
    WHERE deleted_at IS NULL;
CREATE UNIQUE INDEX idx_business_employees_internal_code
    ON business_employees(business_id, internal_code)
    WHERE deleted_at IS NULL AND internal_code IS NOT NULL;

CREATE TABLE business_employee_location_assignments (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    business_id UUID NOT NULL REFERENCES businesses(id),
    employee_id UUID NOT NULL REFERENCES business_employees(id) ON DELETE CASCADE,
    location_id UUID NOT NULL REFERENCES business_locations(id),
    is_primary BOOLEAN NOT NULL DEFAULT false,
    assigned_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    assigned_by UUID REFERENCES platform_identities(id),
    UNIQUE (employee_id, location_id)
);

CREATE INDEX idx_employee_location_assignments_employee
    ON business_employee_location_assignments(employee_id);
CREATE INDEX idx_employee_location_assignments_location
    ON business_employee_location_assignments(location_id);

CREATE UNIQUE INDEX idx_employee_one_primary_assignment
    ON business_employee_location_assignments(employee_id)
    WHERE is_primary = true;

CREATE TRIGGER trg_business_employees_updated_at BEFORE UPDATE ON business_employees
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

ALTER TABLE business_employees ENABLE ROW LEVEL SECURITY;
ALTER TABLE business_employee_location_assignments ENABLE ROW LEVEL SECURITY;

CREATE POLICY business_employees_member_read ON business_employees FOR SELECT USING (
    deleted_at IS NULL AND business_id = current_business_id()
);

CREATE POLICY business_employee_assignments_member_read
    ON business_employee_location_assignments FOR SELECT USING (
    business_id = current_business_id()
);
