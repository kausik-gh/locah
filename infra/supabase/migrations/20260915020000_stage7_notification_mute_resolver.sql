-- Stage 7 — narrow resolver for notification mute suppression.
--
-- Bug: NotificationService._muted_identities needs to check OTHER
-- recipients' mute preferences during fan-out (Doc 09 CORE-015 / Doc 11
-- §17.7), but notification_prefs_api_write (20260802000000) is
-- `USING (identity_id = current_identity_id() AND business_id =
-- current_business_id())` — an AND, correctly keeping one member's
-- preferences private from every OTHER member for the general case, but it
-- also means the fan-out's own internal lookup can only ever see the
-- CURRENT ACTOR's row. The actor firing an event is essentially never the
-- recipient being checked (you mute notifications to stop hearing about
-- things OTHER people trigger), so muting silently never suppressed
-- anything for anyone but yourself.
--
-- Fix: a narrow SECURITY DEFINER resolver instead of widening
-- notification_prefs_api_write to a business-wide SELECT arm (which would
-- let any member read every other member's preference rows directly, not
-- just have the server's own fan-out check see them). The function is
-- scoped to exactly the three columns the fan-out check needs, takes only
-- the recipient set the caller already computed (NotificationService.
-- resolve_recipients, itself correctly business/permission-scoped), and is
-- reachable only by the API role. notification_prefs_api_write itself is
-- unchanged — every direct SELECT/INSERT/UPDATE/DELETE on the table still
-- requires identity_id = current_identity_id(), so a member still cannot
-- read or alter anyone else's preferences through any other path.
CREATE OR REPLACE FUNCTION resolve_muted_identities(
    p_business_id uuid,
    p_category text,
    p_identity_ids uuid[]
) RETURNS TABLE(identity_id uuid)
LANGUAGE sql
STABLE
SECURITY DEFINER
SET search_path = public
AS $$
    SELECT identity_id
    FROM platform_notification_preferences
    WHERE business_id = p_business_id
      AND category = p_category
      AND identity_id = ANY(p_identity_ids)
      AND in_app_enabled = false
      AND deleted_at IS NULL
$$;

COMMENT ON FUNCTION resolve_muted_identities(uuid, text, uuid[]) IS
    'Internal fan-out helper only. Returns which of the given identities '
    'have muted the given category for the given business. Not exposed on '
    'any route; called only from NotificationService._muted_identities, '
    'itself only fed the recipient set NotificationService.resolve_recipients '
    'already computed under normal permission/location scoping. Does not '
    're-derive current_business_id() because the worker (role=service, '
    'RLS-bypassing, no GUCs bound) calls the same fan-out path for '
    'scheduled events (e.g. membership.enrolment.expired) as the API does.';

REVOKE ALL ON FUNCTION resolve_muted_identities(uuid, text, uuid[]) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION resolve_muted_identities(uuid, text, uuid[]) TO platform_api;
