-- Applied to the hosted project on 2026-09-29 and recorded in its migration
-- history, but never committed. Brought into Git unchanged (the statement
-- below is the hosted history's own text) so the repository and the hosted
-- history agree. The location list section may carry the business's own
-- places (name, address, hours, primary) that the public renderer shows.
UPDATE website_section_types
SET content_schema = '{"type":"object","properties":{"title":{"type":"string","maxLength":120},"show_hours":{"type":"boolean"},"show_map":{"type":"boolean"},"locations":{"type":"array","maxItems":12,"items":{"type":"object","required":["name"],"properties":{"id":{"type":"string","maxLength":80},"name":{"type":"string","maxLength":80},"address":{"type":"string","maxLength":500},"hours_summary":{"type":"string","maxLength":500},"is_primary":{"type":"boolean"}}}}}}'::jsonb
WHERE id = 'location_list';
