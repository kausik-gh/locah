-- Razorpay merchant credentials: store the owner-supplied Key ID + Key Secret
-- so the platform can act as their merchant account. The Key Secret is
-- encrypted at rest (platform_core.crypto / Fernet); only ciphertext lands
-- here. Key ID is not secret and stays in provider_metadata for display.
--
-- Forward-only. No backfill needed — every existing row is a 'stub'/'not_connected'
-- connection with no real credentials.

ALTER TABLE payments_merchant_connections
    ADD COLUMN IF NOT EXISTS encrypted_credentials text,
    ADD COLUMN IF NOT EXISTS last_verified_at timestamptz,
    ADD COLUMN IF NOT EXISTS verification_error text;

-- 'invalid_credentials' is the state a Razorpay key pair lands in when the
-- live verification call returns 401. Widen the CHECK from
-- 20260727090000_stage9_payments_kernel.sql.
ALTER TABLE payments_merchant_connections
    DROP CONSTRAINT IF EXISTS payments_merchant_connections_status_check;
ALTER TABLE payments_merchant_connections
    ADD CONSTRAINT payments_merchant_connections_status_check
    CHECK (status IN ('not_connected', 'pending', 'active', 'suspended', 'invalid_credentials'));

COMMENT ON COLUMN payments_merchant_connections.encrypted_credentials IS
    'Fernet ciphertext of {"key_id","key_secret"} — never plaintext, never logged.';
COMMENT ON COLUMN payments_merchant_connections.last_verified_at IS
    'When a live provider API call last confirmed these credentials work.';
COMMENT ON COLUMN payments_merchant_connections.verification_error IS
    'Provider-reported reason the last verification failed, if status = invalid_credentials.';
