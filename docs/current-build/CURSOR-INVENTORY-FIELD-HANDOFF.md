# Inventory field handoff

Branch `parallel/cursor-inventory-field`, cut from `origin/main` (`1cb02e1`). This lane extends the existing inventory ledger. It does not replace it, and it does not change Jobs, Dispatch, Payments, Procurement, or Supply.

## What is in place

Migration `infra/supabase/migrations/20260930220000_inventory_field.sql`.

- **Transfers.** `requested` → `approved` when the transfer asks for approval → `in_transit` → `received`. Sending posts `transfer_out` on the source. The destination does not gain the quantity until receipt posts `transfer_in` for that same quantity. While it is in transit the quantity is not available at either location. The same idempotency key does not move it again.
- **Van stock.** A van is a `business_locations` row with `stock_role = 'van'`. Central → van and van → central use the same transfer. The van board is `GET /v1/platform/businesses/{id}/inventory/vans`.
- **Job contract.** `POST .../inventory/jobs/consume` and `POST .../inventory/jobs/return-unused` take an opaque `job_ref`. They do not read or write a jobs table. Unused return cannot exceed what that job took from that location. Replay of the same key does not deduct again.
- **Customer assets.** One `customer_assets` row. Kinds: vehicle, device, ac_unit, machine, pet, policy, other. Kind-specific facts are `traits`. Pet and policy are allowed because the capability universe names them on this shared primitive. There is no clinical record and no policy product.
- **Client-owned stock.** A separate `inventory_records` row with `owner_customer_id` set. Inward and outward post `client_inward` / `client_outward` on that row only. Sale, reservation, POS, stock counts, and the stock home read `owner_customer_id is null`, so client goods are not business-available stock.

Workspace routes `/b/{id}/inventory/transfers` (Requested, In transit, Received) and `/b/{id}/inventory/vans`.

## Not in this slice

Serial-numbered transfers. Quantity transfers refuse a serial-tracked item rather than drop the serial. Partial receipt (receipt is the full quantity that was sent). Jobs, bookings, and AMC do not reference `customer_assets` yet; the id is there for them.

## Local proof

No hosted database was touched.

`apps/api/tests/test_inventory_field.py` — 6 passed against a fresh local database `locah_inventory_field` on port 54329.

Covered: source 20, send 5, source available 15 and destination 0 while in transit, receive makes the destination exactly 5, replay does not post a second `transfer_in`. Approval blocks send until approved, and approval itself does not move stock. Central → van, van on-hand, job consumption, unused return that cannot exceed what was used, van → central. Client inward/outward leaves the business balance at 20. Asset kinds including pet and policy, replay, and another business sees an empty list. RLS on `inventory_transfers`, `inventory_transfer_lines`, `inventory_field_keys`, `inventory_job_uses`, and `customer_assets`.

Ruff was run on the touched Python paths and passed.

The transfer and van pages were not opened in a browser. This worktree has no `node_modules`, and the workspace dev server that is already running is another branch.

READY_TO_INTEGRATE
