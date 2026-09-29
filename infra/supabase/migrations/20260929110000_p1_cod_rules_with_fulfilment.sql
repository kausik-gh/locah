-- P1-10D1: paying on delivery / at pickup is an order rule, not a WhatsApp one
-- (Founder refinement — Orders & Customer Transactions: the owner configures
-- COD for every channel; Payments §5). The rules move from messaging_settings
-- to fulfilment_settings so a business without WhatsApp can set them; the
-- website checkout and WhatsApp journeys read the same row.

ALTER TABLE fulfilment_settings
    ADD COLUMN IF NOT EXISTS cod_allowed BOOLEAN NOT NULL DEFAULT true,
    ADD COLUMN IF NOT EXISTS first_order_cod_cap NUMERIC(12, 2)
        CHECK (first_order_cod_cap IS NULL OR first_order_cod_cap > 0);

-- Keep every rule an owner already set.
INSERT INTO fulfilment_settings (business_id)
SELECT m.business_id FROM messaging_settings m
WHERE NOT EXISTS (SELECT 1 FROM fulfilment_settings f WHERE f.business_id = m.business_id);

UPDATE fulfilment_settings f
SET cod_allowed = m.cod_allowed,
    first_order_cod_cap = NULLIF(m.first_order_cod_cap, 0)
FROM messaging_settings m
WHERE m.business_id = f.business_id;

COMMENT ON COLUMN messaging_settings.cod_allowed IS
    'Superseded by fulfilment_settings.cod_allowed (20260929110000); not read or written.';
COMMENT ON COLUMN messaging_settings.first_order_cod_cap IS
    'Superseded by fulfilment_settings.first_order_cod_cap (20260929110000); not read or written.';
