# Stage 7 — Bookings & Scheduling Kernel

Module: `bookings` · Doc 11 §9.3, Doc 12 `bookings_bookings`

## APIs

Base: `/v1/platform/businesses/{business_id}/`

| Method | Path | Permission |
|--------|------|------------|
| GET | `/bookings` | `bookings.read` |
| POST | `/bookings` | `bookings.create` |
| GET | `/bookings/{id}` | `bookings.read` |
| PATCH | `/bookings/{id}` | `bookings.update` |
| POST | `/bookings/{id}/status` | `bookings.update` |
| POST | `/bookings/{id}/cancel` | `bookings.cancel` |
| POST | `/bookings/{id}/reschedule` | `bookings.update` |
| GET | `/bookings/{id}/history` | `bookings.read` |
| GET | `/bookings/{id}/notes` | `bookings.read` |
| POST | `/bookings/{id}/notes` | `bookings.update` |
| POST | `/bookings/check-availability` | `bookings.manage_availability` |

List filters: `?status=`, `?search=`, `?customer_contact_id=`, `?location_id=`, `?employee_id=`

## Reservation modes (Doc 11 §9.3)

`appointment`, `accommodation`, `table`, `class_session`, `rental`

## Status machine (Doc 04 §6.4 subset)

```text
pending → confirmed → checked_in → completed
    |          |
 rejected   cancelled / no_show
```

## Events

`booking.created`, `booking.updated`, `booking.confirmed`, `booking.rejected`, `booking.checked_in`, `booking.completed`, `booking.cancelled`, `booking.rescheduled`, `booking.no_show`, `booking.note.created`

Calendar sync, waitlists, notifications, and Payments checkout orchestration deferred per Doc 11 §9.3–§9.4.

## Tests

`apps/api/tests/test_bookings_kernel.py`

---

# Stage 7 Engineering Report

## 1. Executive Summary

Stage 7 implements the **Bookings & Scheduling Kernel** for First Launch. Businesses can create and manage reservations across documented modes (appointment, accommodation, table, class/session, rental), enforce scheduling conflicts, progress bookings through a controlled lifecycle, and integrate with Customer, Location, Employee, and Offerings kernels.

## 2. Implemented Components

| Component | Role |
|-----------|------|
| `BookingService` | Create, list, get, patch, idempotent creation |
| `BookingLifecycleService` | Status transitions, reschedule |
| `AvailabilityService` | Employee overlap + capacity conflict prevention |
| `BookingNoteService` | Internal notes |
| `BookingResolver` | Lookup, serialization, history |
| `validation/booking.py` | Payload, transition, availability validation |
| `v1_platform_bookings.py` | REST API |

## 3. Database Changes

Migration: `infra/supabase/migrations/20260727080000_stage7_bookings_kernel.sql`

| Table | Purpose |
|-------|---------|
| `bookings_bookings` | Booking header with slot, mode, capacity |
| `bookings_booking_status_history` | Status audit trail |
| `bookings_booking_notes` | Internal notes |

Indexes per Doc 12 §5.9 including `idx_bookings_location_time`. RLS read policies.

## 4. Domain Models

- `Booking` — reservation_mode, starts_at/ends_at, party_size, optional offering/employee/customer refs
- `BookingStatusHistory` — immutable transitions
- `BookingNote` — internal notes

## 5. Services

See §2. Cross-module refs (`offering_id`, `employee_id`) stored as UUID without cross-module FK (Doc 12 §5.10).

## 6. APIs

Documented above.

## 7. Authorization Integration

`bookings.read`, `bookings.create`, `bookings.update`, `bookings.cancel`, `bookings.manage_availability`

## 8. Audit Integration

All mutations via `AuditService`; status history table for lifecycle audit.

## 9. Outbox Integration

Canonical booking events per Doc 04 §6.4; worker registry updated. Customer timeline projection on create/status change.

## 10. Resolver Design

`BookingResolver` — business-scoped lookup, mutable gate, serialization.

## 11. Validation Rules

| Rule | Source |
|------|--------|
| ends_at > starts_at | Scheduling integrity |
| Controlled status transitions | Doc 04 §6.4 |
| Employee location assignment | Doc 11 §9.3 workforce integration |
| Employee double-booking prevention | Doc 11 §9.3 conflict prevention |
| Capacity limits (table/class/rental/accommodation) | Doc 11 §9.3 modes |
| Idempotent create | Doc 11 §9.3 |

## 12. Search Design

`booking_number`, `title`, `internal_reference` ILIKE; filters by status, customer, location, employee.

## 13. Performance

Composite indexes on location+time and employee+time for conflict queries. Single-query list.

## 14. Testing Summary

Lifecycle, employee conflict (409), reschedule, cancel, isolation, audit/outbox.

## 15. Files Created

