-- P1-09: built Storefront tools are always available. Reviews can follow a
-- booking even when Orders is off, so its only prerequisite is a Business.
UPDATE module_definitions
SET dependencies = ARRAY['core-business-profile']::text[]
WHERE id = 'reviews';

-- Backfill only missing states. A previous explicit off state is not silently
-- overwritten; BusinessService creates active states for new businesses.
INSERT INTO business_module_states (business_id, module_id, activation_state, enabled_at, activated_at)
SELECT b.id, m.module_id, 'active', now(), now()
FROM businesses b
CROSS JOIN (VALUES ('reviews'), ('compliance')) AS m(module_id)
WHERE b.deleted_at IS NULL
  AND NOT EXISTS (
      SELECT 1 FROM business_module_states s
      WHERE s.business_id = b.id AND s.module_id = m.module_id
  );
