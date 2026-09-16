# Stage 3 — Location & People Kernel

First business operations domain: locations, branches, employees, and location assignments.

## Scope

- **Location domain** — primary + branches, status, address, contact, timezone, coordinates, internal code, notes
- **Employee domain** — business workforce profiles (not authentication); optional Identity/Membership link
- **Assignments** — assign, transfer, remove, primary assignment per employee

## Database

Migration: `infra/supabase/migrations/20260727040000_stage3_location_people_kernel.sql`

- Extends `business_locations` with `status`, `internal_code`, `phone`, `email`, `latitude`, `longitude`, `notes`
- Partial unique index: one active primary location per business
- New `business_employees` and `business_employee_location_assignments` tables with RLS read policies

## Services

| Service | Responsibility |
|---------|----------------|
| `LocationService` | Location lifecycle (CRUD, primary, archive, reactivate) |
| `EmployeeService` | Employee lifecycle (CRUD, deactivate) |
| `EmployeeLocationAssignmentService` | Assignment lifecycle (assign, remove, transfer, primary assignment) |

## APIs

Base path: `/v1/platform/businesses/{business_id}/`

### Locations

| Method | Path | Permission |
|--------|------|------------|
| GET | `/locations` | `locations.read` |
| POST | `/locations` | `locations.create` |
| GET | `/locations/{id}` | `locations.read` |
| PATCH | `/locations/{id}` | `locations.update` |
| POST | `/locations/{id}/set-primary` | `locations.update` |
| POST | `/locations/{id}/archive` | `locations.delete` |
| POST | `/locations/{id}/reactivate` | `locations.update` |

List filters: `?status=`, `?search=` (name substring, case-insensitive).

### Employees

| Method | Path | Permission |
|--------|------|------------|
| GET | `/employees` | `workforce.read` |
| POST | `/employees` | `workforce.create` |
| GET | `/employees/{id}` | `workforce.read` |
| PATCH | `/employees/{id}` | `workforce.update` |
| POST | `/employees/{id}/deactivate` | `workforce.deactivate` |
| GET | `/employees/{id}/locations` | `workforce.read` |
| POST | `/employees/{id}/locations` | `workforce.update` |
| DELETE | `/employees/{id}/locations/{location_id}` | `workforce.update` |
| POST | `/employees/{id}/transfer` | `workforce.update` |

List filters: `?status=`, `?search=` (display_name substring).

Legacy `/v1/b/{business_id}/locations` remains for backward compatibility.

## Events

- `location.created`, `location.updated`, `location.archived`
- `employee.created`, `employee.updated`, `employee.deactivated`, `employee.assigned`, `employee.unassigned`, `employee.transferred`

## Rules

- Exactly one primary location per business (DB-enforced)
- Primary location cannot be archived until another location is promoted
- Archived locations require explicit reactivation (PATCH `status=active` or `/reactivate`)
- Employee is distinct from platform authentication/membership
- No duplicate employee–location assignments (DB unique constraint)
- One primary assignment per employee (partial unique index)

## Tests

`apps/api/tests/test_location_people_kernel.py`

---

# Stage 3 Engineering Report (Review Pass)

## Architectural Changes (Review Pass)

1. **Extracted `EmployeeLocationAssignmentService`** — assignment assign/remove/transfer logic moved out of `EmployeeService` into a dedicated service aligned with Stage 2 engine-per-concern pattern.
2. **Normalized queryable location fields** — replaced `coordinates JSONB` and `contact JSONB` with explicit `latitude`, `longitude`, `phone`, `email` columns per Document 10 §30.3 and Document 12 §5.8.
3. **Removed redundant employee `contact JSONB`** — workforce contact uses top-level `email` and `phone` columns (Document 04 field matrix; Doc 10 prohibits JSONB for filterable contact data).
4. **Validation aligned with Stage 2E–2H** — kept dedicated `validation/*.py` modules; added shared `validation/contact.py` for email/phone format rules.
5. **List filtering** — added optional `search` query parameter on location and employee list endpoints; cursor pagination deferred (see decisions below).

