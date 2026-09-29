-- Kitchen preparation (Capability Universe §6.2 `kitchen`, §7.1 Kitchen display, §7.2 Kitchen).
--
-- The sales order stays the commercial record. These tables are preparation
-- truth only: a kitchen ticket (KOT), the lines each station cooks, and the
-- visible events when an order changes after cooking has started.
--
-- Nothing here decrements stock. When a ticket is served the kitchen publishes
-- `kitchen.preparation.completed`. Recipe and BOM consumption belongs to the
-- Inventory/Recipe lane, which subscribes to that event after the branches combine.

CREATE TABLE kitchen_stations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    business_id UUID NOT NULL REFERENCES businesses(id),
    -- Null means the station covers every location of the business.
    location_id UUID REFERENCES business_locations(id),
    key TEXT NOT NULL CHECK (key ~ '^[a-z][a-z0-9_]{1,31}$'),
    name TEXT NOT NULL CHECK (char_length(btrim(name)) BETWEEN 1 AND 40),
    sort_order INTEGER NOT NULL DEFAULT 0,
    active BOOLEAN NOT NULL DEFAULT true,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (business_id, key)
);

CREATE TABLE kitchen_station_routes (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    business_id UUID NOT NULL REFERENCES businesses(id),
    offering_id UUID NOT NULL REFERENCES offerings_catalog_offerings(id),
    station_id UUID NOT NULL REFERENCES kitchen_stations(id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (offering_id, station_id)
);
CREATE INDEX kitchen_station_routes_business ON kitchen_station_routes (business_id, offering_id);

-- One KOT number series per business. Not an order number.
CREATE TABLE kitchen_counters (
    business_id UUID PRIMARY KEY REFERENCES businesses(id),
    next_number INTEGER NOT NULL DEFAULT 1 CHECK (next_number >= 1)
);

CREATE TABLE kitchen_tickets (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    business_id UUID NOT NULL REFERENCES businesses(id),
    location_id UUID NOT NULL REFERENCES business_locations(id),
    -- The commercial order this preparation belongs to. One ticket per order.
    order_id UUID NOT NULL REFERENCES orders_orders(id),
    ticket_number TEXT NOT NULL,
    channel TEXT NOT NULL,
    service_mode TEXT NOT NULL CHECK (service_mode IN ('dine_in', 'takeaway', 'pickup', 'delivery', 'counter')),
    service_label TEXT NOT NULL,
    priority TEXT NOT NULL DEFAULT 'normal' CHECK (priority IN ('normal', 'rush')),
    status TEXT NOT NULL DEFAULT 'new' CHECK (status IN ('new', 'preparing', 'ready', 'completed', 'cancelled')),
    -- Set when the order changed after cooking started. The prep facts stay.
    attention TEXT CHECK (attention IS NULL OR attention IN ('cancel', 'adjust')),
    notes TEXT NOT NULL DEFAULT '',
    entered_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    started_at TIMESTAMPTZ,
    ready_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    -- True once kitchen.preparation.completed has been published for this ticket.
    consumption_published BOOLEAN NOT NULL DEFAULT false,
    version INTEGER NOT NULL DEFAULT 1,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (business_id, order_id),
    UNIQUE (business_id, ticket_number)
);
CREATE INDEX kitchen_tickets_board ON kitchen_tickets (business_id, status, entered_at);

CREATE TABLE kitchen_ticket_lines (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    business_id UUID NOT NULL REFERENCES businesses(id),
    location_id UUID NOT NULL REFERENCES business_locations(id),
    ticket_id UUID NOT NULL REFERENCES kitchen_tickets(id),
    -- Snapshot reference. Not a second order line, and not rewritten after start.
    order_line_id UUID NOT NULL,
    station_id UUID NOT NULL REFERENCES kitchen_stations(id),
    offering_id UUID NOT NULL,
    variant_id UUID,
    title TEXT NOT NULL,
    quantity INTEGER NOT NULL CHECK (quantity > 0),
    modifiers JSONB NOT NULL DEFAULT '{}'::jsonb,
    modifier_lines TEXT[] NOT NULL DEFAULT '{}',
    prep_status TEXT NOT NULL DEFAULT 'new'
        CHECK (prep_status IN ('new', 'preparing', 'ready', 'completed', 'cancelled')),
    origin TEXT NOT NULL DEFAULT 'original' CHECK (origin IN ('original', 'added')),
    attention TEXT CHECK (attention IS NULL OR attention IN ('cancel', 'adjust')),
    entered_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    started_at TIMESTAMPTZ,
    ready_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ
);
-- One original line per station. Added lines (a later quantity) are extra rows.
CREATE UNIQUE INDEX kitchen_ticket_lines_original
    ON kitchen_ticket_lines (ticket_id, order_line_id, station_id)
    WHERE origin = 'original';
CREATE INDEX kitchen_ticket_lines_ticket ON kitchen_ticket_lines (ticket_id);

-- Visible preparation history. Cancel and adjustment rows are what the pass reads
-- when the order changes after cooking has started. Append-only.
CREATE TABLE kitchen_line_events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    business_id UUID NOT NULL REFERENCES businesses(id),
    location_id UUID NOT NULL REFERENCES business_locations(id),
    ticket_id UUID NOT NULL REFERENCES kitchen_tickets(id),
    line_id UUID REFERENCES kitchen_ticket_lines(id),
    kind TEXT NOT NULL,
    summary TEXT NOT NULL,
    detail JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX kitchen_line_events_ticket ON kitchen_line_events (ticket_id, created_at);

-- One row per outbox event the kitchen has applied. Replaying the event inserts nothing.
CREATE TABLE kitchen_intakes (
    event_id UUID PRIMARY KEY,
    business_id UUID NOT NULL REFERENCES businesses(id),
    order_id UUID NOT NULL,
    action TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ---------------------------------------------------------------- RLS
-- Business-scoped for the API role. Tickets, lines and events also respect
-- location scope: a cook limited to one location cannot read another's pass.
DO $$
DECLARE t TEXT;
BEGIN
    FOREACH t IN ARRAY ARRAY[
        'kitchen_stations', 'kitchen_station_routes', 'kitchen_counters',
        'kitchen_tickets', 'kitchen_ticket_lines', 'kitchen_line_events', 'kitchen_intakes'
    ] LOOP
        EXECUTE format('ALTER TABLE %I ENABLE ROW LEVEL SECURITY', t);
        EXECUTE format('ALTER TABLE %I FORCE ROW LEVEL SECURITY', t);
        EXECUTE format(
            'CREATE POLICY %I ON %I FOR SELECT TO public USING (business_id = current_business_id())',
            t || '_member_read', t);
        EXECUTE format(
            'CREATE POLICY %I ON %I FOR ALL TO platform_api USING (business_id = current_business_id()) '
            'WITH CHECK (business_id = current_business_id())',
            t || '_api_write', t);
        EXECUTE format('REVOKE ALL PRIVILEGES ON TABLE %I FROM anon', t);
    END LOOP;

    FOREACH t IN ARRAY ARRAY[
        'kitchen_stations', 'kitchen_station_routes', 'kitchen_counters',
        'kitchen_tickets', 'kitchen_ticket_lines'
    ] LOOP
        EXECUTE format('GRANT SELECT, INSERT, UPDATE, DELETE ON %I TO platform_api', t);
    END LOOP;

    -- Events and the intake log are append-only for the API role.
    EXECUTE 'GRANT SELECT, INSERT ON kitchen_line_events TO platform_api';
    EXECUTE 'GRANT SELECT, INSERT ON kitchen_intakes TO platform_api';
    EXECUTE 'REVOKE UPDATE, DELETE ON kitchen_line_events FROM platform_api';
    EXECUTE 'REVOKE UPDATE, DELETE ON kitchen_intakes FROM platform_api';

    FOREACH t IN ARRAY ARRAY['kitchen_tickets', 'kitchen_ticket_lines', 'kitchen_line_events', 'kitchen_stations'] LOOP
        EXECUTE format(
            'CREATE POLICY %I ON %I AS RESTRICTIVE FOR ALL TO platform_api '
            'USING (location_scope_allows(location_id)) WITH CHECK (location_scope_allows(location_id))',
            t || '_location_scope', t);
    END LOOP;
END
$$;
