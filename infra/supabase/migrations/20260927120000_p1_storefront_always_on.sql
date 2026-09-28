-- Phase B P1-02 · Capability Universe §6.1: "Storefront is always on."
-- New businesses start with every built Storefront module active
-- (BusinessService.create_business). This backfills the one built Storefront
-- module outside Platform Core — customer-relationships — for businesses that
-- never had it. A module an owner deliberately switched off earlier is left as
-- it is (owner choice wins); switching it off is refused from now on.
INSERT INTO business_module_states (business_id, module_id, activation_state, enabled_at, activated_at)
SELECT b.id, 'customer-relationships', 'active', now(), now()
FROM businesses b
WHERE b.deleted_at IS NULL
  AND NOT EXISTS (
      SELECT 1 FROM business_module_states s
      WHERE s.business_id = b.id AND s.module_id = 'customer-relationships'
  );
