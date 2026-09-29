-- Dispatch execution (Capability Universe §13; founder: dispatch owns the
-- physical work after the sale exists).
--
-- The order stays the sale. Fulfilment stays the pickup/delivery choice.
-- A dispatch job is the execution of that choice: who is carrying it, the
-- pickup and drop-off, the planned time, the actual times, and an append-only
-- status history. Live coordinates are not stored here — a device that is
-- actually sharing a location is a later activation. This migration does not
-- invent a position.

CREATE TABLE dispatch_jobs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    business_id UUID NOT NULL REFERENCES businesses(id),
    order_id UUID NOT NULL REFERENCES orders_orders(id),
    fulfilment_job_id UUID REFERENCES fulfilment_jobs(id),
    location_id UUID NOT NULL REFERENCES business_locations(id),
    -- delivery executes a drop-off; pickup executes a customer collection.
    kind TEXT NOT NULL CHECK (kind IN ('delivery', 'pickup')),
    status TEXT NOT NULL DEFAULT 'unassigned'
        CHECK (status IN (
            'unassigned', 'assigned', 'picked_up', 'out_for_delivery',
            'delivered', 'failed'
        )),
    assigned_member_id UUID REFERENCES workforce_members(id),
    customer_contact_id UUID REFERENCES customer_relationships_contacts(id),
    order_number TEXT NOT NULL,
    -- Snapshot of the shop the crew collects from, and the address they take
    -- it to. These are location references copied at create time, not a live fix.
    pickup_label TEXT,
    pickup_address JSONB,
    dropoff JSONB,
    planned_at TIMESTAMPTZ,
    assigned_at TIMESTAMPTZ,
    picked_up_at TIMESTAMPTZ,
    out_for_delivery_at TIMESTAMPTZ,
    delivered_at TIMESTAMPTZ,
    failed_at TIMESTAMPTZ,
    proof_note TEXT CHECK (proof_note IS NULL OR char_length(proof_note) <= 500),
    failure_reason TEXT CHECK (failure_reason IS NULL OR char_length(failure_reason) <= 500),
    idempotency_key TEXT,
    created_by UUID REFERENCES platform_identities(id),
    updated_by UUID REFERENCES platform_identities(id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    version INTEGER NOT NULL DEFAULT 1,
    UNIQUE (business_id, order_id)
);

CREATE UNIQUE INDEX idx_dispatch_jobs_idempotency
    ON dispatch_jobs (business_id, idempotency_key)
    WHERE idempotency_key IS NOT NULL;
CREATE INDEX idx_dispatch_jobs_board
    ON dispatch_jobs (business_id, status, planned_at);
CREATE INDEX idx_dispatch_jobs_assignee
    ON dispatch_jobs (business_id, assigned_member_id)
    WHERE assigned_member_id IS NOT NULL;

-- Append-only status history. Replaying a transition sends the same
-- idempotency key and inserts nothing new.
CREATE TABLE dispatch_events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    business_id UUID NOT NULL REFERENCES businesses(id),
    job_id UUID NOT NULL REFERENCES dispatch_jobs(id),
    location_id UUID NOT NULL REFERENCES business_locations(id),
    assigned_member_id UUID REFERENCES workforce_members(id),
    idempotency_key TEXT NOT NULL,
    from_status TEXT,
    to_status TEXT NOT NULL,
    note TEXT CHECK (note IS NULL OR char_length(note) <= 500),
    actor_identity_id UUID REFERENCES platform_identities(id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (business_id, idempotency_key)
);

CREATE INDEX idx_dispatch_events_job
    ON dispatch_events (business_id, job_id, created_at);

ALTER TABLE dispatch_jobs ENABLE ROW LEVEL SECURITY;
ALTER TABLE dispatch_jobs FORCE ROW LEVEL SECURITY;
ALTER TABLE dispatch_events ENABLE ROW LEVEL SECURITY;
ALTER TABLE dispatch_events FORCE ROW LEVEL SECURITY;

CREATE POLICY dispatch_jobs_api ON dispatch_jobs FOR ALL TO platform_api
    USING (business_id = current_business_id())
    WITH CHECK (business_id = current_business_id());
CREATE POLICY dispatch_events_api ON dispatch_events FOR ALL TO platform_api
    USING (business_id = current_business_id())
    WITH CHECK (business_id = current_business_id());

-- Assignment scope, the same primitive bookings and tasks already use.
-- A member limited to their assignments sees only jobs assigned to their
-- workforce record. An unassigned job is not theirs. Unset assignee means
-- no assignment limit (owner, dispatcher).
CREATE POLICY dispatch_jobs_assignment_scope ON dispatch_jobs
    AS RESTRICTIVE FOR ALL TO platform_api
    USING (assignment_scope_allows_member(assigned_member_id))
    WITH CHECK (assignment_scope_allows_member(assigned_member_id));
CREATE POLICY dispatch_events_assignment_scope ON dispatch_events
    AS RESTRICTIVE FOR ALL TO platform_api
    USING (assignment_scope_allows_member(assigned_member_id))
    WITH CHECK (assignment_scope_allows_member(assigned_member_id));

CREATE POLICY dispatch_jobs_location_scope ON dispatch_jobs
    AS RESTRICTIVE FOR ALL TO platform_api
    USING (location_scope_allows(location_id))
    WITH CHECK (location_scope_allows(location_id));
CREATE POLICY dispatch_events_location_scope ON dispatch_events
    AS RESTRICTIVE FOR ALL TO platform_api
    USING (location_scope_allows(location_id))
    WITH CHECK (location_scope_allows(location_id));

GRANT SELECT, INSERT, UPDATE, DELETE ON dispatch_jobs, dispatch_events TO platform_api;
REVOKE ALL ON dispatch_jobs, dispatch_events FROM anon;
