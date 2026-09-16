-- Stage 7 — website draft-version race (AUD-08)
--
-- `WebsiteResolver.resolve_draft_version` picked the current draft with
-- `ORDER BY created_at DESC LIMIT 1`. Multiple draft rows per website exist by
-- design (`replace_draft_from_generation` soft-replaces: insert a new draft,
-- leave the old one), and `created_at` defaults to `now()` = transaction start
-- time — so two drafts written in one transaction tie, and the "which draft is
-- current" pick becomes arbitrary. Under load that surfaced as a section edit
-- or publish resolving against the wrong (pre-generation) draft.
--
-- Fix: an explicit `superseded_at` marker + a partial unique index that makes
-- "at most one live draft per website" a database invariant, not a timing
-- artefact. `resolve_draft_version` filters `superseded_at IS NULL` — no
-- ordering involved.

ALTER TABLE website_versions
    ADD COLUMN superseded_at timestamptz;

-- Backfill: for each website, keep the newest draft live, mark the rest
-- superseded. `id` breaks any `created_at` tie deterministically.
WITH ranked AS (
    SELECT id,
           row_number() OVER (
               PARTITION BY website_id
               ORDER BY created_at DESC, id DESC
           ) AS rn
    FROM website_versions
    WHERE version_type = 'draft'
)
UPDATE website_versions v
SET superseded_at = now()
FROM ranked
WHERE v.id = ranked.id AND ranked.rn > 1;

-- At most one live draft per website. `replace_draft_from_generation` marks the
-- prior draft superseded and inserts the new one in the same transaction, so
-- this holds across the swap; two concurrent replacements race here and the
-- loser's INSERT fails (correct — better than a silent wrong-draft pick).
CREATE UNIQUE INDEX uq_website_versions_one_live_draft
    ON website_versions (website_id)
    WHERE version_type = 'draft' AND superseded_at IS NULL;

-- Read path: the live draft, no ORDER BY.
CREATE INDEX idx_website_versions_live_draft
    ON website_versions (website_id, business_id)
    WHERE version_type = 'draft' AND superseded_at IS NULL;
