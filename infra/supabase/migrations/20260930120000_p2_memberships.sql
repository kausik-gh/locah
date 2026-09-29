-- P2-02: one recurring-relationship engine (Founder refinement — Memberships &
-- Subscriptions; Capability Universe §10). Gym memberships, session packs,
-- daily deliveries, fee plans, AMC service contracts and club dues share this
-- foundation; the plan kind decides the experience.
--
-- What is stored, and why:
--   * periods — every paid (or to-be-paid) stretch of cover is its own row and
--     is never rewritten on renewal (Jan, Feb, Mar stay three rows). A freeze
--     moves `ends_at` and leaves `base_ends_at` and a freeze row as history.
--   * payment applications — which payment paid which period or instalment,
--     unique per payment, so a replayed payment can never extend twice.
--   * session uses — one row per consumption, unique idempotency key, so a
--     replayed booking or check-in consumes once.
--   * instalments (fee plans), delivery overrides and generated deliveries
--     (subscriptions), service visits (AMC) — each its own occurrence row.
-- Status (PENDING_PAYMENT = 'pending', ACTIVE, PAUSED, GRACE, EXPIRED,
-- CANCELLED) is recalculated from these rows; "expiring soon" is derived.

-- ---------------------------------------------------------------- plans
ALTER TABLE memberships_plans
    ADD COLUMN plan_kind TEXT NOT NULL DEFAULT 'access'
        CHECK (plan_kind IN ('access', 'session_pack', 'recurring_delivery', 'service_contract',
                             'fee_plan', 'member_dues')),
    ADD COLUMN grace_days INTEGER NOT NULL DEFAULT 0 CHECK (grace_days BETWEEN 0 AND 90),
    ADD COLUMN grace_allows_entry BOOLEAN NOT NULL DEFAULT false,
    ADD COLUMN freeze_allowed BOOLEAN NOT NULL DEFAULT false,
    ADD COLUMN max_freeze_days INTEGER CHECK (max_freeze_days IS NULL OR max_freeze_days BETWEEN 1 AND 365),
    ADD COLUMN sessions_included INTEGER CHECK (sessions_included IS NULL OR sessions_included BETWEEN 1 AND 1000),
    -- When a session-pack session counts as used: when booked, when the
    -- booking is completed, or at a check-in.
    ADD COLUMN consume_on TEXT NOT NULL DEFAULT 'completed'
        CHECK (consume_on IN ('booked', 'completed', 'checkin')),
    ADD COLUMN no_show_consumes BOOLEAN NOT NULL DEFAULT true,
    -- Subscriptions: the default schedule {offering_id, quantity, days[0..6 = Mon..Sun],
    -- slot, window, cutoff "HH:MM"}; prepaid by period, or postpaid on the khata.
    ADD COLUMN delivery JSONB,
    ADD COLUMN billing_timing TEXT NOT NULL DEFAULT 'prepaid' CHECK (billing_timing IN ('prepaid', 'postpaid')),
    -- Fee plans: [{label, amount, due_after_days}] copied onto each enrolment.
    ADD COLUMN instalment_template JSONB,
    -- Service contracts: how many preventive visits a period covers, how often.
    ADD COLUMN visits_included INTEGER CHECK (visits_included IS NULL OR visits_included BETWEEN 1 AND 365),
    ADD COLUMN visit_every_days INTEGER CHECK (visit_every_days IS NULL OR visit_every_days BETWEEN 1 AND 366);

-- ---------------------------------------------------------------- enrolments (the relationship)
ALTER TABLE memberships_enrolments DROP CONSTRAINT IF EXISTS memberships_enrolments_status_check;
ALTER TABLE memberships_enrolments ADD CONSTRAINT memberships_enrolments_status_check
    CHECK (status IN ('pending', 'active', 'paused', 'grace', 'expired', 'cancelled', 'completed'));
