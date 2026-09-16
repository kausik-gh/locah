-- Stage 3: Marketplace Discovery (Doc 11 §17.3, Doc 12 §14)
-- Postgres GIN full-text — FL-DEC-014 resolved

CREATE TABLE marketplace_business_projections (
    business_id UUID PRIMARY KEY REFERENCES businesses(id),
    slug TEXT NOT NULL,
    display_name TEXT NOT NULL,
    description TEXT,
    business_type TEXT,
    characteristics TEXT[] NOT NULL DEFAULT '{}',
    primary_category TEXT,
    tags TEXT[] NOT NULL DEFAULT '{}',
    primary_location_id UUID,
    city TEXT,
    lat NUMERIC(10, 7),
    lng NUMERIC(10, 7),
    is_discoverable BOOLEAN NOT NULL DEFAULT false,
    logo_asset_id UUID,
    website_status TEXT,
    capability_flags JSONB NOT NULL DEFAULT '{}'::jsonb,
    indexed_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    search_vector TSVECTOR
);

CREATE INDEX idx_marketplace_businesses_search
    ON marketplace_business_projections USING GIN (search_vector);
CREATE INDEX idx_marketplace_businesses_discoverable
    ON marketplace_business_projections (is_discoverable, business_type)
    WHERE is_discoverable = true;
CREATE INDEX idx_marketplace_businesses_city
    ON marketplace_business_projections (city)
    WHERE is_discoverable = true AND city IS NOT NULL;
CREATE INDEX idx_marketplace_businesses_slug
    ON marketplace_business_projections (slug);

CREATE TABLE marketplace_offering_projections (
    id UUID PRIMARY KEY,
    business_id UUID NOT NULL REFERENCES businesses(id),
    offering_type TEXT NOT NULL,
    title TEXT NOT NULL,
    description TEXT,
    price_from NUMERIC(12, 2),
    currency TEXT,
    category TEXT,
    tags TEXT[] NOT NULL DEFAULT '{}',
    location_ids UUID[] NOT NULL DEFAULT '{}',
    is_active BOOLEAN NOT NULL DEFAULT true,
    indexed_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    search_vector TSVECTOR
);

CREATE INDEX idx_marketplace_offerings_search
    ON marketplace_offering_projections USING GIN (search_vector);
CREATE INDEX idx_marketplace_offerings_business
    ON marketplace_offering_projections (business_id)
    WHERE is_active = true;
CREATE INDEX idx_marketplace_offerings_type
    ON marketplace_offering_projections (offering_type)
    WHERE is_active = true;

CREATE OR REPLACE FUNCTION update_business_search_vector() RETURNS TRIGGER AS $$
BEGIN
    NEW.search_vector := to_tsvector(
        'english',
        coalesce(NEW.display_name, '') || ' ' ||
        coalesce(NEW.description, '') || ' ' ||
        coalesce(array_to_string(NEW.tags, ' '), '') || ' ' ||
        coalesce(NEW.city, '') || ' ' ||
        coalesce(NEW.business_type, '') || ' ' ||
        coalesce(NEW.primary_category, '')
    );
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_marketplace_business_search_vector
    BEFORE INSERT OR UPDATE ON marketplace_business_projections
    FOR EACH ROW EXECUTE FUNCTION update_business_search_vector();

CREATE OR REPLACE FUNCTION update_offering_search_vector() RETURNS TRIGGER AS $$
BEGIN
    NEW.search_vector := to_tsvector(
        'english',
        coalesce(NEW.title, '') || ' ' ||
        coalesce(NEW.description, '') || ' ' ||
        coalesce(array_to_string(NEW.tags, ' '), '') || ' ' ||
        coalesce(NEW.category, '') || ' ' ||
        coalesce(NEW.offering_type, '')
    );
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_marketplace_offering_search_vector
    BEFORE INSERT OR UPDATE ON marketplace_offering_projections
    FOR EACH ROW EXECUTE FUNCTION update_offering_search_vector();

-- Indexing health / opt-in consent audit trail (Admin recovery, Doc 11 §17.3)
CREATE TABLE marketplace_index_health (
    business_id UUID PRIMARY KEY REFERENCES businesses(id),
    last_indexed_at TIMESTAMPTZ,
    last_attempt_at TIMESTAMPTZ,
    last_status TEXT NOT NULL DEFAULT 'never'
        CHECK (last_status IN ('never', 'indexed', 'deindexed', 'failed', 'stale')),
    last_error TEXT,
    last_reason TEXT,
    discoverability_consented_at TIMESTAMPTZ,
    consented_by UUID REFERENCES platform_identities(id),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_marketplace_index_health_status
    ON marketplace_index_health (last_status, last_attempt_at DESC);

ALTER TABLE marketplace_business_projections ENABLE ROW LEVEL SECURITY;
ALTER TABLE marketplace_offering_projections ENABLE ROW LEVEL SECURITY;
ALTER TABLE marketplace_index_health ENABLE ROW LEVEL SECURITY;

-- Public read of discoverable projections (API uses service role / worker; RLS for defense)
CREATE POLICY marketplace_business_public_read ON marketplace_business_projections
    FOR SELECT USING (is_discoverable = true);
CREATE POLICY marketplace_offering_public_read ON marketplace_offering_projections
    FOR SELECT USING (is_active = true);
CREATE POLICY marketplace_health_member_read ON marketplace_index_health
    FOR SELECT USING (business_id = current_business_id());
