# Stage 4 Completion — Commerce (Cart/Checkout, Fulfilment, Order UI)

Modules: `fulfilment` (optional, launch-ready) · closes Doc 11 §17.4 remaining exits  
Related frozen kernels: Orders, Payments, Inventory (untouched)

---

## Scope verification (pre-implementation)

**Confirmed:** `fulfilment` is a Full/Launch-Ready optional module (Document 11 §8.1 / §10.4), already registered in `module_definitions` / `module_registry` with features `fulfilment.core` and `fulfilment.delivery_zones`. It is entitlement/activation-gated (unlike Platform Core).

**Confirmed:** WEB-007 and WEB-008 are First Launch depth:

> Doc 11 §4.1: `WEB-007` — “Promoted to real First Launch cart, checkout, and confirmation depth”; `WEB-008` — “Required at Basic tracking/fulfilment-status depth”.

> Doc 11 §17.4 Exit: purchase-based commerce flows pass end-to-end; pickup and Business delivery states work; Business and consumer order experiences exist.

> Doc 11 §10.4 Required: pickup; Business-managed delivery; zones; charges; mode selection; preparation/ready/out-for-delivery/delivered; basic customer-facing status; Business list/detail; cancellation/failure outcomes. Deferred: driver networks, route optimization, courier aggregation.

> Doc 12 §11.2: storefront route strategy includes `/{slug}/checkout`.

> Doc 09 §5.3: WEB-007 empty/invalid/payment-failed/order-pending states; WEB-008 invalid/expired/delayed/failed states.

Canonical permissions (Document 12): `fulfilment.read`, `fulfilment.update_status`, `fulfilment.manage_config` (not invented aliases).

---

## APIs

| Method | Path | Auth |
|--------|------|------|
| GET/PATCH | `/v1/b/{business_id}/fulfilment/settings` | fulfilment.read / manage_config |
| POST/GET | `/v1/b/{business_id}/fulfilment/zones` | manage_config / read |
| GET | `/v1/b/{business_id}/fulfilment/jobs` | fulfilment.read |
| GET | `/v1/b/{business_id}/fulfilment/jobs/{job_id}` | fulfilment.read |
| PATCH | `/v1/b/{business_id}/fulfilment/jobs/{job_id}/status` | fulfilment.update_status |
| GET | `/v1/public/websites/{slug}/offerings` | public |
| GET | `/v1/public/websites/{slug}/checkout/options` | public |
| POST | `/v1/public/websites/{slug}/checkout/quote` | public |
| POST | `/v1/public/websites/{slug}/checkout` | public (guest) |
| GET | `/v1/public/orders/{order_id}/tracking?token=` | public (bounded token) |

UI: `apps/web` `/{slug}/checkout`, `/{slug}/track/{orderId}` · `apps/workspace` orders + fulfilment boards

## Events

`fulfilment.job_created`, `fulfilment.status_changed`, `fulfilment.failed`, `fulfilment.delivered`, `fulfilment.zone_configured`  
Consumes `order.cancelled` / `order.rejected` to cancel open jobs.

## Tests

- `apps/api/tests/test_fulfilment_kernel.py`
- `apps/api/tests/test_checkout_flow.py`
- `apps/api/tests/test_order_tracking.py`

---

# Stage 4 Commerce Completion — Engineering Report

## 1. Executive Summary

Stage 4 commerce completion closes Document 11 §17.4 exits that remained after the frozen Orders/Payments/Inventory kernels: launch-depth **Fulfilment** (pickup + Business delivery, zones/charges, status machine), **guest cart/checkout** (`/{slug}/checkout`), **bounded order tracking**, and **Workspace order/fulfilment management UIs**. Order/Payment/Inventory domain logic was not modified. Checkout orchestration creates `SalesOrder` + `FulfilmentJob` (+ payment attempt) atomically via existing services.

## 2. Implemented Components

| Component | Role |
|-----------|------|
| `fulfilment_settings` / `fulfilment_zones` / `fulfilment_jobs` | Domain tables |
| `FulfilmentService` | Zones, charges, jobs, tracking, status machine |
| `CheckoutService` | Public guest checkout orchestration |
| Routers | `v1_fulfilment`, `v1_public_checkout` |
| apps/web | WEB-007 / WEB-008 + offerings_list cart source |
| apps/workspace | Orders board/detail; Fulfilment board/detail/zones |
| Worker | Outbox handlers for fulfilment events + order cancel → job cancel |

## 3. Database Changes

Migration: `infra/supabase/migrations/20260729000000_stage4_fulfilment_commerce.sql`

- Settings (pickup/delivery flags, delivery-fee offering link)
- Zones (city / radius / postal_prefix match + charge)
- Jobs (one per order, tracking token + TTL, status machine)

## 4. Domain Models

`FulfilmentSettings`, `FulfilmentZone`, `FulfilmentJob` in `platform_core.models`.

Reused without modification: `SalesOrder`, `OrderLineItem`, `PaymentAttempt`, `InventoryRecord`, `CustomerTimelineService`, Website rendering.

## 5. Services

- **FulfilmentService** — module gate, zone match (server-side charge), job create/transition, public tracking
- **CheckoutService** — offerings list, options, quote, place order (OrderService → FulfilmentService → PaymentAttemptService)

Delivery fee is included in the order total by appending a private non-inventory “Delivery fee” offering line (unit_price = zone charge) so payment amount validation remains satisfied without changing Payments.

