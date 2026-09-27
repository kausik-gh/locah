-- Phase B · P1-07 — WhatsApp foundation
-- Source: LOCAH Business Capability Universe §6.2 `messaging` ("business inbox,
-- templates, opt-ins, routing to human or AI, SMS / email"), §9.1 (WhatsApp
-- Cloud API, Embedded Signup per business, coexistence), §12.1 (router; a
-- human reply pauses automation for 12 h), §12.4 (templates, consent), §12.5
-- (workspace inbox), §8.4 / §9.3 (every message is metered), §26.3 P1-07
-- ("owner connects a number and receives order notifications").
--
-- One WhatsApp number per business. The access token is encrypted at rest
-- (platform_core.crypto), never returned to a client.

CREATE TABLE messaging_channels (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    business_id UUID NOT NULL REFERENCES businesses(id),
    kind TEXT NOT NULL DEFAULT 'whatsapp' CHECK (kind IN ('whatsapp')),
    -- meta_cloud: the real WhatsApp Cloud API through Embedded Signup.
    -- sandbox: a local/test stand-in that records messages instead of
    -- delivering them; refused unless MESSAGING_SANDBOX is on.
    provider TEXT NOT NULL CHECK (provider IN ('meta_cloud', 'sandbox')),
    status TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'connected', 'disconnected', 'error')),
    display_phone TEXT CHECK (char_length(display_phone) <= 20),
    display_name TEXT CHECK (char_length(display_name) <= 120),
    phone_number_id TEXT CHECK (char_length(phone_number_id) <= 64),
    waba_id TEXT CHECK (char_length(waba_id) <= 64),
    -- Coexistence: the owner keeps the WhatsApp Business app on the same number.
    coexistence BOOLEAN NOT NULL DEFAULT false,
    quality_rating TEXT CHECK (char_length(quality_rating) <= 20),
    messaging_limit TEXT CHECK (char_length(messaging_limit) <= 40),
    encrypted_token TEXT,
    last_error TEXT CHECK (char_length(last_error) <= 500),
    last_webhook_at TIMESTAMPTZ,
    connected_at TIMESTAMPTZ,
    connected_by UUID REFERENCES platform_identities(id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    version INTEGER NOT NULL DEFAULT 1
);
CREATE UNIQUE INDEX messaging_channels_one_live ON messaging_channels (business_id, kind) WHERE status <> 'disconnected';
CREATE UNIQUE INDEX messaging_channels_phone ON messaging_channels (phone_number_id)
    WHERE phone_number_id IS NOT NULL AND status <> 'disconnected';

-- What the business sends customers automatically, its language, and how long
-- a person's reply keeps automation quiet in that chat.
CREATE TABLE messaging_settings (
    business_id UUID PRIMARY KEY REFERENCES businesses(id),
    language TEXT NOT NULL DEFAULT 'en' CHECK (language IN ('en', 'ta', 'hi')),
    customer_updates JSONB NOT NULL DEFAULT '{}'::jsonb,
    human_pause_hours INTEGER NOT NULL DEFAULT 12 CHECK (human_pause_hours BETWEEN 1 AND 72),
    updated_by UUID REFERENCES platform_identities(id),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    version INTEGER NOT NULL DEFAULT 1
);

-- Approval state of each library template per business (Meta approves per
-- WhatsApp Business Account and language).
CREATE TABLE messaging_templates (
    business_id UUID NOT NULL REFERENCES businesses(id),
    template_key TEXT NOT NULL CHECK (template_key ~ '^[a-z][a-z0-9_]{1,60}$'),
    language TEXT NOT NULL CHECK (language IN ('en', 'ta', 'hi')),
    status TEXT NOT NULL DEFAULT 'submitted' CHECK (status IN ('submitted', 'approved', 'rejected', 'paused')),
    provider_template_id TEXT CHECK (char_length(provider_template_id) <= 64),
    rejected_reason TEXT CHECK (char_length(rejected_reason) <= 300),
    submitted_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    decided_at TIMESTAMPTZ,
    PRIMARY KEY (business_id, template_key, language)
);

CREATE TABLE messaging_conversations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    business_id UUID NOT NULL REFERENCES businesses(id),
    channel_id UUID NOT NULL REFERENCES messaging_channels(id),
    contact_id UUID REFERENCES customer_relationships_contacts(id),
    wa_id TEXT NOT NULL CHECK (wa_id ~ '^[0-9]{6,20}$'),
    -- customer: the inbox. staff: alerts sent to a team member's own phone,
    -- kept for the record but never shown as a customer chat.
    kind TEXT NOT NULL DEFAULT 'customer' CHECK (kind IN ('customer', 'staff')),
    profile_name TEXT CHECK (char_length(profile_name) <= 120),
    state TEXT NOT NULL DEFAULT 'open' CHECK (state IN ('open', 'closed')),
    -- bot: LOCAH's structured replies may answer; person: a person is handling it.
    handler TEXT NOT NULL DEFAULT 'bot' CHECK (handler IN ('bot', 'person')),
    needs_person BOOLEAN NOT NULL DEFAULT false,
    topic TEXT CHECK (topic IN ('order', 'booking', 'lead', 'payment', 'support')),
    assigned_to UUID REFERENCES platform_identities(id),
    unread INTEGER NOT NULL DEFAULT 0 CHECK (unread >= 0),
    last_inbound_at TIMESTAMPTZ,
    last_outbound_at TIMESTAMPTZ,
    last_human_at TIMESTAMPTZ,
    waiting_since TIMESTAMPTZ,
    last_preview TEXT CHECK (char_length(last_preview) <= 200),
    journey JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    version INTEGER NOT NULL DEFAULT 1,
    CONSTRAINT messaging_conversations_one_per_number UNIQUE (channel_id, wa_id)
);
CREATE INDEX messaging_conversations_list ON messaging_conversations (business_id, state, updated_at DESC);
CREATE INDEX messaging_conversations_waiting ON messaging_conversations (business_id, waiting_since)
    WHERE waiting_since IS NOT NULL;
