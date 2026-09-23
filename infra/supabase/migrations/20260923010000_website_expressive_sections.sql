-- Expressive, truthful website sections.
--
-- Two new platform section types and two optional hero fields. Every one of them
-- is filled from what the owner actually said, so the renderer gains range
-- without gaining a way to invent evidence:
--
--   highlights    numbers the owner stated ("200-bed", "since 1948"), shown as a
--                 stats strip. Values are verified against the owner's words
--                 before they are ever written here.
--   feature_grid  what the business does, one item per thing the owner named,
--                 or the steps of how a customer works with them. Replaces a
--                 catalogue section that renders empty on a brand-new business.
--   hero.eyebrow / hero.headline_accent
--                 a short location/category line above the headline, and the
--                 part of the headline set in the accent colour.
--
-- Idempotent: safe to re-run, and a no-op where already applied.

UPDATE website_section_types
SET content_schema = '{"type":"object","required":["headline"],"properties":{"headline":{"type":"string","maxLength":120},"headline_accent":{"type":"string","maxLength":60},"eyebrow":{"type":"string","maxLength":60},"subheadline":{"type":"string","maxLength":300},"cta_label":{"type":"string","maxLength":60},"cta_url":{"type":"string","maxLength":500},"image_asset_id":{"type":"string","format":"uuid"}}}'::jsonb
WHERE id = 'hero';

INSERT INTO website_section_types (id, label, description, content_schema, allowed_variants, contributing_module, sort_order) VALUES
('highlights', 'Highlights', 'A few numbers the business itself stated, shown prominently',
 '{"type":"object","properties":{"title":{"type":"string","maxLength":120},"items":{"type":"array","maxItems":6,"items":{"type":"object","required":["value","label"],"properties":{"value":{"type":"string","maxLength":24},"label":{"type":"string","maxLength":40}}}}}}'::jsonb,
 ARRAY['strip', 'cards'],
 NULL, 15),
('feature_grid', 'What we do', 'The things the business does, or how a customer works with them',
 '{"type":"object","properties":{"title":{"type":"string","maxLength":120},"subtitle":{"type":"string","maxLength":300},"items":{"type":"array","maxItems":9,"items":{"type":"object","required":["title"],"properties":{"title":{"type":"string","maxLength":80},"body":{"type":"string","maxLength":240}}}}}}'::jsonb,
 ARRAY['cards', 'steps', 'list'],
 NULL, 25)
ON CONFLICT (id) DO UPDATE
SET label = EXCLUDED.label,
    description = EXCLUDED.description,
    content_schema = EXCLUDED.content_schema,
    allowed_variants = EXCLUDED.allowed_variants,
    sort_order = EXCLUDED.sort_order;
