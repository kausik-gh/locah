-- Stage 6: Orders, Sales & Commerce Kernel (First Launch scope)
-- Payments checkout orchestration deferred; workspace order lifecycle included per Doc 11 §9.2

CREATE TABLE orders_orders (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    business_id UUID NOT NULL REFERENCES businesses(id),
    location_id UUID NOT NULL REFERENCES business_locations(id),
    customer_contact_id UUID REFERENCES customer_relationships_contacts(id),
    order_number TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending'
        CHECK (status IN (
            'pending', 'accepted', 'preparing', 'ready',
            'completed', 'cancelled', 'rejected'
        )),
    payment_method TEXT NOT NULL DEFAULT 'cod'
        CHECK (payment_method IN ('cod', 'online', 'pay_at_business', 'pay_later')),
    payment_status TEXT NOT NULL DEFAULT 'pending'
        CHECK (payment_status IN ('pending', 'pending_offline', 'paid', 'refunded')),
    currency TEXT NOT NULL DEFAULT 'INR',
    subtotal NUMERIC(12, 2) NOT NULL DEFAULT 0 CHECK (subtotal >= 0),
    tax_amount NUMERIC(12, 2) NOT NULL DEFAULT 0 CHECK (tax_amount >= 0),
    discount_amount NUMERIC(12, 2) NOT NULL DEFAULT 0 CHECK (discount_amount >= 0),
    total_amount NUMERIC(12, 2) NOT NULL DEFAULT 0 CHECK (total_amount >= 0),
    internal_reference TEXT,
    cancellation_reason TEXT,
    cancelled_by UUID REFERENCES platform_identities(id),
    idempotency_key TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    deleted_at TIMESTAMPTZ,
    version INTEGER NOT NULL DEFAULT 1
);

CREATE UNIQUE INDEX idx_orders_number ON orders_orders(business_id, order_number)
    WHERE deleted_at IS NULL;
CREATE UNIQUE INDEX idx_orders_idempotency ON orders_orders(business_id, idempotency_key)
    WHERE deleted_at IS NULL AND idempotency_key IS NOT NULL;
CREATE INDEX idx_orders_business_status ON orders_orders(business_id, status, created_at DESC)
    WHERE deleted_at IS NULL;
CREATE INDEX idx_orders_customer ON orders_orders(business_id, customer_contact_id)
    WHERE deleted_at IS NULL AND customer_contact_id IS NOT NULL;
CREATE INDEX idx_orders_location ON orders_orders(business_id, location_id)
    WHERE deleted_at IS NULL;

CREATE TABLE orders_order_line_items (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    business_id UUID NOT NULL REFERENCES businesses(id),
    order_id UUID NOT NULL REFERENCES orders_orders(id) ON DELETE CASCADE,
    offering_id UUID NOT NULL REFERENCES offerings_catalog_offerings(id),
    variant_id UUID REFERENCES offerings_catalog_variants(id),
    title TEXT NOT NULL,
    sku TEXT,
    unit_price NUMERIC(12, 2) NOT NULL CHECK (unit_price >= 0),
    quantity INTEGER NOT NULL CHECK (quantity > 0),
    tax_rate NUMERIC(5, 2),
    line_subtotal NUMERIC(12, 2) NOT NULL CHECK (line_subtotal >= 0),
    line_tax NUMERIC(12, 2) NOT NULL DEFAULT 0 CHECK (line_tax >= 0),
    line_total NUMERIC(12, 2) NOT NULL CHECK (line_total >= 0),
    track_inventory BOOLEAN NOT NULL DEFAULT false,
    quantity_reserved INTEGER NOT NULL DEFAULT 0 CHECK (quantity_reserved >= 0),
    quantity_deducted INTEGER NOT NULL DEFAULT 0 CHECK (quantity_deducted >= 0),
    sort_order INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_order_line_items_order ON orders_order_line_items(order_id, sort_order);

CREATE TABLE orders_order_status_history (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    business_id UUID NOT NULL REFERENCES businesses(id),
    order_id UUID NOT NULL REFERENCES orders_orders(id) ON DELETE CASCADE,
    from_status TEXT,
    to_status TEXT NOT NULL,
    actor_identity_id UUID REFERENCES platform_identities(id),
    reason TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_order_status_history_order ON orders_order_status_history(order_id, created_at DESC);

CREATE TABLE orders_order_notes (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    business_id UUID NOT NULL REFERENCES businesses(id),
    order_id UUID NOT NULL REFERENCES orders_orders(id) ON DELETE CASCADE,
    body TEXT NOT NULL,
    author_identity_id UUID NOT NULL REFERENCES platform_identities(id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    deleted_at TIMESTAMPTZ,
    version INTEGER NOT NULL DEFAULT 1
);

CREATE INDEX idx_order_notes_order ON orders_order_notes(order_id)
    WHERE deleted_at IS NULL;

CREATE TRIGGER trg_orders_orders_updated_at BEFORE UPDATE ON orders_orders
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();
CREATE TRIGGER trg_orders_notes_updated_at BEFORE UPDATE ON orders_order_notes
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

ALTER TABLE orders_orders ENABLE ROW LEVEL SECURITY;
ALTER TABLE orders_order_line_items ENABLE ROW LEVEL SECURITY;
ALTER TABLE orders_order_status_history ENABLE ROW LEVEL SECURITY;
ALTER TABLE orders_order_notes ENABLE ROW LEVEL SECURITY;

CREATE POLICY orders_orders_read ON orders_orders FOR SELECT USING (
    deleted_at IS NULL AND business_id = current_business_id()
);
CREATE POLICY orders_line_items_read ON orders_order_line_items FOR SELECT USING (
    business_id = current_business_id()
);
CREATE POLICY orders_status_history_read ON orders_order_status_history FOR SELECT USING (
    business_id = current_business_id()
);
CREATE POLICY orders_notes_read ON orders_order_notes FOR SELECT USING (
    deleted_at IS NULL AND business_id = current_business_id()
);
