-- P1-10E6: the language a customer is written to in (PR-10, GP-22 P1 part —
-- "English, Tamil, Hindi"). A customer's WhatsApp replies follow the language
-- they write in ('detected') until they pick one from the menu ('chosen'),
-- which then sticks. Unset means the business's own messaging language.

ALTER TABLE customer_relationships_contacts
    ADD COLUMN IF NOT EXISTS language TEXT CHECK (language IS NULL OR language IN ('en', 'ta', 'hi')),
    ADD COLUMN IF NOT EXISTS language_source TEXT CHECK (language_source IS NULL OR language_source IN ('chosen', 'detected'));