ALTER TABLE memberships_enrolments
    ADD COLUMN location_id UUID REFERENCES business_locations(id),
    ADD COLUMN responsible_identity_id UUID REFERENCES platform_identities(id),
    ADD COLUMN channel TEXT,
    -- Who pays when it is not the member (a guardian for a student).
    ADD COLUMN payer_contact_id UUID REFERENCES customer_relationships_contacts(id),
    -- A stable reference into another module: an academic enrolment for a
    -- fee plan, a customer asset for an AMC. Opaque here; the owner module owns it.
    ADD COLUMN source_ref_type TEXT CHECK (source_ref_type IS NULL OR source_ref_type IN
        ('academic_enrolment', 'customer_asset')),
    ADD COLUMN source_ref_id UUID,
    -- This subscriber's schedule (subscriptions), from the plan's default.
    ADD COLUMN delivery JSONB,
    -- Cached answers (recalculated from periods, freezes and instalments).
    ADD COLUMN valid_until TIMESTAMPTZ,
    ADD COLUMN grace_until TIMESTAMPTZ,
    ADD COLUMN next_due_on DATE,
    -- What the member shows at the front desk (QR / typed code).
    ADD COLUMN checkin_code TEXT;
CREATE UNIQUE INDEX idx_enrolments_checkin_code ON memberships_enrolments (business_id, checkin_code)
    WHERE checkin_code IS NOT NULL;
CREATE INDEX idx_enrolments_valid_until ON memberships_enrolments (business_id, valid_until)
    WHERE deleted_at IS NULL;
CREATE INDEX idx_enrolments_source_ref ON memberships_enrolments (business_id, source_ref_type, source_ref_id)
    WHERE source_ref_id IS NOT NULL;

