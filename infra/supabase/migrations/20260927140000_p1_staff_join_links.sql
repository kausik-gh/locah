-- Phase B P1 · Staff logins (founder instruction: the owner gives a person a
-- role and creates the login they use; Capability Universe §7.3).
-- An owner adds a person with a role and scope; LOCAH makes a one-time join
-- link. Only a hash of the link's token is stored. The person opens it,
-- creates their login with the invited email (or signs in) and joins with
-- the role already set.
ALTER TABLE business_invitations
    ADD COLUMN display_name TEXT,
    ADD COLUMN join_token_hash TEXT;

CREATE UNIQUE INDEX business_invitations_join_token
    ON business_invitations (join_token_hash) WHERE join_token_hash IS NOT NULL;

-- The link is the credential for reading the invitation before the person has
-- any membership: bound transaction-locally as app.current_join_token (the
-- hash), exactly like quote and booking share tokens.
CREATE POLICY business_invitations_join_token_read ON business_invitations FOR SELECT TO platform_api
    USING (join_token_hash IS NOT NULL
           AND join_token_hash = NULLIF(current_setting('app.current_join_token', true), ''));
