-- Projects and Work Orders: committed work, tracked from agreement to done.
--
-- What this is, and what it deliberately is not
-- ---------------------------------------------
-- An order records a purchase and a booking records a slot. Neither can say
-- "this is a six-week kitchen refit, here are its stages, here is who is doing
-- each part, here is where it has got to." That is the gap: work that outlives a
-- single transaction and has to be steered while it runs.
--
-- One entity, not two. An interior designer's "project" and an electrician's
-- "work order" differ in how long they last and how many stages they have, not
-- in what they are — a unit of committed work for a customer, executed by
-- assigned people, tracked to completion. Making them separate tables would
-- duplicate every lifecycle rule for a difference that is vocabulary. The noun
-- and the starting stages come from the Business-Type Profile
-- (`ProjectSemantics`), so a clinic sees "Case" and a studio sees "Project"
-- without either becoming a branch in this schema or in the service.
--
-- What it does not own
-- --------------------
-- Customers, workforce, quotations, payments, audit, notifications and events
-- already exist and are referenced, never copied. A project points at the quote
-- it came from; it does not restate the quote's prices. It points at a workforce
-- member for an assignment; it does not keep a second list of who works here.
-- The one number a project carries of its own is `agreed_value`, and that is a
-- snapshot copied from the accepted quote at conversion for reporting — the
-- quote remains the commercial truth.

