-- Finish the quotes domain (Capability Universe §6.2, §19.4, §21.10).
--
-- The commercial record stays quotes_quotes. This migration adds what that
-- record was missing: where an RFQ came from, whether a discount is waiting
-- on the owner, when the customer opened this version, a payment plan the
-- quote itself owns, and line facts for MOQ, lead time, quantity breaks,
-- a bill of quantities, and a size matrix.
--
-- An accepted quote's prices are locked in the database, not only in the
-- service. A later update of a total, a rate, a discount, a line, a charge
-- or a plan row is refused. Opening the quote, recording a conversion
-- target, and clearing a share token are not price changes.

ALTER TABLE quotes_quotes
    ADD COLUMN source TEXT NOT NULL DEFAULT 'manual'
        CHECK (source IN ('manual', 'website', 'whatsapp')),
    ADD COLUMN source_ref TEXT,
    ADD COLUMN approval_status TEXT NOT NULL DEFAULT 'not_required'
        CHECK (approval_status IN ('not_required', 'pending', 'approved', 'rejected')),
    ADD COLUMN opened_at TIMESTAMPTZ,
    ADD COLUMN last_opened_at TIMESTAMPTZ,
    ADD COLUMN open_count INTEGER NOT NULL DEFAULT 0 CHECK (open_count >= 0),
    ADD COLUMN price_locked_at TIMESTAMPTZ,
    ADD COLUMN conversion_target TEXT
        CHECK (conversion_target IS NULL OR conversion_target IN ('order', 'project', 'invoice')),
    ADD COLUMN otp_hash TEXT,
    ADD COLUMN otp_expires_at TIMESTAMPTZ,
    ADD COLUMN otp_attempts INTEGER NOT NULL DEFAULT 0 CHECK (otp_attempts >= 0);

ALTER TABLE quotes_quote_items
    ADD COLUMN line_kind TEXT NOT NULL DEFAULT 'item'
        CHECK (line_kind IN ('item', 'boq', 'size_matrix')),
    ADD COLUMN moq NUMERIC(12, 3) CHECK (moq IS NULL OR moq > 0),
    ADD COLUMN lead_time_days INTEGER CHECK (lead_time_days IS NULL OR lead_time_days >= 0),
    ADD COLUMN quantity_breaks JSONB NOT NULL DEFAULT '[]'::jsonb,
    ADD COLUMN boq_section TEXT,
    ADD COLUMN size_matrix JSONB NOT NULL DEFAULT '[]'::jsonb;


