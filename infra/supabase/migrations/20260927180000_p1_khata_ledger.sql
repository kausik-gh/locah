-- Phase B · P1-06 — Khata / credit book
-- Source: LOCAH Business Capability Universe §6.2 `ledger` ("running balance
-- per customer and supplier, credit limits, ageing, reminders, settlements";
-- data ledger_account, ledger_entry), §14.5 ("a credit sale posts to the
-- customer's ledger. They get a WhatsApp statement with a UPI link; the owner
-- sees ageing and sets credit limits. At a limit, POS blocks credit unless a
-- manager overrides."), §23 #3 (udhaar kept in notebooks), §26.3 P1-06
-- ("balance equals sum of entries under concurrent writes").
--
-- An account's balance is kept on the account and moved only together with a
-- new entry, under the account's row lock: balance = sum(entries) always.
-- Entries are never edited or deleted; a mistake is corrected by a new entry.

CREATE TABLE ledger_accounts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    business_id UUID NOT NULL REFERENCES businesses(id),
    party_type TEXT NOT NULL CHECK (party_type IN ('customer', 'supplier')),
    customer_contact_id UUID REFERENCES customer_relationships_contacts(id),
    display_name TEXT NOT NULL CHECK (char_length(display_name) BETWEEN 1 AND 160),
    phone TEXT CHECK (char_length(phone) <= 20),
    gstin TEXT CHECK (gstin ~ '^[0-9]{2}[A-Z0-9]{10}[0-9A-Z]Z[0-9A-Z]$'),
    -- Customer: what they owe us. Supplier: what we owe them. Never computed
    -- from anything but the account's own entries.
    balance NUMERIC(14, 2) NOT NULL DEFAULT 0,
    -- The most this customer may owe (NULL = no limit set by the owner).
    credit_limit NUMERIC(14, 2) CHECK (credit_limit >= 0),
    credit_days INTEGER CHECK (credit_days BETWEEN 0 AND 365),
    status TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'closed')),
    public_token_hash TEXT,
    notes TEXT CHECK (char_length(notes) <= 500),
    last_entry_at TIMESTAMPTZ,
    created_by UUID REFERENCES platform_identities(id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    version INTEGER NOT NULL DEFAULT 1,
    CHECK (party_type = 'customer' OR customer_contact_id IS NULL)
);
CREATE UNIQUE INDEX ledger_accounts_one_per_customer
    ON ledger_accounts (business_id, customer_contact_id) WHERE customer_contact_id IS NOT NULL;
CREATE INDEX ledger_accounts_list ON ledger_accounts (business_id, party_type, balance DESC);
CREATE INDEX ledger_accounts_phone ON ledger_accounts (business_id, phone) WHERE phone IS NOT NULL;
CREATE UNIQUE INDEX ledger_accounts_public_token
    ON ledger_accounts (public_token_hash) WHERE public_token_hash IS NOT NULL;

CREATE TABLE ledger_entries (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    business_id UUID NOT NULL REFERENCES businesses(id),
    account_id UUID NOT NULL REFERENCES ledger_accounts(id),
    seq BIGINT NOT NULL CHECK (seq >= 1),
    kind TEXT NOT NULL CHECK (kind IN (
        'opening_balance', 'credit_sale', 'payment_received', 'return_credit',
        'purchase', 'payment_made', 'adjustment'
    )),
    -- Signed: positive moves the balance up (they owe us more / we owe them
    -- more), negative moves it down.
    amount NUMERIC(14, 2) NOT NULL CHECK (amount <> 0),
    balance_after NUMERIC(14, 2) NOT NULL,
    entry_date DATE NOT NULL,
    due_date DATE,
    method TEXT CHECK (method IN ('cash', 'upi', 'card', 'bank_transfer', 'cheque', 'other')),
    reference TEXT CHECK (char_length(reference) <= 120),
    note TEXT CHECK (char_length(note) <= 300),
    document_id UUID REFERENCES invoicing_documents(id),
    shift_id UUID REFERENCES pos_shifts(id),
    location_id UUID REFERENCES business_locations(id),
    over_limit_approved_by UUID REFERENCES platform_identities(id),
    idempotency_key TEXT,
    created_by UUID REFERENCES platform_identities(id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT ledger_entries_seq UNIQUE (account_id, seq)
);
CREATE INDEX ledger_entries_account ON ledger_entries (account_id, seq);
CREATE INDEX ledger_entries_business ON ledger_entries (business_id, entry_date DESC);
CREATE INDEX ledger_entries_document ON ledger_entries (business_id, document_id) WHERE document_id IS NOT NULL;
CREATE UNIQUE INDEX ledger_entries_idempotency
    ON ledger_entries (business_id, idempotency_key) WHERE idempotency_key IS NOT NULL;

-- Entries are the history: never rewritten.
CREATE OR REPLACE FUNCTION ledger_entries_append_only() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    RAISE EXCEPTION 'ledger entries are append-only; record a correcting entry instead';
END;
$$;
CREATE TRIGGER ledger_entries_no_update BEFORE UPDATE OR DELETE ON ledger_entries
    FOR EACH ROW EXECUTE FUNCTION ledger_entries_append_only();

-- A bill sold on the customer's account (khata) says so.
ALTER TABLE invoicing_documents ADD COLUMN on_account BOOLEAN NOT NULL DEFAULT false;

-- Khata money paid at a counter carries the shift, so the drawer counts it
-- from the entry itself (no second record of the same money).
CREATE INDEX ledger_entries_shift ON ledger_entries (shift_id) WHERE shift_id IS NOT NULL;

DO $$
DECLARE t TEXT;
BEGIN
    FOREACH t IN ARRAY ARRAY['ledger_accounts', 'ledger_entries'] LOOP
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

-- The customer's statement link is its credential (hash only), like bills.
CREATE POLICY ledger_accounts_statement_token_read ON ledger_accounts FOR SELECT TO platform_api
    USING (public_token_hash IS NOT NULL
           AND public_token_hash = (SELECT NULLIF(current_setting('app.current_statement_token', true), '')));
CREATE POLICY ledger_entries_statement_token_read ON ledger_entries FOR SELECT TO platform_api
    USING (EXISTS (SELECT 1 FROM ledger_accounts a
                   WHERE a.id = account_id AND a.public_token_hash IS NOT NULL
                     AND a.public_token_hash = (SELECT NULLIF(current_setting('app.current_statement_token', true), ''))));
