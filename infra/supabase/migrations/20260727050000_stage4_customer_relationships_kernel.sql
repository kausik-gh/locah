-- Stage 4: CRM & Customer Management Kernel (customer-relationships module)

CREATE TABLE customer_relationships_contacts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    business_id UUID NOT NULL REFERENCES businesses(id),
    identity_id UUID REFERENCES platform_identities(id),
    display_name TEXT NOT NULL,
    phone TEXT,
    email TEXT,
    status TEXT NOT NULL DEFAULT 'active'
        CHECK (status IN ('active', 'blocked', 'archived')),
    tags TEXT[] NOT NULL DEFAULT '{}',
    preferred_location_id UUID REFERENCES business_locations(id),
    customer_since TIMESTAMPTZ NOT NULL DEFAULT now(),
    last_interaction_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    deleted_at TIMESTAMPTZ,
    version INTEGER NOT NULL DEFAULT 1
);

CREATE INDEX idx_crm_contacts_business ON customer_relationships_contacts(business_id);
CREATE INDEX idx_crm_contacts_active ON customer_relationships_contacts(business_id)
    WHERE deleted_at IS NULL AND status = 'active';
CREATE INDEX idx_crm_contacts_display_name ON customer_relationships_contacts(business_id, display_name)
    WHERE deleted_at IS NULL;
CREATE INDEX idx_crm_contacts_phone ON customer_relationships_contacts(business_id, phone)
    WHERE deleted_at IS NULL AND phone IS NOT NULL;
CREATE INDEX idx_crm_contacts_email ON customer_relationships_contacts(business_id, email)
    WHERE deleted_at IS NULL AND email IS NOT NULL;

CREATE UNIQUE INDEX idx_crm_contacts_unique_phone
    ON customer_relationships_contacts(business_id, phone)
    WHERE deleted_at IS NULL AND phone IS NOT NULL;

CREATE UNIQUE INDEX idx_crm_contacts_unique_email
    ON customer_relationships_contacts(business_id, email)
    WHERE deleted_at IS NULL AND email IS NOT NULL;

CREATE TABLE customer_relationships_notes (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    business_id UUID NOT NULL REFERENCES businesses(id),
    contact_id UUID NOT NULL REFERENCES customer_relationships_contacts(id) ON DELETE CASCADE,
    body TEXT NOT NULL,
    author_identity_id UUID NOT NULL REFERENCES platform_identities(id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    deleted_at TIMESTAMPTZ,
    version INTEGER NOT NULL DEFAULT 1
);

CREATE INDEX idx_crm_notes_contact ON customer_relationships_notes(contact_id)
    WHERE deleted_at IS NULL;

CREATE TABLE customer_relationships_timeline_entries (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    business_id UUID NOT NULL REFERENCES businesses(id),
    contact_id UUID NOT NULL REFERENCES customer_relationships_contacts(id) ON DELETE CASCADE,
    activity_type TEXT NOT NULL,
    resource_type TEXT,
    resource_id UUID,
    location_id UUID REFERENCES business_locations(id),
    summary JSONB NOT NULL DEFAULT '{}'::jsonb,
    occurred_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    source_event_id UUID,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_crm_timeline_contact ON customer_relationships_timeline_entries(contact_id, occurred_at DESC);
CREATE UNIQUE INDEX idx_crm_timeline_idempotent
    ON customer_relationships_timeline_entries(business_id, source_event_id)
    WHERE source_event_id IS NOT NULL;

CREATE TRIGGER trg_crm_contacts_updated_at BEFORE UPDATE ON customer_relationships_contacts
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();
CREATE TRIGGER trg_crm_notes_updated_at BEFORE UPDATE ON customer_relationships_notes
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

ALTER TABLE customer_relationships_contacts ENABLE ROW LEVEL SECURITY;
ALTER TABLE customer_relationships_notes ENABLE ROW LEVEL SECURITY;
ALTER TABLE customer_relationships_timeline_entries ENABLE ROW LEVEL SECURITY;

CREATE POLICY crm_contacts_member_read ON customer_relationships_contacts FOR SELECT USING (
    deleted_at IS NULL AND business_id = current_business_id()
);

CREATE POLICY crm_notes_member_read ON customer_relationships_notes FOR SELECT USING (
    deleted_at IS NULL AND business_id = current_business_id()
);

CREATE POLICY crm_timeline_member_read ON customer_relationships_timeline_entries FOR SELECT USING (
    business_id = current_business_id()
);
