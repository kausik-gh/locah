-- P1-10B: one LOCAH customer identity across every business (Founder §12–13;
-- Business OS Guide §1; Doc 12 line 848: "Guest-to-authenticated linking:
-- only through verified identifier matching (phone or email verification).
-- No weak matching.").
--
-- A person who bought as a guest from three shops with the same email, and
-- later signs in to LOCAH with that email verified, sees those orders in My
-- Activity. The link is made only for the calling identity, only on its
-- verified email, and only onto contacts no identity has claimed yet — never
-- by name or an unverified phone.

CREATE INDEX IF NOT EXISTS idx_contacts_unlinked_email
    ON customer_relationships_contacts (lower(email))
    WHERE identity_id IS NULL AND deleted_at IS NULL AND email IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_contacts_identity
    ON customer_relationships_contacts (identity_id, business_id)
    WHERE identity_id IS NOT NULL AND deleted_at IS NULL;

CREATE OR REPLACE FUNCTION link_verified_customer_contacts()
RETURNS TABLE (business_id uuid, contact_id uuid)
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
DECLARE
    v_identity uuid := current_identity_id();
    v_email text;
BEGIN
    IF v_identity IS NULL THEN
        RETURN;
    END IF;
    SELECT lower(i.email) INTO v_email
    FROM platform_identities i
    WHERE i.id = v_identity AND i.email_verified;
    IF v_email IS NULL OR v_email = '' THEN
        RETURN;
    END IF;
    RETURN QUERY
    UPDATE customer_relationships_contacts c
       SET identity_id = v_identity, updated_at = now()
     WHERE c.identity_id IS NULL
       AND c.deleted_at IS NULL
       AND lower(c.email) = v_email
    RETURNING c.business_id, c.id;
END;
$$;

REVOKE ALL ON FUNCTION link_verified_customer_contacts() FROM PUBLIC, anon, authenticated;
GRANT EXECUTE ON FUNCTION link_verified_customer_contacts() TO platform_api;

-- The customer's own records in one business, for "My account" on that
-- business's website: which contacts in that business are the caller's.
CREATE OR REPLACE FUNCTION my_contacts_in_business(p_business_id uuid)
RETURNS TABLE (contact_id uuid)
LANGUAGE sql
SECURITY DEFINER
STABLE
SET search_path = public
AS $$
    SELECT c.id FROM customer_relationships_contacts c
    WHERE c.business_id = p_business_id
      AND c.identity_id = current_identity_id()
      AND current_identity_id() IS NOT NULL
      AND c.deleted_at IS NULL;
$$;

REVOKE ALL ON FUNCTION my_contacts_in_business(uuid) FROM PUBLIC, anon, authenticated;
GRANT EXECUTE ON FUNCTION my_contacts_in_business(uuid) TO platform_api;
