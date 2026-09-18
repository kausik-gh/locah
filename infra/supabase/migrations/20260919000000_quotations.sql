-- Quotations: a commercial proposal a business issues before any order exists.
--
-- Why this is not an order
-- -----------------------
-- An order records something that happened; a quote records something offered.
-- The offer has to survive unchanged even as the catalogue moves on, because
-- what the business is bound to is what the customer was actually sent. So
-- every line carries its own copy of the title, description, unit price and tax
-- rate, and nothing here joins back to the offering to render a total. The
-- offering id is kept for reporting and for conversion, never as the source of
-- a number.
--
-- Why a revision is a new row
-- --------------------------
-- Once a quote is issued it stops being editable. Changing the price of an
-- issued quote would rewrite history the customer already has a copy of, so a
-- change produces a new quote that supersedes the old one, and the old one
-- stays exactly as it was sent. `revision` and `supersedes_quote_id` make the
-- chain readable; `root_quote_id` makes the whole chain queryable in one hop.

CREATE TABLE quotes_quotes (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    business_id UUID NOT NULL REFERENCES businesses(id),
    location_id UUID REFERENCES business_locations(id),
    customer_contact_id UUID REFERENCES customer_relationships_contacts(id),

    quote_number TEXT NOT NULL,
    revision INTEGER NOT NULL DEFAULT 1 CHECK (revision >= 1),
    supersedes_quote_id UUID REFERENCES quotes_quotes(id),
    root_quote_id UUID,

    status TEXT NOT NULL DEFAULT 'draft' CHECK (status IN (
        'draft', 'issued', 'accepted', 'rejected', 'expired', 'cancelled', 'superseded'
    )),

    title TEXT,
    -- Free text the business writes once and the customer reads on the document.
    terms TEXT,
    notes TEXT,
    -- Never shown to the customer; the internal note beside the offer.
    internal_notes TEXT,

    currency TEXT NOT NULL DEFAULT 'INR',
    -- Every money column is NUMERIC(12,2): a quote is a commercial commitment,
    -- and float drift on a total someone signs is not acceptable.
    subtotal NUMERIC(12, 2) NOT NULL DEFAULT 0,
    discount_amount NUMERIC(12, 2) NOT NULL DEFAULT 0 CHECK (discount_amount >= 0),
    tax_amount NUMERIC(12, 2) NOT NULL DEFAULT 0,
    charges_amount NUMERIC(12, 2) NOT NULL DEFAULT 0 CHECK (charges_amount >= 0),
    total NUMERIC(12, 2) NOT NULL DEFAULT 0 CHECK (total >= 0),

    -- A quote-level discount the business grants on top of any per-line ones.
    -- Percent is resolved to an amount when totals are computed and both are
    -- stored, so the document can say "10% off" and still be arithmetically
    -- reproducible years later.
    discount_type TEXT CHECK (discount_type IN ('amount', 'percent')),
    discount_value NUMERIC(12, 2) CHECK (discount_value IS NULL OR discount_value >= 0),

    deposit_type TEXT CHECK (deposit_type IN ('amount', 'percent')),
    deposit_value NUMERIC(12, 2) CHECK (deposit_value IS NULL OR deposit_value >= 0),
    deposit_amount NUMERIC(12, 2) NOT NULL DEFAULT 0 CHECK (deposit_amount >= 0),

    valid_until TIMESTAMPTZ,

    -- Opaque share credential, the same shape bookings already use for guest
    -- management. A quote link goes to someone who has no LOCAH account, so it
    -- cannot depend on a session.
    access_token TEXT,
    access_token_expires_at TIMESTAMPTZ,

    issued_at TIMESTAMPTZ,
    accepted_at TIMESTAMPTZ,
    rejected_at TIMESTAMPTZ,
    cancelled_at TIMESTAMPTZ,
    decided_by_name TEXT,
    decision_reason TEXT,

    -- Where an accepted quote went. Deliberately loose: a quote can become an
    -- order today and a project or a booking later, and the quote should not
    -- need a migration each time a new downstream workflow appears.
    converted_to_type TEXT,
    converted_to_id UUID,
    converted_at TIMESTAMPTZ,

    idempotency_key TEXT,
    created_by UUID REFERENCES platform_identities(id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    deleted_at TIMESTAMPTZ,
    version INTEGER NOT NULL DEFAULT 1,

    CONSTRAINT quotes_decision_needs_status CHECK (
        (accepted_at IS NULL OR status IN ('accepted', 'superseded'))
        AND (rejected_at IS NULL OR status IN ('rejected', 'superseded'))
    )
);

-- One live number per business. Revisions share the number and differ by
-- revision, which is what lets a customer holding "Q-2026-0007" recognise the
-- revised copy as the same negotiation.
CREATE UNIQUE INDEX quotes_number_revision_key
    ON quotes_quotes (business_id, quote_number, revision)
    WHERE deleted_at IS NULL;

CREATE UNIQUE INDEX quotes_idempotency_key
    ON quotes_quotes (business_id, idempotency_key)
    WHERE idempotency_key IS NOT NULL AND deleted_at IS NULL;

CREATE UNIQUE INDEX quotes_access_token_key
    ON quotes_quotes (access_token)
    WHERE access_token IS NOT NULL;

CREATE INDEX quotes_business_status ON quotes_quotes (business_id, status)
    WHERE deleted_at IS NULL;
CREATE INDEX quotes_customer ON quotes_quotes (business_id, customer_contact_id)
    WHERE deleted_at IS NULL;
CREATE INDEX quotes_root ON quotes_quotes (root_quote_id);
-- Finds quotes that have run out of time without scanning the table.
CREATE INDEX quotes_expiry_sweep ON quotes_quotes (valid_until)
    WHERE status = 'issued' AND deleted_at IS NULL;


CREATE TABLE quotes_quote_items (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    business_id UUID NOT NULL REFERENCES businesses(id),
    quote_id UUID NOT NULL REFERENCES quotes_quotes(id) ON DELETE CASCADE,

    -- Where this line came from, for reporting and conversion. Never read back
    -- to price the line: see the snapshot columns below.
    offering_id UUID,

    -- The snapshot. These are what the customer was shown, frozen at the moment
    -- the line was added, and they stay correct after the catalogue changes.
    title TEXT NOT NULL,
    description TEXT,
    unit_label TEXT,

    quantity NUMERIC(12, 3) NOT NULL DEFAULT 1 CHECK (quantity > 0),
    unit_price NUMERIC(12, 2) NOT NULL DEFAULT 0 CHECK (unit_price >= 0),
    tax_rate NUMERIC(6, 3) NOT NULL DEFAULT 0 CHECK (tax_rate >= 0),

    discount_type TEXT CHECK (discount_type IN ('amount', 'percent')),
    discount_value NUMERIC(12, 2) CHECK (discount_value IS NULL OR discount_value >= 0),

    line_subtotal NUMERIC(12, 2) NOT NULL DEFAULT 0,
    line_discount NUMERIC(12, 2) NOT NULL DEFAULT 0 CHECK (line_discount >= 0),
    line_tax NUMERIC(12, 2) NOT NULL DEFAULT 0,
    line_total NUMERIC(12, 2) NOT NULL DEFAULT 0,

    sort_order INTEGER NOT NULL DEFAULT 0,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX quotes_items_quote ON quotes_quote_items (quote_id, sort_order);


-- Charges a business adds beside the lines: delivery, installation, a floor
-- premium on a flat. Separate from items because they are not things the
-- customer chose a quantity of, and separate from a single charges column
-- because the document has to itemise them.
CREATE TABLE quotes_quote_charges (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    business_id UUID NOT NULL REFERENCES businesses(id),
    quote_id UUID NOT NULL REFERENCES quotes_quotes(id) ON DELETE CASCADE,
    label TEXT NOT NULL,
    amount NUMERIC(12, 2) NOT NULL DEFAULT 0,
    taxable BOOLEAN NOT NULL DEFAULT false,
    tax_rate NUMERIC(6, 3) NOT NULL DEFAULT 0 CHECK (tax_rate >= 0),
    sort_order INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX quotes_charges_quote ON quotes_quote_charges (quote_id, sort_order);


ALTER TABLE quotes_quotes ENABLE ROW LEVEL SECURITY;
ALTER TABLE quotes_quotes FORCE ROW LEVEL SECURITY;
ALTER TABLE quotes_quote_items ENABLE ROW LEVEL SECURITY;
ALTER TABLE quotes_quote_items FORCE ROW LEVEL SECURITY;
ALTER TABLE quotes_quote_charges ENABLE ROW LEVEL SECURITY;
ALTER TABLE quotes_quote_charges FORCE ROW LEVEL SECURITY;

CREATE POLICY quotes_member_read ON quotes_quotes
    FOR SELECT TO public USING (deleted_at IS NULL AND business_id = current_business_id());
CREATE POLICY quotes_api_write ON quotes_quotes
    FOR ALL TO platform_api USING (business_id = current_business_id())
    WITH CHECK (business_id = current_business_id());

CREATE POLICY quotes_items_member_read ON quotes_quote_items
    FOR SELECT TO public USING (business_id = current_business_id());
CREATE POLICY quotes_items_api_write ON quotes_quote_items
    FOR ALL TO platform_api USING (business_id = current_business_id())
    WITH CHECK (business_id = current_business_id());

CREATE POLICY quotes_charges_member_read ON quotes_quote_charges
    FOR SELECT TO public USING (business_id = current_business_id());
CREATE POLICY quotes_charges_api_write ON quotes_quote_charges
    FOR ALL TO platform_api USING (business_id = current_business_id())
    WITH CHECK (business_id = current_business_id());

GRANT SELECT, INSERT, UPDATE, DELETE ON quotes_quotes TO platform_api;
GRANT SELECT, INSERT, UPDATE, DELETE ON quotes_quote_items TO platform_api;
GRANT SELECT, INSERT, UPDATE, DELETE ON quotes_quote_charges TO platform_api;


INSERT INTO module_definitions (id, name, module_class, description, dependencies, is_available)
VALUES ('quotes', 'Quotations', 'optional',
        'Commercial proposals with versioning, validity and acceptance',
        '{core-business-profile}', true)
ON CONFLICT (id) DO NOTHING;
