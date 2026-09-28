-- Phase B · P1-05 — Counter billing (POS)
-- Source: LOCAH Business Capability Universe §14.1 (counter flow: open shift →
-- scan or search → cart → tender → receipt + WhatsApp bill → stock moved →
-- close shift counted vs expected; hold and recall; returns → credit note +
-- stock back; UPI QR; card via external terminal; discount cap per role;
-- voids/returns past the window need a manager PIN), §14.2 (offline: cached
-- catalogue with a version stamp, bills queue on the device, each register
-- reserves a block of invoice numbers — default 50 — while online, UPI to
-- verify), §14.3 (scanner as keyboard or camera, in-store codes and labels,
-- weighed-label barcodes decoded with a per-business format), §14.5 (cash
-- closing), §14.6 (two-register offline sync: no duplicate or missing numbers).
--
-- A POS register is the invoicing register (§14.4 series GSTIN × FY ×
-- register): one concept, not two. A counter sale is a bill from the one
-- billing engine with source 'pos'.

-- ---------------------------------------------------------------------------
-- The owner's counter rules. Every value is the owner's choice.
-- ---------------------------------------------------------------------------
CREATE TABLE pos_settings (
    business_id UUID PRIMARY KEY REFERENCES businesses(id),
    upi_vpa TEXT CHECK (upi_vpa ~ '^[A-Za-z0-9._-]{2,255}@[A-Za-z][A-Za-z0-9.-]{1,64}$'),
    upi_payee_name TEXT CHECK (char_length(upi_payee_name) <= 100),
    return_window_days INTEGER NOT NULL DEFAULT 7 CHECK (return_window_days BETWEEN 0 AND 365),
    -- Largest discount each role may give without a manager PIN, as a percent
    -- of the bill, e.g. {"cashier": 5, "manager": 20}. Missing role = 0.
    discount_caps JSONB NOT NULL DEFAULT '{}'::jsonb,
    block_size INTEGER NOT NULL DEFAULT 50 CHECK (block_size BETWEEN 10 AND 500),
    -- Weighed-label barcode format set during pilot (§14.3, VB-16), e.g.
    -- {"prefix": "2", "item_digits": 5, "value": "weight", "value_digits": 5, "value_decimals": 3}
    weighed_label JSONB,
    receipt_footer TEXT CHECK (char_length(receipt_footer) <= 300),
    updated_by UUID REFERENCES platform_identities(id),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- A manager's approval PIN (only its hash). Used on a cashier's device to
-- approve a discount above the cap, a void or a return past the window.
CREATE TABLE pos_approval_pins (
    business_id UUID NOT NULL REFERENCES businesses(id),
    identity_id UUID NOT NULL REFERENCES platform_identities(id),
    pin_hash TEXT NOT NULL,
    failed_attempts INTEGER NOT NULL DEFAULT 0,
    locked_until TIMESTAMPTZ,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (business_id, identity_id)
);

-- ---------------------------------------------------------------------------
-- Cash-drawer shifts (§14.1, §14.5). One open shift per register.
-- ---------------------------------------------------------------------------
CREATE TABLE pos_shifts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    business_id UUID NOT NULL REFERENCES businesses(id),
    location_id UUID NOT NULL REFERENCES business_locations(id),
    register_id UUID NOT NULL REFERENCES invoicing_registers(id),
    device_id TEXT NOT NULL CHECK (char_length(device_id) BETWEEN 3 AND 80),
    status TEXT NOT NULL DEFAULT 'open' CHECK (status IN ('open', 'closed')),
    opened_by UUID NOT NULL REFERENCES platform_identities(id),
    opened_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    opening_cash NUMERIC(14, 2) NOT NULL CHECK (opening_cash >= 0),
    closed_by UUID REFERENCES platform_identities(id),
    closed_at TIMESTAMPTZ,
    expected_cash NUMERIC(14, 2),
    counted_cash NUMERIC(14, 2) CHECK (counted_cash >= 0),
    variance NUMERIC(14, 2),
    close_note TEXT CHECK (char_length(close_note) <= 500),
    CHECK (status = 'open' OR (closed_at IS NOT NULL AND counted_cash IS NOT NULL))
);
CREATE UNIQUE INDEX pos_shifts_one_open ON pos_shifts (business_id, register_id) WHERE status = 'open';
CREATE INDEX pos_shifts_list ON pos_shifts (business_id, opened_at DESC);

