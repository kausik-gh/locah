-- Stage 7: Core Notifications (Platform Core group `core-notifications`)
-- Authority: Doc 09 CORE-015 (Notifications page), Doc 11 §17.7 (Stage 7 scope),
--            Doc 12 §5.5 (standard columns), §5.7 (status as text + CHECK, never ENUM)
--
-- Platform Core, not an optional module: always entitled, so routes carry gates
-- [1]-[5] + [8] but NOT the [6] entitlement / [7] module-state gates (AUD-01 rule).
-- Table prefix `platform_` matches the other Platform Core tables.

-- ============================================================
-- NOTIFICATIONS — business-scoped, per-recipient
-- ============================================================
CREATE TABLE platform_notifications (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    business_id UUID NOT NULL REFERENCES businesses(id),
    -- Recipient is a Platform Identity holding a membership in this Business.
    recipient_identity_id UUID NOT NULL REFERENCES platform_identities(id),
    -- Canonical event-ish type, e.g. 'order.placed', 'invitation.received'.
    notification_type TEXT NOT NULL,
    -- Grouping for filters + preference toggles (Doc 09 CORE-015 "activity type").
    category TEXT NOT NULL DEFAULT 'operational'
        CHECK (category IN ('operational', 'commercial', 'access', 'platform')),
    severity TEXT NOT NULL DEFAULT 'info'
        CHECK (severity IN ('info', 'warning', 'critical')),
    title TEXT NOT NULL,
    body TEXT,
    -- "Open destination" (Doc 09 CORE-015): resource the notification points at.
    -- Cross-module reference by stable ID, no FK (Doc 12 §5.10).
    resource_type TEXT,
    resource_id UUID,
    -- Location scoping so Location-scoped members only see their own (Doc 09 §9.1).
    location_id UUID REFERENCES business_locations(id),
    payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    read_at TIMESTAMPTZ,
    correlation_id TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    deleted_at TIMESTAMPTZ,
    version INTEGER NOT NULL DEFAULT 1
);

-- Primary read path: one recipient's inbox within one Business, newest first.
CREATE INDEX idx_notifications_recipient
    ON platform_notifications (business_id, recipient_identity_id, created_at DESC)
    WHERE deleted_at IS NULL;
-- Unread badge count.
CREATE INDEX idx_notifications_unread
    ON platform_notifications (business_id, recipient_identity_id)
    WHERE deleted_at IS NULL AND read_at IS NULL;
CREATE INDEX idx_notifications_type
    ON platform_notifications (business_id, notification_type)
    WHERE deleted_at IS NULL;
-- Idempotent fan-out: one notification per (recipient, type, resource) per event.
CREATE UNIQUE INDEX uq_notifications_dedupe
    ON platform_notifications (recipient_identity_id, notification_type, resource_id, correlation_id)
    WHERE deleted_at IS NULL AND resource_id IS NOT NULL AND correlation_id IS NOT NULL;

-- ============================================================
-- PREFERENCES — per identity, per Business, per category
-- Backs NOTIFICATIONS_MANAGE_PREFERENCES, which already exists in permissions.py.
-- In-app only at First Launch; email/SMS channels are Post-MVP (Doc 09 §"Messaging"
-- is Conditional MVP), so no channel columns are invented here.
-- ============================================================
CREATE TABLE platform_notification_preferences (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    business_id UUID NOT NULL REFERENCES businesses(id),
    identity_id UUID NOT NULL REFERENCES platform_identities(id),
    category TEXT NOT NULL
        CHECK (category IN ('operational', 'commercial', 'access', 'platform')),
    in_app_enabled BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    deleted_at TIMESTAMPTZ,
    version INTEGER NOT NULL DEFAULT 1,
    UNIQUE (business_id, identity_id, category)
);

CREATE INDEX idx_notification_prefs_identity
    ON platform_notification_preferences (business_id, identity_id)
    WHERE deleted_at IS NULL;

-- ============================================================
-- UPDATED_AT TRIGGERS
-- ============================================================
CREATE TRIGGER trg_notifications_updated_at BEFORE UPDATE ON platform_notifications
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();
CREATE TRIGGER trg_notification_prefs_updated_at BEFORE UPDATE ON platform_notification_preferences
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

-- ============================================================
-- ROW LEVEL SECURITY
-- Stricter than the other kernels: a notification is readable only by its own
-- recipient, not by every member of the Business (no cross-identity leakage,
-- Doc 09 ACC-011). Service role bypasses for writes, as in every prior migration.
-- ============================================================
ALTER TABLE platform_notifications ENABLE ROW LEVEL SECURITY;
ALTER TABLE platform_notification_preferences ENABLE ROW LEVEL SECURITY;

CREATE POLICY notifications_read ON platform_notifications FOR SELECT USING (
    deleted_at IS NULL
    AND business_id = current_business_id()
    AND recipient_identity_id = current_identity_id()
);
CREATE POLICY notification_prefs_read ON platform_notification_preferences FOR SELECT USING (
    deleted_at IS NULL
    AND business_id = current_business_id()
    AND identity_id = current_identity_id()
);
