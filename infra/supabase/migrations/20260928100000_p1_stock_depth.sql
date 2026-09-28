-- P1-10A: stock depth (Capability Universe §15.1; Business OS Guide §11).
--
-- One stock truth stays one stock truth: every change below is still an
-- inventory_movements row against one inventory_records row. What this adds is
-- the detail different businesses need about that stock:
--   * batches with expiry, picked first-expiry-first-out (pharmacy, dairy, packaged food)
--   * serial numbers with warranty lookup (electronics, appliances)
--   * owner-entered yields and cutting runs (meat, fish, sweets: whole bird -> curry cut)
--   * wastage with reasons (expired, damaged, trim loss, spoiled)
--   * stock counts whose variances need approval
--   * reorder min/max per location, buying units (crate, case), weighted-average value
-- Quantities stay integers in the item's stock unit (piece, gram, millilitre);
-- money is integer paise.

-- ---------------------------------------------------------------- offerings
ALTER TABLE offerings_catalog_offerings
    ADD COLUMN batch_tracked BOOLEAN NOT NULL DEFAULT false,
    ADD COLUMN serial_tracked BOOLEAN NOT NULL DEFAULT false,
    ADD COLUMN warranty_months INTEGER CHECK (warranty_months IS NULL OR warranty_months BETWEEN 0 AND 240),
    -- How it is bought: [{"label": "crate", "quantity": 24}] — quantity in stock units.
    ADD COLUMN buy_units JSONB NOT NULL DEFAULT '[]'::jsonb CHECK (jsonb_typeof(buy_units) = 'array');

-- ---------------------------------------------------------------- records
ALTER TABLE inventory_records
    ADD COLUMN reorder_max INTEGER CHECK (reorder_max IS NULL OR reorder_max >= 0),
    ADD COLUMN stock_value_paise BIGINT NOT NULL DEFAULT 0 CHECK (stock_value_paise >= 0),
    ADD COLUMN last_counted_at TIMESTAMPTZ;

-- ---------------------------------------------------------------- movements
ALTER TABLE inventory_movements DROP CONSTRAINT IF EXISTS inventory_movements_movement_type_check;
ALTER TABLE inventory_movements ADD CONSTRAINT inventory_movements_movement_type_check
    CHECK (movement_type IN (
        'opening_stock', 'adjustment', 'receipt', 'deduction', 'reversal', 'reservation',
        'wastage', 'count_variance', 'conversion_out', 'conversion_in'
    ));
ALTER TABLE inventory_movements
    ADD COLUMN reason_code TEXT CHECK (reason_code IS NULL OR reason_code IN (
        'expired', 'damaged', 'trim_loss', 'spoiled', 'theft', 'sample', 'other')),
    ADD COLUMN batch_id UUID,
    ADD COLUMN value_delta_paise BIGINT NOT NULL DEFAULT 0,
    ADD COLUMN source_type TEXT,
    ADD COLUMN source_id UUID;
CREATE INDEX idx_inventory_movements_type ON inventory_movements (business_id, movement_type, created_at DESC);

-- ---------------------------------------------------------------- batches
CREATE TABLE inventory_batches (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    business_id UUID NOT NULL REFERENCES businesses(id),
    location_id UUID NOT NULL REFERENCES business_locations(id),
    inventory_record_id UUID NOT NULL REFERENCES inventory_records(id),
    offering_id UUID NOT NULL REFERENCES offerings_catalog_offerings(id),
    variant_id UUID REFERENCES offerings_catalog_variants(id),
    batch_code TEXT NOT NULL CHECK (length(batch_code) BETWEEN 1 AND 60),
    expires_on DATE,
    received_on DATE NOT NULL DEFAULT CURRENT_DATE,
    quantity_received INTEGER NOT NULL CHECK (quantity_received > 0),
    quantity_on_hand INTEGER NOT NULL CHECK (quantity_on_hand >= 0),
    status TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'depleted', 'written_off')),
    created_by UUID REFERENCES platform_identities(id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    version INTEGER NOT NULL DEFAULT 1,
    CHECK (quantity_on_hand <= quantity_received)
);
CREATE INDEX inventory_batches_fefo ON inventory_batches (inventory_record_id, status, expires_on NULLS LAST, received_on);
CREATE INDEX inventory_batches_expiry ON inventory_batches (business_id, status, expires_on);
ALTER TABLE inventory_movements ADD CONSTRAINT inventory_movements_batch_fk
    FOREIGN KEY (batch_id) REFERENCES inventory_batches(id);

