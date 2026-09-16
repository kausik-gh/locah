# LOCAH — First Launch Completion Report (Evidence-Based, FINAL)

**Status: this report supersedes the earlier device-bridge-constrained version of this same document.** That earlier pass could read/write files but had no shell execution, so every fix in it was labeled "implemented, not verified." This pass had full shell execution against a fresh, locally-bootstrapped scratch database (all migrations + seed, mirroring CI's `postgres:16` container) and produced real, reproduced `pytest` output.

## 1. Migrations

All 31 migrations (27 pre-existing + 4 from this engagement) applied cleanly on a fresh database. Fixed one ordering hazard before applying: two migrations shared the identical `20260915010000` timestamp prefix (`stage7_activity_business_names_resolver.sql` and `stage7_notification_mute_resolver.sql`) — renamed the latter to `20260915020000`. No SQL content changed.

## 2. Root causes found and fixed this pass

| # | Root cause | Tests affected | Fix |
|---|---|---|---|
| A | `apps/api/src/platform_api/db.py` had dropped the `async_sessionmaker` import while `get_service_db_session()` (all `/v1/admin/*` routes, payment webhook) still used it — a `NameError` | 9 (`test_admin_support.py` ×6, `test_isolation.py::test_super_admin_action_is_attributed`, `test_payments_kernel.py` ×2) | Restored the import |
| B | `test_outbox.py`'s bounded 10-poll retry never reached its own event because the shared outbox batch was backlogged by other tests writing outbox rows without dispatching them | 1 (`test_outbox.py::test_outbox_worker_processes_event`) | Added the same backlog-drain pattern already used in `test_jobs.py` |
| C | `MarketplaceSearchService.search` never called `bind_public_context` before checking each candidate's eligibility; `evaluate_eligibility` reads `business_profiles`/`websites`, whose RLS policies only have a `business_id = current_business_id()` arm (no public arm) — every result was silently filtered out | 4 (`test_marketplace_indexing.py::test_indexing_is_business_isolated`, `test_marketplace_search.py` ×3) | Call `bind_public_context(session, business_id)` per-candidate before each `evaluate_eligibility` check, matching the pattern already used in `get_marketplace_profile`, `checkout.py`, `public_booking.py`, and the order-tracking resolver |
| D | Nonexistent-`business_id` switch now returns 403 (membership-checked-first) instead of a hardcoded 404 | 1 (`test_context_switching.py::test_switch_failures`) | **Not fixed** — Doc 12 §21.3 explicitly permits either code for this bucket; the assertion was left as-is per standing instruction not to weaken assertions to force green |
| E | Re-running suites against a non-fresh scratch database mid-session caused transient slug collisions | 5 (transient only, one intermediate run) | Not a defect — disappeared on a fresh database; noted for the record only |

No RLS policy was widened, no visibility default changed, no assertion altered to manufacture a pass.

## 3. Final test result (reproduced twice, independent fresh databases)

- **RLS-enforcing:** 1 failed / 302 passed / 0 skipped
- **Bypass:** 1 failed / 302 passed / 0 skipped

The one remaining failure in both modes is `test_switch_failures`, for the reason in row D — identical in both modes because it's a code-path-order effect, not an RLS-enforcement effect. This is the same discrepancy flagged and diagnosed as a spec-permitted ambiguity earlier in this engagement (Doc 12 §21.3: "Member with permission, wrong Business → 403 or 404").

### Regression groups, final clean run

| Group | Result |
|---|---|
| Category B (checkout/fulfilment/order-tracking/website-publish) | 12/12 |
| My Activity | 6/6 |
| Invitation engine | 10/10 |
| Employee assign/transfer/deactivate | pass |
| Order create/lifecycle/inventory | pass |
| Notification kernel | 9/9 |
| Worker jobs/outbox | 7/7 |
| Marketplace indexing/search | 9/9 |
| Context switching | 8/9 (row D) |

## 4. Build / type / lint

- `ruff check .` — all checks passed.
- `ruff format --check .` — clean on every file touched across this engagement; ~119 pre-existing files elsewhere in the repo are already drifted from current `ruff format` output, unrelated to this work, left untouched.
- `mypy --explicit-package-bases .` — 38 pre-existing errors in 19 files, none in any file touched this engagement. Not fixed (pre-existing, out of scope).
- `pnpm typecheck` — could not run: `node_modules` not installed in this checkout. No frontend/TypeScript file was touched. This is an environment gap, not a defect — needs to be run somewhere with dependencies installed before signing off the frontend.

## 5. Doc 11 First Launch readiness matrix

"VERIFIED" = a named test file exercises this area and passes in the 302-pass run, not merely "code exists."

| Area | Status | Evidence |
|---|---|---|
| Business onboarding | VERIFIED | `test_business_creation.py`, `test_gates.py` |
| AI generation + deterministic fallback | VERIFIED | `test_website_generation.py` |
| Website draft/edit/preview/publish | VERIFIED | `test_website_kernel.py`, `test_website_publish.py`, `test_website_draft_race.py`, `test_website_questionnaire.py` |
| Marketplace | VERIFIED | `test_marketplace_search.py`, `test_marketplace_indexing.py`, `test_marketplace_recovery.py` — fixed this pass |
| Offerings / Checkout / Orders | VERIFIED | `test_inventory_kernel.py`, `test_checkout_flow.py`, `test_orders_kernel.py` |
| Payments | VERIFIED | `test_payments_kernel.py`, `test_merchant_razorpay.py` |
| Inventory / Fulfilment | VERIFIED | `test_inventory_kernel.py`, `test_fulfilment_kernel.py` |
| Order tracking | VERIFIED | `test_order_tracking.py` |
| Bookings / Memberships / Workforce | VERIFIED | `test_bookings_kernel.py`, `test_booking_deposits.py`, `test_booking_migration.py`, `test_memberships_kernel.py`, `test_membership_engine.py`, `test_workforce_kernel.py` |
| Notifications | VERIFIED | `test_notifications_kernel.py`, incl. mute-suppression fix |
| My Activity | VERIFIED | `test_my_activity.py` |
| Entitlements / Permissions | VERIFIED | `test_business_entitlements.py`, `test_authorization_engine.py`, `test_actor_matrix.py` |
| Tenant isolation | VERIFIED, one caveat | `test_isolation.py` + cross-business assertions; caveat is the spec-permitted row-D ambiguity, not an isolation failure |
| Webhooks | VERIFIED | `test_payments_kernel.py` signature/idempotency tests |
| Outbox / jobs | VERIFIED | `test_jobs.py`, `test_outbox.py` — both fixed this pass |
| Admin/support | VERIFIED | `test_admin_support.py`, `test_isolation.py::test_super_admin_action_is_attributed` — fixed this pass (root cause A) |
| Observability | PARTIAL | `test_logging_redaction.py` passes; not reviewed in depth beyond that |
| Backup / recovery | **NO AUTOMATED EVIDENCE** | No test in `apps/api/tests` or `apps/worker/tests` exercises backup, point-in-time recovery, or restoration |
| Provider failure / degraded modes | PARTIAL | AI-generation fallback and `test_marketplace_recovery.py` cover two specific paths; broader provider-outage coverage not reviewed |

## 6. Final Go/No-Go

| Category | Item |
|---|---|
| **GO** | All First Launch functional areas in §5 marked VERIFIED — onboarding, website, marketplace, offerings/checkout/orders, payments, inventory/fulfilment, bookings/memberships/workforce, notifications, My Activity, entitlements/permissions, tenant isolation, webhooks, outbox/jobs, admin/support. Backend suite: 302/303 passing, reproducibly, in both RLS-enforcing and bypass modes, on a fresh database. Lint clean. |
| **CONDITIONAL** | (1) **Backup/recovery** — Doc 11 §21.1 requires this be available and tested; no automated coverage exists. Minimum action: a documented restore runbook plus one manual restoration drill against a disposable staging database. Operational verification, not an engineering change. (2) **`pnpm typecheck`/frontend build** — not run this pass (missing `node_modules` in this checkout); no frontend code changed, but needs to run green somewhere with dependencies installed before full sign-off. Manual verification. (3) Reproduce the same 302/303 result against the actual dev/staging Supabase project, not just a local scratch database, to rule out environment-specific divergence. Operational verification. |
| **NO-GO** | None identified. |

**Final recommendation: CONDITIONAL GO.** The engineering evidence is in — real root causes found and fixed (not guessed), reproduced twice on fresh databases, in both RLS-enforcing and bypass modes, with the one remaining failure being a documented spec-permitted ambiguity (Doc 12 §21.3), not a defect. What stands between this and an unqualified GO is operational, not engineering: run the backup/restore drill, run the frontend build where `node_modules` exists, and confirm the same numbers against the real Supabase project.
