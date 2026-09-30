-- Applied to the hosted project on 2026-09-29 under this version and recorded
-- in its migration history, but never committed; the repository used the same
-- version for the dated pre-orders migration (now 20260929120100), so the
-- hosted history hid that one. Brought into Git unchanged (the hosted
-- history's own statement): only the API role resolves a payment link's business.
REVOKE EXECUTE ON FUNCTION payment_request_business(TEXT) FROM anon, authenticated;
