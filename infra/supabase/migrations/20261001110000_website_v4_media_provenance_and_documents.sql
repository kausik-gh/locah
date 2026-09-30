-- Website creative v4: media provenance, and a private bucket for the
-- owner's menus, catalogues, price lists and brochures.
--
-- 1. Every media asset records where it came from. A draft picture LOCAH drew
--    (Gemini) is never presented as the owner's own photo: it is
--    `gemini_generated`, says which slot it was drawn for and by which job and
--    prompt version, and stays a `draft` until the owner approves, replaces or
--    removes it. Owner uploads are `owner_uploaded` and approved.
-- 2. `owner-documents` is PRIVATE: LOCAH reads these files server-side (service
--    role) to fill the catalogue; they are never served publicly. Writes and
--    reads are limited to the uploader's own folder (`<auth uid>/...`).
--
-- Idempotent: safe to re-run.

ALTER TABLE media_assets
    ADD COLUMN IF NOT EXISTS source_type TEXT NOT NULL DEFAULT 'owner_uploaded',
    ADD COLUMN IF NOT EXISTS generated_for TEXT,
    ADD COLUMN IF NOT EXISTS generation_job_id UUID,
    ADD COLUMN IF NOT EXISTS prompt_version TEXT,
    ADD COLUMN IF NOT EXISTS approval_state TEXT NOT NULL DEFAULT 'approved';

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'media_assets_source_type_check') THEN
        ALTER TABLE media_assets ADD CONSTRAINT media_assets_source_type_check CHECK (source_type IN (
            'owner_uploaded', 'catalogue_extracted', 'existing_business_asset', 'gemini_generated',
            'graphic_generated'));
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'media_assets_approval_state_check') THEN
        ALTER TABLE media_assets ADD CONSTRAINT media_assets_approval_state_check CHECK (approval_state IN (
            'draft', 'approved', 'removed'));
    END IF;
END $$;

-- Pictures the platform already generated (stored under generated/) are drafts.
UPDATE media_assets
SET source_type = 'gemini_generated', approval_state = 'draft'
WHERE storage_key LIKE 'generated/%' AND source_type = 'owner_uploaded';

CREATE INDEX IF NOT EXISTS idx_media_assets_generated
    ON media_assets(business_id, source_type) WHERE deleted_at IS NULL;

-- ------------------------------------------------------ owner documents bucket

INSERT INTO storage.buckets (id, name, public, file_size_limit, allowed_mime_types)
VALUES ('owner-documents', 'owner-documents', false, 20971520,
        ARRAY['application/pdf', 'image/jpeg', 'image/png', 'image/webp'])
ON CONFLICT (id) DO UPDATE
SET public = false,
    file_size_limit = EXCLUDED.file_size_limit,
    allowed_mime_types = EXCLUDED.allowed_mime_types;

DROP POLICY IF EXISTS owner_documents_insert ON storage.objects;
DROP POLICY IF EXISTS owner_documents_select ON storage.objects;
DROP POLICY IF EXISTS owner_documents_delete ON storage.objects;

CREATE POLICY owner_documents_insert ON storage.objects
    FOR INSERT TO authenticated
    WITH CHECK (bucket_id = 'owner-documents' AND (storage.foldername(name))[1] = auth.uid()::text);

CREATE POLICY owner_documents_select ON storage.objects
    FOR SELECT TO authenticated
    USING (bucket_id = 'owner-documents' AND (storage.foldername(name))[1] = auth.uid()::text);

CREATE POLICY owner_documents_delete ON storage.objects
    FOR DELETE TO authenticated
    USING (bucket_id = 'owner-documents' AND (storage.foldername(name))[1] = auth.uid()::text);
