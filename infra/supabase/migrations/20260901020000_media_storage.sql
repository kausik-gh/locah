-- Media & storage foundation (Doc 12 §15). Forward-only.
--
-- Two parts:
--   1. media_assets gains the columns Doc 12 §15.2 specifies but the Stage 2
--      table lacked (bucket, width, height, purpose, deleted_at).
--   2. The `media` storage bucket is constrained. It was created outside
--      version control and was writable by ANY anonymous caller
--      (media_insert / media_update were role `public` with only a
--      bucket_id check, no size or MIME limit). Nothing referenced it and
--      media_assets was empty, so the open policies are replaced with:
--        - public SELECT (bucket is the Doc 12 `business-public` equivalent)
--        - authenticated INSERT/UPDATE/DELETE scoped to the caller's own
--          `{supabase_user_id}/` path prefix.
--      Business ownership of an asset is authoritative in media_assets,
--      which only the API writes; the uid prefix is purely write-scoping so
--      the policy needs no cross-schema join.

-- ---------------------------------------------------------------- 1. columns
ALTER TABLE media_assets ADD COLUMN IF NOT EXISTS bucket TEXT NOT NULL DEFAULT 'media';
ALTER TABLE media_assets ADD COLUMN IF NOT EXISTS width INTEGER;
ALTER TABLE media_assets ADD COLUMN IF NOT EXISTS height INTEGER;
ALTER TABLE media_assets ADD COLUMN IF NOT EXISTS purpose TEXT;
ALTER TABLE media_assets ADD COLUMN IF NOT EXISTS deleted_at TIMESTAMPTZ;

CREATE INDEX IF NOT EXISTS idx_media_assets_purpose
    ON media_assets(business_id, purpose) WHERE deleted_at IS NULL;

-- ------------------------------------------------------------- 2. bucket cfg
-- Ensure the bucket exists on a fresh project (it was created out-of-band on
-- the original project). Idempotent — a no-op where it already exists.
INSERT INTO storage.buckets (id, name, public)
VALUES ('media', 'media', true)
ON CONFLICT (id) DO NOTHING;

-- Doc 12 §15.4: images only, static, 10MB. SVG stays out (XSS).
UPDATE storage.buckets
SET file_size_limit = 10485760,
    allowed_mime_types = ARRAY['image/jpeg', 'image/png', 'image/webp', 'image/gif']
WHERE id = 'media';

-- ---------------------------------------------------------------- 3. policies
DROP POLICY IF EXISTS media_public_read ON storage.objects;
DROP POLICY IF EXISTS media_insert ON storage.objects;
DROP POLICY IF EXISTS media_update ON storage.objects;
DROP POLICY IF EXISTS media_delete ON storage.objects;

-- Published Business media is public by design (logos, hero images).
CREATE POLICY media_public_read ON storage.objects
    FOR SELECT TO public
    USING (bucket_id = 'media');

-- A signed-in caller may only write under their own uid prefix.
CREATE POLICY media_insert ON storage.objects
    FOR INSERT TO authenticated
    WITH CHECK (
        bucket_id = 'media'
        AND (storage.foldername(name))[1] = auth.uid()::text
    );

CREATE POLICY media_update ON storage.objects
    FOR UPDATE TO authenticated
    USING (
        bucket_id = 'media'
        AND (storage.foldername(name))[1] = auth.uid()::text
    )
    WITH CHECK (
        bucket_id = 'media'
        AND (storage.foldername(name))[1] = auth.uid()::text
    );

CREATE POLICY media_delete ON storage.objects
    FOR DELETE TO authenticated
    USING (
        bucket_id = 'media'
        AND (storage.foldername(name))[1] = auth.uid()::text
    );
