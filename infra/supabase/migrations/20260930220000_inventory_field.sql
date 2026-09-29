-- Inventory field (founder refinement: multi-location, van stock, customer assets,
-- client-owned stock). Extends the one inventory ledger. Does not replace it.
--
-- A transfer is a real movement:
--   requested → approved where required → in transit → received.
-- Stock in transit is not on hand at the source (transfer_out already posted)
-- and not on hand at the destination until receipt posts transfer_in.
-- A van is a business_locations row with stock_role = 'van', not a second stock system.
-- customer_assets is one generic primitive (vehicle, device, AC unit, machine,
-- pet, policy). Kind-specific facts live in traits, not in a table per industry.
-- Client-owned quantity is a separate inventory_records row (owner_customer_id set)
-- and is never the row sale, POS, or reservation reads.

-- ---------------------------------------------------------------- locations
ALTER TABLE business_locations
    ADD COLUMN stock_role TEXT NOT NULL DEFAULT 'store'
        CHECK (stock_role IN ('store', 'warehouse', 'van'));

-- ---------------------------------------------------------------- client-owned balances
ALTER TABLE inventory_records
    ADD COLUMN owner_customer_id UUID REFERENCES customer_relationships_contacts(id);

-- The old unique indexes treated every balance at a location as the shop's.
-- Business-owned (owner null) and client-owned stay unique on their own keys.
DROP INDEX IF EXISTS idx_inventory_record_no_variant;
DROP INDEX IF EXISTS idx_inventory_record_with_variant;

CREATE UNIQUE INDEX idx_inventory_record_business_no_variant
    ON inventory_records (business_id, offering_id, location_id)
    WHERE variant_id IS NULL AND owner_customer_id IS NULL;
CREATE UNIQUE INDEX idx_inventory_record_business_variant
    ON inventory_records (business_id, offering_id, variant_id, location_id)
    WHERE variant_id IS NOT NULL AND owner_customer_id IS NULL;
CREATE UNIQUE INDEX idx_inventory_record_client_no_variant
    ON inventory_records (business_id, offering_id, location_id, owner_customer_id)
    WHERE variant_id IS NULL AND owner_customer_id IS NOT NULL;
CREATE UNIQUE INDEX idx_inventory_record_client_variant
    ON inventory_records (business_id, offering_id, variant_id, location_id, owner_customer_id)
    WHERE variant_id IS NOT NULL AND owner_customer_id IS NOT NULL;
CREATE INDEX idx_inventory_records_owner
    ON inventory_records (business_id, owner_customer_id)
    WHERE owner_customer_id IS NOT NULL;

-- ---------------------------------------------------------------- movements
ALTER TABLE inventory_movements DROP CONSTRAINT IF EXISTS inventory_movements_movement_type_check;
ALTER TABLE inventory_movements ADD CONSTRAINT inventory_movements_movement_type_check
    CHECK (movement_type IN (
        'opening_stock', 'adjustment', 'receipt', 'deduction', 'reversal', 'reservation',
        'wastage', 'count_variance', 'conversion_out', 'conversion_in',
        'transfer_out', 'transfer_in', 'job_consumption', 'job_return',
        'client_inward', 'client_outward'
    ));

-- ---------------------------------------------------------------- transfers
CREATE TABLE inventory_transfers (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    business_id UUID NOT NULL REFERENCES businesses(id),
    source_location_id UUID NOT NULL REFERENCES business_locations(id),
    destination_location_id UUID NOT NULL REFERENCES business_locations(id),
    status TEXT NOT NULL DEFAULT 'requested'
        CHECK (status IN ('requested', 'approved', 'in_transit', 'received', 'cancelled')),
    requires_approval BOOLEAN NOT NULL DEFAULT false,
    idempotency_key TEXT,
    note TEXT,
    requested_by UUID REFERENCES platform_identities(id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    version INTEGER NOT NULL DEFAULT 1,
    CHECK (source_location_id <> destination_location_id),
    CHECK (idempotency_key IS NULL OR length(idempotency_key) BETWEEN 8 AND 80)
);
CREATE UNIQUE INDEX inventory_transfers_idem
    ON inventory_transfers (business_id, idempotency_key)
    WHERE idempotency_key IS NOT NULL;
CREATE INDEX inventory_transfers_status
    ON inventory_transfers (business_id, status, created_at DESC);

CREATE TABLE inventory_transfer_lines (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    business_id UUID NOT NULL REFERENCES businesses(id),
    transfer_id UUID NOT NULL REFERENCES inventory_transfers(id),
    offering_id UUID NOT NULL REFERENCES offerings_catalog_offerings(id),
    variant_id UUID REFERENCES offerings_catalog_variants(id),
    quantity INTEGER NOT NULL CHECK (quantity > 0),
    -- Value that left the source, applied once when the destination receives.
    value_paise BIGINT NOT NULL DEFAULT 0,
    -- Batch identity captured at send, so receipt can restore it at the destination.
    allocations JSONB NOT NULL DEFAULT '[]'::jsonb,
    CHECK (jsonb_typeof(allocations) = 'array')
);
CREATE UNIQUE INDEX inventory_transfer_lines_item
    ON inventory_transfer_lines (
        transfer_id, offering_id,
        COALESCE(variant_id, '00000000-0000-0000-0000-000000000000'::uuid)
    );
CREATE INDEX inventory_transfer_lines_transfer ON inventory_transfer_lines (transfer_id);

-- One row per idempotency key. Replaying the key returns the stored result
-- and does not post another movement.
CREATE TABLE inventory_field_keys (
    business_id UUID NOT NULL REFERENCES businesses(id),
    idempotency_key TEXT NOT NULL CHECK (length(idempotency_key) BETWEEN 8 AND 80),
    action TEXT NOT NULL,
    subject_id UUID,
    snapshot JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (business_id, idempotency_key)
);

-- ---------------------------------------------------------------- job consumption contract
-- The jobs lane passes a job_ref. This table does not reference a jobs table.
-- quantity_back cannot exceed quantity_out (unused parts only).
CREATE TABLE inventory_job_uses (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    business_id UUID NOT NULL REFERENCES businesses(id),
    location_id UUID NOT NULL REFERENCES business_locations(id),
    job_ref UUID NOT NULL,
    offering_id UUID NOT NULL REFERENCES offerings_catalog_offerings(id),
    variant_id UUID REFERENCES offerings_catalog_variants(id),
    quantity_out INTEGER NOT NULL DEFAULT 0 CHECK (quantity_out >= 0),
    quantity_back INTEGER NOT NULL DEFAULT 0 CHECK (quantity_back >= 0),
    value_out_paise BIGINT NOT NULL DEFAULT 0,
    value_back_paise BIGINT NOT NULL DEFAULT 0,
    allocations JSONB NOT NULL DEFAULT '[]'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CHECK (quantity_back <= quantity_out),
    CHECK (jsonb_typeof(allocations) = 'array')
);
CREATE UNIQUE INDEX inventory_job_uses_key
    ON inventory_job_uses (
        business_id, location_id, job_ref, offering_id,
        COALESCE(variant_id, '00000000-0000-0000-0000-000000000000'::uuid)
    );

-- ---------------------------------------------------------------- customer assets
CREATE TABLE customer_assets (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    business_id UUID NOT NULL REFERENCES businesses(id),
    customer_id UUID NOT NULL REFERENCES customer_relationships_contacts(id),
    asset_kind TEXT NOT NULL CHECK (asset_kind IN (
        'vehicle', 'device', 'ac_unit', 'machine', 'pet', 'policy', 'other'
    )),
    label TEXT NOT NULL CHECK (length(label) BETWEEN 1 AND 160),
    identifier TEXT CHECK (identifier IS NULL OR length(identifier) BETWEEN 1 AND 80),
    traits JSONB NOT NULL DEFAULT '{}'::jsonb CHECK (jsonb_typeof(traits) = 'object'),
    status TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'archived')),
    notes TEXT,
    idempotency_key TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    deleted_at TIMESTAMPTZ,
    version INTEGER NOT NULL DEFAULT 1
);
CREATE INDEX customer_assets_customer
    ON customer_assets (business_id, customer_id)
    WHERE deleted_at IS NULL;
