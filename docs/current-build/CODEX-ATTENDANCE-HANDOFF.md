# Shared Attendance + Check-ins handoff

## Branch and commits

- **BRANCH:** `parallel/codex-attendance`
- **HEAD SHA:** run `git rev-parse HEAD` after checkout; the code tip at handoff authoring is `8f754a8569588ccbce96ed68eeec2b5def764e5f`. The documentation commit necessarily changes the final branch tip.
- **MAIN BASE SHA:** `1cb02e1449815ecf365a976d1694c9bd6681b2c2`
- **COMMITS:** `5d358ee` — shared attendance engine, migration, endpoints, Workspace flows and PostgreSQL tests; `8f754a8` — minimal shared API, permission, assignment-scope and event registration; a final documentation commit contains this handoff.
- **MIGRATIONS:** `infra/supabase/migrations/20260930230000_attendance_events.sql`. It is additive and uses the requested migration range. No hosted Supabase instance was changed.

## Domain model

`attendance_events` is one business-tenant table for `membership_checkin`, `academic_session`, `staff_site` and `booking_arrival`. It stores source occurrence ID, exactly one contact/workforce subject, optional location and assignee, mode-specific status, actor, channel, timestamps, verification metadata, idempotency key and version. Academic occurrence/student and booking-arrival uniqueness are enforced by indexes; transaction advisory locks serialize replay. Source domains retain their own lifecycle, eligibility and identity truth. `geo_verified` cannot be true in this implementation because no real verifier is connected.

## Implemented surfaces and contracts

- **MEMBER CHECK-IN IMPLEMENTED:** QR/manual API and Workspace form accept a stable membership enrolment UUID, call `MembershipCheckinEligibility.decide`, record allowed/warning visits once, and reject denied visits. A repeated request key returns the original record. The default provider fails closed; it does **not** infer eligibility from Membership tables.
- **ACADEMIC ATTENDANCE IMPLEMENTED:** read-only Academics source adapter, today's sessions, scoped class roster, unsaved default-present presentation, one save for every active enrolled student, explicit exceptions (`absent`, `late`, `excused`), replay protection, and owner/manager correction with version and audit reason. It references the existing session occurrence; it does not define classes, students, enrolments or teachers. If the Academics tables are missing it fails closed.
- **STAFF/SITE ATTENDANCE IMPLEMENTED:** active workforce member and business location validation, location assignment check, self check-in/checkout, replay protection and a Workspace self-service form. GPS is expressly *not* asserted.
- **BOOKINGS CONTRACT:** confirmed, customer-linked booking can produce one physical-arrival event. Booking status is not updated; a real PostgreSQL test asserts this. No booking workflow or public UI was modified.
- **MEMBERSHIP CONTRACT:** `MembershipCheckinDecision(enrolment_id, customer_contact_id, state, reason)` and `MembershipCheckinEligibility` protocol in `attendance_contracts.py`; route dependency `get_membership_eligibility` currently supplies `UnconnectedMembershipEligibility` (503).
- **ACADEMICS CONTRACT:** `AcademicAttendanceSource` reads `academics_sessions`, `academics_batches`, `academics_enrolments` and contact names, checks the tenant/session status and teacher/location scope. It depends on the separately owned P5 schema retaining these field names and its RLS exposing only authorized rows.

## Security and events

- **RLS:** tenant policy plus restrictive location/assignee policies for `platform_api`; no direct `anon` or `authenticated` table grant. Server-side permission, module, tenant, assignment and location checks precede writes. A local PostgreSQL tenant-isolation test confirms another business sees zero events; a scoped staff member cannot read or check out a colleague's event.
- **PERMISSIONS:** `attendance.read`, `attendance.record`, `attendance.manage`. Assignment-scoped roles may receive read/record but not manage. Existing owner permission aggregation picks up the identifiers. Broad role-template/navigation edits were deliberately deferred to owning integration lanes.
- **EVENTS:** outbox/audit emit `attendance.checked_in`, `attendance.checked_out`, `attendance.session_recorded`. Academic correction is audit-recorded with reason; booking state is untouched.

## Verification

- **DATABASE TEST RESULTS:** `5 passed, 1 Starlette/httpx deprecation warning` against disposable local PostgreSQL 18 on `127.0.0.1:55441`, with all `origin/main` migrations, Attendance migration and platform seed applied. Each case rolls back its fixtures. Coverage: Asha/Bharat class save and replay, unrelated teacher rejection, member allow/replay/deny and tenant RLS, staff own scope/checkout/no fake geo proof, booking arrival idempotency/booking-state preservation, unauthenticated API and rejected geo spoof field. The P5 tables were transactionally stubbed because that separate branch is not on this base; after merge, the test conditionally uses the actual P5 tables.
- **STATIC/BUILD:** Workspace production build, TypeScript check, ESLint, Ruff, targeted Mypy (three new Python source files), and Git whitespace check passed. The build emitted existing CSS Autoprefixer mixed-support warnings. These checks are not browser acceptance.
- **PLAYWRIGHT RESULT:** **NOT RUN / NOT PASSING.** Chrome is installed, but this checkout has no authenticated local API + Workspace + auth/browser-fixture stack, and neither the P2-02 Memberships eligibility adapter nor P5 Academics schema is present on `origin/main`. A browser on an existing localhost/deployed build would not exercise this branch. No text-injection or mocked browser result is claimed.

## Partial, activation and merge boundaries

- **PARTIAL:** front-desk QR input is a UUID scan/manual field; actual Membership QR payload parsing and eligibility decision are an adapter responsibility. Guardian/customer attendance history is not exposed. Staff check-in has no GPS proof or shift scheduling. Today's list currently shows subject UUIDs rather than resolved names.
- **ACTIVATION_REQUIRED:** merge P2-02 and wire its authoritative eligibility provider into the route dependency; merge P5 Academics and verify the source SQL, teacher RLS and real roster test; grant narrow teacher/front-desk/staff permissions through the owning role-template workflow; enable the Attendance module for target businesses; run authenticated desktop Chrome flows at desktop and 390px against a local API, Workspace and database. Do not expose member check-in as working until the provider is connected.
- **SHARED FILES TOUCHED:** `apps/api/src/platform_api/main.py`, `packages/permissions/src/identifiers.ts`, `python/core/platform_core/permissions.py`, `python/core/platform_core/authorization/assignment_scope.py`, `python/core/platform_core/events/catalogue.py` — all confined to the separate `chore(integration)` commit.
- **CLAUDE INTEGRATION REQUIRED:** connect P2-02 Memberships eligibility and real QR enrolment reference; do not import Attendance into Memberships or duplicate Membership lifecycle logic.
- **KNOWN LIMITATIONS:** tests exercise service/database behavior but not a signed-in browser; guardian isolation is by absent customer-facing route and denied direct table grant, not a portal acceptance test; no real P5 RLS test before its merge.
- **KNOWN MERGE RISKS:** P2-02/P5 may add adjacent router, permission and role-template changes; reconcile those small shared edits, then rerun the whole PostgreSQL suite. If P5 changes its academic table/column contract, update only the read-only adapter after inspecting the final schema.
- **READY_TO_INTEGRATE = NO** for product activation. The branch is ready for code review/merge preparation, but real Membership eligibility, merged Academics, and authenticated browser acceptance are required before claiming an end-to-end operational Attendance release.
