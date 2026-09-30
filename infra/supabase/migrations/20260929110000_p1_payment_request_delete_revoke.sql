-- Applied to the hosted project on 2026-09-29 under this version and recorded
-- in its migration history, but never committed; the repository used the same
-- version for the COD-rules migration (now 20260929110100), so the hosted
-- history hid that one. Brought into Git unchanged (the hosted history's own
-- statement): the API role may not delete payment requests.
REVOKE DELETE ON payments_requests FROM platform_api;
