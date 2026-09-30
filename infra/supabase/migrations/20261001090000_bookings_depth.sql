-- Bookings depth (Founder refinement — Bookings §9, §15–§17, §20–§21;
-- Master Doc §6.1, §11.4): holds that release when unpaid, a waitlist that
-- offers a freed place and waits for the customer to take it, and recurring
-- series of linked occurrences.
--
-- One booking record stays the truth. A series only links bookings (each
-- occurrence is an ordinary booking, edited or cancelled on its own). A
-- waitlist entry is a request, never a booking: it becomes one only when the
-- customer takes the offer, through the same booking path and its checks.

ALTER TABLE bookings_policies
    -- How long an unpaid online deposit keeps its slot before it is released.
    ADD COLUMN hold_minutes INTEGER NOT NULL DEFAULT 15 CHECK (hold_minutes BETWEEN 5 AND 1440),
    ADD COLUMN waitlist_enabled BOOLEAN NOT NULL DEFAULT false,
    -- How long a freed place is kept for the customer it was offered to.
    ADD COLUMN waitlist_offer_minutes INTEGER NOT NULL DEFAULT 60
        CHECK (waitlist_offer_minutes BETWEEN 5 AND 2880);

CREATE TABLE bookings_series (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    business_id UUID NOT NULL REFERENCES businesses(id),
    location_id UUID NOT NULL REFERENCES business_locations(id),
    -- Every week, every two weeks … (the only repeat the sources ask for).
    interval_weeks INTEGER NOT NULL DEFAULT 1 CHECK (interval_weeks BETWEEN 1 AND 4),
    occurrences INTEGER NOT NULL CHECK (occurrences BETWEEN 2 AND 52),
    status TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'ended')),
    -- Provider on the occurrences, so assignment-scope RLS can see the series.
    provider_id UUID REFERENCES workforce_members(id),
    ended_at TIMESTAMPTZ,
    created_by UUID,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    version INTEGER NOT NULL DEFAULT 1
);
CREATE TRIGGER bookings_series_updated BEFORE UPDATE ON bookings_series
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

ALTER TABLE bookings_bookings
    ADD COLUMN hold_expires_at TIMESTAMPTZ,
    ADD COLUMN series_id UUID REFERENCES bookings_series(id),
    ADD COLUMN occurrence_index INTEGER CHECK (occurrence_index IS NULL OR occurrence_index >= 1);
CREATE INDEX bookings_bookings_series ON bookings_bookings (series_id, starts_at) WHERE series_id IS NOT NULL;
CREATE UNIQUE INDEX bookings_bookings_series_occurrence ON bookings_bookings (series_id, occurrence_index)
    WHERE series_id IS NOT NULL;

CREATE TABLE bookings_waitlist_entries (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    business_id UUID NOT NULL REFERENCES businesses(id),
    location_id UUID NOT NULL REFERENCES business_locations(id),
    offering_id UUID REFERENCES offerings_catalog_offerings(id),
    provider_id UUID REFERENCES workforce_members(id),
    reservation_mode TEXT NOT NULL,
    starts_at TIMESTAMPTZ NOT NULL,
    ends_at TIMESTAMPTZ NOT NULL,
    party_size INTEGER NOT NULL DEFAULT 1 CHECK (party_size > 0),
    customer_contact_id UUID NOT NULL REFERENCES customer_relationships_contacts(id),
    channel TEXT,
    status TEXT NOT NULL DEFAULT 'waiting'
        CHECK (status IN ('waiting', 'offered', 'booked', 'expired', 'withdrawn')),
    offered_at TIMESTAMPTZ,
    offer_expires_at TIMESTAMPTZ,
    -- The link the offer carries; only its holder may take the place.
    claim_token TEXT,
    booking_id UUID REFERENCES bookings_bookings(id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    version INTEGER NOT NULL DEFAULT 1,
    CHECK (ends_at > starts_at),
    CHECK (status <> 'offered' OR (offer_expires_at IS NOT NULL AND claim_token IS NOT NULL)),
    CHECK (status <> 'booked' OR booking_id IS NOT NULL)
);
-- One open request per customer per slot.
CREATE UNIQUE INDEX bookings_waitlist_open ON bookings_waitlist_entries
    (business_id, customer_contact_id, location_id, reservation_mode, starts_at, COALESCE(offering_id, '00000000-0000-0000-0000-000000000000'::uuid))
    WHERE status IN ('waiting', 'offered');
CREATE INDEX bookings_waitlist_queue ON bookings_waitlist_entries (business_id, location_id, status, created_at);
CREATE TRIGGER bookings_waitlist_entries_updated BEFORE UPDATE ON bookings_waitlist_entries
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

-- ---------------------------------------------------------------- RLS
DO $$
DECLARE t TEXT;
BEGIN
    FOREACH t IN ARRAY ARRAY['bookings_series', 'bookings_waitlist_entries'] LOOP
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

CREATE POLICY bookings_series_location_scope ON bookings_series AS RESTRICTIVE FOR ALL TO platform_api
    USING (location_scope_allows(location_id)) WITH CHECK (location_scope_allows(location_id));
CREATE POLICY bookings_series_assignment_scope ON bookings_series AS RESTRICTIVE FOR ALL TO platform_api
    USING (assignment_scope_allows_member(provider_id)) WITH CHECK (assignment_scope_allows_member(provider_id));
CREATE POLICY bookings_waitlist_location_scope ON bookings_waitlist_entries AS RESTRICTIVE FOR ALL TO platform_api
    USING (location_scope_allows(location_id)) WITH CHECK (location_scope_allows(location_id));
CREATE POLICY bookings_waitlist_assignment_scope ON bookings_waitlist_entries AS RESTRICTIVE FOR ALL TO platform_api
    USING (assignment_scope_allows_member(provider_id)) WITH CHECK (assignment_scope_allows_member(provider_id));
