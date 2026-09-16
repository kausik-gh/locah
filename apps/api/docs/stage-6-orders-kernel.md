# Stage 6 — Orders, Sales & Commerce Kernel

Module: `orders` · Doc 11 §9.2, Doc 12 `orders_*` tables

## APIs

Base: `/v1/platform/businesses/{business_id}/`

| Method | Path | Permission |
|--------|------|------------|
| GET | `/orders` | `orders.read` |
| POST | `/orders` | `orders.create` |
| GET | `/orders/{id}` | `orders.read` |
| PATCH | `/orders/{id}` | `orders.update_status` |
| POST | `/orders/{id}/status` | `orders.update_status` |
| POST | `/orders/{id}/cancel` | `orders.cancel` |
| POST | `/orders/{id}/complete` | `orders.update_status` |
| GET | `/orders/{id}/history` | `orders.read` |
| GET | `/orders/{id}/notes` | `orders.read` |
| POST | `/orders/{id}/notes` | `orders.update_status` |

List filters: `?status=`, `?search=`, `?customer_contact_id=`, `?location_id=`

## Status machine (Doc 04 §6.3, First Launch subset)

```text
pending → accepted → preparing → ready → completed
    |         |           |
 rejected  cancelled   cancelled
```

Terminal: `completed`, `cancelled`, `rejected`

## Inventory integration (Doc 11 §10.3)

| Event | Inventory action |
|-------|------------------|
| Order created | Reserve stock (`reservation`) |
| Order completed | Deduct reserved stock (`deduction`) |
| Order cancelled/rejected | Release reservation (`reversal`) |

## Events

`order.created`, `order.updated`, `order.accepted`, `order.preparing`, `order.ready`, `order.completed`, `order.cancelled`, `order.rejected`, `order.note.created`

Consumer checkout, payment orchestration, and fulfilment handoff deferred to Payments/Fulfilment modules (Doc 11 §9.2).

## Tests

`apps/api/tests/test_orders_kernel.py`

---

# Stage 6 Engineering Report

## 1. Executive Summary

Stage 6 implements the **Orders, Sales & Commerce Kernel** for First Launch workspace operations. Businesses can create orders with canonical line-item snapshots, progress orders through a controlled status machine, manage notes and history, and integrate with Customer, Offerings, Location, and Inventory kernels — with authorization, audit, and outbox on every mutation.

Payments checkout orchestration and marketplace cart are **deferred** per Doc 11 §9.2.

## 2. Implemented Components

| Component | Role |
|-----------|------|
| `OrderService` | Create, list, get, patch, idempotent creation |
| `OrderLifecycleService` | Status transitions, history, inventory side-effects |
| `OrderCalculationService` | Line and order total computation |
| `OrderNoteService` | Internal order notes |
| `OrderResolver` | Lookup, serialization, line/history loading |
| `validation/order.py` | Payload and transition validation |
| `v1_platform_orders.py` | REST API |

## 3. Database Changes

Migration: `infra/supabase/migrations/20260727070000_stage6_orders_kernel.sql`

| Table | Purpose |
|-------|---------|
| `orders_orders` | Sales order header with totals, payment fields, idempotency |
| `orders_order_line_items` | Canonical snapshots with reservation/deduction tracking |
| `orders_order_status_history` | Immutable status audit trail |
| `orders_order_notes` | Internal notes |

Unique indexes on `(business_id, order_number)` and idempotency key. RLS read policies.

## 4. Domain Models

- `SalesOrder` — location, optional `customer_contact_id`, status, payment_method/status, totals
- `OrderLineItem` — offering/variant refs + snapshot pricing fields
- `OrderStatusHistory` — from/to status with actor and reason
- `OrderNote` — internal note with author

## 5. Services

See §2. Line items built from `OfferingResolver` with price from variant or offering. Totals via `OrderCalculationService`.

## 6. APIs

Documented above. Create accepts `idempotency_key` (Doc 11 §9.2).

## 7. Authorization Integration

Reuses `require_business_actor()` with Doc 12 orders permissions: `orders.read`, `orders.create`, `orders.update_status`, `orders.cancel`.

## 8. Audit Integration

All mutations via `AuditService.record()` — resource types `order`, `order_note`. Status changes recorded in `orders_order_status_history`.

## 9. Outbox Integration