-- ---------------------------------------------------------------- serials
CREATE TABLE inventory_serials (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    business_id UUID NOT NULL REFERENCES businesses(id),
    location_id UUID NOT NULL REFERENCES business_locations(id),
    inventory_record_id UUID NOT NULL REFERENCES inventory_records(id),
    offering_id UUID NOT NULL REFERENCES offerings_catalog_offerings(id),
    variant_id UUID REFERENCES offerings_catalog_variants(id),
    serial TEXT NOT NULL CHECK (length(serial) BETWEEN 3 AND 64),
    status TEXT NOT NULL DEFAULT 'in_stock' CHECK (status IN ('in_stock', 'sold', 'written_off')),
    received_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    sold_at TIMESTAMPTZ,
    sold_document_id UUID REFERENCES invoicing_documents(id),
    sold_order_id UUID REFERENCES orders_orders(id),
    customer_contact_id UUID REFERENCES customer_relationships_contacts(id),
    warranty_until DATE,
    created_by UUID REFERENCES platform_identities(id),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    version INTEGER NOT NULL DEFAULT 1
);
CREATE UNIQUE INDEX inventory_serials_unique ON inventory_serials (business_id, offering_id, upper(serial));
CREATE INDEX inventory_serials_lookup ON inventory_serials (business_id, upper(serial));
CREATE INDEX inventory_serials_record ON inventory_serials (inventory_record_id, status);

-- ---------------------------------------------------------------- yields
-- Owner-entered: "1 kg whole chicken gives 800 g curry cut" is 8000 basis points.
CREATE TABLE inventory_yields (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    business_id UUID NOT NULL REFERENCES businesses(id),
    source_offering_id UUID NOT NULL REFERENCES offerings_catalog_offerings(id),
    output_offering_id UUID NOT NULL REFERENCES offerings_catalog_offerings(id),
    yield_bp INTEGER NOT NULL CHECK (yield_bp BETWEEN 1 AND 10000),
    note TEXT CHECK (note IS NULL OR length(note) <= 200),
    created_by UUID REFERENCES platform_identities(id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    version INTEGER NOT NULL DEFAULT 1,
    CHECK (source_offering_id <> output_offering_id)
);
CREATE UNIQUE INDEX inventory_yields_pair ON inventory_yields (business_id, source_offering_id, output_offering_id);

-- A cutting / processing run: source consumed, outputs made, the rest is trim.
CREATE TABLE inventory_conversions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    business_id UUID NOT NULL REFERENCES businesses(id),
    location_id UUID NOT NULL REFERENCES business_locations(id),
    source_offering_id UUID NOT NULL REFERENCES offerings_catalog_offerings(id),
    source_quantity INTEGER NOT NULL CHECK (source_quantity > 0),
    -- [{"offering_id", "expected", "actual", "value_paise"}], quantities in stock units
    outputs JSONB NOT NULL CHECK (jsonb_typeof(outputs) = 'array'),
    trim_quantity INTEGER NOT NULL CHECK (trim_quantity >= 0),
    note TEXT CHECK (note IS NULL OR length(note) <= 300),
    actor_identity_id UUID REFERENCES platform_identities(id),
    idempotency_key TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX inventory_conversions_recent ON inventory_conversions (business_id, created_at DESC);
CREATE UNIQUE INDEX inventory_conversions_idem ON inventory_conversions (business_id, idempotency_key)
    WHERE idempotency_key IS NOT NULL;

-- ---------------------------------------------------------------- counts
CREATE TABLE inventory_counts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    business_id UUID NOT NULL REFERENCES businesses(id),
    location_id UUID NOT NULL REFERENCES business_locations(id),
    category_id UUID REFERENCES offerings_catalog_categories(id),
    label TEXT NOT NULL CHECK (length(label) BETWEEN 1 AND 120),
    status TEXT NOT NULL DEFAULT 'open' CHECK (status IN ('open', 'submitted', 'approved', 'cancelled')),
    started_by UUID REFERENCES platform_identities(id),
    submitted_by UUID REFERENCES platform_identities(id),
    submitted_at TIMESTAMPTZ,
    decided_by UUID REFERENCES platform_identities(id),
    decided_at TIMESTAMPTZ,
    decision_note TEXT CHECK (decision_note IS NULL OR length(decision_note) <= 300),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    version INTEGER NOT NULL DEFAULT 1
);
CREATE INDEX inventory_counts_open ON inventory_counts (business_id, status, created_at DESC);

