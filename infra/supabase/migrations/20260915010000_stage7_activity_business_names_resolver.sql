-- Stage 7 — narrow SECURITY DEFINER resolver for My Activity Business names
-- Authority: Doc 11 §21.1 gate 2, Category D (read-after-write / cross-read
-- visibility gap under RLS enforcement).
--
-- ConsumerActivityService.list_for_identity joins consumer_activity_projections
-- to businesses to attach each activity's Business display_name. The
-- projection's own RLS policy (identity_id = current_identity_id()) lets a
-- consumer read their own activity rows regardless of Business visibility,
-- but the JOIN also runs the activity row through businesses_api_select,
-- which a consumer (no membership in that Business) never satisfies — so
-- the JOIN silently drops every row, even though the consumer is fully
-- entitled to see their own activity. This function exposes exactly two
-- columns (id, display_name), restricted to the caller-supplied id list —
-- nothing else about the Business, no other table, no general visibility
-- grant.

CREATE FUNCTION resolve_activity_business_names(p_business_ids uuid[])
RETURNS TABLE(id uuid, display_name text)
LANGUAGE sql
SECURITY DEFINER
STABLE
SET search_path = public
AS $$
    SELECT b.id, b.display_name
    FROM businesses b
    WHERE b.id = ANY(p_business_ids);
$$;

GRANT EXECUTE ON FUNCTION resolve_activity_business_names(uuid[]) TO platform_api;
