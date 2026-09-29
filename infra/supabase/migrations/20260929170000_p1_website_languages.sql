-- P1-10E6: the languages a business's website speaks (PR-10, GP-22 P1 part —
-- "English, Tamil and Hindi across UI and messages"). The first is what a
-- visitor sees first; a visitor can switch to any other. This changes the
-- site's own words (buttons, headings LOCAH supplies, cart, checkout, pages
-- a customer is sent to); what the owner wrote stays as they wrote it.

ALTER TABLE websites
    ADD COLUMN IF NOT EXISTS languages TEXT[] NOT NULL DEFAULT '{en}'
        CHECK (cardinality(languages) BETWEEN 1 AND 3 AND languages <@ ARRAY['en', 'ta', 'hi']::TEXT[]);
