# Stage 4 — CRM & Customer Management Kernel

Module: `customer-relationships` · Entity: `CustomerContact` (Doc 10 §4.7)

## APIs

Base: `/v1/platform/businesses/{business_id}/`

| Method | Path | Permission |
|--------|------|------------|
| GET | `/customers` | `customers.read` |
| GET | `/customers/export` | `customers.export` |
| POST | `/customers` | `customers.update` |
| GET | `/customers/{id}` | `customers.read` |
| PATCH | `/customers/{id}` | `customers.update` |
| POST | `/customers/{id}/block` | `customers.update` |
| POST | `/customers/{id}/archive` | `customers.update` |
| POST | `/customers/{id}/restore` | `customers.update` |
| GET | `/customers/{id}/timeline` | `customers.read` |
| GET | `/customers/{id}/notes` | `customers.read` |
| POST | `/customers/{id}/notes` | `customers.manage_notes` |

List filters: `?status=`, `?search=`, `?location_id=`

## Events

Emit: `customer.created`, `customer.updated`, `customer.blocked`, `customer.archived`, `customer.restored`, `customer.tagged`, `customer.note.created`

Timeline projection handlers for `order.created` / `booking.confirmed` deferred until those modules ship (Doc 11 §10.1).

## Tests

`apps/api/tests/test_customer_kernel.py`

---

# Stage 4 Engineering Report

## 1. Executive Summary

Stage 4 implements the **CRM & Customer Management Kernel** for the `customer-relationships` module. Businesses can create and manage customer contacts (distinct from platform authentication), apply tags, manage notes, view a timeline foundation, and search/filter customers — all scoped to a single business with authorization, audit, and outbox integration.

## 2. Implemented Components

| Component | Role |
|-----------|------|
| `CustomerService` | Contact lifecycle: CRUD, block, archive, restore, export, dedup |
| `CustomerNoteService` | Internal notes (`customers.manage_notes`) |
| `CustomerTimelineService` | Timeline projection foundation (read + idempotent write) |
| `CustomerResolver` | Lookup, operable gate, serialization |
| `validation/customer.py` | Create/patch/note/tag validation |
| `v1_platform_customers.py` | REST API |

## 3. Database Changes

Migration: `infra/supabase/migrations/20260727050000_stage4_customer_relationships_kernel.sql`

| Table | Purpose |
|-------|---------|
| `customer_relationships_contacts` | Business-scoped customer profile |
| `customer_relationships_notes` | Internal notes with author |
| `customer_relationships_timeline_entries` | Activity projection store |

Partial unique indexes on `(business_id, phone)` and `(business_id, email)` for deduplication. Timeline idempotency via `(business_id, source_event_id)`.

## 4. Domain Models

- `CustomerContact` — display_name, phone, email, status, tags[], preferred_location_id, optional identity_id
- `CustomerNote` — body, author_identity_id
- `CustomerTimelineEntry` — activity_type, resource_type/id, summary JSONB, occurred_at, source_event_id

## 5. Services

See §2. `CustomerService` orchestrates timeline seed on create (`customer.registered` entry).

## 6. APIs

Documented above. Create uses `customers.update` (Doc 12 defines no separate create permission).

## 7. Authorization Integration

All endpoints use `require_business_actor(PERMISSION)` → `AuthorizationService`. Permissions from Doc 12 §8.2 unchanged.

## 8. Audit Integration

Audit on: create, update, block, archive, restore, tag changes, note create. Resource types: `customer`, `customer_note`.

## 9. Outbox Integration

Events registered in worker `KNOWN_HANDLERS`. Handlers stub-acknowledged pending downstream consumers.

## 10. Resolver Design

`CustomerResolver`: `resolve()`, `require_operable()`, `resolve_operable()`, `serialize_contact/note/timeline_entry`.

## 11. Validation Rules

- Display name required (1–120 chars)
- At least one of phone or email on create; cannot clear both on patch
- Email format via shared `validation/contact.py`
- Tags: max 20, max 64 chars each, normalized lowercase, deduped
- Preferred location must belong to business and be active
- Phone/email dedup per business (DB + service)
- Optimistic concurrency via `version`

