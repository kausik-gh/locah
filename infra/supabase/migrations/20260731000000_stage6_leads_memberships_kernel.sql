-- Stage 6: Relationships, Leads, Memberships & Workforce Completion
-- Authority: Doc 11 §17.6 (scope/exit), §9.5 (Memberships depth), §10.2 (Leads depth)
-- Recurring billing deferred pending FL-DEC-005 — fixed-duration + manual renewal only.
-- Customer interaction history extends the existing customer_relationships tables
-- (Stage 4); no new CRM tables here.

-- ============================================================
-- LEADS (module: leads) — Doc 11 §10.2
-- Pipeline: new -> contacted -> qualified -> won | lost
-- ============================================================
CREATE TABLE leads_leads (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    business_id UUID NOT NULL REFERENCES businesses(id),
    -- Consumer contact + enquiry
    display_name TEXT NOT NULL,
    email TEXT,
    phone TEXT,
    message TEXT,
    -- Origin (Doc 11 §10.2: source and originating context)
    source TEXT NOT NULL DEFAULT 'manual'
        CHECK (source IN ('manual', 'website_enquiry', 'marketplace', 'import')),
    origin_context JSONB NOT NULL DEFAULT '{}'::jsonb,
    -- Cross-module offering/listing reference (no FK per §5.10 pattern for offerings)
    offering_id UUID,
    -- Pipeline
    status TEXT NOT NULL DEFAULT 'new'
        CHECK (status IN ('new', 'contacted', 'qualified', 'won', 'lost')),
    lost_reason TEXT,
    -- Assignee (Platform Core identity FK, mirrors actor_identity_id elsewhere)
    assignee_identity_id UUID REFERENCES platform_identities(id),
    -- Follow-up (basic reminder — scheduler materialises, no complex recurrence)
    next_follow_up_at TIMESTAMPTZ,
    -- On Won: link/create the Business-scoped CustomerContact; Lead is retained.
    customer_contact_id UUID REFERENCES customer_relationships_contacts(id),
    -- Audit
    created_by UUID REFERENCES platform_identities(id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    deleted_at TIMESTAMPTZ,
    version INTEGER NOT NULL DEFAULT 1
);

CREATE INDEX idx_leads_business ON leads_leads(business_id) WHERE deleted_at IS NULL;
CREATE INDEX idx_leads_pipeline ON leads_leads(business_id, status)
    WHERE deleted_at IS NULL;
CREATE INDEX idx_leads_assignee ON leads_leads(business_id, assignee_identity_id)
    WHERE deleted_at IS NULL AND assignee_identity_id IS NOT NULL;
CREATE INDEX idx_leads_follow_up ON leads_leads(business_id, next_follow_up_at)
    WHERE deleted_at IS NULL AND next_follow_up_at IS NOT NULL;
CREATE INDEX idx_leads_email ON leads_leads(business_id, lower(email))
    WHERE deleted_at IS NULL AND email IS NOT NULL;

CREATE TABLE leads_lead_status_history (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    business_id UUID NOT NULL REFERENCES businesses(id),
    lead_id UUID NOT NULL REFERENCES leads_leads(id) ON DELETE CASCADE,
    from_status TEXT,
    to_status TEXT NOT NULL,
    actor_identity_id UUID REFERENCES platform_identities(id),
    reason TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_lead_status_history ON leads_lead_status_history(lead_id, created_at DESC);

CREATE TABLE leads_lead_notes (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    business_id UUID NOT NULL REFERENCES businesses(id),
    lead_id UUID NOT NULL REFERENCES leads_leads(id) ON DELETE CASCADE,
    body TEXT NOT NULL,
    author_identity_id UUID NOT NULL REFERENCES platform_identities(id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    deleted_at TIMESTAMPTZ,
    version INTEGER NOT NULL DEFAULT 1
);

CREATE INDEX idx_lead_notes_lead ON leads_lead_notes(lead_id, created_at DESC)
    WHERE deleted_at IS NULL;

-- ============================================================
-- MEMBERSHIPS (module: memberships) — Doc 11 §9.5
-- Customer-facing membership plans + enrolments. Distinct from
-- business_memberships (Team & Access / staff).
-- ============================================================
CREATE TABLE memberships_plans (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    business_id UUID NOT NULL REFERENCES businesses(id),
    name TEXT NOT NULL,
    description TEXT,
    -- Optional public Offering surface (offerings-catalog, no FK per pattern)
    offering_id UUID,
    -- Pricing
    price_amount NUMERIC(12, 2) NOT NULL DEFAULT 0,
    currency TEXT NOT NULL DEFAULT 'INR',
    -- Validity model. 'recurring' reserved for FL-DEC-005; only 'fixed_duration'
    -- is creatable at First Launch (enforced in the service layer).
    billing_model TEXT NOT NULL DEFAULT 'fixed_duration'
        CHECK (billing_model IN ('fixed_duration', 'recurring')),
    duration_days INTEGER CHECK (duration_days IS NULL OR duration_days > 0),
    -- Lifecycle + discoverability
    status TEXT NOT NULL DEFAULT 'draft'
        CHECK (status IN ('draft', 'active', 'archived')),
    visibility TEXT NOT NULL DEFAULT 'private'
        CHECK (visibility IN ('public', 'private')),
    created_by UUID REFERENCES platform_identities(id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    deleted_at TIMESTAMPTZ,
    version INTEGER NOT NULL DEFAULT 1
);

CREATE INDEX idx_membership_plans_business ON memberships_plans(business_id)
    WHERE deleted_at IS NULL;
CREATE INDEX idx_membership_plans_public ON memberships_plans(business_id, visibility)
    WHERE deleted_at IS NULL AND status = 'active';

-- Which class/session offerings a plan grants booking access to (the membership
-- gate for Stage 6 class booking). Absence of any row for an offering means the
-- Stage 5 capacity-only path is unchanged.
CREATE TABLE memberships_plan_offering_access (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    business_id UUID NOT NULL REFERENCES businesses(id),
    plan_id UUID NOT NULL REFERENCES memberships_plans(id) ON DELETE CASCADE,
    offering_id UUID NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (plan_id, offering_id)
);

CREATE INDEX idx_plan_offering_access_offering
    ON memberships_plan_offering_access(business_id, offering_id);

CREATE TABLE memberships_enrolments (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    business_id UUID NOT NULL REFERENCES businesses(id),
    plan_id UUID NOT NULL REFERENCES memberships_plans(id),
    -- Customer identity is the Business-scoped contact; platform identity optional.
    customer_contact_id UUID NOT NULL REFERENCES customer_relationships_contacts(id),
    identity_id UUID REFERENCES platform_identities(id),
    -- Validity window
    starts_at TIMESTAMPTZ NOT NULL,
    ends_at TIMESTAMPTZ,
    status TEXT NOT NULL DEFAULT 'pending'
        CHECK (status IN (
            'pending', 'active', 'paused', 'expired', 'cancelled', 'completed'
        )),
    -- Payment linkage (payments module, no FK per pattern)
    payment_attempt_id UUID,
    payment_status TEXT NOT NULL DEFAULT 'pending'
        CHECK (payment_status IN ('pending', 'pending_offline', 'paid', 'refunded')),
    -- Manual renewal only at First Launch; kept for renewal visibility.
    auto_renew BOOLEAN NOT NULL DEFAULT false,
    paused_at TIMESTAMPTZ,
    cancelled_at TIMESTAMPTZ,
    cancellation_reason TEXT,
    idempotency_key TEXT,
    created_by UUID REFERENCES platform_identities(id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    deleted_at TIMESTAMPTZ,
    version INTEGER NOT NULL DEFAULT 1
);

CREATE INDEX idx_enrolments_business ON memberships_enrolments(business_id)
    WHERE deleted_at IS NULL;
CREATE INDEX idx_enrolments_plan ON memberships_enrolments(business_id, plan_id)
    WHERE deleted_at IS NULL;
CREATE INDEX idx_enrolments_contact ON memberships_enrolments(business_id, customer_contact_id)
    WHERE deleted_at IS NULL;
CREATE INDEX idx_enrolments_active ON memberships_enrolments(business_id, customer_contact_id, status)
    WHERE deleted_at IS NULL AND status = 'active';
CREATE UNIQUE INDEX idx_enrolments_idempotency
    ON memberships_enrolments(business_id, idempotency_key)
    WHERE idempotency_key IS NOT NULL AND deleted_at IS NULL;

CREATE TABLE memberships_enrolment_status_history (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    business_id UUID NOT NULL REFERENCES businesses(id),
    enrolment_id UUID NOT NULL REFERENCES memberships_enrolments(id) ON DELETE CASCADE,
    from_status TEXT,
    to_status TEXT NOT NULL,
    actor_identity_id UUID REFERENCES platform_identities(id),
    reason TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_enrolment_status_history
    ON memberships_enrolment_status_history(enrolment_id, created_at DESC);

-- ============================================================
-- UPDATED_AT TRIGGERS
-- ============================================================
CREATE TRIGGER trg_leads_updated_at BEFORE UPDATE ON leads_leads
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();
CREATE TRIGGER trg_lead_notes_updated_at BEFORE UPDATE ON leads_lead_notes
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();
CREATE TRIGGER trg_membership_plans_updated_at BEFORE UPDATE ON memberships_plans
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();
CREATE TRIGGER trg_enrolments_updated_at BEFORE UPDATE ON memberships_enrolments
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

-- ============================================================
-- ROW LEVEL SECURITY (business-scoped read; service role bypasses for writes,
-- mirroring every prior kernel migration)
-- ============================================================
ALTER TABLE leads_leads ENABLE ROW LEVEL SECURITY;
ALTER TABLE leads_lead_status_history ENABLE ROW LEVEL SECURITY;
ALTER TABLE leads_lead_notes ENABLE ROW LEVEL SECURITY;
ALTER TABLE memberships_plans ENABLE ROW LEVEL SECURITY;
ALTER TABLE memberships_plan_offering_access ENABLE ROW LEVEL SECURITY;
ALTER TABLE memberships_enrolments ENABLE ROW LEVEL SECURITY;
ALTER TABLE memberships_enrolment_status_history ENABLE ROW LEVEL SECURITY;

CREATE POLICY leads_read ON leads_leads FOR SELECT USING (
    deleted_at IS NULL AND business_id = current_business_id()
);
CREATE POLICY lead_status_history_read ON leads_lead_status_history FOR SELECT USING (
    business_id = current_business_id()
);
CREATE POLICY lead_notes_read ON leads_lead_notes FOR SELECT USING (
    deleted_at IS NULL AND business_id = current_business_id()
);
CREATE POLICY membership_plans_read ON memberships_plans FOR SELECT USING (
    deleted_at IS NULL AND business_id = current_business_id()
);
CREATE POLICY plan_offering_access_read ON memberships_plan_offering_access FOR SELECT USING (
    business_id = current_business_id()
);
CREATE POLICY enrolments_read ON memberships_enrolments FOR SELECT USING (
    deleted_at IS NULL AND business_id = current_business_id()
);
CREATE POLICY enrolment_status_history_read ON memberships_enrolment_status_history FOR SELECT USING (
    business_id = current_business_id()
);