-- One limit per business. Five percent until the owner sets another.
CREATE TABLE quotes_settings (
    business_id UUID PRIMARY KEY REFERENCES businesses(id),
    executive_discount_limit_percent NUMERIC(5, 2) NOT NULL DEFAULT 5
        CHECK (executive_discount_limit_percent >= 0 AND executive_discount_limit_percent <= 100),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- The schedule offered with the quote. Amounts stay as the business wrote
-- them (a percent or a fixed amount). Payments turns them into a link later.
CREATE TABLE quotes_payment_plan_lines (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    business_id UUID NOT NULL REFERENCES businesses(id),
    quote_id UUID NOT NULL REFERENCES quotes_quotes(id) ON DELETE CASCADE,
    label TEXT NOT NULL,
    amount_type TEXT NOT NULL CHECK (amount_type IN ('amount', 'percent')),
    amount_value NUMERIC(12, 2) NOT NULL CHECK (amount_value >= 0),
    due_rule TEXT NOT NULL CHECK (due_rule IN ('on_acceptance', 'net_days', 'milestone')),
    due_days INTEGER CHECK (due_days IS NULL OR due_days >= 0),
    sort_order INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX quotes_plan_quote ON quotes_payment_plan_lines (quote_id, sort_order);

-- One row each time the customer opens this version.
CREATE TABLE quotes_views (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    business_id UUID NOT NULL REFERENCES businesses(id),
    quote_id UUID NOT NULL REFERENCES quotes_quotes(id) ON DELETE CASCADE,
    opened_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX quotes_views_quote ON quotes_views (quote_id, opened_at);

-- Replaying the same website lead or WhatsApp message must not open a second draft.
CREATE TABLE quotes_rfq_intakes (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    business_id UUID NOT NULL REFERENCES businesses(id),
    channel TEXT NOT NULL CHECK (channel IN ('website', 'whatsapp')),
    idempotency_key TEXT NOT NULL,
    quote_id UUID NOT NULL REFERENCES quotes_quotes(id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (business_id, channel, idempotency_key)
);


ALTER TABLE quotes_settings ENABLE ROW LEVEL SECURITY;
ALTER TABLE quotes_settings FORCE ROW LEVEL SECURITY;
ALTER TABLE quotes_payment_plan_lines ENABLE ROW LEVEL SECURITY;
ALTER TABLE quotes_payment_plan_lines FORCE ROW LEVEL SECURITY;
ALTER TABLE quotes_views ENABLE ROW LEVEL SECURITY;
ALTER TABLE quotes_views FORCE ROW LEVEL SECURITY;
ALTER TABLE quotes_rfq_intakes ENABLE ROW LEVEL SECURITY;
ALTER TABLE quotes_rfq_intakes FORCE ROW LEVEL SECURITY;

CREATE POLICY quotes_settings_member_read ON quotes_settings
    FOR SELECT TO public USING (business_id = current_business_id());
CREATE POLICY quotes_settings_api ON quotes_settings
    FOR ALL TO platform_api USING (business_id = current_business_id())
    WITH CHECK (business_id = current_business_id());

CREATE POLICY quotes_plan_member_read ON quotes_payment_plan_lines
    FOR SELECT TO public USING (business_id = current_business_id());
CREATE POLICY quotes_plan_api ON quotes_payment_plan_lines
    FOR ALL TO platform_api USING (business_id = current_business_id())
    WITH CHECK (business_id = current_business_id());

CREATE POLICY quotes_views_member_read ON quotes_views
    FOR SELECT TO public USING (business_id = current_business_id());
CREATE POLICY quotes_views_api ON quotes_views
    FOR ALL TO platform_api USING (business_id = current_business_id())
    WITH CHECK (business_id = current_business_id());

CREATE POLICY quotes_rfq_member_read ON quotes_rfq_intakes
    FOR SELECT TO public USING (business_id = current_business_id());
CREATE POLICY quotes_rfq_api ON quotes_rfq_intakes
    FOR ALL TO platform_api USING (business_id = current_business_id())
    WITH CHECK (business_id = current_business_id());

GRANT SELECT, INSERT, UPDATE, DELETE ON quotes_settings TO platform_api;
GRANT SELECT, INSERT, UPDATE, DELETE ON quotes_payment_plan_lines TO platform_api;
GRANT SELECT, INSERT, UPDATE, DELETE ON quotes_views TO platform_api;
GRANT SELECT, INSERT, UPDATE, DELETE ON quotes_rfq_intakes TO platform_api;


-- Accepted prices cannot move. Status, view counts, conversion bookkeeping
-- and the share token can.
CREATE OR REPLACE FUNCTION quotes_guard_accepted_prices() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
    IF TG_OP = 'UPDATE' AND OLD.status = 'accepted' THEN
        IF NEW.subtotal IS DISTINCT FROM OLD.subtotal
            OR NEW.discount_amount IS DISTINCT FROM OLD.discount_amount
            OR NEW.tax_amount IS DISTINCT FROM OLD.tax_amount
            OR NEW.charges_amount IS DISTINCT FROM OLD.charges_amount
            OR NEW.total IS DISTINCT FROM OLD.total
            OR NEW.discount_type IS DISTINCT FROM OLD.discount_type
            OR NEW.discount_value IS DISTINCT FROM OLD.discount_value
            OR NEW.deposit_type IS DISTINCT FROM OLD.deposit_type
            OR NEW.deposit_value IS DISTINCT FROM OLD.deposit_value
            OR NEW.deposit_amount IS DISTINCT FROM OLD.deposit_amount
            OR NEW.currency IS DISTINCT FROM OLD.currency
        THEN
            RAISE EXCEPTION 'accepted quote prices are locked'
                USING ERRCODE = 'check_violation';
        END IF;
    END IF;
    RETURN NEW;
END;
$$;

CREATE TRIGGER quotes_accepted_price_lock
    BEFORE UPDATE ON quotes_quotes
    FOR EACH ROW EXECUTE FUNCTION quotes_guard_accepted_prices();


CREATE OR REPLACE FUNCTION quotes_guard_accepted_children() RETURNS trigger
LANGUAGE plpgsql AS $$
DECLARE
    parent_status TEXT;
    parent_id UUID;
BEGIN
    parent_id := COALESCE(NEW.quote_id, OLD.quote_id);
    SELECT status INTO parent_status FROM quotes_quotes WHERE id = parent_id;
    IF parent_status = 'accepted' THEN
        RAISE EXCEPTION 'accepted quote prices are locked'
            USING ERRCODE = 'check_violation';
    END IF;
    IF TG_OP = 'DELETE' THEN
        RETURN OLD;
    END IF;
    RETURN NEW;
END;
$$;

CREATE TRIGGER quotes_items_accepted_lock
    BEFORE INSERT OR UPDATE OR DELETE ON quotes_quote_items
    FOR EACH ROW EXECUTE FUNCTION quotes_guard_accepted_children();

CREATE TRIGGER quotes_charges_accepted_lock
    BEFORE INSERT OR UPDATE OR DELETE ON quotes_quote_charges
    FOR EACH ROW EXECUTE FUNCTION quotes_guard_accepted_children();

CREATE TRIGGER quotes_plan_accepted_lock
    BEFORE INSERT OR UPDATE OR DELETE ON quotes_payment_plan_lines
    FOR EACH ROW EXECUTE FUNCTION quotes_guard_accepted_children();