-- ---------------------------------------------------------------- periods
CREATE TABLE memberships_periods (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    business_id UUID NOT NULL REFERENCES businesses(id),
    enrolment_id UUID NOT NULL REFERENCES memberships_enrolments(id),
    seq INTEGER NOT NULL CHECK (seq >= 1),
    starts_at TIMESTAMPTZ NOT NULL,
    base_ends_at TIMESTAMPTZ NOT NULL,
    ends_at TIMESTAMPTZ NOT NULL,
    amount NUMERIC(12, 2) NOT NULL DEFAULT 0 CHECK (amount >= 0),
    paid_amount NUMERIC(12, 2) NOT NULL DEFAULT 0 CHECK (paid_amount >= 0),
    payment_state TEXT NOT NULL DEFAULT 'unpaid'
        CHECK (payment_state IN ('unpaid', 'part_paid', 'paid', 'waived', 'cancelled')),
    sessions_included INTEGER CHECK (sessions_included IS NULL OR sessions_included >= 0),
    source TEXT NOT NULL DEFAULT 'join' CHECK (source IN ('join', 'renewal', 'early_renewal', 'autopay', 'manual')),
    created_by UUID REFERENCES platform_identities(id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    paid_at TIMESTAMPTZ,
    CHECK (ends_at > starts_at),
    CHECK (ends_at >= base_ends_at),
    UNIQUE (enrolment_id, seq)
);
CREATE INDEX idx_membership_periods_enrolment ON memberships_periods (business_id, enrolment_id, seq);

-- ---------------------------------------------------------------- freezes / pauses
CREATE TABLE memberships_freezes (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    business_id UUID NOT NULL REFERENCES businesses(id),
    enrolment_id UUID NOT NULL REFERENCES memberships_enrolments(id),
    kind TEXT NOT NULL DEFAULT 'freeze' CHECK (kind IN ('freeze', 'pause')),
    starts_on DATE NOT NULL,
    ends_on DATE NOT NULL,
    days INTEGER NOT NULL CHECK (days BETWEEN 1 AND 366),
    -- Whether the cover end moved (a gym freeze does; a milk pause does not).
    extends_cover BOOLEAN NOT NULL DEFAULT true,
    reason TEXT CHECK (reason IS NULL OR length(reason) <= 200),
    status TEXT NOT NULL DEFAULT 'confirmed' CHECK (status IN ('confirmed', 'cancelled')),
    approved_by UUID REFERENCES platform_identities(id),
    channel TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    cancelled_at TIMESTAMPTZ,
    CHECK (ends_on >= starts_on),
    CHECK (days = ends_on - starts_on + 1)
);
CREATE INDEX idx_membership_freezes_enrolment ON memberships_freezes (business_id, enrolment_id, starts_on);

-- ---------------------------------------------------------------- session uses
CREATE TABLE memberships_session_uses (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    business_id UUID NOT NULL REFERENCES businesses(id),
    enrolment_id UUID NOT NULL REFERENCES memberships_enrolments(id),
    period_id UUID NOT NULL REFERENCES memberships_periods(id),
    used_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    source_type TEXT NOT NULL CHECK (source_type IN ('booking', 'checkin', 'manual')),
    source_id UUID,
    idempotency_key TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'consumed' CHECK (status IN ('consumed', 'reversed')),
    reason TEXT CHECK (reason IS NULL OR length(reason) <= 200),
    recorded_by UUID REFERENCES platform_identities(id),
    reversed_at TIMESTAMPTZ,
    UNIQUE (business_id, idempotency_key)
);
CREATE INDEX idx_membership_session_uses_period ON memberships_session_uses (business_id, period_id, status);

-- ---------------------------------------------------------------- instalments (fee plans, dues schedules)
CREATE TABLE memberships_instalments (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    business_id UUID NOT NULL REFERENCES businesses(id),
    enrolment_id UUID NOT NULL REFERENCES memberships_enrolments(id),
    seq INTEGER NOT NULL CHECK (seq >= 1),
    label TEXT NOT NULL CHECK (length(label) BETWEEN 1 AND 80),
    amount NUMERIC(12, 2) NOT NULL CHECK (amount > 0),
    due_on DATE NOT NULL,
    paid_amount NUMERIC(12, 2) NOT NULL DEFAULT 0 CHECK (paid_amount >= 0),
    status TEXT NOT NULL DEFAULT 'due' CHECK (status IN ('due', 'part_paid', 'paid', 'waived', 'cancelled')),
    paid_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (enrolment_id, seq)
);
CREATE INDEX idx_membership_instalments_due ON memberships_instalments (business_id, status, due_on);

-- ---------------------------------------------------------------- which payment paid what
CREATE TABLE memberships_payment_applications (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    business_id UUID NOT NULL REFERENCES businesses(id),
    enrolment_id UUID NOT NULL REFERENCES memberships_enrolments(id),
    payment_attempt_id UUID NOT NULL REFERENCES payments_payment_attempts(id),
    charge_type TEXT NOT NULL CHECK (charge_type IN ('period', 'instalment')),
    charge_id UUID NOT NULL,
    amount NUMERIC(12, 2) NOT NULL CHECK (amount > 0),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (payment_attempt_id, charge_type, charge_id)
);
CREATE INDEX idx_membership_payment_applications_payment
    ON memberships_payment_applications (business_id, payment_attempt_id);

-- ---------------------------------------------------------------- subscriptions: changes and generated deliveries
CREATE TABLE memberships_delivery_overrides (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    business_id UUID NOT NULL REFERENCES businesses(id),
    enrolment_id UUID NOT NULL REFERENCES memberships_enrolments(id),
    on_date DATE NOT NULL,
    slot TEXT NOT NULL DEFAULT '',
    kind TEXT NOT NULL CHECK (kind IN ('skip', 'quantity')),
    quantity NUMERIC(12, 3) CHECK (quantity IS NULL OR quantity > 0),
    channel TEXT,
    created_by UUID REFERENCES platform_identities(id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    cancelled_at TIMESTAMPTZ,
    CHECK ((kind = 'quantity') = (quantity IS NOT NULL))
);
CREATE UNIQUE INDEX idx_membership_delivery_override_live
    ON memberships_delivery_overrides (enrolment_id, on_date, slot) WHERE cancelled_at IS NULL;

CREATE TABLE memberships_deliveries (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    business_id UUID NOT NULL REFERENCES businesses(id),
    enrolment_id UUID NOT NULL REFERENCES memberships_enrolments(id),
    on_date DATE NOT NULL,
    slot TEXT NOT NULL DEFAULT '',
    quantity NUMERIC(12, 3) NOT NULL DEFAULT 0 CHECK (quantity >= 0),
    status TEXT NOT NULL CHECK (status IN ('ordered', 'skipped', 'paused', 'not_covered')),
    order_id UUID,
    unit_price NUMERIC(12, 2),
    amount NUMERIC(12, 2),
    -- Postpaid: the khata entry that billed it (month-end statement).
    ledger_entry_id UUID,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (enrolment_id, on_date, slot)
);
CREATE INDEX idx_membership_deliveries_day ON memberships_deliveries (business_id, on_date, status);

-- ---------------------------------------------------------------- service contracts: covered visits
CREATE TABLE memberships_service_visits (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    business_id UUID NOT NULL REFERENCES businesses(id),
    enrolment_id UUID NOT NULL REFERENCES memberships_enrolments(id),
    period_id UUID NOT NULL REFERENCES memberships_periods(id),
    seq INTEGER NOT NULL CHECK (seq >= 1),
    due_on DATE NOT NULL,
    status TEXT NOT NULL DEFAULT 'scheduled'
        CHECK (status IN ('scheduled', 'requested', 'done', 'cancelled', 'missed')),
    -- The Jobs module's job for this visit (Jobs owns the work itself).
    job_ref UUID,
    requested_at TIMESTAMPTZ,
    done_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (period_id, seq)
);
CREATE INDEX idx_membership_service_visits_due ON memberships_service_visits (business_id, status, due_on);

-- ---------------------------------------------------------------- RLS
DO $$
DECLARE t TEXT;
BEGIN
    FOREACH t IN ARRAY ARRAY['memberships_periods', 'memberships_freezes', 'memberships_session_uses',
                             'memberships_instalments', 'memberships_payment_applications',
                             'memberships_delivery_overrides', 'memberships_deliveries',
                             'memberships_service_visits'] LOOP
        EXECUTE format('ALTER TABLE %I ENABLE ROW LEVEL SECURITY', t);
        EXECUTE format('ALTER TABLE %I FORCE ROW LEVEL SECURITY', t);
        EXECUTE format('CREATE POLICY %I ON %I FOR SELECT TO public USING (business_id = current_business_id())',
                       t || '_member_read', t);
        EXECUTE format('CREATE POLICY %I ON %I FOR ALL TO platform_api USING (business_id = current_business_id()) '
                       'WITH CHECK (business_id = current_business_id())', t || '_api_write', t);
        -- The relationship's history is never deleted: corrections are new rows
        -- or a status change (cancelled / reversed).
        EXECUTE format('GRANT SELECT, INSERT, UPDATE ON %I TO platform_api', t);
        EXECUTE format('REVOKE DELETE ON %I FROM platform_api', t);
        EXECUTE format('REVOKE ALL PRIVILEGES ON TABLE %I FROM anon', t);
    END LOOP;
END
$$;

-- A period is history: what it covered from, what it was bought for and what
-- it cost never change. Only a freeze may move its end (ends_at), and payment
-- may fill it (paid_amount, payment_state, paid_at).
CREATE OR REPLACE FUNCTION memberships_period_is_history() RETURNS trigger
    LANGUAGE plpgsql AS $$
BEGIN
    IF NEW.business_id <> OLD.business_id OR NEW.enrolment_id <> OLD.enrolment_id OR NEW.seq <> OLD.seq
       OR NEW.starts_at <> OLD.starts_at OR NEW.base_ends_at <> OLD.base_ends_at OR NEW.amount <> OLD.amount
       OR NEW.source <> OLD.source OR NEW.created_at <> OLD.created_at THEN
        RAISE EXCEPTION 'membership periods are history: only their end (by a freeze) and payment may change'
            USING ERRCODE = 'check_violation';
    END IF;
    RETURN NEW;
END
$$;
CREATE TRIGGER trg_membership_periods_history BEFORE UPDATE ON memberships_periods
    FOR EACH ROW EXECUTE FUNCTION memberships_period_is_history();

-- A subscription's daily delivery is a real order, from the channel "subscription".
ALTER TABLE orders_orders DROP CONSTRAINT IF EXISTS orders_orders_channel_check;
ALTER TABLE orders_orders ADD CONSTRAINT orders_orders_channel_check
    CHECK (channel IN ('web', 'whatsapp', 'pos', 'phone', 'workspace', 'marketplace', 'chitbridge', 'subscription'));