-- Cash in and out of the drawer that is not a sale: petty expenses, cash
-- refunds for returns, cash added (float) or taken to the bank.
CREATE TABLE pos_cash_movements (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    business_id UUID NOT NULL REFERENCES businesses(id),
    shift_id UUID NOT NULL REFERENCES pos_shifts(id),
    location_id UUID NOT NULL REFERENCES business_locations(id),
    kind TEXT NOT NULL CHECK (kind IN ('petty_expense', 'refund', 'cash_in', 'cash_out')),
    amount NUMERIC(14, 2) NOT NULL CHECK (amount > 0),
    reason TEXT NOT NULL CHECK (char_length(reason) BETWEEN 1 AND 300),
    document_id UUID REFERENCES invoicing_documents(id),
    client_mutation_id UUID,
    created_by UUID NOT NULL REFERENCES platform_identities(id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX pos_cash_movements_shift ON pos_cash_movements (business_id, shift_id);

-- ---------------------------------------------------------------------------
-- Bills and payments remember the counter they came from.
-- ---------------------------------------------------------------------------
ALTER TABLE invoicing_documents
    ADD COLUMN shift_id UUID REFERENCES pos_shifts(id),
    ADD COLUMN device_id TEXT CHECK (char_length(device_id) <= 80),
    ADD COLUMN sold_at TIMESTAMPTZ,
    ADD COLUMN pos_meta JSONB NOT NULL DEFAULT '{}'::jsonb;
CREATE INDEX invoicing_documents_shift ON invoicing_documents (business_id, shift_id) WHERE shift_id IS NOT NULL;

ALTER TABLE invoicing_payments
    ADD COLUMN shift_id UUID REFERENCES pos_shifts(id),
    -- UPI taken without confirmation (offline, or no provider): "UPI to
    -- verify", reconciled later (§14.2). Cash and card are verified at once.
    ADD COLUMN verification TEXT NOT NULL DEFAULT 'verified'
        CHECK (verification IN ('verified', 'to_verify', 'not_received')),
    ADD COLUMN verified_by UUID REFERENCES platform_identities(id),
    ADD COLUMN verified_at TIMESTAMPTZ;
CREATE INDEX invoicing_payments_to_verify ON invoicing_payments (business_id)
    WHERE verification = 'to_verify';
CREATE INDEX invoicing_payments_shift ON invoicing_payments (business_id, shift_id) WHERE shift_id IS NOT NULL;

-- ---------------------------------------------------------------------------
-- RLS: business-scoped for the API role; anon gets nothing. Shifts and cash
-- belong to a location: a location-limited cashier sees only theirs.
-- ---------------------------------------------------------------------------
DO $$
DECLARE t TEXT;
BEGIN
    FOREACH t IN ARRAY ARRAY['pos_settings', 'pos_approval_pins', 'pos_shifts', 'pos_cash_movements']
    LOOP
        EXECUTE format('ALTER TABLE %I ENABLE ROW LEVEL SECURITY', t);
        EXECUTE format('ALTER TABLE %I FORCE ROW LEVEL SECURITY', t);
        IF t <> 'pos_approval_pins' THEN  -- PIN hashes are read only by the API
            EXECUTE format('CREATE POLICY %I ON %I FOR SELECT TO public USING (business_id = current_business_id())',
                           t || '_member_read', t);
        END IF;
        EXECUTE format('CREATE POLICY %I ON %I FOR ALL TO platform_api USING (business_id = current_business_id()) '
                       'WITH CHECK (business_id = current_business_id())', t || '_api_write', t);
        EXECUTE format('GRANT SELECT, INSERT, UPDATE, DELETE ON %I TO platform_api', t);
        EXECUTE format('REVOKE ALL PRIVILEGES ON TABLE %I FROM anon', t);
    END LOOP;
    FOREACH t IN ARRAY ARRAY['pos_shifts', 'pos_cash_movements'] LOOP
        EXECUTE format(
            'CREATE POLICY %I ON %I AS RESTRICTIVE FOR ALL TO platform_api '
            'USING (location_scope_allows(location_id)) WITH CHECK (location_scope_allows(location_id))',
            t || '_location_scope', t);
    END LOOP;
END
$$;