## Implementation Decisions

### Display name column reuse

The canonical `BusinessLocation` entity uses a human-readable label (Document 03 §1.10). Stage 1 foundation already defined `business_locations.name`. Stage 3 maps API “display name” semantics to `name` rather than adding a duplicate column, avoiding a redundant migration on an existing table.

### Coordinates and contact — normalized, not JSONB

**Document 10 §30.3** explicitly prohibits JSONB for fields used in filtering, sorting, or reporting. **Document 12 §5.8** prohibits JSONB for queryable business operational data. **Document 04** lists per-location phone and geo-coordinates as distinct fields.

Accordingly:
- `latitude` / `longitude` are `DOUBLE PRECISION` columns (geo point without PostGIS in MVP).
- `phone` / `email` are `TEXT` columns on `business_locations`.
- `address` remains JSONB — established Stage 1 precedent for structured postal addresses (variable shape, not primary filter key).
- `hours` remains JSONB — per-day schedule structure (Document 03).

Employee contact uses `email` and `phone` columns only; no parallel JSONB blob.

### Assignment service extraction

Assignment has its own table, REST endpoints, outbox events (`employee.assigned`, `employee.unassigned`, `employee.transferred`), and primary-assignment invariants. Keeping it inside `EmployeeService` blurred lifecycle boundaries. Extraction mirrors Stage 2’s one-service-per-engine pattern (`BusinessSettingsService`, `PermissionEngineService`, etc.) while `EmployeeService` retains create/update/deactivate only.

`EmployeeResolver.serialize_employee()` centralizes read-model shaping for both services.

### Validation architecture

Stages 2A, 2E–2H established `python/core/platform_core/validation/<domain>.py` with `validate_*_create_payload` / `validate_*_patch_payload` raising `ValidationError`. Stage 3 follows this — not inline service validation (except membership-link and duplicate-code checks that require DB reads).

Shared contact rules live in `validation/contact.py`, reused by location and employee validators.

### Pagination — search only, cursor deferred

**Document 10 §29.1** mandates cursor-based pagination for list endpoints. No `v1_platform_*` router implements cursor pagination yet (members, invitations, entitlements all return full lists). Introducing cursor pagination only for Stage 3 would create an inconsistent partial implementation.

**Decision:** add `?search=` and `?status=` filters (matching existing status-filter pattern) and `meta.count`. Cursor pagination (`cursor`, `limit`, `meta.next_cursor`) will be introduced via a shared platform list helper across all routers in a follow-up pass.

### Service radius

Document 03/04 reference `service radius` on locations. Deferred — not in Stage 3 First Launch scope (Document 11 §6 Location Foundation lists address, hours, availability scope only).

## Regression Safety

| Area | Status |
|------|--------|
| API routes / permissions | Unchanged paths and permission keys |
| Legacy `/v1/b/.../locations` | Still uses `create_location_simple`; unaffected |
| Outbox event types | Unchanged |
| Audit actions | Unchanged |
| Resolvers | Extended (`serialize_employee` on resolver); lookup behavior unchanged |
| Migration | Single migration file updated before deploy; no conflict with applied migrations if reset locally |

## Compliance with Documents 04–12

- Reuses Authorization, Audit, Outbox, Gates, Identity, Membership engines — no parallel implementations.
- Location-scoped assignment table includes `business_id` + FK to `business_locations` (Document 12 §5.5).
- Workforce profiles independent of Workspace access (Document 11 §10.5).
- No HR/payroll/attendance scope introduced.
- JSONB rules respected for operational queryable fields.

## Files Touched (Review Pass)

**Created:** `services/employee_location_assignment.py`, `validation/contact.py`

**Modified:** migration, models, `services/employee.py`, `services/location.py`, `resolvers/employee_resolver.py`, `validation/location.py`, `validation/employee.py`, both platform routers, this doc.
