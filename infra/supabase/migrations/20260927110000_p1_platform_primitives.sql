-- Phase B · P1-02 — shared platform primitives
-- Source: LOCAH Business Capability Universe §24.1 #3–#9 and #12, §2 rules 11 and 13,
-- §10.4 (ladder rules), §14.2 and §14.4 (numbering), §25.1 (DPDP consent).
--
-- Every table is business-scoped, RLS-enforced for the API role, and read
-- only through the API (anon gets nothing). The worker connects as the owner
-- role and bypasses RLS to process due automation steps across tenants.

-- ---------------------------------------------------------------------------
-- #4 Automation ladders. One engine for every timed sequence tied to an
-- entity (renewals, reminders, recalls, dunning). A rule row is the owner's
-- switch and edits for one ladder; a step row is one scheduled action and
-- doubles as the owner-visible activity log (§2 rule 11: idempotent, visible,
-- switchable off).
-- ---------------------------------------------------------------------------
CREATE TABLE automation_rules (
    business_id UUID NOT NULL REFERENCES businesses(id),
    ladder_key TEXT NOT NULL CHECK (ladder_key ~ '^[a-z][a-z0-9_.]{2,60}$'),
    enabled BOOLEAN NOT NULL DEFAULT true,
    -- Owner edits to the ladder's defaults: step offsets, disabled steps,
    -- quiet hours. Validated by the application registry.
    config JSONB NOT NULL DEFAULT '{}'::jsonb,
    updated_by UUID REFERENCES platform_identities(id),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (business_id, ladder_key)
);

CREATE TABLE automation_steps (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    business_id UUID NOT NULL REFERENCES businesses(id),
    ladder_key TEXT NOT NULL,
    step_key TEXT NOT NULL,
    entity_type TEXT NOT NULL,
    entity_id UUID NOT NULL,
    -- Which occurrence this belongs to (a membership's period number, an
    -- invoice's due date...). Part of the idempotency key, so a replayed
    -- webhook or a re-run schedule can never create a second step.
    period_key TEXT NOT NULL DEFAULT '',
    idempotency_key TEXT NOT NULL,
    due_at TIMESTAMPTZ NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending' CHECK (status IN (
        'pending', 'processing', 'done', 'skipped', 'cancelled', 'failed'
    )),
    attempts INTEGER NOT NULL DEFAULT 0,
    context JSONB NOT NULL DEFAULT '{}'::jsonb,
    -- What happened, in words the owner can read ("Reminder sent to Priya on
    -- WhatsApp", "Skipped: renewed on 28 Sep").
    outcome TEXT,
    result JSONB,
    leased_until TIMESTAMPTZ,
    leased_by TEXT,
    executed_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT automation_steps_idempotency UNIQUE (business_id, idempotency_key)
);

CREATE INDEX automation_steps_due ON automation_steps (due_at)
    WHERE status IN ('pending', 'processing');
CREATE INDEX automation_steps_entity ON automation_steps (business_id, entity_type, entity_id);
CREATE INDEX automation_steps_log ON automation_steps (business_id, created_at DESC);

-- ---------------------------------------------------------------------------
-- #5 Number series. Gapless, row-locked: one row per series × financial
-- year, allocated inside the transaction that creates the document, so a
-- rolled-back document never burns a number. Offline registers reserve
-- blocks while online (§14.2, default 50).
-- ---------------------------------------------------------------------------
CREATE TABLE number_series (
    business_id UUID NOT NULL REFERENCES businesses(id),
    series_key TEXT NOT NULL,          -- e.g. 'invoice:33ABCDE1234F1Z5:CHN1'
    period TEXT NOT NULL DEFAULT '',   -- financial year '26-27', or '' when not periodic
    prefix TEXT NOT NULL DEFAULT '',
    pad INTEGER NOT NULL DEFAULT 6 CHECK (pad BETWEEN 1 AND 12),
    next_value BIGINT NOT NULL DEFAULT 1 CHECK (next_value >= 1),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (business_id, series_key, period)
);

CREATE TABLE number_series_blocks (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    business_id UUID NOT NULL REFERENCES businesses(id),
    series_key TEXT NOT NULL,
    period TEXT NOT NULL DEFAULT '',
    holder TEXT NOT NULL,              -- the register / device that holds the block
    start_value BIGINT NOT NULL,
    end_value BIGINT NOT NULL,
    status TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'exhausted', 'released')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CHECK (end_value >= start_value)
);
CREATE INDEX number_series_blocks_holder ON number_series_blocks (business_id, series_key, period, holder)
    WHERE status = 'active';

