-- Let a management token find its own booking.
--
-- A guest who books gets one link back: "Manage this booking". Following it
-- reached `PublicBookingService._resolve_by_token`, which selects the booking by
-- id before anything is bound — because the token is what determines the tenant,
-- so no business context can exist yet. The only SELECT policy on
-- bookings_bookings is `business_id = current_business_id()`, so under RLS the
-- row was invisible and every guest was told "This management link is invalid."
-- Viewing, cancelling and rescheduling a booking were all unreachable for the
-- person who made it.
--
-- This is the same shape as `quotes_share_token_read`, and is deliberately the
-- same narrow arm rather than a general public-read on bookings: the token is a
-- credential presented per request, it is bound transaction-locally, and exactly
-- one row — the row whose token matches — becomes visible. A wrong or absent
-- token matches nothing, because NULLIF turns the unset GUC into NULL and NULL
-- never equals a stored token.
--
-- SELECT only. Cancelling or rescheduling still goes through the service, which
-- binds the real business context first and applies the policy window; holding a
-- token is not the same as being the business.

CREATE POLICY bookings_management_token_read ON bookings_bookings
    FOR SELECT TO platform_api
    USING (
        deleted_at IS NULL
        AND management_token IS NOT NULL
        AND management_token = NULLIF(current_setting('app.current_booking_token', true), '')
    );