## 12. Search Design

`?search=` matches display_name, phone, or email (case-insensitive ILIKE). Indexes on `(business_id, display_name)`, phone, email. Cursor pagination deferred — consistent with Stages 2–3 (Doc 10 §29.1 target for shared follow-up).

## 13. Performance

- Composite indexes for business + status + search columns
- Timeline list capped at 100 entries per request
- Single-query list; no N+1 on list endpoints
- Export returns serialized contacts in one query

## 14. Testing Summary

`test_customer_kernel.py`: CRUD, search, dedup conflict, archive/restore, notes, timeline, outbox/audit, business isolation, owner permissions.

## 15. Files Created

```
infra/supabase/migrations/20260727050000_stage4_customer_relationships_kernel.sql
python/core/platform_core/validation/customer.py
python/core/platform_core/resolvers/customer_resolver.py
python/core/platform_core/services/customer.py
python/core/platform_core/services/customer_note.py
python/core/platform_core/services/customer_timeline.py
apps/api/src/platform_api/routers/v1_platform_customers.py
apps/api/tests/test_customer_kernel.py
apps/api/docs/stage-4-customer-relationships-kernel.md
```

## 16. Files Modified

```
python/core/platform_core/models.py
apps/api/src/platform_api/main.py
apps/worker/src/platform_worker/outbox_consumer.py
```

## 17. Architectural Compliance

- Reuses Authorization, Audit, Outbox, Gates, Location resolver for preferred_location
- Table naming per Doc 12 §5.3 (`customer_relationships_*`)
- Customers are business data, not auth users (Doc 11 §10.1)
- No cross-module table reads; timeline ready for event projections (Doc 10 §14.2)
- No orders, bookings, marketing, loyalty, or segmentation automation
- Stages 1–3 untouched

## 18. Implementation Decisions

### Normalized contact fields
Document 10 §30.3 prohibits JSONB for filterable customer contact. `phone` and `email` are `TEXT` columns with partial unique indexes — same decision as Stage 3 location contact normalization.

### Tags as TEXT[] not segments
Document 11 defers advanced segmentation and customer groups. Manual tags (Document 04) implemented as normalized `TEXT[]` on the contact row for launch depth — sufficient for labeling without a segment engine.

### Separate note service
Notes require `customers.manage_notes` while profile edits use `customers.update`. `CustomerNoteService` mirrors Stage 3's assignment/note permission split pattern.

### Timeline foundation only
Document 11 requires timeline from order/booking/membership/lead events, but those modules are out of scope for this stage. `customer_relationships_timeline_entries` + `CustomerTimelineService.record_entry()` with idempotent `source_event_id` provides the projection store; only `customer.registered` is written synchronously today.

### Create permission
Doc 12 lists `customers.update` but not `customers.create`. Create endpoint uses `customers.update` — consistent with permission registry.

### Customer groups deferred
Document 11 explicitly defers segmentation/groups. Not implemented.

## 19. Future Dependencies

| Stage | Depends on CRM |
|-------|----------------|
| Orders | `customer_relationships.on_order_created` worker handler |
| Bookings | Timeline projection from `booking.confirmed` |
| Memberships | Enrolment timeline entries |
| Leads | Lead-won → CustomerContact linkage |
| Loyalty | Stable customer + event history |

## 20. Risks

| Risk | Mitigation |
|------|------------|
| Dedup false positives on shared phones | Partial unique index; explicit 409 on conflict |
| Timeline lag when orders ship | Idempotent `source_event_id` + worker handlers (future) |
| Export without rate limit | `customers.export` permission gate; full-list export acceptable at launch scale |

## 21. Verification Checklist

- [x] Customer profile, contact, status, tags, preferred location
- [x] Business-scoped isolation
- [x] Search and status filtering
- [x] Archive / restore / block lifecycle
- [x] Notes with separate permission
- [x] Timeline foundation (read + seed entry)
- [x] Authorization on all endpoints
- [x] Audit + outbox on mutations
- [x] Dedup on phone/email
- [x] Ruff + Mypy pass
- [x] No changes to Stages 1–3 frozen code paths
- [ ] Full pytest with live Supabase