CREATE UNIQUE INDEX customer_assets_idem
    ON customer_assets (business_id, idempotency_key)
    WHERE idempotency_key IS NOT NULL AND deleted_at IS NULL;

-- ---------------------------------------------------------------- triggers
CREATE TRIGGER trg_inventory_transfers_updated_at BEFORE UPDATE ON inventory_transfers
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();
CREATE TRIGGER trg_inventory_job_uses_updated_at BEFORE UPDATE ON inventory_job_uses
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();
CREATE TRIGGER trg_customer_assets_updated_at BEFORE UPDATE ON customer_assets
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

-- ---------------------------------------------------------------- RLS
DO $$
DECLARE t TEXT;
BEGIN
    FOREACH t IN ARRAY ARRAY[
        'inventory_transfers', 'inventory_transfer_lines', 'inventory_field_keys',
        'inventory_job_uses', 'customer_assets'
    ] LOOP
        EXECUTE format('ALTER TABLE %I ENABLE ROW LEVEL SECURITY', t);
        EXECUTE format('ALTER TABLE %I FORCE ROW LEVEL SECURITY', t);
        EXECUTE format(
            'CREATE POLICY %I ON %I FOR SELECT TO public USING (business_id = current_business_id())',
            t || '_member_read', t);
        EXECUTE format(
            'CREATE POLICY %I ON %I FOR ALL TO platform_api USING (business_id = current_business_id()) '
            'WITH CHECK (business_id = current_business_id())',
            t || '_api_write', t);
        EXECUTE format('GRANT SELECT, INSERT, UPDATE ON %I TO platform_api', t);
        EXECUTE format('REVOKE DELETE ON %I FROM platform_api', t);
        EXECUTE format('REVOKE ALL PRIVILEGES ON TABLE %I FROM anon', t);
    END LOOP;
END
$$;

-- A person limited to some locations sees a transfer when they hold the source
-- or the destination. Lines follow the transfer. Job use follows its location.
CREATE POLICY inventory_transfers_location_scope ON inventory_transfers
    AS RESTRICTIVE FOR ALL TO platform_api
    USING (location_scope_allows(source_location_id) OR location_scope_allows(destination_location_id))
    WITH CHECK (location_scope_allows(source_location_id) OR location_scope_allows(destination_location_id));

CREATE POLICY inventory_transfer_lines_location_scope ON inventory_transfer_lines
    AS RESTRICTIVE FOR ALL TO platform_api
    USING (EXISTS (
        SELECT 1 FROM inventory_transfers t
        WHERE t.id = inventory_transfer_lines.transfer_id
          AND (location_scope_allows(t.source_location_id) OR location_scope_allows(t.destination_location_id))
    ))
    WITH CHECK (EXISTS (
        SELECT 1 FROM inventory_transfers t
        WHERE t.id = inventory_transfer_lines.transfer_id
          AND (location_scope_allows(t.source_location_id) OR location_scope_allows(t.destination_location_id))
    ));

CREATE POLICY inventory_job_uses_location_scope ON inventory_job_uses
    AS RESTRICTIVE FOR ALL TO platform_api
    USING (location_scope_allows(location_id))
    WITH CHECK (location_scope_allows(location_id));