-- ---------------------------------------------------------------------------
-- #7 Document renderer. PDFs rendered from structured data are stored with
-- their SHA-256, so the copy a customer received can be proven unchanged.
-- ---------------------------------------------------------------------------
CREATE TABLE rendered_documents (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    business_id UUID NOT NULL REFERENCES businesses(id),
    doc_type TEXT NOT NULL,            -- invoice, credit_note, quote, receipt, certificate, report_card...
    source_type TEXT NOT NULL,
    source_id UUID NOT NULL,
    version INTEGER NOT NULL DEFAULT 1 CHECK (version >= 1),
    layout TEXT NOT NULL DEFAULT 'a4' CHECK (layout IN ('a4', 'thermal_58', 'thermal_80')),
    media_type TEXT NOT NULL DEFAULT 'application/pdf',
    sha256 TEXT NOT NULL CHECK (sha256 ~ '^[0-9a-f]{64}$'),
    size_bytes INTEGER NOT NULL,
    content BYTEA NOT NULL,
    created_by UUID REFERENCES platform_identities(id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT rendered_documents_version UNIQUE (business_id, source_type, source_id, doc_type, layout, version)
);
CREATE INDEX rendered_documents_source ON rendered_documents (business_id, source_type, source_id);

-- ---------------------------------------------------------------------------
-- #8 Consent store (DPDP Act, WhatsApp marketing). One row per grant; a
-- withdrawal closes the row, a re-grant opens a new one, so the history of
-- what the customer agreed to, when and how is never overwritten.
-- ---------------------------------------------------------------------------
CREATE TABLE customer_consents (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    business_id UUID NOT NULL REFERENCES businesses(id),
    contact_id UUID NOT NULL REFERENCES customer_relationships_contacts(id),
    purpose TEXT NOT NULL CHECK (purpose IN (
        'transactional', 'marketing', 'reminders', 'photos_public', 'data_processing', 'forecast_sharing'
    )),
    channel TEXT NOT NULL CHECK (channel IN ('whatsapp', 'sms', 'email', 'call', 'any')),
    source TEXT NOT NULL,              -- 'checkout_checkbox', 'whatsapp_opt_in', 'staff_recorded', 'my_activity'...
    evidence JSONB NOT NULL DEFAULT '{}'::jsonb,
    granted_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    withdrawn_at TIMESTAMPTZ,
    withdrawn_source TEXT,
    recorded_by UUID REFERENCES platform_identities(id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CHECK (withdrawn_at IS NULL OR withdrawn_at >= granted_at)
);
CREATE UNIQUE INDEX customer_consents_one_open
    ON customer_consents (business_id, contact_id, purpose, channel) WHERE withdrawn_at IS NULL;
CREATE INDEX customer_consents_contact ON customer_consents (business_id, contact_id);

-- ---------------------------------------------------------------------------
-- #9 Usage meters (§2 rule 13). Every metered cost is counted per business per
-- month with an optional cap; usage_events make each count idempotent.
-- ---------------------------------------------------------------------------
CREATE TABLE usage_meters (
    business_id UUID NOT NULL REFERENCES businesses(id),
    resource TEXT NOT NULL CHECK (resource IN (
        'whatsapp_message', 'sms_message', 'email_message', 'voice_minute', 'maps_call', 'model_tokens'
    )),
    period TEXT NOT NULL CHECK (period ~ '^[0-9]{4}-[0-9]{2}$'),
    used BIGINT NOT NULL DEFAULT 0 CHECK (used >= 0),
    cap BIGINT CHECK (cap IS NULL OR cap >= 0),
    alerted_pct INTEGER NOT NULL DEFAULT 0,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (business_id, resource, period)
);

CREATE TABLE usage_events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    business_id UUID NOT NULL REFERENCES businesses(id),
    resource TEXT NOT NULL,
    period TEXT NOT NULL,
    quantity BIGINT NOT NULL CHECK (quantity > 0),
    idempotency_key TEXT NOT NULL,
    context JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT usage_events_idempotency UNIQUE (business_id, idempotency_key)
);
CREATE INDEX usage_events_period ON usage_events (business_id, resource, period);

-- ---------------------------------------------------------------------------
-- #12 Offline sync. A device queues mutations with its own UUIDs while
-- offline; replaying the queue is idempotent on (business, client id).
-- ---------------------------------------------------------------------------
CREATE TABLE offline_mutations (
    business_id UUID NOT NULL REFERENCES businesses(id),
    client_mutation_id UUID NOT NULL,
    device_id TEXT NOT NULL,
    kind TEXT NOT NULL,
    payload JSONB NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('applied', 'rejected')),
    result JSONB,
    client_created_at TIMESTAMPTZ,
    applied_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    applied_by UUID REFERENCES platform_identities(id),
    PRIMARY KEY (business_id, client_mutation_id)
);
CREATE INDEX offline_mutations_device ON offline_mutations (business_id, device_id, applied_at DESC);

-- ---------------------------------------------------------------------------
-- RLS: tenant predicate for the API role; nothing for anon.
-- ---------------------------------------------------------------------------
DO $$
DECLARE t TEXT;
BEGIN
    FOREACH t IN ARRAY ARRAY['automation_rules', 'automation_steps', 'number_series', 'number_series_blocks',
                             'rendered_documents', 'customer_consents', 'usage_meters', 'usage_events',
                             'offline_mutations']
    LOOP
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
