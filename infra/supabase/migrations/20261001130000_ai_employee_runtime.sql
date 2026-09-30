-- AI employee runtime (Capability Universe §8; ledger AN AI-13..AI-18, PM-14, PR-05).
--
-- One shared runtime, not one bot per feature. An AI employee is staff with a
-- role: a kind, an autonomy ceiling, a tool allowlist, limits and a kill
-- switch. It acts only through the same services people use; every action is
-- an ai_actions row. Limits and tiers are enforced in the service
-- (platform_core/ai_employees/runtime.py) — a prompt, a customer message or
-- the employee itself can never change them: no tool writes these tables.
--
-- Tiers: T0 read, T1 draft, T2 act within owner limits, T3 owner approval always.

CREATE TABLE ai_employees (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    business_id UUID NOT NULL REFERENCES businesses(id),
    kind TEXT NOT NULL CHECK (kind IN ('receptionist', 'collections', 'procurement')),
    display_name TEXT NOT NULL,
    -- The highest tier it may use without asking. T3 tools always ask.
    autonomy TEXT NOT NULL DEFAULT 'T1' CHECK (autonomy IN ('T0', 'T1', 'T2')),
    tools TEXT[] NOT NULL DEFAULT '{}',
    limits JSONB NOT NULL DEFAULT '{}'::jsonb,
    enabled BOOLEAN NOT NULL DEFAULT false,
    updated_by UUID REFERENCES platform_identities(id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (business_id, kind)
);

-- The global pause: one switch for every AI employee of a business.
CREATE TABLE ai_employee_controls (
    business_id UUID PRIMARY KEY REFERENCES businesses(id),
    paused BOOLEAN NOT NULL DEFAULT false,
    paused_at TIMESTAMPTZ,
    paused_by UUID REFERENCES platform_identities(id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE ai_actions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    business_id UUID NOT NULL REFERENCES businesses(id),
    ai_employee_id UUID NOT NULL REFERENCES ai_employees(id),
    tool TEXT NOT NULL,
    tier TEXT NOT NULL CHECK (tier IN ('T0', 'T1', 'T2', 'T3')),
    -- Summaries only: never a secret, a token, a card number or a whole message thread.
    input_summary TEXT NOT NULL DEFAULT '',
    result_summary TEXT NOT NULL DEFAULT '',
    related_type TEXT,
    related_id UUID,
    status TEXT NOT NULL CHECK (status IN ('done', 'drafted', 'awaiting_approval', 'approved', 'rejected',
                                           'refused', 'failed', 'escalated')),
    approval_required BOOLEAN NOT NULL DEFAULT false,
    approval_status TEXT CHECK (approval_status IS NULL OR approval_status IN ('pending', 'approved', 'rejected')),
    -- What a T3 action will do once approved (ids and amounts, no secrets).
    pending_args JSONB,
    reason TEXT NOT NULL DEFAULT '',
    source TEXT NOT NULL DEFAULT '',
    conversation_id UUID,
    model TEXT,
    tokens_in INTEGER,
    tokens_out INTEGER,
    decided_by UUID REFERENCES platform_identities(id),
    decided_at TIMESTAMPTZ,
    started_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    completed_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_ai_actions_business_recent ON ai_actions (business_id, created_at DESC);
CREATE INDEX idx_ai_actions_pending ON ai_actions (business_id) WHERE approval_status = 'pending';
CREATE INDEX idx_ai_actions_employee ON ai_actions (ai_employee_id, created_at DESC);

CREATE TRIGGER trg_ai_employees_updated_at BEFORE UPDATE ON ai_employees
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();
CREATE TRIGGER trg_ai_employee_controls_updated_at BEFORE UPDATE ON ai_employee_controls
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

-- A message the AI employee sent is marked as its own in the inbox.
ALTER TABLE messaging_messages DROP CONSTRAINT IF EXISTS messaging_messages_sent_via_check;
ALTER TABLE messaging_messages ADD CONSTRAINT messaging_messages_sent_via_check
    CHECK (sent_via IN ('workspace', 'automation', 'journey', 'business_app', 'ai_employee'));

-- ---------------------------------------------------------------- RLS
DO $$
DECLARE t TEXT;
BEGIN
    FOREACH t IN ARRAY ARRAY['ai_employees', 'ai_employee_controls', 'ai_actions'] LOOP
        EXECUTE format('ALTER TABLE %I ENABLE ROW LEVEL SECURITY', t);
        EXECUTE format('ALTER TABLE %I FORCE ROW LEVEL SECURITY', t);
        EXECUTE format('CREATE POLICY %I ON %I FOR SELECT TO public USING (business_id = current_business_id())',
                       t || '_member_read', t);
        EXECUTE format('CREATE POLICY %I ON %I FOR ALL TO platform_api USING (business_id = current_business_id()) '
                       'WITH CHECK (business_id = current_business_id())', t || '_api', t);
        EXECUTE format('GRANT SELECT, INSERT, UPDATE ON %I TO platform_api', t);
        EXECUTE format('REVOKE DELETE ON %I FROM platform_api', t);
        EXECUTE format('REVOKE ALL PRIVILEGES ON TABLE %I FROM anon', t);
    END LOOP;
END
$$;