CREATE INDEX messaging_conversations_contact ON messaging_conversations (business_id, contact_id);

CREATE TABLE messaging_messages (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    business_id UUID NOT NULL REFERENCES businesses(id),
    conversation_id UUID NOT NULL REFERENCES messaging_conversations(id),
    direction TEXT NOT NULL CHECK (direction IN ('in', 'out')),
    kind TEXT NOT NULL CHECK (kind IN ('text', 'template', 'interactive', 'button', 'list', 'location', 'media',
                                       'reaction', 'unsupported')),
    body TEXT CHECK (char_length(body) <= 4096),
    payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    template_key TEXT,
    language TEXT,
    -- Meta's pricing categories; inbound messages have none.
    category TEXT CHECK (category IN ('service', 'utility', 'marketing', 'authentication')),
    status TEXT NOT NULL CHECK (status IN ('received', 'queued', 'sent', 'delivered', 'read', 'failed', 'blocked')),
    error TEXT CHECK (char_length(error) <= 500),
    provider_message_id TEXT CHECK (char_length(provider_message_id) <= 128),
    idempotency_key TEXT CHECK (char_length(idempotency_key) <= 160),
    -- workspace (a person), automation (a ladder or notification), journey
    -- (structured flow), business_app (the owner replied from the app).
    sent_via TEXT CHECK (sent_via IN ('workspace', 'automation', 'journey', 'business_app')),
    sent_by UUID REFERENCES platform_identities(id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    status_at TIMESTAMPTZ
);
CREATE INDEX messaging_messages_thread ON messaging_messages (conversation_id, created_at);
-- Webhook deliveries are retried by the provider: one row per message id.
CREATE UNIQUE INDEX messaging_messages_provider_id ON messaging_messages (business_id, provider_message_id)
    WHERE provider_message_id IS NOT NULL;
CREATE UNIQUE INDEX messaging_messages_idempotency ON messaging_messages (business_id, idempotency_key)
    WHERE idempotency_key IS NOT NULL;

-- A staff member's own WhatsApp alerts (new orders, chats waiting, ...),
-- sent from the business number to their phone. They switch it on themselves.
CREATE TABLE messaging_staff_alerts (
    business_id UUID NOT NULL REFERENCES businesses(id),
    identity_id UUID NOT NULL REFERENCES platform_identities(id),
    phone TEXT NOT NULL CHECK (phone ~ '^[0-9]{10,15}$'),
    kinds TEXT[] NOT NULL DEFAULT '{}',
    enabled BOOLEAN NOT NULL DEFAULT true,
    opted_in_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (business_id, identity_id)
);

CREATE TABLE messaging_quick_replies (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    business_id UUID NOT NULL REFERENCES businesses(id),
    title TEXT NOT NULL CHECK (char_length(title) BETWEEN 1 AND 60),
    body TEXT NOT NULL CHECK (char_length(body) BETWEEN 1 AND 1000),
    created_by UUID REFERENCES platform_identities(id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX messaging_quick_replies_business ON messaging_quick_replies (business_id, title);

DO $$
DECLARE t TEXT;
BEGIN
    FOREACH t IN ARRAY ARRAY['messaging_channels', 'messaging_settings', 'messaging_templates',
                             'messaging_conversations', 'messaging_messages', 'messaging_staff_alerts',
                             'messaging_quick_replies'] LOOP
        EXECUTE format('ALTER TABLE %I ENABLE ROW LEVEL SECURITY', t);
        EXECUTE format('ALTER TABLE %I FORCE ROW LEVEL SECURITY', t);
        EXECUTE format('CREATE POLICY %I ON %I FOR ALL TO platform_api USING (business_id = current_business_id()) '
                       'WITH CHECK (business_id = current_business_id())', t || '_api_write', t);
        EXECUTE format('GRANT SELECT, INSERT, UPDATE, DELETE ON %I TO platform_api', t);
        EXECUTE format('REVOKE ALL PRIVILEGES ON TABLE %I FROM anon', t);
    END LOOP;
END
$$;

-- Members read conversations and settings of their business. The channel
-- (it holds the encrypted token) and staff alert phones are read through the
-- API only.
DO $$
DECLARE t TEXT;
BEGIN
    FOREACH t IN ARRAY ARRAY['messaging_settings', 'messaging_templates', 'messaging_conversations',
                             'messaging_messages', 'messaging_quick_replies'] LOOP
        EXECUTE format('CREATE POLICY %I ON %I FOR SELECT TO public USING (business_id = current_business_id())',
                       t || '_member_read', t);
    END LOOP;
END
$$;

-- A webhook arrives unbound: it may find exactly the channel whose phone
-- number id it carries, and nothing else, before binding that business.
CREATE POLICY messaging_channels_webhook_read ON messaging_channels FOR SELECT TO platform_api
    USING (phone_number_id IS NOT NULL
           AND phone_number_id = (SELECT NULLIF(current_setting('app.current_wa_phone_number_id', true), '')));