CREATE TABLE projects_projects (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    business_id UUID NOT NULL REFERENCES businesses(id),
    location_id UUID REFERENCES business_locations(id),
    customer_contact_id UUID REFERENCES customer_relationships_contacts(id),

    -- Human reference, per business, e.g. `P-2026-0007`. Unique per business so
    -- two businesses both start at one and neither has to explain a gap.
    reference TEXT NOT NULL,
    title TEXT NOT NULL,
    summary TEXT,
    -- Never shown outside the team.
    internal_notes TEXT,

    -- draft      — being scoped, not yet committed
    -- active     — work is live
    -- on_hold    — paused for a reason worth recording
    -- completed  — finished
    -- cancelled  — abandoned; kept, never deleted
    status TEXT NOT NULL DEFAULT 'draft' CHECK (status IN (
        'draft', 'active', 'on_hold', 'completed', 'cancelled'
    )),
    priority TEXT NOT NULL DEFAULT 'normal' CHECK (priority IN ('low', 'normal', 'high', 'urgent')),

    starts_on DATE,
    due_on DATE,
    completed_at TIMESTAMPTZ,
    cancelled_at TIMESTAMPTZ,
    on_hold_reason TEXT,
    cancellation_reason TEXT,

    -- Where the work came from. A project converted from an accepted quote
    -- keeps the link both ways so the commercial and the operational record can
    -- always be put back together.
    source_quote_id UUID REFERENCES quotes_quotes(id),
    -- A reporting snapshot of the accepted quote total, in that quote's
    -- currency. Never recalculated here; the quote stays authoritative.
    agreed_value NUMERIC(12, 2) CHECK (agreed_value IS NULL OR agreed_value >= 0),
    currency TEXT NOT NULL DEFAULT 'INR',

    -- Who owns the outcome. A workforce member, not an identity: the person
    -- responsible for a job is a role the business staffs, and may not have a
    -- platform login at all.
    lead_member_id UUID REFERENCES workforce_members(id),

    version INTEGER NOT NULL DEFAULT 1,
    created_by UUID REFERENCES platform_identities(id),
    deleted_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE UNIQUE INDEX projects_reference_unique
    ON projects_projects (business_id, reference) WHERE deleted_at IS NULL;
CREATE INDEX projects_by_business_status
    ON projects_projects (business_id, status, created_at DESC) WHERE deleted_at IS NULL;
CREATE INDEX projects_by_customer
    ON projects_projects (business_id, customer_contact_id) WHERE deleted_at IS NULL;
-- One project per accepted quote: converting the same quote twice is a mistake,
-- not a feature, and the constraint is what makes the conversion idempotent.
CREATE UNIQUE INDEX projects_one_per_source_quote
    ON projects_projects (source_quote_id) WHERE source_quote_id IS NOT NULL AND deleted_at IS NULL;


-- A stage of the work. Ordered, named by the business, seeded from the
-- Business-Type Profile when a project is created.
CREATE TABLE projects_phases (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    business_id UUID NOT NULL REFERENCES businesses(id),
    project_id UUID NOT NULL REFERENCES projects_projects(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending' CHECK (status IN (
        'pending', 'in_progress', 'done', 'skipped'
    )),
    -- A phase the customer is told about when it completes. Milestones are a
    -- property of a phase rather than a third table: a milestone with no work
    -- behind it is a date in a calendar, not a stage of a project.
    is_milestone BOOLEAN NOT NULL DEFAULT false,
    due_on DATE,
    completed_at TIMESTAMPTZ,
    sort_order INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX projects_phases_by_project ON projects_phases (project_id, sort_order);


-- The actual work. A task belongs to a project and optionally sits in a phase,
-- because plenty of real jobs are a flat list and forcing a phase on them would
-- be ceremony.
CREATE TABLE projects_tasks (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    business_id UUID NOT NULL REFERENCES businesses(id),
    project_id UUID NOT NULL REFERENCES projects_projects(id) ON DELETE CASCADE,
    phase_id UUID REFERENCES projects_phases(id) ON DELETE SET NULL,

    title TEXT NOT NULL,
    description TEXT,
    status TEXT NOT NULL DEFAULT 'todo' CHECK (status IN (
        'todo', 'in_progress', 'blocked', 'done', 'cancelled'
    )),
    -- Assignment reuses the workforce module rather than inventing a second
    -- notion of who works here.
    assignee_member_id UUID REFERENCES workforce_members(id),
    due_on DATE,
    completed_at TIMESTAMPTZ,
    blocked_reason TEXT,
    sort_order INTEGER NOT NULL DEFAULT 0,

    version INTEGER NOT NULL DEFAULT 1,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX projects_tasks_by_project ON projects_tasks (project_id, sort_order);
CREATE INDEX projects_tasks_by_assignee
    ON projects_tasks (business_id, assignee_member_id, status);


ALTER TABLE projects_projects ENABLE ROW LEVEL SECURITY;
ALTER TABLE projects_projects FORCE ROW LEVEL SECURITY;
ALTER TABLE projects_phases ENABLE ROW LEVEL SECURITY;
ALTER TABLE projects_phases FORCE ROW LEVEL SECURITY;
ALTER TABLE projects_tasks ENABLE ROW LEVEL SECURITY;
ALTER TABLE projects_tasks FORCE ROW LEVEL SECURITY;

CREATE POLICY projects_member_read ON projects_projects
    FOR SELECT TO public USING (deleted_at IS NULL AND business_id = current_business_id());
CREATE POLICY projects_api_write ON projects_projects
    FOR ALL TO platform_api USING (business_id = current_business_id())
    WITH CHECK (business_id = current_business_id());

CREATE POLICY projects_phases_member_read ON projects_phases
    FOR SELECT TO public USING (business_id = current_business_id());
CREATE POLICY projects_phases_api_write ON projects_phases
    FOR ALL TO platform_api USING (business_id = current_business_id())
    WITH CHECK (business_id = current_business_id());

CREATE POLICY projects_tasks_member_read ON projects_tasks
    FOR SELECT TO public USING (business_id = current_business_id());
CREATE POLICY projects_tasks_api_write ON projects_tasks
    FOR ALL TO platform_api USING (business_id = current_business_id())
    WITH CHECK (business_id = current_business_id());

GRANT SELECT, INSERT, UPDATE, DELETE ON projects_projects TO platform_api;
GRANT SELECT, INSERT, UPDATE, DELETE ON projects_phases TO platform_api;
GRANT SELECT, INSERT, UPDATE, DELETE ON projects_tasks TO platform_api;


INSERT INTO module_definitions (id, name, module_class, description, dependencies, is_available)
VALUES ('projects', 'Projects & Work Orders', 'optional',
        'Committed work tracked through stages, tasks and assignments to completion',
        '{core-business-profile}', true)
ON CONFLICT (id) DO NOTHING;
