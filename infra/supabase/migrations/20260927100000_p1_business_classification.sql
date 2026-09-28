-- Phase B · P1-01 — business classification and operating traits
-- Source: LOCAH Business Capability Universe §4.3, §4.4, §6.2, §22, §24 #1–2.
--
-- 1. businesses gains category_key, subcategory_key and org_shape. Until now the
--    kind of business lived in metadata->'classification' (a seed the interview
--    read). The columns make it queryable and are backfilled from that seed.
--    `business_type` is unchanged and keeps meaning "website template key"
--    (§4.1: business_type stays as the website template key).
-- 2. business_traits holds the business's operating traits. Traits start from
--    the subcategory's defaults (source = 'default'), the owner can switch any
--    trait on or off (source = 'owner'), and an AI-suggested trait exists only
--    once the owner confirmed it (source = 'ai_suggested_confirmed').
--    `enabled = false` records an owner switching a default trait off, so a
--    later re-seed of defaults cannot silently turn it back on.
--    Trait keys are validated by the application registry (taxonomy.py), not a
--    CHECK list, so the registry stays the one place the vocabulary lives.
-- 3. module_definitions registers the modules the Capability Universe adds
--    (§6.2). Registration is not entitlement and not activation: nothing here
--    turns a module on for any business.

ALTER TABLE businesses
    ADD COLUMN category_key TEXT,
    ADD COLUMN subcategory_key TEXT,
    ADD COLUMN org_shape TEXT
        CHECK (org_shape IS NULL OR org_shape IN (
            'solo', 'team', 'multi_location', 'franchise_brand', 'franchise_outlet', 'enterprise'
        ));

UPDATE businesses
SET category_key = NULLIF(metadata -> 'classification' ->> 'category_key', ''),
    subcategory_key = NULLIF(metadata -> 'classification' ->> 'subcategory_key', '')
WHERE metadata ? 'classification'
  AND category_key IS NULL;

CREATE INDEX businesses_category ON businesses (category_key, subcategory_key)
    WHERE deleted_at IS NULL;


CREATE TABLE business_traits (
    business_id UUID NOT NULL REFERENCES businesses(id),
    trait_key TEXT NOT NULL CHECK (trait_key ~ '^[a-z][a-z0-9_]{1,40}$'),
    enabled BOOLEAN NOT NULL DEFAULT true,
    source TEXT NOT NULL CHECK (source IN ('default', 'owner', 'ai_suggested_confirmed')),
    set_by UUID REFERENCES platform_identities(id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (business_id, trait_key)
);

ALTER TABLE business_traits ENABLE ROW LEVEL SECURITY;
ALTER TABLE business_traits FORCE ROW LEVEL SECURITY;

CREATE POLICY business_traits_member_read ON business_traits
    FOR SELECT TO public USING (business_id = current_business_id());
CREATE POLICY business_traits_api_write ON business_traits
    FOR ALL TO platform_api USING (business_id = current_business_id())
    WITH CHECK (business_id = current_business_id());

GRANT SELECT, INSERT, UPDATE, DELETE ON business_traits TO platform_api;
REVOKE ALL PRIVILEGES ON TABLE business_traits FROM anon;


-- §6.2 modules. Dependencies mirror platform_core/catalog/modules.py and
-- entitlements/module_registry.py. FUTURE modules are registered unavailable.
INSERT INTO module_definitions (id, name, module_class, description, dependencies, is_available) VALUES
  ('pos',             'Counter billing',            'optional', 'Scan or search, cart, hold bill, split tender, returns, cash drawer shifts, offline queue', '{offerings-catalog,invoicing}', true),
  ('ledger',          'Khata / credit book',        'optional', 'Running balance per customer and supplier, credit limits, ageing, reminders, settlements', '{customer-relationships}', true),
  ('compliance',      'Licences & deadlines',       'optional', 'Licence and filing calendar, expiry reminders, document vault link', '{core-business-profile}', true),
  ('dispatch',        'Live delivery',              'optional', 'Delivery and field jobs, crew assignment, live location, ETA, proof of delivery, COD settlement', '{fulfilment}', true),
  ('tasks',           'Tasks & checklists',         'optional', 'Housekeeping, maintenance, prep, opening / closing checklists', '{core-team-access}', true),
  ('attendance',      'Check-ins',                  'optional', 'Member, student and staff check-in by QR or manual', '{core-team-access}', true),
  ('kitchen',         'Kitchen display',            'optional', 'Kitchen order tickets by station, bump screen, prep timers, printer fallback', '{orders}', true),
  ('ai-employees',    'AI staff',                   'optional', 'One entitlement per AI employee, limits, approvals, meters', '{core-team-access}', true),
  ('connectors',      'Integration hub',            'optional', 'Adapters, credentials, source-of-truth settings, sync logs', '{core-settings}', true),
  ('expenses',        'Expenses & cash book',       'optional', 'Expenses, petty cash, daily cash closing', '{core-business-profile}', true),
  ('procurement',     'Buying',                     'optional', 'Suppliers, price agreements, requisitions, POs, goods receipt, supplier bills, payables', '{core-business-profile}', true),
  ('recipes',         'Recipes & BOM',              'optional', 'Components per offering, yield, wastage, unit conversions, production batches, consumption on sale', '{inventory}', true),
  ('trade-network',   'ChitBridge link',            'optional', 'Entity binding, buyer / supplier relations, chit sync', '{procurement}', true),
  ('jobs',            'Job cards',                  'optional', 'Request, inspect, estimate, approve, work, parts, QC, invoice — linked to a customer asset', '{customer-relationships}', true),
  ('academics',       'Courses & batches',          'optional', 'Courses, batches, timetable, enrolment, assessments, homework, certificates', '{offerings-catalog}', true),
  ('documents',       'Forms & files',              'optional', 'Templates, intake and consent forms, uploads, typed / drawn signatures', '{core-business-profile}', true),
  ('donations',       'Donations',                  'optional', 'Causes, one-off and recurring gifts, 80G receipts, donor timeline', '{payments}', true),
  ('channel-manager', 'OTA sync',                   'optional', 'Room availability sync with travel sites (FUTURE)', '{bookings}', false),
  ('ticketing',       'Event tickets',              'optional', 'Tickets for events (FUTURE)', '{bookings}', false)
ON CONFLICT (id) DO NOTHING;
