-- Phase B · P1-04 — GST invoicing
-- Source: LOCAH Business Capability Universe §14 (one billing engine), §14.4
-- (GST document rules), §14.6 (acceptance tests), §6.2 `invoicing`
-- (tax invoice, bill of supply, credit / debit notes, FY number series per
-- location, place-of-supply tax split), §7.2 (accountant), §25.1 (GST).
-- Business OS Guide: "GST/tax rules are deterministic configuration
-- supplied/verified by the business and its accountant — never guessed."
--
-- LOCAH computes, it does not advise: every rate, registration and treatment
-- below is data the owner or their CA enters. Nothing is seeded.

-- ---------------------------------------------------------------------------
-- How the business bills. One row per business; its existence is the
-- `tax_profile` setup step of the invoicing module.
-- ---------------------------------------------------------------------------
CREATE TABLE invoicing_tax_profiles (
    business_id UUID PRIMARY KEY REFERENCES businesses(id),
    -- Whether catalogue prices already include GST. Chosen by the owner.
    prices_include_tax BOOLEAN NOT NULL,
    -- Round bill totals to the rupee; the difference is its own line (§14.6).
    round_off BOOLEAN NOT NULL,
    -- When a website / WhatsApp order gets its bill.
    issue_on TEXT NOT NULL CHECK (issue_on IN ('order_accepted', 'order_completed', 'manual')),
    -- §14.4 "Anything touching tax treatment … shows 'Confirm with your CA'
    -- and a setting, never an assumption." NULL = not decided yet.
    advances_treatment TEXT CHECK (advances_treatment IN ('receipt_voucher', 'on_bill')),
    default_due_days INTEGER CHECK (default_due_days BETWEEN 0 AND 365),
    terms TEXT CHECK (char_length(terms) <= 2000),
    bank_details TEXT CHECK (char_length(bank_details) <= 1000),
    ca_confirmed_at TIMESTAMPTZ,
    updated_by UUID REFERENCES platform_identities(id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ---------------------------------------------------------------------------
-- GST registrations: one per state the business is registered in, or one
-- "not registered" row. §14.4 decides the document from the scheme.
-- ---------------------------------------------------------------------------
CREATE TABLE invoicing_registrations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    business_id UUID NOT NULL REFERENCES businesses(id),
    scheme TEXT NOT NULL CHECK (scheme IN ('regular', 'composition', 'unregistered')),
    gstin TEXT CHECK (gstin ~ '^[0-9]{2}[A-Z0-9]{10}[0-9A-Z]Z[0-9A-Z]$'),
    legal_name TEXT NOT NULL CHECK (char_length(legal_name) BETWEEN 1 AND 200),
    trade_name TEXT CHECK (char_length(trade_name) <= 200),
    state_code TEXT NOT NULL CHECK (state_code ~ '^[0-9]{2}$'),
    address TEXT CHECK (char_length(address) <= 500),
    -- Printed on every bill of supply. Wording is the owner's / CA's.
    composition_declaration TEXT CHECK (char_length(composition_declaration) <= 300),
    status TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'inactive')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CHECK (scheme = 'unregistered' OR gstin IS NOT NULL),
    CHECK (scheme <> 'unregistered' OR gstin IS NULL),
    CHECK (gstin IS NULL OR substr(gstin, 1, 2) = state_code),
    CHECK (scheme <> 'composition' OR composition_declaration IS NOT NULL)
);
CREATE UNIQUE INDEX invoicing_registrations_gstin
    ON invoicing_registrations (business_id, gstin) WHERE gstin IS NOT NULL;
CREATE INDEX invoicing_registrations_business ON invoicing_registrations (business_id);

-- ---------------------------------------------------------------------------
-- Registers: the billing counters of a location. The invoice series is
-- GSTIN × financial year × register (§14.4), e.g. CHN1/26-27/00123.
-- ---------------------------------------------------------------------------
CREATE TABLE invoicing_registers (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    business_id UUID NOT NULL REFERENCES businesses(id),
    location_id UUID NOT NULL REFERENCES business_locations(id),
    registration_id UUID NOT NULL REFERENCES invoicing_registrations(id),
    code TEXT NOT NULL CHECK (code ~ '^[A-Z0-9]{1,8}$'),
    name TEXT NOT NULL CHECK (char_length(name) BETWEEN 1 AND 80),
    pad INTEGER NOT NULL DEFAULT 5 CHECK (pad BETWEEN 3 AND 8),
    status TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'inactive')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT invoicing_registers_code UNIQUE (business_id, registration_id, code)
);
CREATE INDEX invoicing_registers_location ON invoicing_registers (business_id, location_id);