`order.created`, status-specific events (`order.accepted`, etc.), `order.updated`, `order.note.created`. Worker registry updated.

Customer timeline entries written on create and status change (Doc 11 §10.1 projection foundation).

## 10. Resolver Design

`OrderResolver` — business-scoped lookup, mutable gate (non-terminal states), detail serialization with line items.

## 11. Validation Rules

| Rule | Source |
|------|--------|
| Business ownership on customer, location, offerings | Doc 10 isolation |
| Controlled status transitions | Doc 04 §6.3 |
| Reason required for cancel/reject | Doc 04 audit |
| Stock availability on create | Doc 11 §10.3 |
| Idempotent create | Doc 11 §9.2 |
| Active offerings only | Doc 11 §9.1 |

## 12. Search Design

Orders: `order_number`, `internal_reference` ILIKE. Filters: status, customer, location.

## 13. Performance

Indexes on `(business_id, status, created_at)`, customer, location. Single query list; detail loads line items in one query.

## 14. Testing Summary

`apps/api/tests/test_orders_kernel.py` — lifecycle, inventory reserve/deduct/release, insufficient stock, isolation, audit/outbox.

## 15. Files Created

| Path |
|------|
| `infra/supabase/migrations/20260727070000_stage6_orders_kernel.sql` |
| `python/core/platform_core/validation/order.py` |
| `python/core/platform_core/resolvers/order_resolver.py` |
| `python/core/platform_core/services/order.py` |
| `python/core/platform_core/services/order_lifecycle.py` |
| `python/core/platform_core/services/order_calculation.py` |
| `python/core/platform_core/services/order_note.py` |
| `apps/api/src/platform_api/routers/v1_platform_orders.py` |
| `apps/api/tests/test_orders_kernel.py` |
| `apps/api/docs/stage-6-orders-kernel.md` |

## 16. Files Modified

| Path | Change |
|------|--------|
| `python/core/platform_core/models.py` | Order domain models |
| `python/core/platform_core/services/inventory.py` | Order reservation/deduction/release |
| `apps/api/src/platform_api/main.py` | Router registration |
| `apps/worker/src/platform_worker/outbox_consumer.py` | Known event handlers |

## 17. Architectural Compliance

| Decision | Justification |
|----------|---------------|
| `orders_*` table prefix | Doc 12 §567–568 |
| Line-item snapshots | Doc 11 §9.2 canonical snapshots |
| Customer via `customer_contact_id` FK | Doc 11 §9.2, Stage 4 reuse |
| Inventory via `InventoryService` only | Doc 11 §10.3, user guard |
| No payments module in Stage 6 | Doc 11 — payments separate module |
| Subset of Doc 04 order states | First Launch without delivery module |

## 18. Implementation Decisions

1. **Reserve on create** — stock held at pending; deduct on complete; release on cancel/reject.
2. **`SalesOrder` model name** — avoids shadowing Python/sqlalchemy `Order`.
3. **Complete requires `ready`** — enforces Doc 04 progression subset.
4. **Payment status fields** — placeholder for Payments module linkage without implementing checkout.

## 19. Future Dependencies

| Dependency | When |
|------------|------|
| Payments module | Online checkout, refund coordination (Doc 11 §9.2) |
| Fulfilment module | Delivery status handoff |
| Consumer cart/checkout APIs | Public commerce flow |
| Order expiry worker | Doc 04 `order.expired` |

## 20. Risks

| Risk | Mitigation |
|------|------------|
| Double inventory mutation | All stock ops through `InventoryService` |
| Status skip attempts | Validated transition matrix |
| Idempotency replay | Unique index + return existing order |

## 21. Verification Checklist

- [ ] `npx supabase db reset`
- [ ] `uv run pytest apps/api/tests/test_orders_kernel.py -q`
- [ ] `pnpm lint` / `pnpm typecheck`
- [ ] Full lifecycle deducts inventory correctly
- [ ] Cancel restores available stock

## 22. Integration Matrix

| Engine | Integration |
|--------|-------------|
| Customer (Stage 4) | FK + timeline projection |
| Offerings (Stage 5) | Line snapshots + price source |
| Inventory (Stage 5) | reservation / deduction / reversal |
| Location (Stage 3) | Order location FK + validation |
| Authorization | Existing `orders.*` permissions |
| Audit / Outbox | All mutations |
