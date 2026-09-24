-- Marketplace discovery depth (Doc 09 §3, Doc 11 §13, Doc 12 §14).
--
-- 1. Drop projections whose Business is gone.
--    A soft-deleted Business kept its projection with is_discoverable = true:
--    reconciliation only walked live Businesses, so it never came back for
--    them. The query-time check hid them, but only after LIMIT — on staging
--    278 of 293 projections were for deleted test Businesses, and the
--    Marketplace's first page of twenty held one real business. Idempotent.
DELETE FROM marketplace_offering_projections mo
WHERE NOT EXISTS (
    SELECT 1 FROM businesses b WHERE b.id = mo.business_id AND b.deleted_at IS NULL
);
DELETE FROM marketplace_business_projections mp
WHERE NOT EXISTS (
    SELECT 1 FROM businesses b WHERE b.id = mp.business_id AND b.deleted_at IS NULL
);
UPDATE marketplace_index_health h
SET last_status = 'deindexed', last_reason = 'business_deleted', updated_at = now()
WHERE last_status = 'indexed'
  AND NOT EXISTS (
      SELECT 1 FROM businesses b WHERE b.id = h.business_id AND b.deleted_at IS NULL
  );

-- 2. What a person needs to decide from a listing, denormalised at index time
--    from facts the Business published (platform_core.business_categories,
--    its published website, its catalogue and its primary location).
ALTER TABLE marketplace_business_projections
    ADD COLUMN IF NOT EXISTS category_family TEXT,
    ADD COLUMN IF NOT EXISTS category TEXT,
    ADD COLUMN IF NOT EXISTS locality TEXT,
    ADD COLUMN IF NOT EXISTS region TEXT,
    ADD COLUMN IF NOT EXISTS postal_code TEXT,
    -- 'exact' when the owner set coordinates; 'city' when they are the
    -- centre of the named city, good for ordering and never shown as a
    -- distance.
    ADD COLUMN IF NOT EXISTS geo_precision TEXT,
    ADD COLUMN IF NOT EXISTS keywords TEXT[] NOT NULL DEFAULT '{}',
    ADD COLUMN IF NOT EXISTS cover_url TEXT,
    ADD COLUMN IF NOT EXISTS logo_url TEXT,
    ADD COLUMN IF NOT EXISTS highlights JSONB NOT NULL DEFAULT '[]'::jsonb,
    ADD COLUMN IF NOT EXISTS offering_count INTEGER NOT NULL DEFAULT 0,
    ADD COLUMN IF NOT EXISTS published_at TIMESTAMPTZ,
    -- The phone / WhatsApp number the owner already shows on their published
    -- site, so a listing can offer Call and WhatsApp without a click-through.
    ADD COLUMN IF NOT EXISTS public_contact JSONB NOT NULL DEFAULT '{}'::jsonb,
    -- Where on that site each action lands ("" home, "/menu", "#contact").
    -- A listing only offers an action that has somewhere real to go.
    ADD COLUMN IF NOT EXISTS site_paths JSONB NOT NULL DEFAULT '{}'::jsonb;

ALTER TABLE marketplace_business_projections
    DROP CONSTRAINT IF EXISTS marketplace_business_projections_geo_precision_check;
ALTER TABLE marketplace_business_projections
    ADD CONSTRAINT marketplace_business_projections_geo_precision_check
    CHECK (geo_precision IS NULL OR geo_precision IN ('exact', 'city'));

CREATE INDEX IF NOT EXISTS idx_marketplace_businesses_family
    ON marketplace_business_projections (category_family, category)
    WHERE is_discoverable = true;
CREATE INDEX IF NOT EXISTS idx_marketplace_businesses_geo
    ON marketplace_business_projections (lat, lng)
    WHERE is_discoverable = true AND lat IS NOT NULL;

-- Weighted: the name first, then what it sells and where it is, then prose.
CREATE OR REPLACE FUNCTION update_business_search_vector() RETURNS TRIGGER AS $$
BEGIN
    NEW.search_vector :=
        setweight(to_tsvector('english', coalesce(NEW.display_name, '')), 'A') ||
        setweight(to_tsvector('english',
            coalesce(array_to_string(NEW.keywords, ' '), '') || ' ' ||
            coalesce(array_to_string(NEW.tags, ' '), '')
        ), 'B') ||
        setweight(to_tsvector('english',
            coalesce(NEW.locality, '') || ' ' ||
            coalesce(NEW.city, '') || ' ' ||
            coalesce(NEW.postal_code, '')
        ), 'C') ||
        setweight(to_tsvector('english',
            coalesce(NEW.description, '') || ' ' ||
            coalesce(NEW.business_type, '') || ' ' ||
            coalesce(NEW.primary_category, '')
        ), 'D');
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Re-derive every existing vector under the new weights.
UPDATE marketplace_business_projections SET indexed_at = indexed_at;

-- 3. Reconciliation actually runs. The worker job existed but nothing ever
--    enqueued it; from here each run schedules the next (recurrence_key), and
--    this first one backfills the new columns for every live Business.
INSERT INTO platform_scheduled_jobs (schedule_type, payload, run_at, recurrence_key)
SELECT 'marketplace.reconcile', '{"limit": 1000, "recurring": true}'::jsonb, now(), 'marketplace.reconcile'
WHERE NOT EXISTS (
    SELECT 1 FROM platform_scheduled_jobs
    WHERE recurrence_key = 'marketplace.reconcile' AND status = 'pending'
);
