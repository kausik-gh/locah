-- Stage 2A: Business creation defaults (Doc 10 Business.settings / Business.metadata)
-- Extends businesses with settings and metadata JSONB used at creation for
-- locale, currency, country, language, and notification preference defaults.
-- Does not invent separate preferences/settings tables.

ALTER TABLE businesses
    ADD COLUMN IF NOT EXISTS settings JSONB NOT NULL DEFAULT '{}'::jsonb;

ALTER TABLE businesses
    ADD COLUMN IF NOT EXISTS metadata JSONB NOT NULL DEFAULT '{}'::jsonb;

COMMENT ON COLUMN businesses.settings IS
    'Business-wide user-facing settings (core-settings): locale, currency, country, language, notification defaults';
COMMENT ON COLUMN businesses.metadata IS
    'Module-owned extension metadata; Platform Core may store creation provenance keys';