| Path |
|------|
| `infra/supabase/migrations/20260727080000_stage7_bookings_kernel.sql` |
| `python/core/platform_core/validation/booking.py` |
| `python/core/platform_core/resolvers/booking_resolver.py` |
| `python/core/platform_core/services/booking.py` |
| `python/core/platform_core/services/booking_lifecycle.py` |
| `python/core/platform_core/services/availability.py` |
| `python/core/platform_core/services/booking_note.py` |
| `apps/api/src/platform_api/routers/v1_platform_bookings.py` |
| `apps/api/tests/test_bookings_kernel.py` |
| `apps/api/docs/stage-7-bookings-kernel.md` |

## 16. Files Modified

| Path | Change |
|------|--------|
| `python/core/platform_core/models.py` | Booking domain models |
| `apps/api/src/platform_api/main.py` | Router registration |
| `apps/worker/src/platform_worker/outbox_consumer.py` | Known event handlers |

## 17. Architectural Compliance

| Decision | Justification |
|----------|---------------|
| `bookings_bookings` table name | Doc 12 §569 |
| No Orders integration | User guard; Doc 11 keeps modules independent |
| No Inventory double-decrement | Doc 11 §9.3 explicit rule |
| Cross-module UUID refs without FK | Doc 12 §5.10 |
| Five reservation modes in schema | Doc 11 §9.3 required modes table |
| Payments fields placeholder only | Payments module separate (Doc 11 §9.4) |

## 18. Implementation Decisions

1. **Reschedule as operation** — emits `booking.rescheduled` without terminal `rescheduled` status (Doc 04 describes rescheduled as flow back to confirmed).
2. **Capacity check** — sums `party_size` for overlapping active bookings when `capacity` set.
3. **Employee conflict** — interval overlap query on active statuses.
4. **No calendar sync** — explicitly deferred Doc 11 §9.3.

## 19. Future Dependencies

| Dependency | When |
|------------|------|
| Payments module | Deposits/full collection (Doc 11 §9.3) |
| Workforce availability API | Provider schedule contracts (Doc 11 §9.3) |
| Waitlist/queue | Doc 11 §9.3 deferred |
| Public consumer booking UI | Website/checkout (Doc 11 §4.1) |
| Notifications | Reminder events (Doc 04 `booking.reminder.sent`) |

## 20. Risks

| Risk | Mitigation |
|------|------------|
| Capacity model oversimplified | Mode-specific rules expandable; conflict tests |
| Workforce schedule not fully modeled | Employee overlap + location assignment gates |
| Timezone handling | TIMESTAMPTZ storage; location timezone display deferred to UI |

## 21. Verification Checklist

- [ ] `npx supabase db reset`
- [ ] `uv run pytest apps/api/tests/test_bookings_kernel.py -q`
- [ ] `pnpm lint` / `pnpm typecheck`
- [ ] Lifecycle pending→completed works
- [ ] Employee overlap returns 409

## 22. Integration Matrix

| Engine | Integration |
|--------|-------------|
| Customer (Stage 4) | FK + timeline |
| Location (Stage 3) | FK + validation |
| Employee (Stage 3) | Assignment + overlap checks |
| Offerings (Stage 5) | Reservable offering validation + title |
| Authorization / Audit / Outbox | Standard platform engines |

## 23. Scope Verification

**Decision: Bookings & Scheduling Kernel BELONGS in First Launch — implemented.**

Supporting evidence from Document 11:

- **§602 Module roster:** “| 3 | Bookings | `bookings` | A — Full/Launch-Ready | Required to validate appointment, accommodation, table, class, and rental reservation models |”
- **§247 Enabled modules list** includes `bookings`.
- **§336:** “`ACC-005` Required because `bookings` is First Launch Full”
- **§366 First Launch table:** “| `bookings` | Calendar/list, detail, availability, policies, confirmation/cancellation | Waitlist, queue, advanced recurrence, vertical PMS views |”
- **§9.3 Shared foundation** mandates reservable offering, location, scheduling, availability evaluation, conflict prevention, status/confirmation/cancellation/reschedule, and idempotent creation.
- **Reference models 3–11** (restaurant, hotel, salon, gym, education, repair, rental) explicitly depend on `bookings`.

Supporting evidence from Document 12:

- **§569:** `bookings_bookings <- Module: bookings`
- **§650:** Required index `idx_bookings_location_time`
- **§666:** Optimistic concurrency on Booking entity
- **§947–949:** `bookings.*` permissions defined for First Launch

**Explicitly deferred (not implemented):** Doc 11 §9.3 deferred list — hotel PMS, channel manager, waitlists, walk-in queue, advanced recurrence, clinical records, fleet telemetry, table-floor optimization. User prompt §14 items (Google Calendar, Outlook, AI scheduling, route optimization) are not in First Launch scope.
