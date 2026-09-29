-- Supply lane: suppliers, requisitions, purchase orders, goods receipts,
-- supplier bills, recipes/BOM, sealed trade copies, expenses, connectors,
-- documents and donations.
--
-- Sales orders, requisitions, purchase orders, goods receipts and supplier
-- bills are different records. A purchase order never changes stock. Only a
-- goods receipt does, and it does that by calling the inventory receive path
-- from the application — this migration does not write inventory_records.
--
-- A supplier business never reads the buyer's tables. Sending a purchase order
-- to another LOCAH business copies only the agreed commercial lines through
-- procurement_post_trade, which inserts recipient-owned rows.

CREATE TABLE procurement_suppliers (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    business_id UUID NOT NULL REFERENCES businesses(id),
    name TEXT NOT NULL,
    contact_name TEXT,
    phone TEXT,
    email TEXT,
    connection TEXT NOT NULL DEFAULT 'off_network'
        CHECK (connection IN ('locah', 'off_network')),
    linked_business_id UUID REFERENCES businesses(id),
    payment_terms TEXT,
    credit_days INTEGER NOT NULL DEFAULT 0 CHECK (credit_days >= 0),
    preferred BOOLEAN NOT NULL DEFAULT false,
    status TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'inactive')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT procurement_suppliers_not_self CHECK (linked_business_id IS DISTINCT FROM business_id)
);

CREATE TABLE procurement_supplier_items (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    business_id UUID NOT NULL REFERENCES businesses(id),
    supplier_id UUID NOT NULL REFERENCES procurement_suppliers(id),
    offering_id UUID NOT NULL REFERENCES offerings_catalog_offerings(id),
    supplier_sku TEXT,
    buy_unit TEXT,
    pack_size INTEGER NOT NULL DEFAULT 1 CHECK (pack_size >= 1),
    moq INTEGER NOT NULL DEFAULT 1 CHECK (moq >= 1),
    lead_time_days INTEGER NOT NULL DEFAULT 0 CHECK (lead_time_days >= 0),
    delivery_days INTEGER[] NOT NULL DEFAULT '{}',
    unit_price_paise INTEGER NOT NULL DEFAULT 0 CHECK (unit_price_paise >= 0),
    preferred BOOLEAN NOT NULL DEFAULT false,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (business_id, supplier_id, offering_id)
);

