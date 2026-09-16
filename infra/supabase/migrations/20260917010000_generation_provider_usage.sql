-- Token/latency accounting for website generation (Doc 12 §12.5 / D12-AI-003).
ALTER TABLE website_generation_jobs
    ADD COLUMN IF NOT EXISTS provider_usage JSONB;
