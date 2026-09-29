-- P5 operational jobs. Projects coordinate commitments; a job records one executable visit/repair.
ALTER TABLE inventory_movements DROP CONSTRAINT inventory_movements_movement_type_check;
ALTER TABLE inventory_movements ADD CONSTRAINT inventory_movements_movement_type_check
    CHECK (movement_type IN ('opening_stock','adjustment','receipt','deduction','reversal','reservation',
                            'wastage','count_variance','conversion_out','conversion_in','job_consumption'));

CREATE TABLE jobs_job_cards (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    business_id UUID NOT NULL REFERENCES businesses(id),
    location_id UUID REFERENCES business_locations(id),
    customer_contact_id UUID NOT NULL REFERENCES customer_relationships_contacts(id),
    project_id UUID REFERENCES projects_projects(id),
    source_quote_id UUID REFERENCES quotes_quotes(id),
    source_type TEXT NOT NULL DEFAULT 'manual' CHECK (source_type IN ('manual','booking','project','quote','service_contract','customer_request')),
    source_id UUID,
    reference TEXT NOT NULL,
    title TEXT NOT NULL CHECK (length(trim(title)) > 0),
    problem TEXT,
    asset_description TEXT,
    asset_serial TEXT,
    priority TEXT NOT NULL DEFAULT 'normal' CHECK (priority IN ('low','normal','high','urgent')),
    status TEXT NOT NULL DEFAULT 'new' CHECK (status IN ('new','assigned','inspecting','awaiting_approval','approved','in_progress','waiting_parts','quality_check','completed','cancelled')),
    stage TEXT,
    scheduled_at TIMESTAMPTZ,
    assigned_member_id UUID REFERENCES workforce_members(id),
    work_performed TEXT,
    approval_note TEXT,
    approval_recorded_at TIMESTAMPTZ,
    completion_note TEXT,
    completed_at TIMESTAMPTZ,
    invoice_id UUID,
    version INTEGER NOT NULL DEFAULT 1,
    created_by UUID REFERENCES platform_identities(id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (business_id, reference),
    UNIQUE (business_id, source_type, source_id)
);
CREATE INDEX jobs_by_business_status ON jobs_job_cards (business_id, status, scheduled_at);
CREATE INDEX jobs_by_customer ON jobs_job_cards (business_id, customer_contact_id, created_at DESC);
CREATE INDEX jobs_by_assignee ON jobs_job_cards (business_id, assigned_member_id, status);
CREATE INDEX jobs_by_project ON jobs_job_cards (business_id, project_id) WHERE project_id IS NOT NULL;

CREATE TABLE jobs_parts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    business_id UUID NOT NULL REFERENCES businesses(id),
    job_id UUID NOT NULL REFERENCES jobs_job_cards(id),
    inventory_movement_id UUID NOT NULL REFERENCES inventory_movements(id),
    offering_id UUID NOT NULL REFERENCES offerings_catalog_offerings(id),
    quantity INTEGER NOT NULL CHECK (quantity > 0),
    serials TEXT[] NOT NULL DEFAULT '{}',
    idempotency_key TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (job_id, idempotency_key),
    UNIQUE (inventory_movement_id)
);
CREATE INDEX jobs_parts_by_job ON jobs_parts (business_id, job_id);

ALTER TABLE jobs_job_cards ENABLE ROW LEVEL SECURITY;
ALTER TABLE jobs_job_cards FORCE ROW LEVEL SECURITY;
ALTER TABLE jobs_parts ENABLE ROW LEVEL SECURITY;
ALTER TABLE jobs_parts FORCE ROW LEVEL SECURITY;
REVOKE ALL ON jobs_job_cards, jobs_parts FROM anon, authenticated;
CREATE POLICY jobs_api_scope ON jobs_job_cards FOR ALL TO platform_api
    USING (business_id = current_business_id()) WITH CHECK (business_id = current_business_id());
CREATE POLICY jobs_assignment ON jobs_job_cards AS RESTRICTIVE FOR ALL TO platform_api
    USING (assignment_scope_allows_member(assigned_member_id))
    WITH CHECK (assignment_scope_allows_member(assigned_member_id));
CREATE POLICY jobs_location ON jobs_job_cards AS RESTRICTIVE FOR ALL TO platform_api
    USING (location_scope_allows(location_id)) WITH CHECK (location_scope_allows(location_id));
CREATE POLICY jobs_parts_api_scope ON jobs_parts FOR ALL TO platform_api
    USING (business_id = current_business_id()) WITH CHECK (business_id = current_business_id());
CREATE POLICY jobs_parts_assignment ON jobs_parts AS RESTRICTIVE FOR ALL TO platform_api
    USING (EXISTS (SELECT 1 FROM jobs_job_cards j WHERE j.id = job_id AND assignment_scope_allows_member(j.assigned_member_id)))
    WITH CHECK (EXISTS (SELECT 1 FROM jobs_job_cards j WHERE j.id = job_id AND assignment_scope_allows_member(j.assigned_member_id)));
GRANT SELECT, INSERT, UPDATE ON jobs_job_cards TO platform_api;
GRANT SELECT, INSERT ON jobs_parts TO platform_api;

INSERT INTO module_definitions (id, name, module_class, description, dependencies, is_available)
VALUES ('jobs', 'Job cards', 'optional', 'Operational work, assigned technicians and parts used', '{core-business-profile}', true)
ON CONFLICT (id) DO NOTHING;
