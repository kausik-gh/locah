-- Cashfree sandbox merchant settlement and server-owned commission policy.
-- Existing Razorpay rows remain readable; no provider keys or bank data live here.
ALTER TABLE payments_merchant_connections
    DROP CONSTRAINT IF EXISTS payments_merchant_connections_provider_check;
ALTER TABLE payments_merchant_connections
    ADD CONSTRAINT payments_merchant_connections_provider_check
    CHECK (provider IN ('stub', 'razorpay', 'cod_only', 'cashfree'));

CREATE TABLE payments_platform_fee_rules (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    business_id UUID NOT NULL REFERENCES businesses(id),
    pricing_mode TEXT NOT NULL CHECK (pricing_mode IN ('payg', 'subscription', 'custom')),
    percentage_bps INTEGER NOT NULL DEFAULT 0 CHECK (percentage_bps BETWEEN 0 AND 10000),
    fixed_amount NUMERIC(12, 2) NOT NULL DEFAULT 0 CHECK (fixed_amount >= 0),
    minimum_amount NUMERIC(12, 2) CHECK (minimum_amount >= 0),
    maximum_amount NUMERIC(12, 2) CHECK (maximum_amount >= 0),
    effective_from TIMESTAMPTZ NOT NULL,
    effective_to TIMESTAMPTZ,
    version INTEGER NOT NULL DEFAULT 1,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CHECK (effective_to IS NULL OR effective_to > effective_from),
    CHECK (maximum_amount IS NULL OR minimum_amount IS NULL OR maximum_amount >= minimum_amount)
);
CREATE INDEX idx_payments_platform_fee_rules_active
    ON payments_platform_fee_rules(business_id, effective_from DESC);
ALTER TABLE payments_platform_fee_rules ENABLE ROW LEVEL SECURITY;
-- Fee rules are written by a privileged billing/admin service only. Public
-- checkout reads only its own tenant's rule after binding business context.
CREATE POLICY payments_platform_fee_rules_read ON payments_platform_fee_rules
    FOR SELECT USING (business_id = current_business_id());

ALTER TABLE payments_refunds ADD COLUMN idempotency_key TEXT;
CREATE UNIQUE INDEX idx_payments_refunds_idempotency
    ON payments_refunds(business_id, payment_attempt_id, idempotency_key)
    WHERE idempotency_key IS NOT NULL;
