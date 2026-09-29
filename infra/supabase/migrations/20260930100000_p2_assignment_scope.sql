-- P2-01: assignment scope (Capability Universe §7.2–§7.3, §24 #11).
-- "Assignment scope is the new security primitive." A member whose role's
-- scope is `assignment` (provider, sales executive; later delivery partner,
-- technician, housekeeping) sees and changes only the records assigned to
-- them. The API binds app.current_assignee (their identity id) for such a
-- member; unset means no assignment limit. The server filters the same records
-- first (platform_core.authorization.assignment_scope) — these RESTRICTIVE
-- policies are ANDed with the existing ones, so they only ever narrow.
--
-- Bookings and project tasks are assigned to a workforce member; enquiries
-- (leads) to an identity. Dispatch jobs, job cards and Tasks add their arm
-- when they ship.

CREATE OR REPLACE FUNCTION assignment_scope_allows_identity(assignee uuid) RETURNS boolean
    LANGUAGE sql STABLE AS $$
    SELECT CASE
        WHEN COALESCE(current_setting('app.current_assignee', true), '') = '' THEN true
        WHEN assignee IS NULL THEN false
        ELSE assignee = NULLIF(current_setting('app.current_assignee', true), '')::uuid
    END;
$$;

-- SECURITY DEFINER so the workforce lookup is not itself filtered; it reads one
-- column for the caller's own identity and returns a boolean. (NULLIF: a SQL
-- function's sub-select may be planned before the CASE picks its branch, so the
-- cast must never see an empty string.)
CREATE OR REPLACE FUNCTION assignment_scope_allows_member(member uuid) RETURNS boolean
    LANGUAGE sql STABLE SECURITY DEFINER SET search_path = public AS $$
    SELECT CASE
        WHEN COALESCE(current_setting('app.current_assignee', true), '') = '' THEN true
        WHEN member IS NULL THEN false
        ELSE EXISTS (
            SELECT 1 FROM workforce_members w
             WHERE w.id = member
               AND w.identity_id = NULLIF(current_setting('app.current_assignee', true), '')::uuid)
    END;
$$;

GRANT EXECUTE ON FUNCTION assignment_scope_allows_identity(uuid) TO platform_api;
GRANT EXECUTE ON FUNCTION assignment_scope_allows_member(uuid) TO platform_api;

CREATE POLICY bookings_bookings_assignment_scope ON bookings_bookings AS RESTRICTIVE FOR ALL TO platform_api
    USING (assignment_scope_allows_member(provider_id))
    WITH CHECK (assignment_scope_allows_member(provider_id));

CREATE POLICY leads_leads_assignment_scope ON leads_leads AS RESTRICTIVE FOR ALL TO platform_api
    USING (assignment_scope_allows_identity(assignee_identity_id))
    WITH CHECK (assignment_scope_allows_identity(assignee_identity_id));

CREATE POLICY projects_tasks_assignment_scope ON projects_tasks AS RESTRICTIVE FOR ALL TO platform_api
    USING (assignment_scope_allows_member(assignee_member_id))
    WITH CHECK (assignment_scope_allows_member(assignee_member_id));

-- Quotes: the ones they wrote, or for the customer of an enquiry assigned to them.
CREATE OR REPLACE FUNCTION assignment_scope_allows_quote(author uuid, contact uuid) RETURNS boolean
    LANGUAGE sql STABLE SECURITY DEFINER SET search_path = public AS $$
    SELECT CASE
        WHEN COALESCE(current_setting('app.current_assignee', true), '') = '' THEN true
        WHEN author = NULLIF(current_setting('app.current_assignee', true), '')::uuid THEN true
        WHEN contact IS NULL THEN false
        ELSE EXISTS (
            SELECT 1 FROM leads_leads l
             WHERE l.customer_contact_id = contact
               AND l.assignee_identity_id = NULLIF(current_setting('app.current_assignee', true), '')::uuid)
    END;
$$;
GRANT EXECUTE ON FUNCTION assignment_scope_allows_quote(uuid, uuid) TO platform_api;

CREATE POLICY quotes_quotes_assignment_scope ON quotes_quotes AS RESTRICTIVE FOR ALL TO platform_api
    USING (assignment_scope_allows_quote(created_by, customer_contact_id))
    WITH CHECK (assignment_scope_allows_quote(created_by, customer_contact_id));
