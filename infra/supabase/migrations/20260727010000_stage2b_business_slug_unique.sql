-- Stage 2B: Soft-delete-compatible Business slug uniqueness
-- Active Businesses keep unique slugs; soft-deleted rows no longer block reuse.

ALTER TABLE businesses DROP CONSTRAINT IF EXISTS businesses_slug_key;

CREATE UNIQUE INDEX IF NOT EXISTS businesses_slug_active_key
    ON businesses (slug)
    WHERE deleted_at IS NULL;
