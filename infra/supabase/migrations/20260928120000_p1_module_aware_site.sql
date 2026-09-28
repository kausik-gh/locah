-- P1-10C: the website follows the business's tools (Founder §14–16).
-- A module that becomes ready adds its section to the home page when the
-- owner's design shows nothing for it; the owner can hide any of them. This
-- column is that choice, per module key ("memberships", "bookings", ...).
ALTER TABLE websites
    ADD COLUMN auto_sections_hidden TEXT[] NOT NULL DEFAULT '{}';
