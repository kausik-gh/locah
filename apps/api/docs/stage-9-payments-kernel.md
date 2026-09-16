# Stage 9 — Payments Kernel

Module: `payments` · Doc 11 §9.4, Doc 12 `payments_payment_attempts`

## APIs

Base: `/v1/platform/businesses/{business_id}/`

| Method | Path | Permission |
|--------|------|------------|
| GET | `/payments` | `payments.read` |
| GET | `/payments/export` | `payments.export` |
| POST | `/payments` | `payments.read` + `orders.update_status` or `bookings.update` |
| GET | `/payments/{id}` | `payments.read` |
| POST | `/payments/{id}/record-settlement` | `orders.update_status` |
| POST | `/payments/{id}/refunds` | `payments.refund` |
| GET | `/payments/{id}/refunds` | `payments.read` |
| GET | `/payments/merchant-connection` | `payments.read` |
| PUT | `/payments/merchant-connection` | `payments.manage_connection` |

Webhook (unauthenticated, signature-verified): `POST /v1/webhooks/payments/{provider}`

List filters: `?status=`, `?source_type=`, `?source_id=`

## Payment statuses

`pending` → `processing` | `pending_offline` | `failed`  
`processing` → `succeeded` | `failed` | `pending_offline`  
`pending_offline` → `succeeded` | `failed` (via `record-settlement`)  
`succeeded` → `partially_refunded` | `refunded`

## Events (Doc 04)

`payment.initiated`, `payment.completed`, `payment.failed`, `payment.refunded`, `payment.webhook_processed`, `payment.merchant.updated`

## Tests

`apps/api/tests/test_payments_kernel.py`

---

# Stage 9 Engineering Report

## 1. Executive Summary

Stage 9 implements the **Payments Kernel** for First Launch. Businesses can create payment attempts linked to Orders or Bookings, process online outcomes via verified webhooks, record offline settlement for COD/pay-at-business flows, issue refunds, and manage merchant connection state. Orders and Bookings remain independent — payment status on those entities is updated only from the payments module.

## 2. Implemented Components

| Component | Role |
|-----------|------|
| `PaymentAttemptService` | Create, list, status transitions, offline settlement, export |
| `RefundService` | Partial/full refunds with canonical state |
| `MerchantService` | Provider connection onboarding state |
| `PaymentWebhookService` | Doc 12 §18.6 pipeline: verify → idempotency → durable receipt → process |
| `PaymentResolver` | Lookup and serialization |
| `validation/payment.py` | Payload, transitions, refund rules |
| `payments/provider_adapter.py` | Stub/Razorpay signature verification |
| `v1_platform_payments.py` | Platform REST API |
| `webhooks_payments.py` | Inbound webhook router |

## 3. Database Changes

Migration: `infra/supabase/migrations/20260727090000_stage9_payments_kernel.sql`

| Table | Purpose |
|-------|---------|
| `payments_merchant_connections` | Per-business provider onboarding state |
| `payments_payment_attempts` | Canonical payment attempts with idempotency |
| `payments_refunds` | Refund records |
| `payments_webhook_receipts` | Durable webhook idempotency receipts |

Indexes: business+status, source linkage, idempotency partial unique. RLS read policies on business-scoped tables.

## 4. Domain Models

`MerchantConnection`, `PaymentAttempt`, `PaymentRefund`, `PaymentWebhookReceipt` in `platform_core/models.py`.

Source types: `order`, `booking` (schema allows `membership`; API rejects until memberships kernel ships per Doc 11 §9.5 dependency).

## 5. Services

Focused services per architecture guard — no monolithic payment service. Cross-module integration: payments validates order/booking ownership via resolvers and updates `payment_status` on source entities after status changes.

## 6. APIs

REST under `/v1/platform/businesses/{business_id}/payments*`. Webhook at `/v1/webhooks/payments/{provider}`. Response envelope `{ data, meta: { correlation_id } }`.

## 7. Authorization Integration

Reuses `AuthorizationService` and documented permissions (Doc 12 §permissions table): `payments.read`, `payments.refund`, `payments.manage_connection`, `payments.export`. Payment creation additionally requires source-specific checkout permission (`orders.update_status` or `bookings.update`).

## 8. Audit Integration

Audited: payment initiated, completed, failed, refunded, webhook processed, merchant updated. Webhook audit uses business primary owner as actor with `actor_context=system`.

## 9. Outbox Integration

Events: `payment.initiated`, `payment.completed`, `payment.failed`, `payment.refunded`, `payment.webhook_processed`, `payment.merchant.updated`. Registered in worker `KNOWN_HANDLERS`.

## 10. Resolver Design

`PaymentResolver.resolve_attempt` — business-scoped lookup with soft-delete filter. `resolve_merchant` — provider-scoped connection lookup. Serialization includes refundable balance.

## 11. Validation Rules

- Business ownership via path + RLS
- Order/booking ownership and amount bounds
- Customer contact ownership when provided
- State machine transitions (`ALLOWED_TRANSITIONS`)
- Refund amount ≤ refundable balance; reason required
- Webhook HMAC signature (`PAYMENT_WEBHOOK_SECRET`)
- Idempotency key deduplication per business
- Membership source rejected until module available

## 12. Performance

