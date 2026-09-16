-- Stage 5: Offerings Catalog + Inventory Kernel (First Launch scope)
-- Procurement/suppliers deferred per Document 11 §10.3

CREATE TABLE offerings_catalog_categories (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    business_id UUID NOT NULL REFERENCES businesses(id),
    name TEXT NOT NULL,
    slug TEXT NOT NULL,
    parent_id UUID REFERENCES offerings_catalog_categories(id),
    sort_order INTEGER NOT NULL DEFAULT 0,
    status TEXT NOT NULL DEFAULT 'active'
        CHECK (status IN ('active', 'archived')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    deleted_at TIMESTAMPTZ,
    version INTEGER NOT NULL DEFAULT 1
);

CREATE INDEX idx_offerings_categories_business ON offerings_catalog_categories(business_id)
    WHERE deleted_at IS NULL;
CREATE UNIQUE INDEX idx_offerings_categories_slug
    ON offerings_catalog_categories(business_id, slug)
    WHERE deleted_at IS NULL;

CREATE TABLE offerings_catalog_offerings (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    business_id UUID NOT NULL REFERENCES businesses(id),
    category_id UUID REFERENCES offerings_catalog_categories(id),
    offering_type TEXT NOT NULL DEFAULT 'product'
        CHECK (offering_type IN (
            'product', 'menu_item', 'service', 'accommodation',
            'membership_plan', 'class_session', 'rental', 'listing'
        )),
    title TEXT NOT NULL,
    description TEXT,
    sku TEXT,
    barcode TEXT,
    status TEXT NOT NULL DEFAULT 'draft'
        CHECK (status IN ('draft', 'active', 'archived')),
    price_type TEXT NOT NULL DEFAULT 'fixed'
        CHECK (price_type IN ('fixed', 'starting_from', 'variable', 'free', 'enquiry')),
    price_amount NUMERIC(12, 2),
    currency TEXT NOT NULL DEFAULT 'INR',
    unit_of_measure TEXT,
    tax_rate NUMERIC(5, 2),
    track_inventory BOOLEAN NOT NULL DEFAULT false,
    low_stock_threshold INTEGER,
    visibility TEXT NOT NULL DEFAULT 'public'
        CHECK (visibility IN ('public', 'private')),
    image_asset_ids UUID[] NOT NULL DEFAULT '{}',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    deleted_at TIMESTAMPTZ,
    version INTEGER NOT NULL DEFAULT 1
);

CREATE INDEX idx_offerings_business ON offerings_catalog_offerings(business_id)
    WHERE deleted_at IS NULL;
CREATE INDEX idx_offerings_category ON offerings_catalog_offerings(category_id)
    WHERE deleted_at IS NULL;
CREATE INDEX idx_offerings_title ON offerings_catalog_offerings(business_id, title)
    WHERE deleted_at IS NULL;
CREATE UNIQUE INDEX idx_offerings_sku
    ON offerings_catalog_offerings(business_id, sku)
    WHERE deleted_at IS NULL AND sku IS NOT NULL;

CREATE TABLE offerings_catalog_variants (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    business_id UUID NOT NULL REFERENCES businesses(id),
    offering_id UUID NOT NULL REFERENCES offerings_catalog_offerings(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    sku TEXT,
    barcode TEXT,
    price_amount NUMERIC(12, 2),
    sort_order INTEGER NOT NULL DEFAULT 0,
    status TEXT NOT NULL DEFAULT 'active'
        CHECK (status IN ('active', 'archived')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    deleted_at TIMESTAMPTZ,
    version INTEGER NOT NULL DEFAULT 1
);

CREATE INDEX idx_offerings_variants_offering ON offerings_catalog_variants(offering_id)
    WHERE deleted_at IS NULL;
CREATE UNIQUE INDEX idx_offerings_variants_sku
    ON offerings_catalog_variants(business_id, sku)
    WHERE deleted_at IS NULL AND sku IS NOT NULL;

CREATE TABLE inventory_records (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    business_id UUID NOT NULL REFERENCES businesses(id),
    offering_id UUID NOT NULL REFERENCES offerings_catalog_offerings(id),
    variant_id UUID REFERENCES offerings_catalog_variants(id),
    location_id UUID NOT NULL REFERENCES business_locations(id),
    quantity_on_hand INTEGER NOT NULL DEFAULT 0 CHECK (quantity_on_hand >= 0),
    quantity_reserved INTEGER NOT NULL DEFAULT 0 CHECK (quantity_reserved >= 0),
    low_stock_threshold INTEGER,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    version INTEGER NOT NULL DEFAULT 1
);

CREATE UNIQUE INDEX idx_inventory_record_no_variant
    ON inventory_records(business_id, offering_id, location_id)
    WHERE variant_id IS NULL;
CREATE UNIQUE INDEX idx_inventory_record_with_variant
    ON inventory_records(business_id, offering_id, variant_id, location_id)
    WHERE variant_id IS NOT NULL;

CREATE INDEX idx_inventory_records_business ON inventory_records(business_id);
CREATE INDEX idx_inventory_records_location ON inventory_records(location_id);
CREATE INDEX idx_inventory_records_offering ON inventory_records(offering_id);

CREATE TABLE inventory_movements (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    business_id UUID NOT NULL REFERENCES businesses(id),
    offering_id UUID NOT NULL REFERENCES offerings_catalog_offerings(id),
    variant_id UUID REFERENCES offerings_catalog_variants(id),
    location_id UUID NOT NULL REFERENCES business_locations(id),
    inventory_record_id UUID NOT NULL REFERENCES inventory_records(id),
    movement_type TEXT NOT NULL
        CHECK (movement_type IN (
            'opening_stock', 'adjustment', 'receipt', 'deduction', 'reversal', 'reservation'
        )),
    quantity_delta INTEGER NOT NULL,
    quantity_after INTEGER NOT NULL CHECK (quantity_after >= 0),
    reason TEXT,
    actor_identity_id UUID REFERENCES platform_identities(id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_inventory_movements_record ON inventory_movements(inventory_record_id, created_at DESC);
CREATE INDEX idx_inventory_movements_business ON inventory_movements(business_id, created_at DESC);

CREATE TRIGGER trg_offerings_categories_updated_at BEFORE UPDATE ON offerings_catalog_categories
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();
CREATE TRIGGER trg_offerings_offerings_updated_at BEFORE UPDATE ON offerings_catalog_offerings
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();
CREATE TRIGGER trg_offerings_variants_updated_at BEFORE UPDATE ON offerings_catalog_variants
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();
CREATE TRIGGER trg_inventory_records_updated_at BEFORE UPDATE ON inventory_records
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

ALTER TABLE offerings_catalog_categories ENABLE ROW LEVEL SECURITY;
ALTER TABLE offerings_catalog_offerings ENABLE ROW LEVEL SECURITY;
ALTER TABLE offerings_catalog_variants ENABLE ROW LEVEL SECURITY;
ALTER TABLE inventory_records ENABLE ROW LEVEL SECURITY;
ALTER TABLE inventory_movements ENABLE ROW LEVEL SECURITY;

CREATE POLICY offerings_categories_read ON offerings_catalog_categories FOR SELECT USING (
    deleted_at IS NULL AND business_id = current_business_id()
);
CREATE POLICY offerings_offerings_read ON offerings_catalog_offerings FOR SELECT USING (
    deleted_at IS NULL AND business_id = current_business_id()
);
CREATE POLICY offerings_variants_read ON offerings_catalog_variants FOR SELECT USING (
    deleted_at IS NULL AND business_id = current_business_id()
);
CREATE POLICY inventory_records_read ON inventory_records FOR SELECT USING (
    business_id = current_business_id()
);
CREATE POLICY inventory_movements_read ON inventory_movements FOR SELECT USING (
    business_id = current_business_id()
);
