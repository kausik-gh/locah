-- P1-09: structured, live review section; no generated review text is stored.
INSERT INTO website_section_types
    (id, label, description, content_schema, allowed_variants, contributing_module, sort_order)
VALUES
    ('reviews_section', 'Verified customer reviews',
     'Published reviews from completed customer interactions',
     '{"type":"object","properties":{"title":{"type":"string","maxLength":120},"subtitle":{"type":"string","maxLength":300}}}',
     ARRAY['cards', 'list'], 'reviews', 115)
ON CONFLICT (id) DO UPDATE SET
    label = EXCLUDED.label,
    description = EXCLUDED.description,
    content_schema = EXCLUDED.content_schema,
    allowed_variants = EXCLUDED.allowed_variants,
    contributing_module = EXCLUDED.contributing_module,
    sort_order = EXCLUDED.sort_order;
