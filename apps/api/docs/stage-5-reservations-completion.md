# Stage 5 Completion — Reservations (Workforce, Invariants, Deposits, Booking UI)

Modules: `workforce` (Basic/Controlled optional) · `bookings` (existing kernel completed)  
Related frozen kernels: Orders / Payments / Inventory / Fulfilment (untouched internals)  
Availability overlap/capacity engine retained; provider reference cut over to WorkforceMember.

---

## Scope verification (pre-implementation)

**Confirmed — workforce module (Document 11 §8.1 / §10.5):**  
`workforce` is a Basic/Controlled-Depth optional module (ID `workforce`), entitlement/activation-gated. Required depth: profiles, service association, schedules/availability, Location applicability. Deferred: HR, leave, payroll, shift optimization. `identity_id` is optional and **does not grant Workspace access**.

**Confirmed — rental/resource out of scope (Document 11 §26.2 / FL-DEC-018):**  
Rental/resource depth remains open; not built. `rental` reservation mode may exist in the mode enum but resource inventory depth is deferred.

**Confirmed — My Activity UI is Stage 7 (Document 11 §17.7):**  
Stage 5 writes `consumer_activity_projections` (Document 10/12 §5.13) for booking lifecycle events only. No My Activity page.

**Confirmed — WEB-009 / WEB-010 (Document 11 §4.1–§4.2 / Document 09):**  
Consumer booking flow and bounded management; Workspace Bookings + Workforce pages at First Launch depth.

Permissions reused (Document 12): `workforce.read|create|update|manage_availability|deactivate` (not invented `view`/`manage` aliases).

---

## APIs

| Method | Path | Auth |
|--------|------|------|
| CRUD + assign/associate/availability | `/v1/platform/businesses/{id}/workforce/members…` | workforce.* |
| Bookings + policy | `/v1/platform/businesses/{id}/bookings…`, `/bookings-policy` | bookings.* |
| GET/POST | `/v1/public/websites/{slug}/booking/options\|availability` | public |
| POST | `/v1/public/websites/{slug}/bookings` | public (guest) |
| GET/POST | `/v1/public/bookings/{id}` (+ cancel/reschedule) | bounded token |

UI: `apps/web` `/{slug}/book`, `/{slug}/bookings/{id}` · `apps/workspace` bookings + workforce

## Events

`workforce.member_created`, `workforce.availability_updated`, `booking.deposit_collected` (+ existing booking lifecycle events)

---

# Stage 5 Reservations Completion — Engineering Report

## 1. Executive Summary

Stage 5 closes Document 11 §17.5 exit criteria by introducing a real **Workforce** provider domain (Document 10 §4.8), migrating `Booking.employee_id` → `Booking.provider_id`, proving mode-specific availability invariants, adding Business-configured **deposits** via `PaymentAttemptService`, shipping WEB-009/WEB-010 and Workspace Bookings/Workforce UIs, and writing **consumer activity projections** for Stage 7 My Activity — without building that UI or rental/membership depth.

## 2. Implemented Components

| Component | Role |
|-----------|------|
| `workforce_members` (+ location/service/availability) | Operational providers |
| `bookings_policies` | Deposit + cancel window config |
| `Booking.provider_id` | Cutover from BusinessEmployee |
| `WorkforceService` | CRUD, eligibility, audit/outbox |
| `AvailabilityService` | Provider joins + advisory locks |
| `BookingService` deposits | Server-side deposit + payment attempt |
| `PublicBookingService` | WEB-009/010 orchestration |
| `ConsumerActivityService` | Doc 12 §5.13 projection writer |
| Routers | `v1_workforce`, `v1_public_bookings`, bookings policy |
| apps/web + apps/workspace | Consumer + Business booking UX |

## 3. Database Changes

Migration: `infra/supabase/migrations/20260730000000_stage5_workforce_booking_providers.sql`

- Workforce tables + `bookings_policies` + `consumer_activity_projections`
- `provider_id`, deposit fields, `management_token`, `payment_status` includes `deposit_paid`
- Backfill WorkforceMembers from distinct `employee_id` values, copy location assignments, set `provider_id`
- **Verification DO block:** fails migration if any non-deleted booking with `employee_id` lacks `provider_id`
- Drops `employee_id` (pre-launch clean cutover)
- RLS SELECT policies for workforce / policies / activity projections

