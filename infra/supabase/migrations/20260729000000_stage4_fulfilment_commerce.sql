-- Stage 4 completion: Fulfilment (launch depth) — Doc 11 §10.4 / §17.4
-- Optional module `fulfilment` (already in module_definitions)

CREATE TABLE fulfilment_settings (
    business_id UUID PRIMARY KEY REFERENCES businesses(id),
    pickup_enabled BOOLEAN NOT NULL DEFAULT true,
    delivery_enabled BOOLEAN NOT NULL DEFAULT false,
    delivery_fee_offering_id UUID REFERENCES offerings_catalog_offerings(id),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    version INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE fulfilment_zones (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    business_id UUID NOT NULL REFERENCES businesses(id),
    location_id UUID REFERENCES business_locations(id),
    name TEXT NOT NULL,
    match_type TEXT NOT NULL DEFAULT 'city'
        CHECK (match_type IN ('city', 'radius', 'postal_prefix')),
    city TEXT,
    postal_prefix TEXT,
    center_lat NUMERIC(10, 7),
    center_lng NUMERIC(10, 7),
    radius_km NUMERIC(8, 2),
    charge_amount NUMERIC(12, 2) NOT NULL DEFAULT 0 CHECK (charge_amount >= 0),
    currency TEXT NOT NULL DEFAULT 'INR',
    is_active BOOLEAN NOT NULL DEFAULT true,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    deleted_at TIMESTAMPTZ,
    version INTEGER NOT NULL DEFAULT 1
);

CREATE INDEX idx_fulfilment_zones_business
    ON fulfilment_zones (business_id)
    WHERE deleted_at IS NULL AND is_active = true;

CREATE TABLE fulfilment_jobs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    business_id UUID NOT NULL REFERENCES businesses(id),
    order_id UUID NOT NULL REFERENCES orders_orders(id),
    location_id UUID NOT NULL REFERENCES business_locations(id),
    mode TEXT NOT NULL CHECK (mode IN ('pickup', 'delivery')),
    status TEXT NOT NULL DEFAULT 'pending'
        CHECK (status IN (
            'pending', 'preparing', 'ready', 'out_for_delivery',
            'delivered', 'failed', 'cancelled'
        )),
    zone_id UUID REFERENCES fulfilment_zones(id),
    delivery_address JSONB,
    delivery_charge NUMERIC(12, 2) NOT NULL DEFAULT 0 CHECK (delivery_charge >= 0),
    currency TEXT NOT NULL DEFAULT 'INR',
    tracking_token TEXT NOT NULL,
    tracking_expires_at TIMESTAMPTZ NOT NULL,
    outcome_reason TEXT,
    created_by UUID REFERENCES platform_identities(id),
    updated_by UUID REFERENCES platform_identities(id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    version INTEGER NOT NULL DEFAULT 1,
    UNIQUE (order_id)
);

CREATE UNIQUE INDEX idx_fulfilment_jobs_tracking_token
    ON fulfilment_jobs (tracking_token);
CREATE INDEX idx_fulfilment_jobs_business_status
    ON fulfilment_jobs (business_id, status, created_at DESC);
CREATE INDEX idx_fulfilment_jobs_order
    ON fulfilment_jobs (business_id, order_id);

ALTER TABLE fulfilment_settings ENABLE ROW LEVEL SECURITY;
ALTER TABLE fulfilment_zones ENABLE ROW LEVEL SECURITY;
ALTER TABLE fulfilment_jobs ENABLE ROW LEVEL SECURITY;

CREATE POLICY fulfilment_settings_member ON fulfilment_settings
    FOR SELECT USING (business_id = current_business_id());
CREATE POLICY fulfilment_zones_member ON fulfilment_zones
    FOR SELECT USING (business_id = current_business_id());
CREATE POLICY fulfilment_jobs_member ON fulfilment_jobs
    FOR SELECT USING (business_id = current_business_id());
