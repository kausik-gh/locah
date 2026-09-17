-- Event subscription registry — per-subscriber delivery for domain events.
--
-- Until now `platform_outbox_events` carried the delivery state itself:
-- one `status`, one `attempt_count`, one `last_error` per event. That models
-- "this event has one consumer" and it was true while the worker's dispatch
-- was two hardcoded `if` branches. It stops being true the moment a second
-- capability cares about the same event, because a retry re-runs the handlers
-- that already succeeded — an `order.created` retried for a failed messaging
-- send would decrement inventory twice.
--
-- Delivery state therefore moves down a level, to (event, subscriber). The
-- outbox row keeps its lease and becomes a fan-out record: it completes when
-- every subscriber registered for its type has reached a terminal state, and
-- each subscriber retries on its own clock without disturbing the others.
--
-- An event with no subscribers is complete, not a dead letter. That is the
-- point: a capability can emit its own events before anything consumes them,
-- and a new consumer registers itself in code rather than by editing the
-- worker. Unknown-event-type protection moves to the event catalogue
-- (platform_core.events.catalogue), which is checked at publish time where a
-- typo is actually attributable, instead of in the worker hours later.

CREATE TABLE platform_event_deliveries (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    event_id UUID NOT NULL REFERENCES platform_outbox_events(id) ON DELETE CASCADE,
    subscriber_id TEXT NOT NULL,
    event_type TEXT NOT NULL,
    business_id UUID,
    status TEXT NOT NULL DEFAULT 'pending'
        CHECK (status IN ('pending', 'processing', 'completed', 'failed', 'dead_letter')),
    attempt_count INTEGER NOT NULL DEFAULT 0,
    max_attempts INTEGER NOT NULL DEFAULT 5,
    next_attempt_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    leased_until TIMESTAMPTZ,
    leased_by TEXT,
    last_error TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    processed_at TIMESTAMPTZ,

    -- The idempotency guarantee: one delivery row per subscriber per event.
    -- Fan-out uses ON CONFLICT DO NOTHING against this, so re-claiming an
    -- event whose lease expired mid-fan-out cannot duplicate deliveries.
    CONSTRAINT platform_event_deliveries_event_subscriber_key
        UNIQUE (event_id, subscriber_id)
);

-- The worker's claim query: due, unleased, not terminal.
CREATE INDEX idx_event_deliveries_due ON platform_event_deliveries(next_attempt_at)
    WHERE status IN ('pending', 'failed', 'processing');

-- Completion check on the parent event ("are all my deliveries terminal?").
CREATE INDEX idx_event_deliveries_event ON platform_event_deliveries(event_id);

-- Operational triage: "what is subscriber X failing on?"
CREATE INDEX idx_event_deliveries_subscriber_status
    ON platform_event_deliveries(subscriber_id, status);

-- Same classification as every other row in 20260802010000: a worker-owned
-- queue, not a tenant resource. `business_id` is carried for triage and for
-- binding tenant context inside a handler, never as an RLS predicate.
ALTER TABLE platform_event_deliveries DISABLE ROW LEVEL SECURITY;

GRANT SELECT, INSERT, UPDATE, DELETE ON platform_event_deliveries TO platform_api;
