-- Website generation questionnaire intake (Doc 12 §12.7).
-- Forward-only. Persists the owner's questionnaire answers on the generation
-- job so the one generate_structured call can use them and so a later
-- "regenerate with more detail" flow can pre-fill. Adds the 'superseded'
-- status for the case where an explicit questionnaire-driven generation
-- replaces an auto-enqueued bootstrap job the worker has not yet claimed.

ALTER TABLE website_generation_jobs
    ADD COLUMN IF NOT EXISTS intake JSONB;

ALTER TABLE website_generation_jobs
    DROP CONSTRAINT IF EXISTS website_generation_jobs_status_check;

ALTER TABLE website_generation_jobs
    ADD CONSTRAINT website_generation_jobs_status_check
    CHECK (status IN ('pending', 'running', 'completed', 'failed', 'fallback_used', 'superseded'));
