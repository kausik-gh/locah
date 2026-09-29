-- Phase B · P3 — Growth: Loyalty, Referrals, Marketing & Attribution
-- Source: LOCAH Business Capability Universe §6.2 (loyalty, marketing), §18 (Marketing, Meta, Local Presence),
-- §18.1–§18.4, §21.3 (Gift vouchers as prepaid balance), §25.1 (DPDP Act, Legal/Regulated guards, Minors).
-- Ledger rows: LY-01, LY-02, LY-03, LY-04, MK-01, MK-02, MK-03, MK-04, MK-05, MK-06, MK-07, MK-08, MK-09, MK-10, MS-26.

-- ============================================================================
-- 1. LOYALTY & REWARDS
-- ============================================================================

CREATE TABLE IF NOT EXISTS loyalty_programs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    business_id UUID NOT NULL REFERENCES businesses(id),
    name TEXT NOT NULL CHECK (char_length(name) BETWEEN 1 AND 80),
    program_type TEXT NOT NULL DEFAULT 'points' CHECK (program_type IN ('points', 'stamps', 'hybrid')),
    points_per_rupee NUMERIC(8, 4) NOT NULL DEFAULT 1.0 CHECK (points_per_rupee >= 0),
    redemption_rupees_per_point NUMERIC(8, 4) NOT NULL DEFAULT 0.25 CHECK (redemption_rupees_per_point > 0),
    min_redemption_points INTEGER NOT NULL DEFAULT 10 CHECK (min_redemption_points >= 0),
    max_redemption_points_per_order INTEGER CHECK (max_redemption_points_per_order IS NULL OR max_redemption_points_per_order >= min_redemption_points),
    expiry_days INTEGER CHECK (expiry_days IS NULL OR expiry_days > 0),
    status TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'paused', 'inactive')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    version INTEGER NOT NULL DEFAULT 1
);
CREATE UNIQUE INDEX IF NOT EXISTS loyalty_programs_one_per_business ON loyalty_programs (business_id) WHERE status = 'active';

CREATE TABLE IF NOT EXISTS loyalty_accounts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    business_id UUID NOT NULL REFERENCES businesses(id),
    customer_contact_id UUID NOT NULL REFERENCES customer_relationships_contacts(id),
    current_points INTEGER NOT NULL DEFAULT 0 CHECK (current_points >= 0),
    lifetime_points_earned INTEGER NOT NULL DEFAULT 0 CHECK (lifetime_points_earned >= 0),
    lifetime_points_redeemed INTEGER NOT NULL DEFAULT 0 CHECK (lifetime_points_redeemed >= 0),
    tier TEXT NOT NULL DEFAULT 'standard',
    joined_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    last_activity_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT loyalty_accounts_business_customer UNIQUE (business_id, customer_contact_id)
);
CREATE INDEX IF NOT EXISTS loyalty_accounts_customer ON loyalty_accounts (business_id, customer_contact_id);

CREATE TABLE IF NOT EXISTS loyalty_ledger (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    business_id UUID NOT NULL REFERENCES businesses(id),
    customer_contact_id UUID NOT NULL REFERENCES customer_relationships_contacts(id),
    delta INTEGER NOT NULL CHECK (delta <> 0),
    balance_after INTEGER NOT NULL CHECK (balance_after >= 0),
    reason TEXT NOT NULL CHECK (reason IN ('earn_order', 'redeem_order', 'referral_bonus', 'stamp_reward', 'manual_adjustment', 'expiry', 'clawback_refund')),
    source_type TEXT NOT NULL CHECK (source_type IN ('order', 'pos', 'referral', 'stamp_card', 'manual', 'expiry', 'reversal')),
    source_id TEXT NOT NULL,
    idempotency_key TEXT NOT NULL,
    actor_id UUID REFERENCES platform_identities(id),
    expires_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT loyalty_ledger_idempotency UNIQUE (business_id, idempotency_key)
);
CREATE INDEX IF NOT EXISTS loyalty_ledger_customer_created ON loyalty_ledger (business_id, customer_contact_id, created_at DESC);