CREATE TABLE procurement_price_agreements (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    business_id UUID NOT NULL REFERENCES businesses(id),
    supplier_item_id UUID NOT NULL REFERENCES procurement_supplier_items(id),
    unit_price_paise INTEGER NOT NULL CHECK (unit_price_paise >= 0),
    pack_size INTEGER NOT NULL DEFAULT 1 CHECK (pack_size >= 1),
    moq INTEGER NOT NULL DEFAULT 1 CHECK (moq >= 1),
    credit_days INTEGER NOT NULL DEFAULT 0 CHECK (credit_days >= 0),
    effective_from DATE NOT NULL,
    effective_to DATE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE procurement_requisitions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    business_id UUID NOT NULL REFERENCES businesses(id),
    location_id UUID REFERENCES business_locations(id),
    source TEXT NOT NULL CHECK (source IN (
        'manual', 'reorder', 'demand', 'recipe', 'par', 'booking', 'subscription'
    )),
    status TEXT NOT NULL DEFAULT 'draft' CHECK (status IN (
        'draft', 'submitted', 'approved', 'rejected', 'converted'
    )),
    explanation TEXT NOT NULL DEFAULT '',
    provenance JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_by UUID REFERENCES platform_identities(id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE procurement_requisition_lines (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    business_id UUID NOT NULL REFERENCES businesses(id),
    requisition_id UUID NOT NULL REFERENCES procurement_requisitions(id),
    offering_id UUID NOT NULL REFERENCES offerings_catalog_offerings(id),
    supplier_id UUID REFERENCES procurement_suppliers(id),
    quantity INTEGER NOT NULL CHECK (quantity > 0),
    demand_quantity INTEGER NOT NULL DEFAULT 0 CHECK (demand_quantity >= 0),
    usable_on_hand INTEGER NOT NULL DEFAULT 0 CHECK (usable_on_hand >= 0),
    confirmed_inbound INTEGER NOT NULL DEFAULT 0 CHECK (confirmed_inbound >= 0),
    safety_stock INTEGER NOT NULL DEFAULT 0 CHECK (safety_stock >= 0),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE procurement_purchase_orders (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    business_id UUID NOT NULL REFERENCES businesses(id),
    supplier_id UUID NOT NULL REFERENCES procurement_suppliers(id),
    requisition_id UUID REFERENCES procurement_requisitions(id),
    reference TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'draft' CHECK (status IN (
        'draft', 'approved', 'sent', 'countered', 'acknowledged',
        'dispatched', 'received', 'disputed', 'billed', 'paid', 'declined'
    )),
    currency TEXT NOT NULL DEFAULT 'INR',
    notes TEXT,
    version INTEGER NOT NULL DEFAULT 1,
    created_by UUID REFERENCES platform_identities(id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (business_id, reference)
);

CREATE TABLE procurement_purchase_order_lines (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    business_id UUID NOT NULL REFERENCES businesses(id),
    purchase_order_id UUID NOT NULL REFERENCES procurement_purchase_orders(id),
    offering_id UUID NOT NULL REFERENCES offerings_catalog_offerings(id),
    quantity INTEGER NOT NULL CHECK (quantity > 0),
    unit_price_paise INTEGER NOT NULL CHECK (unit_price_paise >= 0),
    requested_for TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE procurement_po_events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    business_id UUID NOT NULL REFERENCES businesses(id),
    purchase_order_id UUID NOT NULL REFERENCES procurement_purchase_orders(id),
    actor_id UUID REFERENCES platform_identities(id),
    from_status TEXT,
    to_status TEXT NOT NULL,
    reason TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE procurement_po_counters (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    business_id UUID NOT NULL REFERENCES businesses(id),
    purchase_order_id UUID NOT NULL REFERENCES procurement_purchase_orders(id),
    line_id UUID NOT NULL REFERENCES procurement_purchase_order_lines(id),
    proposed_quantity INTEGER NOT NULL CHECK (proposed_quantity > 0),
    proposed_price_paise INTEGER NOT NULL CHECK (proposed_price_paise >= 0),
    proposed_for TIMESTAMPTZ,
    status TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'accepted', 'declined')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE procurement_goods_receipts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    business_id UUID NOT NULL REFERENCES businesses(id),
    purchase_order_id UUID NOT NULL REFERENCES procurement_purchase_orders(id),
    location_id UUID NOT NULL REFERENCES business_locations(id),
    idempotency_key TEXT NOT NULL,
    notes TEXT,
    created_by UUID REFERENCES platform_identities(id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (business_id, idempotency_key)
);

CREATE TABLE procurement_goods_receipt_lines (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    business_id UUID NOT NULL REFERENCES businesses(id),
    receipt_id UUID NOT NULL REFERENCES procurement_goods_receipts(id),
    offering_id UUID NOT NULL REFERENCES offerings_catalog_offerings(id),
    ordered_quantity INTEGER NOT NULL CHECK (ordered_quantity >= 0),
    received_quantity INTEGER NOT NULL CHECK (received_quantity >= 0),
    damaged_quantity INTEGER NOT NULL DEFAULT 0 CHECK (damaged_quantity >= 0),
    batch_code TEXT,
    expires_on DATE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE procurement_supplier_bills (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    business_id UUID NOT NULL REFERENCES businesses(id),
    supplier_id UUID NOT NULL REFERENCES procurement_suppliers(id),
    purchase_order_id UUID REFERENCES procurement_purchase_orders(id),
    receipt_id UUID REFERENCES procurement_goods_receipts(id),
    invoice_reference TEXT NOT NULL,
    amount_paise INTEGER NOT NULL CHECK (amount_paise >= 0),
    tax_paise INTEGER NOT NULL DEFAULT 0 CHECK (tax_paise >= 0),
    due_on DATE,
    status TEXT NOT NULL DEFAULT 'open' CHECK (status IN ('open', 'partial', 'paid')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (business_id, supplier_id, invoice_reference)
);

CREATE TABLE recipe_boms (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    business_id UUID NOT NULL REFERENCES businesses(id),
    offering_id UUID NOT NULL REFERENCES offerings_catalog_offerings(id),
    name TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (business_id, offering_id)
);

CREATE TABLE recipe_consumptions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    business_id UUID NOT NULL REFERENCES businesses(id),
    idempotency_key TEXT NOT NULL,
    offering_id UUID NOT NULL REFERENCES offerings_catalog_offerings(id),
    quantity INTEGER NOT NULL CHECK (quantity > 0),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (business_id, idempotency_key)
);

CREATE TABLE recipe_bom_lines (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    business_id UUID NOT NULL REFERENCES businesses(id),
    bom_id UUID NOT NULL REFERENCES recipe_boms(id),
    component_offering_id UUID NOT NULL REFERENCES offerings_catalog_offerings(id),
    quantity_per NUMERIC(14, 4) NOT NULL CHECK (quantity_per > 0),
    yield_ratio NUMERIC(8, 4) NOT NULL DEFAULT 1 CHECK (yield_ratio > 0),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE procurement_trade_messages (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    sender_business_id UUID NOT NULL REFERENCES businesses(id),
    recipient_business_id UUID NOT NULL REFERENCES businesses(id),
    source_po_id UUID NOT NULL,
    kind TEXT NOT NULL,
    payload JSONB NOT NULL,
    idempotency_key TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (sender_business_id, idempotency_key)
);

CREATE TABLE procurement_incoming_demands (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    business_id UUID NOT NULL REFERENCES businesses(id),
    source_business_id UUID NOT NULL,
    source_po_id UUID NOT NULL,
    buyer_label TEXT NOT NULL,
    item_label TEXT NOT NULL,
    offering_id UUID,
    quantity INTEGER NOT NULL CHECK (quantity > 0),
    unit_price_paise INTEGER NOT NULL CHECK (unit_price_paise >= 0),
    status TEXT NOT NULL DEFAULT 'incoming' CHECK (status IN (
        'incoming', 'accepted', 'countered', 'declined'
    )),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE expenses_categories (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    business_id UUID NOT NULL REFERENCES businesses(id),
    name TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (business_id, name)
);

CREATE TABLE expenses_records (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    business_id UUID NOT NULL REFERENCES businesses(id),
    category_id UUID REFERENCES expenses_categories(id),
    location_id UUID REFERENCES business_locations(id),
    payee TEXT,
    supplier_id UUID REFERENCES procurement_suppliers(id),
    spent_on DATE NOT NULL,
    amount_paise INTEGER NOT NULL CHECK (amount_paise >= 0),
    tax_paise INTEGER NOT NULL DEFAULT 0 CHECK (tax_paise >= 0),
    method TEXT NOT NULL CHECK (method IN ('cash', 'bank', 'upi', 'card')),
    notes TEXT,
    petty_cash BOOLEAN NOT NULL DEFAULT false,
    created_by UUID REFERENCES platform_identities(id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE connector_connections (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    business_id UUID NOT NULL REFERENCES businesses(id),
    provider TEXT NOT NULL,
    state TEXT NOT NULL DEFAULT 'inactive' CHECK (state IN (
        'inactive', 'paired', 'error', 'paused'
    )),
    direction TEXT NOT NULL CHECK (direction IN ('export', 'import', 'both')),
    authority TEXT NOT NULL CHECK (authority IN (
        'locah', 'external', 'bidirectional'
    )),
    capabilities TEXT[] NOT NULL DEFAULT '{}',
    secret_ref TEXT,
    cursor TEXT,
    last_success_at TIMESTAMPTZ,
    last_error TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (business_id, provider)
);

CREATE TABLE connector_sync_runs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    business_id UUID NOT NULL REFERENCES businesses(id),
    connection_id UUID NOT NULL REFERENCES connector_connections(id),
    idempotency_key TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('ok', 'error')),
    detail TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (connection_id, idempotency_key)
);

CREATE TABLE connector_mappings (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    business_id UUID NOT NULL REFERENCES businesses(id),
    connection_id UUID NOT NULL REFERENCES connector_connections(id),
    family TEXT NOT NULL,
    locah_key TEXT NOT NULL,
    external_key TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (connection_id, family, locah_key)
);

CREATE TABLE documents_records (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    business_id UUID NOT NULL REFERENCES businesses(id),
    document_type TEXT NOT NULL,
    title TEXT NOT NULL,
    storage_key TEXT,
    related_type TEXT,
    related_id UUID,
    expires_on DATE,
    verification_status TEXT NOT NULL DEFAULT 'unverified'
        CHECK (verification_status IN ('unverified', 'verified', 'rejected')),
    created_by UUID REFERENCES platform_identities(id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE donations_causes (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    business_id UUID NOT NULL REFERENCES businesses(id),
    name TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'open' CHECK (status IN ('open', 'closed')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE donations_gifts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    business_id UUID NOT NULL REFERENCES businesses(id),
    cause_id UUID NOT NULL REFERENCES donations_causes(id),
    donor_name TEXT NOT NULL,
    amount_paise INTEGER NOT NULL CHECK (amount_paise > 0),
    payment_id UUID,
    kind TEXT NOT NULL DEFAULT 'one_time' CHECK (kind IN ('one_time', 'pledge')),
    receipt_reference TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (business_id, receipt_reference)
);

CREATE INDEX procurement_suppliers_business ON procurement_suppliers (business_id);
CREATE INDEX procurement_po_business_status ON procurement_purchase_orders (business_id, status);
CREATE INDEX procurement_incoming_business ON procurement_incoming_demands (business_id, status);
CREATE INDEX expenses_business_date ON expenses_records (business_id, spent_on);

-- Sealed cross-tenant copy. The caller must already be the sending business.
-- The function does not read the sender's purchase order. It stores only the
-- payload the application already reduced to agreed commercial fields.
CREATE OR REPLACE FUNCTION procurement_post_trade(
    p_sender UUID,
    p_recipient UUID,
    p_source_po UUID,
    p_buyer_label TEXT,
    p_lines JSONB,
    p_idempotency TEXT
) RETURNS UUID
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
DECLARE
    mid UUID;
    line JSONB;
BEGIN
    IF current_business_id() IS DISTINCT FROM p_sender THEN
        RAISE EXCEPTION 'trade sender does not match the current business';
    END IF;
    IF p_sender = p_recipient THEN
        RAISE EXCEPTION 'a business cannot trade with itself';
    END IF;
    SELECT id INTO mid
    FROM procurement_trade_messages
    WHERE sender_business_id = p_sender AND idempotency_key = p_idempotency;
    IF mid IS NOT NULL THEN
        RETURN mid;
    END IF;
    INSERT INTO procurement_trade_messages (
        sender_business_id, recipient_business_id, source_po_id, kind, payload, idempotency_key
    ) VALUES (
        p_sender, p_recipient, p_source_po, 'purchase_order',
        jsonb_build_object('buyer_label', p_buyer_label, 'lines', p_lines),
        p_idempotency
    ) RETURNING id INTO mid;
    FOR line IN SELECT * FROM jsonb_array_elements(p_lines)
    LOOP
        INSERT INTO procurement_incoming_demands (
            business_id, source_business_id, source_po_id, buyer_label, item_label,
            quantity, unit_price_paise
        ) VALUES (
            p_recipient, p_sender, p_source_po, p_buyer_label,
            line->>'item_label',
            (line->>'quantity')::integer,
            (line->>'unit_price_paise')::integer
        );
    END LOOP;
    RETURN mid;
END;
$$;

REVOKE ALL ON FUNCTION procurement_post_trade(UUID, UUID, UUID, TEXT, JSONB, TEXT) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION procurement_post_trade(UUID, UUID, UUID, TEXT, JSONB, TEXT) TO platform_api;

DO $$
DECLARE
    t TEXT;
BEGIN
    FOREACH t IN ARRAY ARRAY[
        'procurement_suppliers', 'procurement_supplier_items', 'procurement_price_agreements',
        'procurement_requisitions', 'procurement_requisition_lines',
        'procurement_purchase_orders', 'procurement_purchase_order_lines',
        'procurement_po_events', 'procurement_po_counters',
        'procurement_goods_receipts', 'procurement_goods_receipt_lines',
        'procurement_supplier_bills', 'recipe_boms', 'recipe_bom_lines', 'recipe_consumptions',
        'procurement_incoming_demands', 'expenses_categories', 'expenses_records',
        'connector_connections', 'connector_sync_runs', 'connector_mappings',
        'documents_records', 'donations_causes', 'donations_gifts'
    ]
    LOOP
        EXECUTE format('ALTER TABLE %I ENABLE ROW LEVEL SECURITY', t);
        EXECUTE format('ALTER TABLE %I FORCE ROW LEVEL SECURITY', t);
        EXECUTE format(
            'CREATE POLICY %I ON %I FOR SELECT TO public USING (business_id = current_business_id())',
            t || '_read', t
        );
        EXECUTE format(
            'CREATE POLICY %I ON %I FOR ALL TO platform_api USING (business_id = current_business_id()) WITH CHECK (business_id = current_business_id())',
            t || '_write', t
        );
        EXECUTE format('GRANT SELECT, INSERT, UPDATE, DELETE ON %I TO platform_api', t);
    END LOOP;
END $$;

ALTER TABLE procurement_trade_messages ENABLE ROW LEVEL SECURITY;
ALTER TABLE procurement_trade_messages FORCE ROW LEVEL SECURITY;
CREATE POLICY procurement_trade_read ON procurement_trade_messages
    FOR SELECT TO public
    USING (sender_business_id = current_business_id() OR recipient_business_id = current_business_id());
CREATE POLICY procurement_trade_write ON procurement_trade_messages
    FOR ALL TO platform_api
    USING (sender_business_id = current_business_id())
    WITH CHECK (sender_business_id = current_business_id());
GRANT SELECT, INSERT ON procurement_trade_messages TO platform_api;

INSERT INTO module_definitions (id, name, module_class, description, dependencies, is_available)
VALUES
    ('procurement', 'Buying', 'optional', 'Suppliers, requisitions, purchase orders and goods receipts', '{core-business-profile}', true),
    ('recipes', 'Recipes', 'optional', 'Bills of materials and yield for made items', '{core-business-profile}', true),
    ('expenses', 'Expenses', 'optional', 'Spending, petty cash and categories', '{core-business-profile}', true),
    ('connectors', 'Connectors', 'optional', 'External books and sync, including Tally', '{core-business-profile}', true),
    ('documents', 'Documents', 'optional', 'Files linked to the business, with expiry and verification', '{core-business-profile}', true),
    ('donations', 'Donations', 'optional', 'Causes and gifts, separate from orders', '{core-business-profile}', true)
ON CONFLICT (id) DO NOTHING;