## 6. APIs

Documented above. Business APIs under `/v1/b/.../fulfilment` (Doc 12 `/v1/b` pattern). Public checkout under `/v1/public/websites/{slug}/checkout*`. Tracking under `/v1/public/orders/{order_id}/tracking`.

## 7. Authorization Integration

- Workspace fulfilment: `fulfilment.read` / `update_status` / `manage_config`
- Workspace orders: existing `orders.*` APIs
- Public checkout/tracking: no auth (guest); tracking requires secret token

## 8. Audit Integration

Job created, status transitions (with actor + reason on fail/cancel), zone configured, settings updated.

## 9. Outbox Integration

Emits fulfilment lifecycle events. Consumes order cancelled/rejected to cancel open jobs (fulfilment reacts; does not mutate Order rows).

## 10. Resolver Design

No separate cross-module resolver required beyond existing Order/Location/Offering resolvers used inside frozen OrderService. Fulfilment serializes its own DTOs.

## 11. Validation Rules

- Modes offered only when module active + settings/zones configured
- Delivery charge always from matched zone (never client-trusted)
- Order + job created in one request transaction; idempotent key reused
- Pickup cannot enter `out_for_delivery`; delivery must pass through it before `delivered`
- Failure/cancellation require reason

## 12. Performance

Indexes on `(business_id, status)`, `order_id` unique, tracking token unique. Public offerings/options are lightweight reads.

## 13. Testing Summary

| Suite | Coverage |
|-------|----------|
| `test_fulfilment_kernel.py` | Zone charge, delivery status machine, pickup constraint, isolation, audit/outbox |
| `test_checkout_flow.py` | Guest COD pickup, idempotency, empty cart, invalid item, mode gating |
| `test_order_tracking.py` | Valid / invalid / expired token |

## 14. Files Created

- Migration, models, `validation/fulfilment.py`, `services/fulfilment.py`, `services/checkout.py`
- `v1_fulfilment.py`, `v1_public_checkout.py`
- Web checkout/track + OfferingsListSection
- Workspace orders + fulfilment pages
- Tests + this report

## 15. Files Modified

- `apps/api/src/platform_api/main.py`
- `apps/worker/.../outbox_consumer.py`
- `apps/web` SectionRenderer, workspace layout nav
- `python/core/platform_core/models.py`

## 16. Architectural Compliance

| Rule | Status |
|------|--------|
| Do not modify Order/Payment/Inventory internals | Yes |
| Fulfilment consumes Orders | Yes (create after order; cancel on outbox) |
| Optional module entitlement-gated | Yes |
| Launch-depth only (§10.4) | Yes |
| WEB-007/008 First Launch | Yes |
| No driver network / route optimization | Yes |

Citations: Doc 09 §5.3; Doc 11 §4.1–§4.2, §10.4, §17.4; Doc 12 §11.2, fulfilment permissions.

## 17. Implementation Decisions

| Decision | Citation |
|----------|----------|
| Reuse Doc 12 permission IDs (`read`/`update_status`/`manage_config`) | Doc 12 permission grammar |
| Checkout orchestration service (not Order writing FulfilmentJob) | Doc 12 §4.3 cross-module pattern |
| Delivery fee as order line via private offering | Keep payment≤order-total invariant without touching Payments |
| Tracking token + TTL on job | Doc 09 WEB-008 bounded link |
| Guest identity bootstrap for audit actor | Audit requires identity; no login required |

## 18. Future Dependencies

- Third-party courier provider abstraction
- Route optimization / driver marketplace (explicitly deferred)
- ACC consumer order history surfaces
- Online payment provider handoff UX beyond stub processing status

## 19. Risks

| Risk | Mitigation |
|------|------------|
| Modules not enabled → checkout blocked | Clear ValidationError; Workspace enable path |
| Zone misconfiguration | Quote endpoint + checkout rejects unserviceable addresses |
| Tracking token leak | Unlisted URL + expiry; no PII beyond order summary |

## 20. Verification Checklist

- [x] `fulfilment` optional module confirmed
- [x] WEB-007 / WEB-008 First Launch confirmed
- [x] FulfilmentJob + FulfilmentZone
- [x] Status machine pickup/delivery
- [x] Guest checkout atomic order+job
- [x] Server-side zone charges
- [x] Public tracking valid/invalid/expired
- [x] Workspace orders + fulfilment UI
- [x] Audit + outbox
- [x] Tests
- [x] No Order/Payment/Inventory domain edits

## 21. Integration Matrix

| System | Integration |
|--------|-------------|
| Orders | Checkout calls `OrderService.create_order` |
| Payments | Checkout calls `PaymentAttemptService.create_attempt` |
| Inventory | Reservation inside order create (unchanged) |
| Customer Relationships | Guest contact create + timeline via order create |
| Outbox | Fulfilment events; cancel on order cancel |
| Website | offerings_list → cart → checkout |

## 22. Scope Verification

**In scope:** Doc 11 §17.4 remaining exits — real checkout, pickup/delivery fulfilment states, Business + consumer order experiences, launch-depth fulfilment (§10.4).

**Out of scope (not implemented):** Proprietary driver network, route optimization, proof-of-delivery hardware, complex returns logistics, third-party courier aggregation, advanced booking depth (Stage 5), Memberships/Leads/Workforce (Stage 6).
