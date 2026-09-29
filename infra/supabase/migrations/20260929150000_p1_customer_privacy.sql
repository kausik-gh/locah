-- P1-10E3: per-customer export and erasure (MD §25.1 DPDP "access / erasure
-- rights … per-customer export and delete, retention defaults"; CR-08, CO-01).
--
-- Erasure removes a customer's personal details (name, phone, email, notes,
-- enquiry text, WhatsApp message text, delivery addresses) and keeps the
-- transactions the law requires the business to keep — issued bills (CGST Act
-- s.36, 72 months) and khata entries (books of account) — attached to an
-- anonymous record. A customer can download their data and ask for erasure
-- from their account; the request reaches the business, which acts on it.

ALTER TABLE customer_relationships_contacts ADD COLUMN IF NOT EXISTS erased_at TIMESTAMPTZ;

CREATE TABLE customer_relationships_privacy_requests (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    business_id UUID NOT NULL REFERENCES businesses(id),
    contact_id UUID NOT NULL REFERENCES customer_relationships_contacts(id),
    kind TEXT NOT NULL CHECK (kind IN ('access', 'erasure')),
    status TEXT NOT NULL DEFAULT 'open' CHECK (status IN ('open', 'done', 'declined')),
    source TEXT NOT NULL CHECK (source IN ('customer', 'staff')),
    identity_id UUID REFERENCES platform_identities(id),
    note TEXT CHECK (note IS NULL OR length(note) <= 500),
    resolution_note TEXT CHECK (resolution_note IS NULL OR length(resolution_note) <= 500),
    resolved_by UUID REFERENCES platform_identities(id),
    resolved_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE UNIQUE INDEX customer_privacy_one_open_erasure ON customer_relationships_privacy_requests (contact_id)
    WHERE kind = 'erasure' AND status = 'open';
CREATE INDEX customer_privacy_open ON customer_relationships_privacy_requests (business_id, status);

ALTER TABLE customer_relationships_privacy_requests ENABLE ROW LEVEL SECURITY;
ALTER TABLE customer_relationships_privacy_requests FORCE ROW LEVEL SECURITY;
CREATE POLICY customer_privacy_member_read ON customer_relationships_privacy_requests FOR SELECT TO public
    USING (business_id = current_business_id());
CREATE POLICY customer_privacy_api_write ON customer_relationships_privacy_requests FOR ALL TO platform_api
    USING (business_id = current_business_id()) WITH CHECK (business_id = current_business_id());
REVOKE ALL PRIVILEGES ON TABLE customer_relationships_privacy_requests FROM anon;
GRANT SELECT, INSERT, UPDATE ON customer_relationships_privacy_requests TO platform_api;
REVOKE DELETE ON customer_relationships_privacy_requests FROM platform_api;
