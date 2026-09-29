-- One presence record for member, academic, staff and booking occurrences.
-- Eligibility, session/enrolment, employment and booking truth live elsewhere.
CREATE TABLE attendance_events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    business_id UUID NOT NULL REFERENCES businesses(id),
    context TEXT NOT NULL CHECK (context IN ('membership_checkin','academic_session','staff_site','booking_arrival')),
    source_id UUID NOT NULL,
    subject_contact_id UUID REFERENCES customer_relationships_contacts(id),
    subject_member_id UUID REFERENCES workforce_members(id),
    location_id UUID REFERENCES business_locations(id),
    assigned_member_id UUID REFERENCES workforce_members(id),
    status TEXT NOT NULL,
    channel TEXT NOT NULL CHECK (channel IN ('manual','qr','integration')),
    idempotency_key TEXT NOT NULL CHECK (length(idempotency_key) BETWEEN 1 AND 120),
    checked_in_at TIMESTAMPTZ,
    checked_out_at TIMESTAMPTZ,
    recorded_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    recorded_by_identity_id UUID NOT NULL REFERENCES platform_identities(id),
    verification_metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    geo_verified BOOLEAN NOT NULL DEFAULT false CHECK (geo_verified = false),
    version INTEGER NOT NULL DEFAULT 1 CHECK (version > 0),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CHECK ((subject_contact_id IS NOT NULL) <> (subject_member_id IS NOT NULL)),
    CHECK ((context = 'staff_site') = (subject_member_id IS NOT NULL)),
    CHECK ((context = 'academic_session' AND status IN ('present','absent','late','excused'))
        OR (context <> 'academic_session' AND status IN ('checked_in','checked_out'))),
    CHECK (context <> 'staff_site' OR (location_id IS NOT NULL AND source_id = location_id)),
    CHECK (checked_out_at IS NULL OR (checked_in_at IS NOT NULL AND checked_out_at >= checked_in_at)),
    UNIQUE (business_id, idempotency_key)
);
CREATE UNIQUE INDEX attendance_academic_occurrence ON attendance_events
    (business_id, source_id, subject_contact_id) WHERE context = 'academic_session';
CREATE UNIQUE INDEX attendance_booking_arrival ON attendance_events
    (business_id, source_id) WHERE context = 'booking_arrival';
CREATE INDEX attendance_today ON attendance_events (business_id, recorded_at DESC);
CREATE INDEX attendance_subject_contact ON attendance_events (business_id, subject_contact_id, recorded_at DESC)
    WHERE subject_contact_id IS NOT NULL;
CREATE INDEX attendance_subject_member ON attendance_events (business_id, subject_member_id, recorded_at DESC)
    WHERE subject_member_id IS NOT NULL;
CREATE INDEX attendance_source ON attendance_events (business_id, context, source_id);
CREATE INDEX attendance_assignee ON attendance_events (business_id, assigned_member_id, recorded_at DESC)
    WHERE assigned_member_id IS NOT NULL;

ALTER TABLE attendance_events ENABLE ROW LEVEL SECURITY;
ALTER TABLE attendance_events FORCE ROW LEVEL SECURITY;
REVOKE ALL ON attendance_events FROM anon, authenticated;
CREATE POLICY attendance_api_tenant ON attendance_events FOR ALL TO platform_api
    USING (business_id = current_business_id()) WITH CHECK (business_id = current_business_id());
CREATE POLICY attendance_api_location ON attendance_events AS RESTRICTIVE FOR ALL TO platform_api
    USING (location_scope_allows(location_id)) WITH CHECK (location_scope_allows(location_id));
CREATE POLICY attendance_api_assignment ON attendance_events AS RESTRICTIVE FOR ALL TO platform_api
    USING (assignment_scope_allows_member(assigned_member_id))
    WITH CHECK (assignment_scope_allows_member(assigned_member_id));
GRANT SELECT, INSERT, UPDATE ON attendance_events TO platform_api;