Indexes on `(business_id, status, created_at)`, `(business_id, source_type, source_id)`, partial unique on idempotency. Webhook duplicate check uses `(provider, provider_event_id)` unique constraint.

## 13. Testing Summary

`test_payments_kernel.py`: COD offline settlement + order sync, online webhook + refund, invalid signature rejection, business isolation, audit/outbox verification, merchant connection upsert.

## 14. Files Created

- `infra/supabase/migrations/20260727090000_stage9_payments_kernel.sql`
- `python/core/platform_core/validation/payment.py`
- `python/core/platform_core/payments/__init__.py`
- `python/core/platform_core/payments/provider_adapter.py`
- `python/core/platform_core/resolvers/payment_resolver.py`
- `python/core/platform_core/services/merchant.py`
- `python/core/platform_core/services/payment_attempt.py`
- `python/core/platform_core/services/refund.py`
- `python/core/platform_core/services/payment_webhook.py`
- `apps/api/src/platform_api/routers/v1_platform_payments.py`
- `apps/api/src/platform_api/routers/webhooks_payments.py`
- `apps/api/tests/test_payments_kernel.py`
- `apps/api/docs/stage-9-payments-kernel.md`

## 15. Files Modified

- `python/core/platform_core/models.py` — payment domain models
- `apps/api/src/platform_api/main.py` — router registration
- `apps/worker/src/platform_worker/outbox_consumer.py` — payment event handlers
- `.env.example` — `PAYMENT_WEBHOOK_SECRET`

## 16. Architectural Compliance

Reuses Identity, Business, Membership, Authorization, Audit, Outbox, Worker, Orders, Bookings, Customer. No ledger/accounting. No payment logic in Orders module. Provider objects stay in adapter metadata (Doc 11 §9.4 Mandatory boundaries).

## 17. Implementation Decisions

| Decision | Rationale (Doc 11 / Doc 12) |
|----------|----------------------------|
| Event names `payment.initiated` / `payment.completed` | Doc 04 canonical event catalog |
| Offline methods → `pending_offline` until settlement | Doc 11 §9.4: must not mark offline balance paid on order/booking confirm alone |
| Membership payments deferred | Doc 11 §9.5 — memberships kernel not yet implemented |
| Synchronous webhook processing in API | Doc 12 §18.6 durable receipt first; async job enqueue deferred to keep launch scope minimal while honoring verify→idempotency→receipt |
| Stub provider default | Doc 11 §9.4 provider abstraction; production Razorpay adapter hooks via env |

## 18. Future Dependencies

- Memberships kernel for `source_type=membership`
- Full Razorpay production adapter (KYC, capture, settlement events)
- `payment.settlement.received` when reconciliation UI ships
- Payment links (`WEB-015`) — explicitly deferred Doc 11 §9.4
- Recurring payments — gated by `FL-DEC-005`
- Async `webhook.process_payment` job per Doc 12 §18.6 Step 4

## 19. Risks

| Risk | Mitigation |
|------|------------|
| Provider KYC delay | Stub adapter + approved offline methods |
| Webhook replay | Unique `(provider, provider_event_id)` receipt |
| Cross-tenant leakage | Business-scoped resolvers + RLS |
| Stale concurrent updates | Optimistic `version` on payment attempts |

## 20. Verification Checklist

- [x] Scope verified: `payments` module A — Full/Launch-Ready (Doc 11 §607, §9.4)
- [x] Schema matches Doc 12 `payments_payment_attempts`
- [x] Permissions from Doc 12 payments row
- [x] Outbox events registered
- [x] Orders/bookings payment_status synced from payments only
- [x] Webhook signature verification
- [x] Idempotency on create and webhooks
- [x] Finance/accounting not implemented (Stage 8 stop correct)

## 21. Integration Matrix

| Module | Integration |
|--------|-------------|
| Orders | `source_type=order`; updates `payment_status` |
| Bookings | `source_type=booking`; updates `payment_status` |
| Customer | Optional `customer_contact_id` validation |
| Authorization | Doc 12 payment permissions |
| Audit | All mutation paths |
| Outbox | Status and merchant events |
| Worker | Known handler registration |

## 22. Scope Verification

**Canonical module:** `payments` — **Confirmed First Launch** (Doc 11 §607 table row 8, §9.4).

> Doc 11 §607: `| 8 | Payments | payments | A — Full/Launch-Ready | Required for real online/deposit/refund flows while supporting approved offline methods |`

> Doc 11 §9.4 Required payment patterns: online full payment; COD/pay later/pay at Business; deposit/partial; refunds; merchant connection; payment attempt/status/failure; linkage to Orders, Bookings, Memberships; provider abstraction and webhook processing.

> Doc 12 §570: `payments_payment_attempts <- Module: payments`

> Doc 12 §952: `payments.read | payments.refund | payments.manage_connection | payments.export`

**Explicitly NOT implemented (in scope verification):**

- General ledger / accounting (Doc 11 §799, Stage 8 stop)
- Payment links / `WEB-015` (Doc 11 §798)
- Platform wallet, escrow, BNPL (Doc 11 §791–795)
- Membership billing linkage (Doc 11 §9.5 — deferred until memberships kernel)
- Recurring collection unless `FL-DEC-005` approved (Doc 11 §772)