-- ============================================================================
-- 2. STAMP CARDS ('10th coffee free')
-- ============================================================================

CREATE TABLE IF NOT EXISTS stamp_programs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    business_id UUID NOT NULL REFERENCES businesses(id),
    name TEXT NOT NULL CHECK (char_length(name) BETWEEN 1 AND 80),
    qualifying_rule JSONB NOT NULL DEFAULT '{}'::jsonb,
    required_stamps INTEGER NOT NULL CHECK (required_stamps BETWEEN 2 AND 100),
    reward_kind TEXT NOT NULL CHECK (reward_kind IN ('free_item', 'discount_paise', 'discount_percent', 'points')),
    reward_details JSONB NOT NULL DEFAULT '{}'::jsonb,
    status TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'paused')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS stamp_programs_business ON stamp_programs (business_id, status);

CREATE TABLE IF NOT EXISTS stamp_cards (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    business_id UUID NOT NULL REFERENCES businesses(id),
    program_id UUID NOT NULL REFERENCES stamp_programs(id),
    customer_contact_id UUID NOT NULL REFERENCES customer_relationships_contacts(id),
    current_stamps INTEGER NOT NULL DEFAULT 0 CHECK (current_stamps >= 0),
    cycle_count INTEGER NOT NULL DEFAULT 0 CHECK (cycle_count >= 0),
    lifetime_stamps INTEGER NOT NULL DEFAULT 0 CHECK (lifetime_stamps >= 0),
    last_stamp_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT stamp_cards_unique_cycle UNIQUE (business_id, program_id, customer_contact_id)
);

CREATE TABLE IF NOT EXISTS stamp_rewards (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    business_id UUID NOT NULL REFERENCES businesses(id),
    program_id UUID NOT NULL REFERENCES stamp_programs(id),
    customer_contact_id UUID NOT NULL REFERENCES customer_relationships_contacts(id),
    reward_code TEXT NOT NULL,
    cycle_completed INTEGER NOT NULL,
    status TEXT NOT NULL DEFAULT 'issued' CHECK (status IN ('issued', 'redeemed', 'expired')),
    issued_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    redeemed_at TIMESTAMPTZ,
    order_id UUID,
    CONSTRAINT stamp_rewards_code_unique UNIQUE (business_id, reward_code)
);
CREATE INDEX IF NOT EXISTS stamp_rewards_customer ON stamp_rewards (business_id, customer_contact_id, status);

-- ============================================================================
-- 3. REFERRALS (Rewarded on friend's first eligible purchase)
-- ============================================================================

CREATE TABLE IF NOT EXISTS referral_codes (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    business_id UUID NOT NULL REFERENCES businesses(id),
    customer_contact_id UUID NOT NULL REFERENCES customer_relationships_contacts(id),
    code TEXT NOT NULL CHECK (char_length(code) BETWEEN 3 AND 30),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT referral_codes_unique_code UNIQUE (business_id, lower(code)),
    CONSTRAINT referral_codes_one_per_customer UNIQUE (business_id, customer_contact_id)
);

CREATE TABLE IF NOT EXISTS referral_relationships (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    business_id UUID NOT NULL REFERENCES businesses(id),
    referrer_contact_id UUID NOT NULL REFERENCES customer_relationships_contacts(id),
    referee_contact_id UUID NOT NULL REFERENCES customer_relationships_contacts(id),
    code_used TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'qualified', 'rewarded', 'ineligible')),
    qualification_source_type TEXT,
    qualification_source_id TEXT,
    referrer_points_awarded INTEGER NOT NULL DEFAULT 0 CHECK (referrer_points_awarded >= 0),
    referee_points_awarded INTEGER NOT NULL DEFAULT 0 CHECK (referee_points_awarded >= 0),
    qualified_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT referral_no_self_referral CHECK (referrer_contact_id <> referee_contact_id),
    CONSTRAINT referral_one_referrer_per_referee UNIQUE (business_id, referee_contact_id)
);
CREATE INDEX IF NOT EXISTS referral_relationships_referrer ON referral_relationships (business_id, referrer_contact_id);

