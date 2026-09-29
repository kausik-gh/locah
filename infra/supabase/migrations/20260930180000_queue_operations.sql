-- Walk-in queue (Business OS Guide §6.2 `queue` / registry `queue-operations`;
-- Doc 10 QueueEntry; Doc 09 §10.4).
--
-- A lane is one live queue at a location, optionally for one provider,
-- department, or bookable resource. A token (queue_entries) is the walk-in
-- or the check-in. When the person already has a Booking, the token stores
-- booking_id and nothing else from that booking — Bookings stays the only
-- booking record.
--
-- Statuses: waiting → called → serving → served, or missed. Missed can
-- return to waiting only when the lane allows requeue.
-- "Your turn soon" is queue.turn_soon. This migration does not touch Messaging.

CREATE TABLE queue_lanes (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    business_id UUID NOT NULL REFERENCES businesses(id),
    location_id UUID NOT NULL REFERENCES business_locations(id),
    name TEXT NOT NULL CHECK (char_length(name) BETWEEN 1 AND 80),
    provider_id UUID REFERENCES workforce_members(id),
    department TEXT CHECK (department IS NULL OR char_length(department) BETWEEN 1 AND 80),
    resource_id UUID REFERENCES bookings_resources(id),
    allow_requeue BOOLEAN NOT NULL DEFAULT true,
    -- How many people ahead still counts as "your turn soon" (0 = only the next person).
    turn_soon_ahead INTEGER NOT NULL DEFAULT 2 CHECK (turn_soon_ahead BETWEEN 0 AND 50),
    avg_service_minutes INTEGER CHECK (avg_service_minutes IS NULL OR avg_service_minutes BETWEEN 1 AND 480),
    token_seq INTEGER NOT NULL DEFAULT 0,
    token_seq_day DATE,
    status TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'archived')),
    created_by UUID,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    version INTEGER NOT NULL DEFAULT 1
);
CREATE INDEX queue_lanes_location ON queue_lanes (business_id, location_id, status);
CREATE INDEX queue_lanes_provider ON queue_lanes (business_id, provider_id) WHERE provider_id IS NOT NULL;
CREATE TRIGGER queue_lanes_updated BEFORE UPDATE ON queue_lanes
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

CREATE TABLE queue_entries (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    business_id UUID NOT NULL REFERENCES businesses(id),
    location_id UUID NOT NULL REFERENCES business_locations(id),
    lane_id UUID NOT NULL REFERENCES queue_lanes(id),
    token_number INTEGER NOT NULL CHECK (token_number > 0),
    token_day DATE NOT NULL,
    status TEXT NOT NULL DEFAULT 'waiting'
        CHECK (status IN ('waiting', 'called', 'serving', 'served', 'missed')),
    source TEXT NOT NULL CHECK (source IN ('walk_in', 'booking')),
    -- Reference only. Booking columns are not copied here.
    booking_id UUID REFERENCES bookings_bookings(id),
    customer_contact_id UUID REFERENCES customer_relationships_contacts(id),
    -- Walk-in name the desk typed. Null when the token only points at a booking.
    party_label TEXT CHECK (party_label IS NULL OR char_length(party_label) BETWEEN 1 AND 80),
    priority INTEGER NOT NULL DEFAULT 0 CHECK (priority BETWEEN 0 AND 9),
    -- Lane provider at issue time, so assignment-scope RLS can see the row
    -- without reading the booking.
    provider_id UUID,
    visit_cycle INTEGER NOT NULL DEFAULT 1 CHECK (visit_cycle > 0),
    turn_soon_emitted_at TIMESTAMPTZ,
    issued_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    called_at TIMESTAMPTZ,
    serving_at TIMESTAMPTZ,
    closed_at TIMESTAMPTZ,
    requeued_at TIMESTAMPTZ,
    idempotency_key TEXT,
    created_by UUID,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    version INTEGER NOT NULL DEFAULT 1,
    CHECK (source <> 'booking' OR booking_id IS NOT NULL),
    CHECK (source <> 'walk_in' OR booking_id IS NULL)
);
CREATE UNIQUE INDEX queue_entries_token ON queue_entries (lane_id, token_day, token_number);
CREATE UNIQUE INDEX queue_entries_idem ON queue_entries (business_id, idempotency_key)
    WHERE idempotency_key IS NOT NULL;
-- One open token per booking. A finished or missed visit can be checked in again.
CREATE UNIQUE INDEX queue_entries_open_booking ON queue_entries (business_id, booking_id)
    WHERE booking_id IS NOT NULL AND status IN ('waiting', 'called', 'serving');
