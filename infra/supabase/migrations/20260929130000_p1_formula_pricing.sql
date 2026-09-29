-- P1-10D2b: formula-priced offerings (MD §21.2 jewellery: "price = today's metal
-- rate × weight + making charge + GST from a daily rate board"; Business OS Guide
-- p.22). Reusable: any item can be priced from a rate the owner enters (gold,
-- silver, a metal or a commodity by weight) × its quantity, plus a making charge
-- and fixed extras. GST stays data (the item's HSN / rate, IV-06).
--
-- The rate board keeps every value an owner enters (history is never rewritten);
-- entering today's rate re-prices the items that use it, and each order and bill
-- line keeps the inputs it was sold at, so a later rate never changes a sale.

CREATE TABLE pricing_rates (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    business_id UUID NOT NULL REFERENCES businesses(id),
    key TEXT NOT NULL CHECK (key ~ '^[a-z0-9_]{1,40}$'),
    label TEXT NOT NULL CHECK (length(label) BETWEEN 1 AND 60),
    unit TEXT NOT NULL DEFAULT 'g' CHECK (unit IN ('g', 'kg', 'ml', 'l', 'piece', 'carat')),
    archived_at TIMESTAMPTZ,
    created_by UUID REFERENCES platform_identities(id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    version INTEGER NOT NULL DEFAULT 1
);
CREATE UNIQUE INDEX pricing_rates_key ON pricing_rates (business_id, key);

CREATE TABLE pricing_rate_values (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    business_id UUID NOT NULL REFERENCES businesses(id),
    rate_id UUID NOT NULL REFERENCES pricing_rates(id),
    value NUMERIC(14, 4) NOT NULL CHECK (value > 0),
    effective_from TIMESTAMPTZ NOT NULL DEFAULT now(),
    note TEXT CHECK (note IS NULL OR length(note) <= 200),
    entered_by UUID REFERENCES platform_identities(id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX pricing_rate_values_latest ON pricing_rate_values (rate_id, effective_from DESC);

ALTER TABLE offerings_catalog_offerings ADD COLUMN IF NOT EXISTS price_formula JSONB;
-- What a bill line was priced from (the rate, quantity and making charge at sale).
ALTER TABLE invoicing_document_lines ADD COLUMN IF NOT EXISTS price_basis JSONB;

CREATE TRIGGER trg_pricing_rates_updated_at BEFORE UPDATE ON pricing_rates
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

DO $$
DECLARE t TEXT;
BEGIN
    FOREACH t IN ARRAY ARRAY['pricing_rates', 'pricing_rate_values'] LOOP
        EXECUTE format('ALTER TABLE %I ENABLE ROW LEVEL SECURITY', t);
        EXECUTE format('ALTER TABLE %I FORCE ROW LEVEL SECURITY', t);
        EXECUTE format('CREATE POLICY %I ON %I FOR SELECT TO public USING (business_id = current_business_id())',
                       t || '_member_read', t);
        EXECUTE format('CREATE POLICY %I ON %I FOR ALL TO platform_api USING (business_id = current_business_id()) '
                       'WITH CHECK (business_id = current_business_id())', t || '_api_write', t);
        EXECUTE format('REVOKE ALL PRIVILEGES ON TABLE %I FROM anon', t);
    END LOOP;
    GRANT SELECT, INSERT, UPDATE ON pricing_rates TO platform_api;
    REVOKE DELETE ON pricing_rates FROM platform_api;
    -- Rate history is append-only: a correction is a new value.
    GRANT SELECT, INSERT ON pricing_rate_values TO platform_api;
    REVOKE UPDATE, DELETE ON pricing_rate_values FROM platform_api;
END
$$;