-- ============================================================================
-- 4. GIFT VOUCHERS / PREPAID BALANCES
-- ============================================================================

CREATE TABLE IF NOT EXISTS gift_vouchers (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    business_id UUID NOT NULL REFERENCES businesses(id),
    code TEXT NOT NULL CHECK (char_length(code) BETWEEN 6 AND 32),
    holder_contact_id UUID REFERENCES customer_relationships_contacts(id),
    recipient_name TEXT,
    recipient_phone TEXT,
    issued_amount_paise BIGINT NOT NULL CHECK (issued_amount_paise > 0),
    remaining_balance_paise BIGINT NOT NULL CHECK (remaining_balance_paise >= 0),
    currency TEXT NOT NULL DEFAULT 'INR',
    status TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'redeemed', 'expired', 'cancelled')),
    expires_at TIMESTAMPTZ,
    created_by UUID REFERENCES platform_identities(id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT gift_vouchers_unique_code UNIQUE (business_id, upper(code))
);
CREATE INDEX IF NOT EXISTS gift_vouchers_holder ON gift_vouchers (business_id, holder_contact_id);

CREATE TABLE IF NOT EXISTS gift_voucher_transactions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    business_id UUID NOT NULL REFERENCES businesses(id),
    voucher_id UUID NOT NULL REFERENCES gift_vouchers(id),
    delta_paise BIGINT NOT NULL CHECK (delta_paise <> 0),
    balance_after_paise BIGINT NOT NULL CHECK (balance_after_paise >= 0),
    reason TEXT NOT NULL CHECK (reason IN ('issuance', 'redemption', 'refund_reversal', 'cancellation')),
    source_type TEXT NOT NULL,
    source_id TEXT NOT NULL,
    idempotency_key TEXT NOT NULL,
    actor_id UUID REFERENCES platform_identities(id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT gift_voucher_tx_idempotency UNIQUE (business_id, idempotency_key)
);
CREATE INDEX IF NOT EXISTS gift_voucher_tx_voucher ON gift_voucher_transactions (business_id, voucher_id, created_at DESC);

-- ============================================================================
-- 5. MARKETING OFFERS & COUPONS
-- ============================================================================

CREATE TABLE IF NOT EXISTS marketing_offers (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    business_id UUID NOT NULL REFERENCES businesses(id),
    code TEXT NOT NULL CHECK (char_length(code) BETWEEN 2 AND 30),
    name TEXT NOT NULL CHECK (char_length(name) BETWEEN 1 AND 80),
    kind TEXT NOT NULL CHECK (kind IN ('percentage_discount', 'fixed_amount', 'free_delivery', 'first_order', 'win_back')),
    discount_value NUMERIC(10, 2) NOT NULL CHECK (discount_value > 0),
    min_order_amount_paise BIGINT NOT NULL DEFAULT 0 CHECK (min_order_amount_paise >= 0),
    max_discount_paise BIGINT CHECK (max_discount_paise IS NULL OR max_discount_paise > 0),
    usage_limit_total INTEGER CHECK (usage_limit_total IS NULL OR usage_limit_total > 0),
    usage_limit_per_customer INTEGER NOT NULL DEFAULT 1 CHECK (usage_limit_per_customer > 0),
    times_used INTEGER NOT NULL DEFAULT 0 CHECK (times_used >= 0),
    starts_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    expires_at TIMESTAMPTZ,
    status TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'paused', 'expired')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT marketing_offers_unique_code UNIQUE (business_id, upper(code))
);

