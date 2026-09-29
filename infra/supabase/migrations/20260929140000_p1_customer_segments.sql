-- P1-10E2: rule-built customer segments (MD §6.1 customer-relationships "tags,
-- segments"; §18.2 Audiences "Rule-built segments … shows counts; only consented
-- contacts for WhatsApp"). A segment stores its rules only — who is in it is
-- worked out from the business's own records each time it is opened, so it is
-- never a stale copied list.

CREATE TABLE customer_relationships_segments (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    business_id UUID NOT NULL REFERENCES businesses(id),
    name TEXT NOT NULL CHECK (length(name) BETWEEN 1 AND 80),
    rules JSONB NOT NULL CHECK (jsonb_typeof(rules) = 'array'),
    created_by UUID REFERENCES platform_identities(id),
    archived_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    version INTEGER NOT NULL DEFAULT 1
);
CREATE UNIQUE INDEX customer_segments_name ON customer_relationships_segments (business_id, lower(name))
    WHERE archived_at IS NULL;

CREATE TRIGGER trg_customer_segments_updated_at BEFORE UPDATE ON customer_relationships_segments
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

ALTER TABLE customer_relationships_segments ENABLE ROW LEVEL SECURITY;
ALTER TABLE customer_relationships_segments FORCE ROW LEVEL SECURITY;
CREATE POLICY customer_segments_member_read ON customer_relationships_segments FOR SELECT TO public
    USING (business_id = current_business_id());
CREATE POLICY customer_segments_api_write ON customer_relationships_segments FOR ALL TO platform_api
    USING (business_id = current_business_id()) WITH CHECK (business_id = current_business_id());
REVOKE ALL PRIVILEGES ON TABLE customer_relationships_segments FROM anon;
GRANT SELECT, INSERT, UPDATE ON customer_relationships_segments TO platform_api;
REVOKE DELETE ON customer_relationships_segments FROM platform_api;

-- Tag filters read the tags array.
CREATE INDEX IF NOT EXISTS customer_contacts_tags ON customer_relationships_contacts USING gin (tags);
