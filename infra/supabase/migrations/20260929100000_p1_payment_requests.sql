-- P1-10D: collect what is due, simply (Founder refinement — Payments §2–§15;
-- MD §6.1, §12.4). Provider-neutral.
--
-- A payment request is a secure link for an amount against a real transaction
-- (order, booking, membership, bill or khata balance). Paying it creates a
-- payment attempt on the same transaction; the transaction's own state never
-- changes because an attempt failed, and retrying never creates a second order.
--
-- Money paid by UPI straight to the business's own UPI ID cannot be seen by
-- LOCAH: such an attempt stays "being confirmed" until the business confirms it
-- arrived. Online payment through a provider is confirmed only by the
-- provider's verified webhook (Cashfree direction; activation pending).

CREATE TABLE payments_requests (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    business_id UUID NOT NULL REFERENCES businesses(id),
    source_type TEXT NOT NULL
        CHECK (source_type IN ('order', 'booking', 'membership', 'invoice', 'khata')),
    source_id UUID NOT NULL,
    customer_contact_id UUID REFERENCES customer_relationships_contacts(id),
    purpose TEXT NOT NULL CHECK (purpose IN ('full', 'advance', 'deposit', 'balance', 'dues')),
    amount NUMERIC(12, 2) NOT NULL CHECK (amount > 0),
    currency TEXT NOT NULL DEFAULT 'INR',
    -- sha256 of the link token; the token itself is shown once and never stored.
    token_hash TEXT NOT NULL UNIQUE,
    status TEXT NOT NULL DEFAULT 'open' CHECK (status IN ('open', 'paid', 'cancelled', 'expired')),
    note TEXT CHECK (note IS NULL OR length(note) <= 200),
    expires_at TIMESTAMPTZ NOT NULL,
    created_by UUID REFERENCES platform_identities(id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    paid_at TIMESTAMPTZ,
    cancelled_at TIMESTAMPTZ,
    version INTEGER NOT NULL DEFAULT 1
);
CREATE INDEX idx_payments_requests_source ON payments_requests (business_id, source_type, source_id);
CREATE INDEX idx_payments_requests_open ON payments_requests (business_id, status, created_at DESC);
CREATE TRIGGER trg_payments_requests_updated_at BEFORE UPDATE ON payments_requests
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

ALTER TABLE payments_requests ENABLE ROW LEVEL SECURITY;
CREATE POLICY payments_requests_read ON payments_requests FOR SELECT TO public
    USING (business_id = current_business_id());
CREATE POLICY payments_requests_api_write ON payments_requests FOR ALL TO platform_api
    USING (business_id = current_business_id()) WITH CHECK (business_id = current_business_id());
-- Requests are cancelled, never deleted: they are part of the money trail.
GRANT SELECT, INSERT, UPDATE ON payments_requests TO platform_api;

-- Attempts: settle bills and khata balances too; money recorded by the business
-- (cash, UPI, card on its own terminal, bank transfer) and UPI paid straight to
-- the business; an attempt the customer withdrew, or that ran out, is kept.
ALTER TABLE payments_payment_attempts DROP CONSTRAINT IF EXISTS payments_payment_attempts_source_type_check;
ALTER TABLE payments_payment_attempts ADD CONSTRAINT payments_payment_attempts_source_type_check
    CHECK (source_type IN ('order', 'booking', 'membership', 'invoice', 'khata'));
ALTER TABLE payments_payment_attempts DROP CONSTRAINT IF EXISTS payments_payment_attempts_payment_method_check;
ALTER TABLE payments_payment_attempts ADD CONSTRAINT payments_payment_attempts_payment_method_check
    CHECK (payment_method IN ('online', 'cod', 'pay_at_business', 'pay_later',
                              'upi_direct', 'cash', 'upi', 'card', 'bank_transfer'));
ALTER TABLE payments_payment_attempts DROP CONSTRAINT IF EXISTS payments_payment_attempts_status_check;
ALTER TABLE payments_payment_attempts ADD CONSTRAINT payments_payment_attempts_status_check
    CHECK (status IN ('pending', 'processing', 'pending_offline', 'succeeded', 'failed',
                      'partially_refunded', 'refunded', 'cancelled', 'expired'));
ALTER TABLE payments_payment_attempts
    ADD COLUMN request_id UUID REFERENCES payments_requests(id),
    ADD COLUMN purpose TEXT CHECK (purpose IS NULL OR purpose IN ('full', 'advance', 'deposit', 'balance', 'dues')),
    ADD COLUMN reference TEXT CHECK (reference IS NULL OR length(reference) <= 120),
    ADD COLUMN verified_at TIMESTAMPTZ,
    ADD COLUMN verified_by UUID REFERENCES platform_identities(id),
    -- Something the business must look at: a second payment for a link that
    -- was already paid (refund due), or money that did not arrive.
    ADD COLUMN attention TEXT CHECK (attention IS NULL OR attention IN ('paid_twice', 'not_received'));
CREATE INDEX idx_payments_attempts_request ON payments_payment_attempts (request_id) WHERE request_id IS NOT NULL;
CREATE INDEX idx_payments_attempts_attention ON payments_payment_attempts (business_id)
    WHERE attention IS NOT NULL AND deleted_at IS NULL;

-- A transaction can be part paid (an advance or deposit taken, the balance later).
ALTER TABLE orders_orders DROP CONSTRAINT IF EXISTS orders_orders_payment_status_check;
ALTER TABLE orders_orders ADD CONSTRAINT orders_orders_payment_status_check
    CHECK (payment_status IN ('pending', 'pending_offline', 'partially_paid', 'paid', 'refunded'));
ALTER TABLE bookings_bookings DROP CONSTRAINT IF EXISTS bookings_bookings_payment_status_check;
ALTER TABLE bookings_bookings ADD CONSTRAINT bookings_bookings_payment_status_check
    CHECK (payment_status IN ('pending', 'pending_offline', 'deposit_paid', 'partially_paid', 'paid', 'refunded'));
ALTER TABLE memberships_enrolments DROP CONSTRAINT IF EXISTS memberships_enrolments_payment_status_check;
ALTER TABLE memberships_enrolments ADD CONSTRAINT memberships_enrolments_payment_status_check
    CHECK (payment_status IN ('pending', 'pending_offline', 'partially_paid', 'paid', 'refunded'));

-- What a booking costs, fixed when it is made, so a deposit has a balance.
ALTER TABLE bookings_bookings ADD COLUMN total_amount NUMERIC(12, 2) CHECK (total_amount IS NULL OR total_amount >= 0);

-- Where a bill payment came from, so money is counted once: straight onto the
-- bill (NULL), applied from a khata receipt ('khata', already counted as the
-- receipt), or a payment link / recorded payment ('payment_attempt').
ALTER TABLE invoicing_payments ADD COLUMN via TEXT
    CHECK (via IS NULL OR via IN ('khata', 'payment_attempt'));
ALTER TABLE invoicing_payments ADD COLUMN payment_attempt_id UUID REFERENCES payments_payment_attempts(id);
UPDATE invoicing_payments SET via = 'khata' WHERE via IS NULL AND reference LIKE 'Khata%';

-- The payment page is opened by someone holding the link. The token is the
-- credential: this returns only which business a token belongs to (nothing
-- else), so a private business with no public website can still be paid.
CREATE OR REPLACE FUNCTION payment_request_business(p_token_hash TEXT) RETURNS UUID
    LANGUAGE sql STABLE SECURITY DEFINER SET search_path = public AS $$
    SELECT business_id FROM payments_requests WHERE token_hash = p_token_hash LIMIT 1
$$;
REVOKE ALL ON FUNCTION payment_request_business(TEXT) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION payment_request_business(TEXT) TO platform_api;