-- ============================================================================
-- 6. MARKETING CAMPAIGNS & BROADCAST ORCHESTRATION
-- ============================================================================

CREATE TABLE IF NOT EXISTS marketing_campaigns (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    business_id UUID NOT NULL REFERENCES businesses(id),
    name TEXT NOT NULL CHECK (char_length(name) BETWEEN 1 AND 100),
    goal TEXT NOT NULL CHECK (char_length(goal) BETWEEN 1 AND 60),
    channel TEXT NOT NULL CHECK (channel IN ('whatsapp', 'meta_ads')),
    audience_segment_id UUID REFERENCES customer_relationships_segments(id),
    audience_snapshot JSONB NOT NULL DEFAULT '{}'::jsonb,
    offer_id UUID REFERENCES marketing_offers(id),
    creative JSONB NOT NULL DEFAULT '{}'::jsonb,
    budget_paise BIGINT NOT NULL DEFAULT 0 CHECK (budget_paise >= 0),
    estimated_cost_paise BIGINT NOT NULL DEFAULT 0 CHECK (estimated_cost_paise >= 0),
    actual_cost_paise BIGINT NOT NULL DEFAULT 0 CHECK (actual_cost_paise >= 0),
    schedule_type TEXT NOT NULL DEFAULT 'immediate' CHECK (schedule_type IN ('immediate', 'scheduled')),
    scheduled_at TIMESTAMPTZ,
    status TEXT NOT NULL DEFAULT 'DRAFT' CHECK (status IN ('DRAFT', 'READY_FOR_APPROVAL', 'APPROVED', 'SCHEDULED', 'RUNNING', 'PAUSED', 'COMPLETED', 'CANCELLED')),
    approved_by UUID REFERENCES platform_identities(id),
    approved_at TIMESTAMPTZ,
    approval_record JSONB,
    content_hash TEXT,
    created_by UUID REFERENCES platform_identities(id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    version INTEGER NOT NULL DEFAULT 1
);
CREATE INDEX IF NOT EXISTS marketing_campaigns_status ON marketing_campaigns (business_id, status);

CREATE TABLE IF NOT EXISTS marketing_broadcast_recipients (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    business_id UUID NOT NULL REFERENCES businesses(id),
    campaign_id UUID NOT NULL REFERENCES marketing_campaigns(id),
    contact_id UUID NOT NULL REFERENCES customer_relationships_contacts(id),
    phone TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'queued' CHECK (status IN ('queued', 'dispatched', 'delivered', 'failed', 'excluded_no_consent', 'excluded_frequency')),
    cost_paise BIGINT NOT NULL DEFAULT 0,
    idempotency_key TEXT NOT NULL,
    error_reason TEXT,
    dispatched_at TIMESTAMPTZ,
    delivered_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT marketing_recipients_one_per_campaign UNIQUE (campaign_id, contact_id),
    CONSTRAINT marketing_recipients_idempotency UNIQUE (business_id, idempotency_key)
);
CREATE INDEX IF NOT EXISTS marketing_recipients_campaign ON marketing_broadcast_recipients (business_id, campaign_id, status);

CREATE TABLE IF NOT EXISTS marketing_frequency_log (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    business_id UUID NOT NULL REFERENCES businesses(id),
    contact_id UUID NOT NULL REFERENCES customer_relationships_contacts(id),
    channel TEXT NOT NULL,
    campaign_id UUID REFERENCES marketing_campaigns(id),
    sent_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS marketing_freq_contact_window ON marketing_frequency_log (business_id, contact_id, channel, sent_at DESC);

-- ============================================================================
-- 7. APPROXIMATE LAST-TOUCH ATTRIBUTION & RESULTS
-- ============================================================================

CREATE TABLE IF NOT EXISTS marketing_touchpoints (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    business_id UUID NOT NULL REFERENCES businesses(id),
    touchpoint_kind TEXT NOT NULL CHECK (touchpoint_kind IN ('utm', 'ctwa', 'coupon', 'referral', 'campaign')),
    campaign_id UUID REFERENCES marketing_campaigns(id),
    coupon_code TEXT,
    referral_code TEXT,
    utm_source TEXT,
    utm_medium TEXT,
    utm_campaign TEXT,
    customer_contact_id UUID REFERENCES customer_relationships_contacts(id),
    session_id TEXT,
    metadata_snapshot JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS marketing_touchpoints_customer ON marketing_touchpoints (business_id, customer_contact_id, created_at DESC);

CREATE TABLE IF NOT EXISTS marketing_conversions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    business_id UUID NOT NULL REFERENCES businesses(id),
    touchpoint_id UUID NOT NULL REFERENCES marketing_touchpoints(id),
    conversion_kind TEXT NOT NULL CHECK (conversion_kind IN ('order', 'booking', 'lead')),
    conversion_id TEXT NOT NULL,
    revenue_paise BIGINT NOT NULL DEFAULT 0,
    attribution_model TEXT NOT NULL DEFAULT 'approximate_last_touch',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT marketing_conversions_unique_conv UNIQUE (business_id, conversion_kind, conversion_id)
);
CREATE INDEX IF NOT EXISTS marketing_conversions_touchpoint ON marketing_conversions (business_id, touchpoint_id);

CREATE TABLE IF NOT EXISTS marketing_meta_configurations (
    business_id UUID PRIMARY KEY REFERENCES businesses(id),
    ad_account_id TEXT,
    pixel_id TEXT,
    monthly_spend_cap_paise BIGINT NOT NULL DEFAULT 0 CHECK (monthly_spend_cap_paise >= 0),
    current_month_spend_paise BIGINT NOT NULL DEFAULT 0 CHECK (current_month_spend_paise >= 0),
    conversions_api_enabled BOOLEAN NOT NULL DEFAULT false,
    status TEXT NOT NULL DEFAULT 'ACTIVATION_REQUIRED',
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ============================================================================
-- RLS POLICIES FOR ALL TENANT-OWNED GROWTH TABLES
-- ============================================================================

DO $$
DECLARE
    tbl text;
    tables text[] := ARRAY[
        'loyalty_programs',
        'loyalty_accounts',
        'loyalty_ledger',
        'stamp_programs',
        'stamp_cards',
        'stamp_rewards',
        'referral_codes',
        'referral_relationships',
        'gift_vouchers',
        'gift_voucher_transactions',
        'marketing_offers',
        'marketing_campaigns',
        'marketing_broadcast_recipients',
        'marketing_frequency_log',
        'marketing_touchpoints',
        'marketing_conversions',
        'marketing_meta_configurations'
    ];
BEGIN
    FOREACH tbl IN ARRAY tables LOOP
        EXECUTE format('ALTER TABLE %I ENABLE ROW LEVEL SECURITY', tbl);
        EXECUTE format('ALTER TABLE %I FORCE ROW LEVEL SECURITY', tbl);

        EXECUTE format('DROP POLICY IF EXISTS %I ON %I', tbl || '_member_read', tbl);
        EXECUTE format('CREATE POLICY %I ON %I FOR SELECT TO public USING (business_id = current_business_id())', tbl || '_member_read', tbl);

        EXECUTE format('DROP POLICY IF EXISTS %I ON %I', tbl || '_api_write', tbl);
        EXECUTE format('CREATE POLICY %I ON %I FOR ALL TO platform_api USING (business_id = current_business_id()) WITH CHECK (business_id = current_business_id())', tbl || '_api_write', tbl);

        EXECUTE format('REVOKE ALL PRIVILEGES ON TABLE %I FROM anon', tbl);
        EXECUTE format('GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE %I TO platform_api', tbl);
        EXECUTE format('GRANT SELECT ON TABLE %I TO public', tbl);
    END LOOP;
END $$;
