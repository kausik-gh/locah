-- Phase B P1-03 · Offering kinds (Capability Universe §6.1, §6.3): one
-- catalogue, many kinds; kind fields, choice groups (cuts, modifiers,
-- add-ons), packs for weighed goods, units, HSN/SAC and variant axes.

ALTER TABLE offerings_catalog_offerings DROP CONSTRAINT offerings_catalog_offerings_offering_type_check;
ALTER TABLE offerings_catalog_offerings ADD CONSTRAINT offerings_catalog_offerings_offering_type_check
    CHECK (offering_type IN (
        'product', 'weighed_product', 'menu_item', 'service', 'class_session', 'course', 'accommodation',
        'rental', 'membership_plan', 'package', 'property_project', 'property_unit', 'vehicle',
        'portfolio_item', 'digital_product', 'cause', 'listing'
    ));

ALTER TABLE offerings_catalog_offerings
    ADD COLUMN hsn_sac TEXT CHECK (hsn_sac IS NULL OR hsn_sac ~ '^[0-9]{4,8}$'),
    ADD COLUMN attributes JSONB NOT NULL DEFAULT '{}'::jsonb,
    ADD COLUMN option_groups JSONB NOT NULL DEFAULT '[]'::jsonb,
    ADD COLUMN sell_units JSONB NOT NULL DEFAULT '[]'::jsonb,
    ADD COLUMN variant_options JSONB NOT NULL DEFAULT '[]'::jsonb,
    -- The unit stock is counted in: pieces, or grams / millilitres for goods
    -- sold by weight (a 500 g pack takes 500 from stock).
    ADD COLUMN stock_unit TEXT NOT NULL DEFAULT 'piece' CHECK (stock_unit IN ('piece', 'g', 'ml'));

CREATE INDEX offerings_catalog_offerings_kind
    ON offerings_catalog_offerings (business_id, offering_type) WHERE deleted_at IS NULL;

ALTER TABLE offerings_catalog_variants
    ADD COLUMN attributes JSONB NOT NULL DEFAULT '{}'::jsonb;

-- Order lines remember what was chosen (pack, cut, add-ons, a gift amount)
-- and how much stock the line takes, in the offering's stock unit.
ALTER TABLE orders_order_line_items
    ADD COLUMN options JSONB NOT NULL DEFAULT '{}'::jsonb,
    ADD COLUMN stock_quantity INTEGER;
UPDATE orders_order_line_items SET stock_quantity = quantity WHERE stock_quantity IS NULL;
ALTER TABLE orders_order_line_items ALTER COLUMN stock_quantity SET NOT NULL,
    ADD CONSTRAINT orders_order_line_items_stock_quantity_check CHECK (stock_quantity >= 0);