CREATE TABLE inventory_count_lines (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    business_id UUID NOT NULL REFERENCES businesses(id),
    count_id UUID NOT NULL REFERENCES inventory_counts(id),
    inventory_record_id UUID NOT NULL REFERENCES inventory_records(id),
    -- Snapshot when the count started: sales during the count still count.
    expected_quantity INTEGER NOT NULL CHECK (expected_quantity >= 0),
    counted_quantity INTEGER CHECK (counted_quantity IS NULL OR counted_quantity >= 0),
    counted_by UUID REFERENCES platform_identities(id),
    counted_at TIMESTAMPTZ,
    UNIQUE (count_id, inventory_record_id)
);

-- ---------------------------------------------------------------- bill and order lines
ALTER TABLE invoicing_document_lines
    ADD COLUMN serials TEXT[] NOT NULL DEFAULT '{}',
    ADD COLUMN batch_allocations JSONB NOT NULL DEFAULT '[]'::jsonb;
ALTER TABLE orders_order_line_items
    ADD COLUMN serials TEXT[] NOT NULL DEFAULT '{}',
    ADD COLUMN batch_allocations JSONB NOT NULL DEFAULT '[]'::jsonb;

-- ---------------------------------------------------------------- triggers
CREATE TRIGGER trg_inventory_batches_updated_at BEFORE UPDATE ON inventory_batches
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();
CREATE TRIGGER trg_inventory_serials_updated_at BEFORE UPDATE ON inventory_serials
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();
CREATE TRIGGER trg_inventory_yields_updated_at BEFORE UPDATE ON inventory_yields
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();
CREATE TRIGGER trg_inventory_counts_updated_at BEFORE UPDATE ON inventory_counts
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

-- ---------------------------------------------------------------- RLS
DO $$
DECLARE t TEXT;
BEGIN
    FOREACH t IN ARRAY ARRAY['inventory_batches', 'inventory_serials', 'inventory_yields',
                             'inventory_conversions', 'inventory_counts', 'inventory_count_lines'] LOOP
        EXECUTE format('ALTER TABLE %I ENABLE ROW LEVEL SECURITY', t);
        EXECUTE format('ALTER TABLE %I FORCE ROW LEVEL SECURITY', t);
        EXECUTE format('CREATE POLICY %I ON %I FOR SELECT TO public USING (business_id = current_business_id())',
                       t || '_member_read', t);
        EXECUTE format('CREATE POLICY %I ON %I FOR ALL TO platform_api USING (business_id = current_business_id()) '
                       'WITH CHECK (business_id = current_business_id())', t || '_api_write', t);
        -- Stock history is never deleted: corrections are new movements.
        EXECUTE format('GRANT SELECT, INSERT, UPDATE ON %I TO platform_api', t);
        EXECUTE format('REVOKE DELETE ON %I FROM platform_api', t);
        EXECUTE format('REVOKE ALL PRIVILEGES ON TABLE %I FROM anon', t);
    END LOOP;
    -- Location-scoped staff (a store keeper at one shop) see only their locations.
    FOREACH t IN ARRAY ARRAY['inventory_batches', 'inventory_serials', 'inventory_conversions',
                             'inventory_counts'] LOOP
        EXECUTE format(
            'CREATE POLICY %I ON %I AS RESTRICTIVE FOR ALL TO platform_api '
            'USING (location_scope_allows(location_id)) WITH CHECK (location_scope_allows(location_id))',
            t || '_location_scope', t);
    END LOOP;
END
$$;
