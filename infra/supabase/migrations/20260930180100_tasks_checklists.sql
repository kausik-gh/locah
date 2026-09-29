-- Shared tasks and checklists (Business OS Guide §6.2 `tasks`).
--
-- One task engine. A task points at a business, customer, project, job,
-- booking, order, compliance item, location, or staff assignment through
-- related_type / related_id. There is no ProjectTasks, JobTasks, or
-- ComplianceTasks table.
--
-- Assignment scope uses assignee_member_id, the same workforce-member arm
-- as project tasks (P2-01). This migration does not replace that model.

CREATE TABLE tasks_tasks (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    business_id UUID NOT NULL REFERENCES businesses(id),
    location_id UUID REFERENCES business_locations(id),
    title TEXT NOT NULL CHECK (char_length(title) BETWEEN 1 AND 160),
    description TEXT CHECK (description IS NULL OR char_length(description) <= 4000),
    status TEXT NOT NULL DEFAULT 'open'
        CHECK (status IN ('open', 'in_progress', 'completed', 'cancelled')),
    priority TEXT NOT NULL DEFAULT 'normal'
        CHECK (priority IN ('low', 'normal', 'high', 'urgent')),
    due_at TIMESTAMPTZ,
    assignee_member_id UUID REFERENCES workforce_members(id),
    related_type TEXT NOT NULL CHECK (related_type IN (
        'business', 'customer', 'project', 'job', 'booking', 'order',
        'compliance_item', 'location', 'staff_assignment'
    )),
    related_id UUID NOT NULL,
    -- Set for a spawned checklist or a compliance-due task. One open row per key.
    occurrence_key TEXT CHECK (occurrence_key IS NULL OR char_length(occurrence_key) BETWEEN 1 AND 200),
    template_id UUID,
    completed_at TIMESTAMPTZ,
    completed_by UUID,
    created_by UUID,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    version INTEGER NOT NULL DEFAULT 1,
    CHECK (related_type <> 'business' OR related_id = business_id),
    CHECK (status <> 'completed' OR completed_at IS NOT NULL)
);
CREATE INDEX tasks_tasks_assignee ON tasks_tasks (business_id, assignee_member_id, status);
CREATE INDEX tasks_tasks_due ON tasks_tasks (business_id, due_at) WHERE status IN ('open', 'in_progress');
CREATE INDEX tasks_tasks_related ON tasks_tasks (business_id, related_type, related_id);
CREATE UNIQUE INDEX tasks_tasks_occurrence ON tasks_tasks (business_id, occurrence_key)
    WHERE occurrence_key IS NOT NULL AND status <> 'cancelled';
CREATE TRIGGER tasks_tasks_updated BEFORE UPDATE ON tasks_tasks
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

CREATE TABLE tasks_checklist_items (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    business_id UUID NOT NULL REFERENCES businesses(id),
    task_id UUID NOT NULL REFERENCES tasks_tasks(id),
    position INTEGER NOT NULL CHECK (position >= 0),
    label TEXT NOT NULL CHECK (char_length(label) BETWEEN 1 AND 200),
    required BOOLEAN NOT NULL DEFAULT true,
    photo_required BOOLEAN NOT NULL DEFAULT false,
    done_at TIMESTAMPTZ,
    done_by UUID,
    proof_media_id UUID REFERENCES media_assets(id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (task_id, position),
    CHECK (done_at IS NULL OR photo_required = false OR proof_media_id IS NOT NULL)
);
CREATE INDEX tasks_checklist_items_task ON tasks_checklist_items (task_id, position);

CREATE TABLE tasks_history (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    business_id UUID NOT NULL REFERENCES businesses(id),
    task_id UUID NOT NULL REFERENCES tasks_tasks(id),
    action TEXT NOT NULL CHECK (action IN (
        'created', 'updated', 'assigned', 'started', 'checklist', 'completed', 'cancelled'
    )),
    from_status TEXT,
    to_status TEXT,
    note TEXT CHECK (note IS NULL OR char_length(note) <= 500),
    actor_identity_id UUID,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX tasks_history_task ON tasks_history (task_id, created_at);

CREATE OR REPLACE FUNCTION tasks_history_append_only() RETURNS trigger
    LANGUAGE plpgsql AS $$
BEGIN
    RAISE EXCEPTION 'task history is append-only';
END;
$$;
CREATE TRIGGER tasks_history_immutable BEFORE UPDATE OR DELETE ON tasks_history
    FOR EACH ROW EXECUTE FUNCTION tasks_history_append_only();

-- Repeatable operational lists (opening, closing, handover). Spawning copies
-- the items onto one task; the template is not a second task engine.
CREATE TABLE tasks_checklist_templates (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    business_id UUID NOT NULL REFERENCES businesses(id),
    location_id UUID REFERENCES business_locations(id),
    name TEXT NOT NULL CHECK (char_length(name) BETWEEN 1 AND 120),
    kind TEXT NOT NULL DEFAULT 'custom'
        CHECK (kind IN ('opening', 'closing', 'handover', 'prep', 'custom')),
    status TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'archived')),
    created_by UUID,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    version INTEGER NOT NULL DEFAULT 1
);
CREATE TRIGGER tasks_checklist_templates_updated BEFORE UPDATE ON tasks_checklist_templates
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

