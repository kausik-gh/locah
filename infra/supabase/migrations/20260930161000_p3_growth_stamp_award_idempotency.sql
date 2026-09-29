-- Follow-up for P3 growth. A stamp visit must be recorded once.
-- The original stamp reward row is not keyed by the visit, so the same
-- idempotency key could add another stamp. This table is that key.
-- RLS matches the khata / growth pattern: business_id, FORCE, platform_api.

CREATE TABLE IF NOT EXISTS stamp_awards (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    business_id UUID NOT NULL REFERENCES businesses(id),
    program_id UUID NOT NULL REFERENCES stamp_programs(id),
    customer_contact_id UUID NOT NULL REFERENCES customer_relationships_contacts(id),
    idempotency_key TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT stamp_awards_idempotency UNIQUE (business_id, idempotency_key)
);

CREATE INDEX IF NOT EXISTS stamp_awards_customer
    ON stamp_awards (business_id, customer_contact_id, created_at DESC);

ALTER TABLE stamp_awards ENABLE ROW LEVEL SECURITY;
ALTER TABLE stamp_awards FORCE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS stamp_awards_member_read ON stamp_awards;
CREATE POLICY stamp_awards_member_read ON stamp_awards
    FOR SELECT TO public
    USING (business_id = current_business_id());

DROP POLICY IF EXISTS stamp_awards_api_write ON stamp_awards;
CREATE POLICY stamp_awards_api_write ON stamp_awards
    FOR ALL TO platform_api
    USING (business_id = current_business_id())
    WITH CHECK (business_id = current_business_id());

REVOKE ALL PRIVILEGES ON TABLE stamp_awards FROM anon;
GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE stamp_awards TO platform_api;