**Migration backfill verification:** SQL gate + `test_booking_migration.py` asserts `provider_id` column exists, `employee_id` absent, workforce tables present, and no booking references a missing WorkforceMember.

## 4. Domain Models

`WorkforceMember`, `WorkforceLocationAssignment`, `WorkforceServiceAssociation`, `WorkforceAvailability`, `BookingsPolicy`, `ConsumerActivityProjection`; `Booking` fields updated (`provider_id`, deposit, management token).

## 5. Services

- `WorkforceService` — module gate; serialize always includes `grants_workspace_access: false`
- `AvailabilityService` — provider eligibility + conflict; capacity modes unchanged; `pg_advisory_xact_lock` for concurrency
- `BookingService` — create/policy/deposit; activity projection on create
- `BookingLifecycleService` — provider reschedule; activity on confirm/cancel/complete
- `PublicBookingService` — options, availability states, guest book, token manage
- `PaymentAttemptService` — booking deposit → `deposit_paid` (existing sync path)
- `ConsumerActivityService` — projection upsert by identity

## 6. APIs

Platform workforce + bookings policy; public booking options/availability/create; token get/cancel/reschedule. Legacy `employee_id` accepted as alias for `provider_id` on create/availability payloads only.

## 7. Authorization Integration

Reuses Authorization Engine permissions (`workforce.*`, `bookings.*`). WorkforceMember `identity_id` is never consulted for membership or permission grants (Document 11 §10.5).

## 8. Audit Integration

Audited: workforce member created/updated/deactivated, location assign/unassign, service associate, availability updated, booking deposit collected, policy updated (+ existing booking events).

## 9. Outbox Integration

Emitted/handled: `workforce.member_created`, `workforce.availability_updated`, `booking.deposit_collected` (plus related workforce assign events registered in `KNOWN_HANDLERS`).

## 10. Resolver Design

`BookingResolver` serializes `provider_id` + deposit fields. Eligibility resolved via `WorkforceService.assert_provider_eligible` (active member, location assignment, service association when offering present). Public management resolves by `management_token` (+ expiry).

## 11. Validation Rules

- `provider_id` must reference active WorkforceMember assigned to booking Location and associated with service when `offering_id` set
- Deposit amount computed server-side from `bookings_policies` (never trusted from client)
- Closed/inactive Location rejected (`location_closed`)
- Cancel/reschedule respects `cancel_window_hours` (`cancellation_window_closed`)
- Expired management token → `expired_link`
- Post-migration: no orphan `provider_id` / no remaining `employee_id`

## 12. Performance

Provider time index retained pattern (`idx_bookings_provider_time`). Advisory transaction locks serialize overlapping creates/reschedules for the same provider/capacity key without changing the overlap query design.

## 13. Testing Summary

| Suite | Coverage |
|-------|----------|
| `test_workforce_kernel.py` | CRUD, location/service/availability, isolation, no Workspace grant, audit/outbox |
| `test_bookings_kernel.py` | Lifecycle + appointment provider conflict, accommodation/table/class_session invariants, concurrency |
| `test_booking_deposits.py` | Policy deposit + `booking.deposit_collected` |
| `test_booking_migration.py` | Schema cutover + no dangling provider FKs |

class_session remains **capacity-only** (no membership gate — Stage 6).

## 14. Files Created

- `infra/supabase/migrations/20260730000000_stage5_workforce_booking_providers.sql`
- `python/core/platform_core/services/workforce.py`
- `python/core/platform_core/services/consumer_activity.py`
- `python/core/platform_core/services/public_booking.py`
- `apps/api/src/platform_api/routers/v1_workforce.py`
- `apps/api/src/platform_api/routers/v1_public_bookings.py`
- `apps/api/tests/test_workforce_kernel.py`
- `apps/api/tests/test_booking_deposits.py`
- `apps/api/tests/test_booking_migration.py`
- `apps/web/src/lib/booking-api.ts`
- `apps/web/src/app/[slug]/book/*`
- `apps/web/src/app/[slug]/bookings/[bookingId]/*`
- `apps/workspace/src/app/b/[businessId]/bookings/*`
- `apps/workspace/src/app/b/[businessId]/workforce/*`
- `apps/api/docs/stage-5-reservations-completion.md`

## 15. Files Modified

