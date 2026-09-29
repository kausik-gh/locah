-- P2-01: the stage engine (Capability Universe §24 #10) — "configurable stage
-- sets with guarded transitions shared by orders, jobs, leads, projects".
--
-- Each module keeps its core statuses and the rules between them (what
-- releases stock, what makes a customer, what closes a project). A business
-- may add its own named steps inside a status — an order's "Picking" and
-- "Packed" inside Preparing, an enquiry's "Site visit booked" inside Contacted
-- — rename any stage, and mark a step as needing a note. A record's `stage` is
-- one of those steps; moving between statuses still runs through the module's
-- own service. Job cards join with Jobs (P5), dispatch jobs with Dispatch.

CREATE TABLE platform_stage_sets (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    business_id UUID NOT NULL REFERENCES businesses(id),
    entity TEXT NOT NULL CHECK (entity IN ('orders', 'leads', 'projects')),
    stages JSONB NOT NULL CHECK (jsonb_typeof(stages) = 'array'),
    version INTEGER NOT NULL DEFAULT 1,
    updated_by UUID REFERENCES platform_identities(id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (business_id, entity)
);

CREATE TABLE platform_stage_events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    business_id UUID NOT NULL REFERENCES businesses(id),
    entity TEXT NOT NULL CHECK (entity IN ('orders', 'leads', 'projects')),
    record_id UUID NOT NULL,
    from_stage TEXT,
    to_stage TEXT NOT NULL,
    from_status TEXT,
    to_status TEXT NOT NULL,
    note TEXT CHECK (note IS NULL OR char_length(note) <= 500),
    actor_identity_id UUID REFERENCES platform_identities(id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX platform_stage_events_record ON platform_stage_events (business_id, entity, record_id, created_at);

ALTER TABLE orders_orders ADD COLUMN IF NOT EXISTS stage TEXT;
ALTER TABLE leads_leads ADD COLUMN IF NOT EXISTS stage TEXT;
ALTER TABLE projects_projects ADD COLUMN IF NOT EXISTS stage TEXT;

ALTER TABLE platform_stage_sets ENABLE ROW LEVEL SECURITY;
ALTER TABLE platform_stage_sets FORCE ROW LEVEL SECURITY;
CREATE POLICY platform_stage_sets_api ON platform_stage_sets FOR ALL TO platform_api
    USING (business_id = current_business_id()) WITH CHECK (business_id = current_business_id());
GRANT SELECT, INSERT, UPDATE ON platform_stage_sets TO platform_api;

-- Stage events are history: the API may add and read them, never change or remove them.
ALTER TABLE platform_stage_events ENABLE ROW LEVEL SECURITY;
ALTER TABLE platform_stage_events FORCE ROW LEVEL SECURITY;
CREATE POLICY platform_stage_events_read ON platform_stage_events FOR SELECT TO platform_api
    USING (business_id = current_business_id());
CREATE POLICY platform_stage_events_insert ON platform_stage_events FOR INSERT TO platform_api
    WITH CHECK (business_id = current_business_id());
GRANT SELECT, INSERT ON platform_stage_events TO platform_api;

REVOKE ALL ON platform_stage_sets, platform_stage_events FROM anon;
