# Dispatch handoff

Branch `parallel/cursor-dispatch`. Dispatch owns the physical job after the order exists. The order stays the sale. Fulfilment stays the pickup-or-delivery choice. This lane does not change Orders, the fulfilment status machine, Payments, or the assignment-scope mechanism. Jobs join that mechanism the same way bookings do: a loader filter, a write guard, and a restrictive policy.

## What is in place

- Tables `dispatch_jobs` and `dispatch_events` in `infra/supabase/migrations/20260930200000_dispatch_jobs.sql`. One job per order. Append-only status history. No coordinate column.
- Statuses: `unassigned`, `assigned`, `picked_up`, `out_for_delivery`, `delivered`, `failed`. A delivery cannot skip `out_for_delivery`. A pickup cannot enter it. Delivered needs a proof note. Failed needs a reason. The same idempotency key does not move the job again.
- Crew is an existing workforce member. The delivery-partner role is assignment-scoped and may only read jobs and update status. The customer's phone is on the job only while it is active, and only for that job.
- Owner and dispatcher board: Unassigned, Assigned, Out now, Delivered, Failed / attention. Routes `/b/{id}/dispatch` and `/b/{id}/dispatch/{jobId}`.
- Crew route `/b/{id}/crew`: next stop, pickup, drop-off, customer contact, status action.
- Customer tracking attaches `dispatch` on the existing public tracking response. `live_location` is null and `location_mode` is `status_only` until a device actually shares a fix. Maps links are a search for an address the business already has.
- Events: `dispatch.job_created`, `dispatch.assigned`, `dispatch.picked_up`, `dispatch.out_for_delivery`, `dispatch.delivered`, `dispatch.failed`. The moves messaging already listens for are also published as `fulfilment.status_changed` (out for delivery, and again on delivered or failed), `fulfilment.delivered`, and `fulfilment.failed`. Messaging internals are unchanged. There is no customer template for "assigned". The out-for-delivery WhatsApp ladder still checks the fulfilment job's own status, so that message can stay quiet until fulfilment itself is `out_for_delivery`. The delivered message uses `fulfilment.delivered` and does not wait on that.

## Not in this slice

Live GPS, crew shifts, cash on delivery settlement, route ETA, offline queue, a native crew wrapper, auto-assign, and a map dot. Those stay activation-dependent.

## Local proof

No hosted database was touched.

`apps/api/tests/test_dispatch.py` — 4 passed against a fresh local database `locah_dispatch` on port 54329 (the older `locah_test` database was behind the current schema, so it was not used). Covered: create, assign, picked up, out for delivery, deliver with a proof note, replay of the same key, a second delivery partner cannot see the job, a stranger is forbidden, another business sees an empty board, and `dispatch_jobs` / `dispatch_events` are tenant-isolated. Public tracking returned `delivered` with `live_location` null.

Browser, `node tools/acceptance/phase_b/p2_dispatch.mjs` against a local API on port 8013 and workspace on port 3104, system Chrome, database `locah_dispatch`: 9/9. The owner board showed two unassigned jobs and no live-location claim. Assigning Anbu wrote `assigned` on that job. Anbu's My jobs page showed the next stop, pickup, drop-off, and the customer number, and did not show Bala's job. Picked up stored `picked_up`. The crew list fit 390 px. Screenshots are in `acceptance-out/phase_b/p2_dispatch/`.

Ruff was run on the dispatch Python paths and passed. The browser run is the UI check. Pytest is the database check.
