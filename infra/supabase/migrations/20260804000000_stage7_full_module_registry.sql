-- Stage 7 — full optional-module registry (AUD-04, Doc 11 §18.2)
--
-- `module_definitions` held only the 10 First-Launch optional modules. The 11
-- Later/Future modules from `ModuleRegistry`
-- (python/core/platform_core/entitlements/module_registry.py) were absent, so
-- nothing could reference them — the Admin module catalog couldn't list them,
-- a plan couldn't grant them, and `test_module_registry_seed.py` had nothing
-- to check against.
--
-- Doc 11 §18.2: "All 21 optional modules registered with canonical IDs; launch
-- classification stored in release configuration, not as duplicate modules."
-- `is_available` here is the registration flag, NOT the launch gate — launch
-- depth (A/B/C/D) lives in release config against these same canonical IDs.
-- The 11 added below are registered and dependency-linked but carry no
-- entitlement or activation for any Business.
--
-- Descriptions and dependencies mirror the registry exactly. The existing 10
-- optional rows and the 10 core rows are untouched.

INSERT INTO module_definitions (id, name, module_class, description, dependencies, is_available) VALUES
  ('queue-operations',  'Queue Operations',  'optional', 'Walk-in queue and token management',       '{core-team-access}',          true),
  ('invoicing',         'Invoicing',         'optional', 'Invoices and receivables',                 '{core-business-profile}',     true),
  ('loyalty',           'Loyalty',           'optional', 'Points, tiers, and rewards',               '{customer-relationships}',    true),
  ('payroll',           'Payroll',           'optional', 'Compensation and payout coordination',     '{workforce}',                 true),
  ('messaging',         'Messaging',         'optional', 'External messaging channels',              '{core-notifications}',        true),
  ('marketing',         'Marketing',         'optional', 'Campaigns and promotional audiences',      '{customer-relationships}',    true),
  ('reviews',           'Reviews',           'optional', 'Transaction-linked feedback',              '{orders}',                    true),
  ('analytics',         'Analytics',         'optional', 'Business reporting and insights',          '{core-workspace}',            true),
  ('business-passport', 'Business Passport', 'optional', 'Verified credential dossier',              '{core-business-profile}',     true),
  ('business-community','Business Community','optional', 'Community posts and follows',              '{core-marketplace-presence}', true),
  ('b2b-network',       'B2B Network',       'optional', 'Supplier and partner discovery',           '{core-business-profile}',     true)
ON CONFLICT (id) DO NOTHING;
