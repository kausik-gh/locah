-- Stage 7 — narrow SECURITY DEFINER resolver for public order tracking
-- Authority: Doc 11 §21.1 gate 2, Category B (public order-tracking cannot
-- bind app.current_business_id before it knows which Business the order
-- belongs to, and the caller has no membership/context yet).
--
-- FulfilmentService.get_tracking is reached from an unauthenticated public
-- endpoint (a tracking token in the query string, no identity, no business
-- context). It needs the order's business_id before it can
-- bind_public_context(...) and run its existing FulfilmentJob/SalesOrder
-- queries. This function exposes exactly one column (business_id) for one
-- row (by order id) — nothing else about the order, no other table. It does
-- NOT grant SELECT on orders_orders or fulfilment_jobs to platform_api; the
-- existing secrets.compare_digest(job.tracking_token, token) check in
-- get_tracking remains the sole authorization gate, run after this bind.

CREATE FUNCTION resolve_order_business_id(p_order_id uuid)
RETURNS uuid
LANGUAGE sql
SECURITY DEFINER
STABLE
SET search_path = public
AS $$
    SELECT business_id FROM orders_orders WHERE id = p_order_id;
$$;

GRANT EXECUTE ON FUNCTION resolve_order_business_id(uuid) TO platform_api;
