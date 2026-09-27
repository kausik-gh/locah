-- Phase B · P1-08 — WhatsApp journeys
-- Source: LOCAH Business Capability Universe §12.3 (P1 column: order, book,
-- enquire, pay / dues, track, reorder, change / cancel, talk to a person —
-- "every path ends in the same LOCAH order, booking or lead the website
-- would create"), §12.4 (confirm with a button; prices and stock only from
-- LOCAH; COD where the owner allows it, with a first-order COD cap), §6.1
-- orders "channel field (web, WhatsApp, POS, phone, ChitBridge)".

-- Where an order or booking came from. NULL = recorded before channels were.
ALTER TABLE orders_orders ADD COLUMN channel TEXT
    CHECK (channel IN ('web', 'whatsapp', 'pos', 'phone', 'workspace', 'marketplace', 'chitbridge'));
ALTER TABLE bookings_bookings ADD COLUMN channel TEXT
    CHECK (channel IN ('web', 'whatsapp', 'phone', 'workspace', 'marketplace'));
CREATE INDEX orders_orders_channel ON orders_orders (business_id, channel, created_at DESC) WHERE channel IS NOT NULL;

-- An enquiry can arrive on WhatsApp.
ALTER TABLE leads_leads DROP CONSTRAINT IF EXISTS leads_leads_source_check;
ALTER TABLE leads_leads ADD CONSTRAINT leads_leads_source_check
    CHECK (source IN ('manual', 'website_enquiry', 'marketplace', 'import', 'whatsapp'));

-- The owner's rules for orders placed on WhatsApp.
ALTER TABLE messaging_settings
    ADD COLUMN cod_allowed BOOLEAN NOT NULL DEFAULT true,
    -- Largest cash-on-delivery order from a customer's first order (NULL = no cap).
    ADD COLUMN first_order_cod_cap NUMERIC(12, 2) CHECK (first_order_cod_cap >= 0);

-- A customer's tap and LOCAH's answer are written in one transaction; the
-- chat is read in created_at order, so each message takes the clock time it
-- was written rather than the transaction's start.
ALTER TABLE messaging_messages ALTER COLUMN created_at SET DEFAULT clock_timestamp();