-- ---------------------------------------------------------------------------
-- Rates are data (§14.4): per offering or per HSN/SAC, with effective dates,
-- because the GST Council revises them. Never hard-coded, never seeded.
-- ---------------------------------------------------------------------------
CREATE TABLE invoicing_tax_rates (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    business_id UUID NOT NULL REFERENCES businesses(id),
    offering_id UUID REFERENCES offerings_catalog_offerings(id),
    hsn_sac TEXT CHECK (hsn_sac ~ '^[0-9]{2,8}$'),
    rate NUMERIC(5, 2) NOT NULL CHECK (rate >= 0 AND rate <= 100),
    effective_from DATE NOT NULL,
    effective_to DATE,
    note TEXT CHECK (char_length(note) <= 300),
    created_by UUID REFERENCES platform_identities(id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CHECK ((offering_id IS NULL) <> (hsn_sac IS NULL)),
    CHECK (effective_to IS NULL OR effective_to >= effective_from)
);
CREATE INDEX invoicing_tax_rates_hsn ON invoicing_tax_rates (business_id, hsn_sac, effective_from DESC)
    WHERE hsn_sac IS NOT NULL;
CREATE INDEX invoicing_tax_rates_offering ON invoicing_tax_rates (business_id, offering_id, effective_from DESC)
    WHERE offering_id IS NOT NULL;

-- ---------------------------------------------------------------------------
-- Every bill LOCAH produces: tax invoice, bill of supply, bill / receipt,
-- credit note, debit note. Numbered on issue from a gapless series; a
-- cancelled document keeps its number and stays, marked cancelled.
-- Seller, buyer and every amount are snapshots: a reprint in five years shows
-- exactly what was issued.
-- ---------------------------------------------------------------------------
CREATE TABLE invoicing_documents (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    business_id UUID NOT NULL REFERENCES businesses(id),
    location_id UUID NOT NULL REFERENCES business_locations(id),
    register_id UUID NOT NULL REFERENCES invoicing_registers(id),
    registration_id UUID NOT NULL REFERENCES invoicing_registrations(id),
    doc_kind TEXT NOT NULL CHECK (doc_kind IN (
        'tax_invoice', 'bill_of_supply', 'bill', 'credit_note', 'debit_note'
    )),
    status TEXT NOT NULL DEFAULT 'draft' CHECK (status IN ('draft', 'issued', 'cancelled')),
    series_key TEXT,
    fy TEXT CHECK (fy ~ '^[0-9]{2}-[0-9]{2}$'),
    seq BIGINT CHECK (seq >= 1),
    number TEXT,
    issue_date DATE,
    due_date DATE,
    source TEXT NOT NULL DEFAULT 'manual' CHECK (source IN ('manual', 'order', 'pos')),
    order_id UUID REFERENCES orders_orders(id),
    original_document_id UUID REFERENCES invoicing_documents(id),
    note_reason TEXT CHECK (note_reason IN ('return', 'price_reduction', 'price_increase', 'correction', 'other')),
    restock BOOLEAN NOT NULL DEFAULT false,
    customer_contact_id UUID REFERENCES customer_relationships_contacts(id),
    buyer JSONB NOT NULL DEFAULT '{}'::jsonb,   -- name, gstin, address, state_code, phone, email
    seller JSONB NOT NULL DEFAULT '{}'::jsonb,  -- snapshot of the registration at issue
    place_of_supply TEXT CHECK (place_of_supply ~ '^[0-9]{2}$'),
    intra_state BOOLEAN,
    reverse_charge BOOLEAN NOT NULL DEFAULT false,
    prices_include_tax BOOLEAN NOT NULL DEFAULT false,
    currency TEXT NOT NULL DEFAULT 'INR',
    taxable_total NUMERIC(14, 2) NOT NULL DEFAULT 0,
    cgst_total NUMERIC(14, 2) NOT NULL DEFAULT 0,
    sgst_total NUMERIC(14, 2) NOT NULL DEFAULT 0,
    igst_total NUMERIC(14, 2) NOT NULL DEFAULT 0,
    tax_total NUMERIC(14, 2) NOT NULL DEFAULT 0,
    round_off NUMERIC(8, 2) NOT NULL DEFAULT 0,
    grand_total NUMERIC(14, 2) NOT NULL DEFAULT 0,
    -- What the buyer owes: the grand total, less tax the recipient pays
    -- themselves under reverse charge.
    amount_due NUMERIC(14, 2) NOT NULL DEFAULT 0,
    amount_paid NUMERIC(14, 2) NOT NULL DEFAULT 0 CHECK (amount_paid >= 0),
    notes TEXT CHECK (char_length(notes) <= 2000),
    terms TEXT CHECK (char_length(terms) <= 2000),
    public_token_hash TEXT,
    idempotency_key TEXT,
    issued_at TIMESTAMPTZ,
    issued_by UUID REFERENCES platform_identities(id),
    cancelled_at TIMESTAMPTZ,
    cancelled_by UUID REFERENCES platform_identities(id),
    cancel_reason TEXT CHECK (char_length(cancel_reason) <= 500),
    created_by UUID REFERENCES platform_identities(id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    version INTEGER NOT NULL DEFAULT 1,
    CHECK (status = 'draft' OR (number IS NOT NULL AND seq IS NOT NULL AND issue_date IS NOT NULL)),
    CHECK (status <> 'cancelled' OR cancelled_at IS NOT NULL),
    CHECK ((doc_kind IN ('credit_note', 'debit_note')) = (original_document_id IS NOT NULL)),
    CHECK (doc_kind <> 'bill' OR (cgst_total = 0 AND sgst_total = 0 AND igst_total = 0)),
    CHECK (doc_kind <> 'bill_of_supply' OR (cgst_total = 0 AND sgst_total = 0 AND igst_total = 0)),
    CHECK (intra_state IS NOT TRUE OR igst_total = 0),
    CHECK (intra_state IS NOT FALSE OR (cgst_total = 0 AND sgst_total = 0))
);
-- Gapless: one number per series position; a number is never reused.
CREATE UNIQUE INDEX invoicing_documents_series_seq
    ON invoicing_documents (business_id, series_key, fy, seq) WHERE seq IS NOT NULL;
-- One live bill per order (a cancelled one may be replaced).
CREATE UNIQUE INDEX invoicing_documents_one_per_order
    ON invoicing_documents (business_id, order_id)
    WHERE order_id IS NOT NULL AND status <> 'cancelled'
      AND doc_kind IN ('tax_invoice', 'bill_of_supply', 'bill');
CREATE UNIQUE INDEX invoicing_documents_idempotency
    ON invoicing_documents (business_id, idempotency_key) WHERE idempotency_key IS NOT NULL;
CREATE UNIQUE INDEX invoicing_documents_public_token
    ON invoicing_documents (public_token_hash) WHERE public_token_hash IS NOT NULL;
CREATE INDEX invoicing_documents_list ON invoicing_documents (business_id, issue_date DESC, created_at DESC);
CREATE INDEX invoicing_documents_customer ON invoicing_documents (business_id, customer_contact_id);
CREATE INDEX invoicing_documents_original ON invoicing_documents (business_id, original_document_id)
    WHERE original_document_id IS NOT NULL;

CREATE TABLE invoicing_document_lines (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    business_id UUID NOT NULL REFERENCES businesses(id),
    document_id UUID NOT NULL REFERENCES invoicing_documents(id) ON DELETE CASCADE,
    offering_id UUID REFERENCES offerings_catalog_offerings(id),
    variant_id UUID REFERENCES offerings_catalog_variants(id),
    order_line_id UUID REFERENCES orders_order_line_items(id),
    original_line_id UUID REFERENCES invoicing_document_lines(id),
    title TEXT NOT NULL CHECK (char_length(title) BETWEEN 1 AND 300),
    hsn_sac TEXT CHECK (hsn_sac ~ '^[0-9]{2,8}$'),
    unit_label TEXT CHECK (char_length(unit_label) <= 20),
    quantity NUMERIC(12, 3) NOT NULL CHECK (quantity > 0),
    unit_price NUMERIC(12, 2) NOT NULL CHECK (unit_price >= 0),
    discount NUMERIC(12, 2) NOT NULL DEFAULT 0 CHECK (discount >= 0),
    taxable_value NUMERIC(14, 2) NOT NULL,
    tax_rate NUMERIC(5, 2) CHECK (tax_rate >= 0 AND tax_rate <= 100),
    cgst NUMERIC(12, 2) NOT NULL DEFAULT 0,
    sgst NUMERIC(12, 2) NOT NULL DEFAULT 0,
    igst NUMERIC(12, 2) NOT NULL DEFAULT 0,
    line_total NUMERIC(14, 2) NOT NULL,
    stock_quantity INTEGER NOT NULL DEFAULT 0 CHECK (stock_quantity >= 0),
    sort_order INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX invoicing_document_lines_document ON invoicing_document_lines (document_id, sort_order);
CREATE INDEX invoicing_document_lines_hsn ON invoicing_document_lines (business_id, hsn_sac);

-- Money received against a bill (cash, UPI, bank transfer…). Payments made
-- through the order's online checkout are read from the order.
CREATE TABLE invoicing_payments (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    business_id UUID NOT NULL REFERENCES businesses(id),
    document_id UUID NOT NULL REFERENCES invoicing_documents(id),
    amount NUMERIC(14, 2) NOT NULL CHECK (amount > 0),
    method TEXT NOT NULL CHECK (method IN ('cash', 'upi', 'card', 'bank_transfer', 'cheque', 'other')),
    reference TEXT CHECK (char_length(reference) <= 120),
    received_on DATE NOT NULL,
    recorded_by UUID REFERENCES platform_identities(id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX invoicing_payments_document ON invoicing_payments (business_id, document_id);

-- ---------------------------------------------------------------------------
-- Orders priced by the same engine once a tax profile exists: what the
-- engine decided (scheme, inclusive, place of supply) and the round-off line.
-- ---------------------------------------------------------------------------
ALTER TABLE orders_orders
    ADD COLUMN round_off NUMERIC(8, 2) NOT NULL DEFAULT 0,
    ADD COLUMN tax_basis JSONB NOT NULL DEFAULT '{}'::jsonb;

-- ---------------------------------------------------------------------------
-- RLS: business-scoped for the API role; anon gets nothing.
-- ---------------------------------------------------------------------------
DO $$
DECLARE t TEXT;
BEGIN
    FOREACH t IN ARRAY ARRAY['invoicing_tax_profiles', 'invoicing_registrations', 'invoicing_registers',
                             'invoicing_tax_rates', 'invoicing_documents', 'invoicing_document_lines',
                             'invoicing_payments']
    LOOP
        EXECUTE format('ALTER TABLE %I ENABLE ROW LEVEL SECURITY', t);
        EXECUTE format('ALTER TABLE %I FORCE ROW LEVEL SECURITY', t);
        EXECUTE format('CREATE POLICY %I ON %I FOR SELECT TO public USING (business_id = current_business_id())',
                       t || '_member_read', t);
        EXECUTE format('CREATE POLICY %I ON %I FOR ALL TO platform_api USING (business_id = current_business_id()) '
                       'WITH CHECK (business_id = current_business_id())', t || '_api_write', t);
        EXECUTE format('GRANT SELECT, INSERT, UPDATE, DELETE ON %I TO platform_api', t);
        EXECUTE format('REVOKE ALL PRIVILEGES ON TABLE %I FROM anon', t);
    END LOOP;
END
$$;

-- Bills and registers belong to a location: a location-limited member sees
-- only their locations' bills (RESTRICTIVE, like orders and quotes).
DO $$
DECLARE t TEXT;
BEGIN
    FOREACH t IN ARRAY ARRAY['invoicing_documents', 'invoicing_registers'] LOOP
        EXECUTE format(
            'CREATE POLICY %I ON %I AS RESTRICTIVE FOR ALL TO platform_api '
            'USING (location_scope_allows(location_id)) WITH CHECK (location_scope_allows(location_id))',
            t || '_location_scope', t);
    END LOOP;
END $$;

-- A bill's share link is its credential (the customer's "Your bill from
-- <business>" copy): only its hash is stored, bound per request as
-- app.current_bill_token, exactly like quote and join tokens.
CREATE POLICY invoicing_documents_bill_token_read ON invoicing_documents FOR SELECT TO platform_api
    USING (public_token_hash IS NOT NULL AND status <> 'draft'
           AND public_token_hash = (SELECT NULLIF(current_setting('app.current_bill_token', true), '')));
CREATE POLICY invoicing_document_lines_bill_token_read ON invoicing_document_lines FOR SELECT TO platform_api
    USING (EXISTS (SELECT 1 FROM invoicing_documents d
                   WHERE d.id = document_id AND d.public_token_hash IS NOT NULL AND d.status <> 'draft'
                     AND d.public_token_hash = (SELECT NULLIF(current_setting('app.current_bill_token', true), ''))));
