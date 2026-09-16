-- Stage 7 — enable RLS on business_invitations (AUD-02 follow-up)
-- Authority: Doc 11 §21.1 gate 2 ("RLS is enabled and tested wherever the
-- execution context supports it").
--
-- 20260802000000_stage7_rls_role_separation.sql defined
-- business_invitations_api_select / business_invitations_api_write but never
-- turned RLS on for this table, so both policies have been dormant since
-- they were created — every platform_api-authenticated caller could read or
-- write any Business's invitations regardless of the policy text. Forward-
-- only fix: enable and force RLS so the existing, unchanged policies are
-- actually enforced.

ALTER TABLE business_invitations ENABLE ROW LEVEL SECURITY;
ALTER TABLE business_invitations FORCE ROW LEVEL SECURITY;