CREATE TABLE tasks_checklist_template_items (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    business_id UUID NOT NULL REFERENCES businesses(id),
    template_id UUID NOT NULL REFERENCES tasks_checklist_templates(id),
    position INTEGER NOT NULL CHECK (position >= 0),
    label TEXT NOT NULL CHECK (char_length(label) BETWEEN 1 AND 200),
    required BOOLEAN NOT NULL DEFAULT true,
    photo_required BOOLEAN NOT NULL DEFAULT false,
    UNIQUE (template_id, position)
);

-- Idempotency keys for task event handlers (redelivery does the work once).
CREATE TABLE tasks_handler_receipts (
    business_id UUID NOT NULL REFERENCES businesses(id),
    subscriber_id TEXT NOT NULL,
    idempotency_key TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (business_id, subscriber_id, idempotency_key)
);

ALTER TABLE tasks_tasks
    ADD CONSTRAINT tasks_tasks_template_fk
    FOREIGN KEY (template_id) REFERENCES tasks_checklist_templates(id);

-- ---------------------------------------------------------------- RLS
DO $$
DECLARE t TEXT;
BEGIN
    FOREACH t IN ARRAY ARRAY[
        'tasks_tasks', 'tasks_checklist_items', 'tasks_history',
        'tasks_checklist_templates', 'tasks_checklist_template_items', 'tasks_handler_receipts'
    ] LOOP
        EXECUTE format('ALTER TABLE %I ENABLE ROW LEVEL SECURITY', t);
        EXECUTE format('ALTER TABLE %I FORCE ROW LEVEL SECURITY', t);
        EXECUTE format('CREATE POLICY %I ON %I FOR SELECT TO public USING (business_id = current_business_id())',
                       t || '_member_read', t);
        EXECUTE format('CREATE POLICY %I ON %I FOR ALL TO platform_api USING (business_id = current_business_id()) '
                       'WITH CHECK (business_id = current_business_id())', t || '_api', t);
        EXECUTE format('GRANT SELECT, INSERT, UPDATE ON %I TO platform_api', t);
        EXECUTE format('REVOKE DELETE ON %I FROM platform_api', t);
        EXECUTE format('REVOKE ALL PRIVILEGES ON TABLE %I FROM anon', t);
    END LOOP;
END
$$;

CREATE POLICY tasks_tasks_location_scope ON tasks_tasks AS RESTRICTIVE FOR ALL TO platform_api
    USING (location_scope_allows(location_id))
    WITH CHECK (location_scope_allows(location_id));
CREATE POLICY tasks_tasks_assignment_scope ON tasks_tasks AS RESTRICTIVE FOR ALL TO platform_api
    USING (assignment_scope_allows_member(assignee_member_id))
    WITH CHECK (assignment_scope_allows_member(assignee_member_id));

-- Items and history follow the parent task, so an assignment-scoped member
-- cannot read another person's checklist by id.
CREATE POLICY tasks_items_follow_task ON tasks_checklist_items AS RESTRICTIVE FOR ALL TO platform_api
    USING (EXISTS (
        SELECT 1 FROM tasks_tasks t
         WHERE t.id = tasks_checklist_items.task_id
           AND assignment_scope_allows_member(t.assignee_member_id)
           AND location_scope_allows(t.location_id)))
    WITH CHECK (EXISTS (
        SELECT 1 FROM tasks_tasks t
         WHERE t.id = tasks_checklist_items.task_id
           AND assignment_scope_allows_member(t.assignee_member_id)
           AND location_scope_allows(t.location_id)));

CREATE POLICY tasks_history_follow_task ON tasks_history AS RESTRICTIVE FOR ALL TO platform_api
    USING (EXISTS (
        SELECT 1 FROM tasks_tasks t
         WHERE t.id = tasks_history.task_id
           AND assignment_scope_allows_member(t.assignee_member_id)
           AND location_scope_allows(t.location_id)))
    WITH CHECK (EXISTS (
        SELECT 1 FROM tasks_tasks t
         WHERE t.id = tasks_history.task_id
           AND assignment_scope_allows_member(t.assignee_member_id)
           AND location_scope_allows(t.location_id)));