CREATE INDEX queue_entries_board ON queue_entries (lane_id, status, priority DESC, issued_at);
CREATE TRIGGER queue_entries_updated BEFORE UPDATE ON queue_entries
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

CREATE TABLE queue_entry_events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    business_id UUID NOT NULL REFERENCES businesses(id),
    entry_id UUID NOT NULL REFERENCES queue_entries(id),
    action TEXT NOT NULL CHECK (action IN ('issued', 'called', 'serving', 'served', 'missed', 'requeued')),
    from_status TEXT,
    to_status TEXT NOT NULL,
    actor_identity_id UUID,
    note TEXT CHECK (note IS NULL OR char_length(note) <= 300),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX queue_entry_events_entry ON queue_entry_events (entry_id, created_at);

CREATE OR REPLACE FUNCTION queue_history_append_only() RETURNS trigger
    LANGUAGE plpgsql AS $$
BEGIN
    RAISE EXCEPTION 'queue history is append-only';
END;
$$;
CREATE TRIGGER queue_entry_events_immutable BEFORE UPDATE OR DELETE ON queue_entry_events
    FOR EACH ROW EXECUTE FUNCTION queue_history_append_only();

-- Materialised once per visit by the queue.turn_soon handler. Messaging reads
-- this contract; it does not own the table.
CREATE TABLE queue_turn_notices (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    business_id UUID NOT NULL REFERENCES businesses(id),
    entry_id UUID NOT NULL REFERENCES queue_entries(id),
    visit_cycle INTEGER NOT NULL,
    ahead INTEGER NOT NULL CHECK (ahead >= 0),
    token_number INTEGER NOT NULL,
    customer_contact_id UUID,
    booking_id UUID,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (entry_id, visit_cycle)
);

-- ---------------------------------------------------------------- RLS
DO $$
DECLARE t TEXT;
BEGIN
    FOREACH t IN ARRAY ARRAY['queue_lanes', 'queue_entries', 'queue_entry_events', 'queue_turn_notices'] LOOP
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

-- Location scope and assignment scope already exist (P1 roles, P2-01).
-- A provider sees the lane and tokens where they are the provider.
-- A shared department lane (no provider) is for location-scoped desk staff.
CREATE POLICY queue_lanes_location_scope ON queue_lanes AS RESTRICTIVE FOR ALL TO platform_api
    USING (location_scope_allows(location_id))
    WITH CHECK (location_scope_allows(location_id));
CREATE POLICY queue_lanes_assignment_scope ON queue_lanes AS RESTRICTIVE FOR ALL TO platform_api
    USING (assignment_scope_allows_member(provider_id))
    WITH CHECK (assignment_scope_allows_member(provider_id));

CREATE POLICY queue_entries_location_scope ON queue_entries AS RESTRICTIVE FOR ALL TO platform_api
    USING (location_scope_allows(location_id))
    WITH CHECK (location_scope_allows(location_id));
CREATE POLICY queue_entries_assignment_scope ON queue_entries AS RESTRICTIVE FOR ALL TO platform_api
    USING (assignment_scope_allows_member(provider_id))
    WITH CHECK (assignment_scope_allows_member(provider_id));

-- History and turn notices follow the token, so a provider cannot read
-- another provider's calls by guessing an id.
CREATE POLICY queue_events_follow_entry ON queue_entry_events AS RESTRICTIVE FOR ALL TO platform_api
    USING (EXISTS (
        SELECT 1 FROM queue_entries e
         WHERE e.id = queue_entry_events.entry_id
           AND assignment_scope_allows_member(e.provider_id)
           AND location_scope_allows(e.location_id)))
    WITH CHECK (EXISTS (
        SELECT 1 FROM queue_entries e
         WHERE e.id = queue_entry_events.entry_id
           AND assignment_scope_allows_member(e.provider_id)
           AND location_scope_allows(e.location_id)));

CREATE POLICY queue_notices_follow_entry ON queue_turn_notices AS RESTRICTIVE FOR ALL TO platform_api
    USING (EXISTS (
        SELECT 1 FROM queue_entries e
         WHERE e.id = queue_turn_notices.entry_id
           AND assignment_scope_allows_member(e.provider_id)
           AND location_scope_allows(e.location_id)))
    WITH CHECK (EXISTS (
        SELECT 1 FROM queue_entries e
         WHERE e.id = queue_turn_notices.entry_id
           AND assignment_scope_allows_member(e.provider_id)
           AND location_scope_allows(e.location_id)));
