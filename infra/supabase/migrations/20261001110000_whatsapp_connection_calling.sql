-- WhatsApp connection states and calls.
--
-- Checked against Meta's current WhatsApp Business Platform documentation on
-- 2026-09-30 (docs/current-build/WHATSAPP-CALLING-SETUP.md): after Embedded
-- Signup a Tech Provider exchanges the code, subscribes the app to the WABA's
-- webhooks AND registers the business phone number (POST /{id}/register with a
-- two-step PIN). Until the number is registered it cannot send; the channel
-- now records that step instead of calling itself connected after the code
-- exchange alone.
--
-- Calls (WhatsApp Business Calling API, and later a PSTN provider) are their
-- own records: who called whom, when, what happened, who handled it, and what
-- it led to. No SDP, media or tokens are stored in them.

ALTER TABLE messaging_channels
    ADD COLUMN phone_registered_at TIMESTAMPTZ,
    ADD COLUMN registration_error TEXT CHECK (registration_error IS NULL OR char_length(registration_error) <= 500),
    ADD COLUMN calling_status TEXT NOT NULL DEFAULT 'off' CHECK (calling_status IN ('off', 'enabled')),
    ADD COLUMN calling_checked_at TIMESTAMPTZ,
    ADD COLUMN calling_error TEXT CHECK (calling_error IS NULL OR char_length(calling_error) <= 500);

-- Numbers already connected went through a path that could only succeed once
-- the number worked (the sandbox, or a real send). Keep them as they were.
UPDATE messaging_channels SET phone_registered_at = COALESCE(connected_at, created_at) WHERE status = 'connected';

CREATE TABLE calls_sessions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    business_id UUID NOT NULL REFERENCES businesses(id),
    channel TEXT NOT NULL CHECK (channel IN ('whatsapp_call', 'pstn')),
    provider TEXT NOT NULL CHECK (char_length(provider) BETWEEN 1 AND 40),
    direction TEXT NOT NULL CHECK (direction IN ('inbound', 'outbound')),
    external_call_id TEXT NOT NULL CHECK (char_length(external_call_id) BETWEEN 1 AND 200),
    from_number TEXT CHECK (from_number IS NULL OR char_length(from_number) <= 32),
    to_number TEXT CHECK (to_number IS NULL OR char_length(to_number) <= 32),
    customer_contact_id UUID REFERENCES customer_relationships_contacts(id),
    state TEXT NOT NULL DEFAULT 'ringing'
        CHECK (state IN ('ringing', 'accepted', 'connected', 'ended', 'missed', 'rejected', 'failed')),
    handled_by_type TEXT NOT NULL DEFAULT 'none' CHECK (handled_by_type IN ('none', 'human', 'ai_employee')),
    handled_by_id UUID,
    within_business_hours BOOLEAN,
    started_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    answered_at TIMESTAMPTZ,
    ended_at TIMESTAMPTZ,
    duration_seconds INTEGER CHECK (duration_seconds IS NULL OR duration_seconds >= 0),
    end_status TEXT CHECK (end_status IS NULL OR char_length(end_status) <= 40),
    -- What the call led to (a booking, a lead, an order), by reference only.
    related_type TEXT CHECK (related_type IS NULL OR related_type IN ('booking', 'lead', 'order', 'payment_request')),
    related_id UUID,
    -- Human / AI hand-offs, in order: [{"at", "from", "to", "why"}].
    handoffs JSONB NOT NULL DEFAULT '[]'::jsonb,
    note TEXT CHECK (note IS NULL OR char_length(note) <= 500),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    version INTEGER NOT NULL DEFAULT 1,
    UNIQUE (business_id, channel, external_call_id)
);
CREATE INDEX calls_sessions_recent ON calls_sessions (business_id, started_at DESC);
CREATE TRIGGER calls_sessions_updated BEFORE UPDATE ON calls_sessions
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

-- Whether a customer has allowed this business to call them on WhatsApp
-- (call_permission_reply). A business never calls without one.
CREATE TABLE calls_permissions (
    business_id UUID NOT NULL REFERENCES businesses(id),
    wa_id TEXT NOT NULL CHECK (wa_id ~ '^[0-9]{8,15}$'),
    customer_contact_id UUID REFERENCES customer_relationships_contacts(id),
    status TEXT NOT NULL CHECK (status IN ('requested', 'granted', 'rejected')),
    is_permanent BOOLEAN NOT NULL DEFAULT false,
    expires_at TIMESTAMPTZ,
    -- Timestamps of permission requests sent (Meta: at most 1 a day, 2 a week).
    requests JSONB NOT NULL DEFAULT '[]'::jsonb,
    source TEXT CHECK (source IS NULL OR char_length(source) <= 40),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (business_id, wa_id)
);

DO $$
DECLARE t TEXT;
BEGIN
    FOREACH t IN ARRAY ARRAY['calls_sessions', 'calls_permissions'] LOOP
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