- `python/core/platform_core/models.py` — workforce + booking fields
- `python/core/platform_core/services/availability.py`, `booking.py`, `booking_lifecycle.py`, `payment_attempt.py`
- `python/core/platform_core/validation/booking.py`, `resolvers/booking_resolver.py`
- `apps/api/src/platform_api/routers/v1_platform_bookings.py`, `main.py`
- `apps/worker/src/platform_worker/outbox_consumer.py`
- `apps/api/tests/test_bookings_kernel.py`
- `apps/workspace/src/app/b/[businessId]/layout.tsx`, `lib/api.ts`

## 16. Architectural Compliance

| Decision | Citation |
|----------|----------|
| WorkforceMember as booking provider (not BusinessEmployee) | Doc 10 §4.8; Doc 11 §10.5, §17.1, §17.5 |
| identity_id ≠ Workspace membership | Doc 11 §10.5 |
| Keep availability engine; change joins only | Doc 11 §17.5; plan Architecture Guard |
| Deposits via PaymentAttemptService | Doc 11 §17.5; reuse checkout payment pattern |
| WEB-009/WEB-010 + Workspace Bookings/Workforce | Doc 11 §4.1–§4.2; Doc 09 WEB-009/010 |
| Activity projections only (no My Activity UI) | Doc 10/12 §5.13; Doc 11 §17.7 |
| No rental depth | Doc 11 §26.2 FL-DEC-018 |
| No membership-gated class booking | Stage 6 |

Orders/Payments/Inventory/Fulfilment domain internals were not modified beyond booking payment-status sync already owned by PaymentAttemptService.

## 17. Implementation Decisions

1. **Clean drop of `employee_id`** after verified backfill — appropriate pre-launch; migration aborts on orphans.
2. **Advisory locks** for concurrency tests / overbooking races without EXCLUDE constraints.
3. **Management tokens** for WEB-010 bounded links (90-day default expiry).
4. **Legacy `employee_id` request alias** during API cutover for older clients/tests payloads.
5. Canonical permissions kept as `workforce.read/…` rather than inventing `workforce.view/manage`.

## 18. Future Dependencies

- Stage 6: membership-gated class booking
- Stage 7: My Activity UI consuming `consumer_activity_projections`
- FL-DEC-018: rental/resource depth if approved
- Deferred Workforce: HR, leave, payroll, optimization (Doc 11 §4.2)
- Deferred bookings: waitlist, queue, advanced recurrence, vertical PMS

## 19. Risks

| Risk | Mitigation |
|------|------------|
| Providers without service associations fail booking when offering selected | Server validation + UI filters associated providers |
| Concurrent creates without lock | `pg_advisory_xact_lock` in availability assert |
| Deposit offline status ambiguity | `pending_offline` vs `deposit_paid` both accepted; purpose metadata drives sync |
| Identity FK on linkage | Only link existing PlatformIdentity |

## 20. Verification Checklist

- [x] Workforce entry criterion satisfied (module + domain + APIs + UI)
- [x] appointment / accommodation / table / class_session invariants tested
- [x] concurrency overbooking test
- [x] deposits + payment_status
- [x] WEB-009 / WEB-010 + Workspace Bookings/Workforce
- [x] consumer activity projections written (no My Activity UI)
- [x] Migration backfill verified (no orphaned provider references; `employee_id` dropped)
- [x] No Workspace access from Workforce identity linkage
- [x] Rental depth / membership class gate / My Activity UI not implemented

## 21. Integration Matrix

| Surface | Integration |
|---------|-------------|
| Availability | WorkforceMember + WorkforceLocationAssignment |
| Booking create | Policy deposit → PaymentAttemptService |
| Lifecycle | Outbox + Audit + CustomerTimeline + ConsumerActivity |
| Public web | Guest identity bootstrap (checkout pattern) |
| Workspace | Bookings list/detail/policy; Workforce profile/assign/schedule |
| Worker | New event types in `KNOWN_HANDLERS` |

## 22. Scope Verification

Proceeded only after confirming:

1. **workforce** = Basic/Controlled optional module (Doc 11 §8.1, §10.5)  
2. **FL-DEC-018** rental/resource still open — not built  
3. **My Activity UI** = Stage 7 (Doc 11 §17.7); Stage 5 only feeds Doc 12 §5.13 projections  

End of Stage 5 engineering report.
