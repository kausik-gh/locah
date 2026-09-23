-- Creative website sections (creative-composer-v2).
--
-- The interview composer no longer fills a template's slots: it composes a page
-- from the business's own catalogue and a creative direction. Three section
-- types carry that structure, and three existing types gain the variants and
-- fields the new compositions use. Every value is filled from what the owner
-- said (items, prices, delivery, payment) or is editorial wording that passed
-- governance; none needs a module, because none of it is a live record.
--
--   category_showcase  categories of what is sold, image-led
--   product_showcase   the items a visitor chooses between (cuts, dishes,
--                      plans, projects), grouped by category; owner prices only
--   fulfilment_strip   how buying works: weight, delivery, pickup, payment
--   hero               + commerce_split, editorial_overlay, cinematic,
--                        airy_split, editorial_split; + badges (true fact chips)
--   about              + story_split; + eyebrow, quote (the owner's own line), anchor
--   cta_band           + image_banner; + image_asset_id
--
-- Idempotent: safe to re-run.

UPDATE website_section_types
SET content_schema = '{"type":"object","required":["headline"],"properties":{"headline":{"type":"string","maxLength":120},"headline_accent":{"type":"string","maxLength":60},"eyebrow":{"type":"string","maxLength":60},"subheadline":{"type":"string","maxLength":300},"cta_label":{"type":"string","maxLength":60},"cta_url":{"type":"string","maxLength":500},"image_asset_id":{"type":"string","format":"uuid"},"badges":{"type":"array","maxItems":4,"items":{"type":"string","maxLength":40}}}}'::jsonb,
    allowed_variants = ARRAY['centered', 'left_aligned', 'image_left', 'image_right', 'full_width', 'commerce_split', 'editorial_overlay', 'cinematic', 'airy_split', 'editorial_split']
WHERE id = 'hero';

UPDATE website_section_types
SET content_schema = '{"type":"object","properties":{"title":{"type":"string","maxLength":120},"body":{"type":"string","maxLength":2000},"image_asset_id":{"type":"string","format":"uuid"},"eyebrow":{"type":"string","maxLength":40},"quote":{"type":"string","maxLength":200},"anchor":{"type":"string","maxLength":30}}}'::jsonb,
    allowed_variants = ARRAY['text_only', 'image_left', 'image_right', 'story_split']
WHERE id = 'about';

UPDATE website_section_types
SET content_schema = '{"type":"object","required":["headline","cta_label"],"properties":{"headline":{"type":"string","maxLength":200},"body":{"type":"string","maxLength":500},"cta_label":{"type":"string","maxLength":60},"cta_url":{"type":"string","maxLength":500},"image_asset_id":{"type":"string","format":"uuid"}}}'::jsonb,
    allowed_variants = ARRAY['centered', 'left_aligned', 'image_banner']
WHERE id = 'cta_band';

INSERT INTO website_section_types (id, label, description, content_schema, allowed_variants, contributing_module, sort_order) VALUES
('category_showcase', 'Categories', 'The categories of what the business sells, with pictures',
 '{"type":"object","properties":{"title":{"type":"string","maxLength":120},"subtitle":{"type":"string","maxLength":300},"anchor":{"type":"string","maxLength":30},"items":{"type":"array","maxItems":12,"items":{"type":"object","required":["name"],"properties":{"name":{"type":"string","maxLength":80},"description":{"type":"string","maxLength":200},"meta":{"type":"string","maxLength":60},"tags":{"type":"array","maxItems":8,"items":{"type":"string","maxLength":40}},"image_asset_id":{"type":"string","format":"uuid"}}}}}}'::jsonb,
 ARRAY['image_cards', 'tiles', 'chips'],
 NULL, 26),
('product_showcase', 'Products', 'The things a visitor chooses between, grouped by category',
 '{"type":"object","properties":{"title":{"type":"string","maxLength":120},"subtitle":{"type":"string","maxLength":300},"anchor":{"type":"string","maxLength":30},"order_label":{"type":"string","maxLength":40},"filters":{"type":"array","maxItems":12,"items":{"type":"string","maxLength":40}},"categories":{"type":"array","maxItems":12,"items":{"type":"object","required":["name"],"properties":{"name":{"type":"string","maxLength":80},"description":{"type":"string","maxLength":200},"meta":{"type":"string","maxLength":60},"tags":{"type":"array","maxItems":8,"items":{"type":"string","maxLength":40}},"image_asset_id":{"type":"string","format":"uuid"}}}},"items":{"type":"array","maxItems":48,"items":{"type":"object","required":["name"],"properties":{"name":{"type":"string","maxLength":80},"category":{"type":"string","maxLength":80},"description":{"type":"string","maxLength":200},"price":{"type":"string","maxLength":40},"unit":{"type":"string","maxLength":40},"image_asset_id":{"type":"string","format":"uuid"}}}}}}'::jsonb,
 ARRAY['category_boards', 'commerce_grid', 'menu_grid', 'compact_list', 'project_cards', 'plan_cards', 'service_cards'],
 NULL, 27),
('fulfilment_strip', 'How ordering works', 'Delivery, pickup, quantities and payment, as the business described them',
 '{"type":"object","properties":{"title":{"type":"string","maxLength":120},"anchor":{"type":"string","maxLength":30},"items":{"type":"array","maxItems":5,"items":{"type":"object","required":["title"],"properties":{"kind":{"type":"string","maxLength":20},"title":{"type":"string","maxLength":60},"body":{"type":"string","maxLength":160}}}}}}'::jsonb,
 ARRAY['icons', 'steps'],
 NULL, 28)
ON CONFLICT (id) DO UPDATE
SET label = EXCLUDED.label,
    description = EXCLUDED.description,
    content_schema = EXCLUDED.content_schema,
    allowed_variants = EXCLUDED.allowed_variants,
    sort_order = EXCLUDED.sort_order;
