-- Let a share token find its own quote.
--
-- The customer holding a quote link has no account and no business context, so
-- the token in the URL is the entire credential. But the only SELECT policy on
-- quotes_quotes is `business_id = current_business_id()`, and the token lookup
-- is what *determines* the business — it cannot bind one first. Under RLS the
-- lookup therefore returned nothing and every share link 404'd.
--
-- The fix is an arm that treats the token as what it is: a credential presented
-- per request. The caller binds `app.current_quote_token` and exactly one row
-- becomes visible — the row whose token matches. Nothing else is exposed: no
-- listing, no guessing, and a wrong or absent token matches nothing because
-- NULLIF turns the unset case into NULL, which never equals a stored token.
--
-- SELECT only. A token holder reading their quote is not a token holder
-- editing it; acceptance still goes through the service, which binds the real
-- business context first and applies the lifecycle rules.

CREATE POLICY quotes_share_token_read ON quotes_quotes
    FOR SELECT TO platform_api
    USING (
        deleted_at IS NULL
        AND access_token IS NOT NULL
        AND access_token = NULLIF(current_setting('app.current_quote_token', true), '')
    );
