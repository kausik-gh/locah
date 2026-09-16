-- Stage 7: Bookings & Scheduling Kernel (First Launch scope)
-- Doc 11 §9.3 shared foundation + required reservation modes

CREATE TABLE bookings_bookings (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    business_id UUID NOT NULL REFERENCES businesses(id),
    location_id UUID NOT NULL REFERENCES business_locations(id),
    customer_contact_id UUID REFERENCES customer_relationships_contacts(id),
    offering_id UUID,
    employee_id UUID,
    booking_number TEXT NOT NULL,
    reservation_mode TEXT NOT NULL
        CHECK (reservation_mode IN (
            'appointment', 'accommodation', 'table', 'class_session', 'rental'
        )),
    status TEXT NOT NULL DEFAULT 'pending'
        CHECK (status IN (
            'pending', 'confirmed', 'checked_in', 'completed',
            'cancelled', 'rejected', 'no_show'
        )),
    title TEXT NOT NULL,
    starts_at TIMESTAMPTZ NOT NULL,
    ends_at TIMESTAMPTZ NOT NULL,
    party_size INTEGER NOT NULL DEFAULT 1 CHECK (party_size > 0),
    guest_count INTEGER,
    capacity INTEGER CHECK (capacity IS NULL OR capacity > 0),
    payment_method TEXT NOT NULL DEFAULT 'cod'
        CHECK (payment_method IN ('cod', 'online', 'pay_at_business', 'pay_later')),
    payment_status TEXT NOT NULL DEFAULT 'pending'
        CHECK (payment_status IN ('pending', 'pending_offline', 'paid', 'refunded')),
    internal_reference TEXT,
    cancellation_reason TEXT,
    cancelled_by UUID REFERENCES platform_identities(id),
    idempotency_key TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    deleted_at TIMESTAMPTZ,
    version INTEGER NOT NULL DEFAULT 1,
    CHECK (ends_at > starts_at)
);

CREATE UNIQUE INDEX idx_bookings_number ON bookings_bookings(business_id, booking_number)
    WHERE deleted_at IS NULL;
CREATE UNIQUE INDEX idx_bookings_idempotency ON bookings_bookings(business_id, idempotency_key)
    WHERE deleted_at IS NULL AND idempotency_key IS NOT NULL;
CREATE INDEX idx_bookings_business_status ON bookings_bookings(business_id, status, starts_at DESC)
    WHERE deleted_at IS NULL;
CREATE INDEX idx_bookings_location_time ON bookings_bookings(location_id, starts_at, ends_at)
    WHERE deleted_at IS NULL AND status NOT IN ('cancelled', 'rejected', 'no_show');
CREATE INDEX idx_bookings_employee_time ON bookings_bookings(business_id, employee_id, starts_at, ends_at)
    WHERE deleted_at IS NULL AND employee_id IS NOT NULL
      AND status NOT IN ('cancelled', 'rejected', 'no_show');
CREATE INDEX idx_bookings_customer ON bookings_bookings(business_id, customer_contact_id)
    WHERE deleted_at IS NULL AND customer_contact_id IS NOT NULL;

CREATE TABLE bookings_booking_status_history (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    business_id UUID NOT NULL REFERENCES businesses(id),
    booking_id UUID NOT NULL REFERENCES bookings_bookings(id) ON DELETE CASCADE,
    from_status TEXT,
    to_status TEXT NOT NULL,
    actor_identity_id UUID REFERENCES platform_identities(id),
    reason TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_booking_status_history ON bookings_booking_status_history(booking_id, created_at DESC);

CREATE TABLE bookings_booking_notes (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    business_id UUID NOT NULL REFERENCES businesses(id),
    booking_id UUID NOT NULL REFERENCES bookings_bookings(id) ON DELETE CASCADE,
    body TEXT NOT NULL,
    author_identity_id UUID NOT NULL REFERENCES platform_identities(id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    deleted_at TIMESTAMPTZ,
    version INTEGER NOT NULL DEFAULT 1
);

CREATE INDEX idx_booking_notes ON bookings_booking_notes(booking_id)
    WHERE deleted_at IS NULL;

CREATE TRIGGER trg_bookings_updated_at BEFORE UPDATE ON bookings_bookings
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();
CREATE TRIGGER trg_booking_notes_updated_at BEFORE UPDATE ON bookings_booking_notes
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

ALTER TABLE bookings_bookings ENABLE ROW LEVEL SECURITY;
ALTER TABLE bookings_booking_status_history ENABLE ROW LEVEL SECURITY;
ALTER TABLE bookings_booking_notes ENABLE ROW LEVEL SECURITY;

CREATE POLICY bookings_read ON bookings_bookings FOR SELECT USING (
    deleted_at IS NULL AND business_id = current_business_id()
);
CREATE POLICY bookings_history_read ON bookings_booking_status_history FOR SELECT USING (
    business_id = current_business_id()
);
CREATE POLICY bookings_notes_read ON bookings_booking_notes FOR SELECT USING (
    deleted_at IS NULL AND business_id = current_business_id()
);
