-- Stage 9: Payments Kernel (First Launch scope)
-- Doc 11 §9.4, Doc 12 payments_payment_attempts

CREATE TABLE payments_merchant_connections (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    business_id UUID NOT NULL REFERENCES businesses(id),
    provider TEXT NOT NULL DEFAULT 'stub'
        CHECK (provider IN ('stub', 'razorpay', 'cod_only')),
    status TEXT NOT NULL DEFAULT 'not_connected'
        CHECK (status IN ('not_connected', 'pending', 'active', 'suspended')),
    provider_metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    version INTEGER NOT NULL DEFAULT 1,
    UNIQUE (business_id, provider)
);

CREATE TABLE payments_payment_attempts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    business_id UUID NOT NULL REFERENCES businesses(id),
    customer_contact_id UUID REFERENCES customer_relationships_contacts(id),
    source_type TEXT NOT NULL
        CHECK (source_type IN ('order', 'booking', 'membership')),
    source_id UUID NOT NULL,
    amount NUMERIC(12, 2) NOT NULL CHECK (amount > 0),
    currency TEXT NOT NULL DEFAULT 'INR',
    payment_method TEXT NOT NULL
        CHECK (payment_method IN ('online', 'cod', 'pay_at_business', 'pay_later')),
    status TEXT NOT NULL DEFAULT 'pending'
        CHECK (status IN (
            'pending', 'processing', 'pending_offline', 'succeeded',
            'failed', 'partially_refunded', 'refunded'
        )),
    provider TEXT NOT NULL DEFAULT 'stub',
    provider_reference TEXT,
    provider_metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    refunded_amount NUMERIC(12, 2) NOT NULL DEFAULT 0 CHECK (refunded_amount >= 0),
    failure_code TEXT,
    failure_reason TEXT,
    idempotency_key TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    deleted_at TIMESTAMPTZ,
    version INTEGER NOT NULL DEFAULT 1
);

CREATE UNIQUE INDEX idx_payments_idempotency ON payments_payment_attempts(business_id, idempotency_key)
    WHERE deleted_at IS NULL AND idempotency_key IS NOT NULL;
CREATE INDEX idx_payments_business_status ON payments_payment_attempts(business_id, status, created_at DESC)
    WHERE deleted_at IS NULL;
CREATE INDEX idx_payments_source ON payments_payment_attempts(business_id, source_type, source_id)
    WHERE deleted_at IS NULL;

CREATE TABLE payments_refunds (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    business_id UUID NOT NULL REFERENCES businesses(id),
    payment_attempt_id UUID NOT NULL REFERENCES payments_payment_attempts(id),
    amount NUMERIC(12, 2) NOT NULL CHECK (amount > 0),
    status TEXT NOT NULL DEFAULT 'pending'
        CHECK (status IN ('pending', 'succeeded', 'failed')),
    reason TEXT,
    provider_reference TEXT,
    failure_reason TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    version INTEGER NOT NULL DEFAULT 1
);

CREATE INDEX idx_payments_refunds_payment ON payments_refunds(payment_attempt_id, created_at DESC);

CREATE TABLE payments_webhook_receipts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    provider TEXT NOT NULL,
    provider_event_id TEXT NOT NULL,
    payment_attempt_id UUID REFERENCES payments_payment_attempts(id),
    raw_payload JSONB NOT NULL,
    status TEXT NOT NULL DEFAULT 'received'
        CHECK (status IN ('received', 'processed', 'failed')),
    processed_at TIMESTAMPTZ,
    failure_reason TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (provider, provider_event_id)
);

CREATE INDEX idx_payments_webhooks_status ON payments_webhook_receipts(status, created_at DESC);

CREATE TRIGGER trg_payments_merchant_updated_at BEFORE UPDATE ON payments_merchant_connections
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();
CREATE TRIGGER trg_payments_attempts_updated_at BEFORE UPDATE ON payments_payment_attempts
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();
CREATE TRIGGER trg_payments_refunds_updated_at BEFORE UPDATE ON payments_refunds
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

ALTER TABLE payments_merchant_connections ENABLE ROW LEVEL SECURITY;
ALTER TABLE payments_payment_attempts ENABLE ROW LEVEL SECURITY;
ALTER TABLE payments_refunds ENABLE ROW LEVEL SECURITY;
ALTER TABLE payments_webhook_receipts ENABLE ROW LEVEL SECURITY;

CREATE POLICY payments_merchant_read ON payments_merchant_connections FOR SELECT USING (
    business_id = current_business_id()
);
CREATE POLICY payments_attempts_read ON payments_payment_attempts FOR SELECT USING (
    deleted_at IS NULL AND business_id = current_business_id()
);
CREATE POLICY payments_refunds_read ON payments_refunds FOR SELECT USING (
    business_id = current_business_id()
);
