# Claude — Phase B final integration handoff

Status: **IN PROGRESS** (interim; updated as each checkpoint lands).

| Field | Value |
| --- | --- |
| FINAL BRANCH | `claude/phase-b-final-integration` (pushed; never force-pushed) |
| WORKTREE | `C:/Users/KausikGH/Documents/locah-final-integration` |
| MAIN BASE | `1cb02e1449815ecf365a976d1694c9bd6681b2c2` (`origin/main`, not yet updated) |
| HEAD | see `git log -1` on the branch; checkpoints listed below |

## Source packets — all merged

| Packet | Branch | Head merged | Merge commit |
| --- | --- | --- | --- |
| A Memberships (P2-02) | `claude/p2-02-memberships-wip` | `88ca43c` | `7425356` |
| B Supply / B2B / recipes | `parallel/cursor-supply-b2b` | `0d3c80f` | `229a396` |
| C Inventory field | `parallel/cursor-inventory-field` | `7245f54` | `2c4bfc9` (+ `679dba3` import fix) |
| D Projects / Jobs / Academics | `parallel/codex-projects-jobs-academics` | `e821a63` | `c40f853` |
| E Quotes | `parallel/cursor-quotes` | `b52002c` | `d7ed1a2` |
| F Queue + Tasks | `parallel/cursor-queue-tasks` | `25a0d69` | `472a0ea` |
| G Kitchen / KDS | `parallel/cursor-kitchen` | `ccf09ff` | `839b465` |
| H Dispatch / Crew | `parallel/cursor-dispatch` | `2b115c6` | `c111ce6` |
| I Growth (hardened) | `parallel/cursor-growth-hardening` | `8921222` | `7550111` |
| J Attendance | `parallel/codex-attendance` | `f8a1348` | `8ff25d7` |
| K Documents / Forms | `parallel/codex-documents-forms` | `d070a7e` | `74d7b26` |

`parallel/antigravity-growth` is an ancestor of the hardened Growth head and was
**not** merged separately. `parallel/kimi-loyalty` (`84eead2`) is an old local
branch behind main; not a packet, not merged.

## Shared-registry reconciliation (done, verified)

- Python `ALL_PERMISSIONS` and `packages/permissions/src/identifiers.ts` match
  exactly: 158 identifiers, no duplicate keys or values. `documents.read` came
  from both Supply and Documents; defined once.
- Assignment allowlist: bookings, leads, quotes (+issue), customers, jobs
  (read/complete/use_parts), academics (read/teach), queue (read/operate),
  tasks (read/complete), dispatch (read/update_status), attendance
  (read/record). Never `inventory.read`, `*.manage`, `quotes.approve`.
- Assignment ORM read filters + write guard cover Booking, Lead, ProjectTask,
  Quote, WorkTask, QueueLane, QueueEntry, DispatchJob, DispatchEvent. Location
  scope covers the queue, tasks and dispatch models too.
- Surfaces built: workspace, pos, kitchen, crew. READY_AHEAD: provider,
  sales executive, technician, teacher, kitchen, dispatcher, delivery partner,
  marketer.
- Event catalogue: one owner per family; the supply `documents` register and
  the Documents workflow share the single `documents` owner.
- Every nav label and Home label has Tamil/Hindi first-draft wording
  (pending native review, VB-22).

## Cross-module wiring

| Contract | Status | Proof |
| --- | --- | --- |
| Order → Kitchen (one KOT) | DONE (packet G) | test_kitchen 6/6; test_integration_restaurant |
| Kitchen → Recipe/BOM → Inventory | DONE (this integration) | test_integration_restaurant: 1000 g → 700 g once; replay + re-accept unchanged |
| Membership → Attendance eligibility | DONE (this integration) | test_integration_membership_attendance 2/2 |
| Attendance check-in → session-pack use | DONE (this integration) | same file: one session per visit, replay-safe |
| Academics → Attendance roster | DONE, verified on real P5 schema | test_attendance_postgres 5/5 |
| Jobs → Inventory part use | PARTIAL — P5 `StockService.consume_for_job` works (20→17→17→15); Inventory Field's `InventoryFieldService.consume_for_job` (van + unused return) is a second entry point on the same ledger; Jobs should route through it | test_p5_operations, test_inventory_field |
| Queue → Messaging | DONE (packet F subscriber) | test_queue |
| Compliance → Tasks | to verify | — |
| Quote → Payments / conversion | NOT STARTED (published, no consumer) | — |
| Dispatch → Messaging | NOT STARTED | — |
| Growth hooks (loyalty/referral/voucher) | NOT STARTED as subscribers | — |
| Membership AMC → Jobs, recurring delivery → Orders | to verify | — |
| Documents domain contracts | related_type/related_id hooks only | — |

## Tests

- Fresh replay, all migrations through `20260930240000_documents_forms.sql`:
  **clean** (`tools/acceptance/stack/db.sh`, local Postgres 18, port 54329).
- Full API + worker suite at `74d7b26` (frozen worktree, `-n 6`):
  **1256 passed, 2 failed, 1 skipped**. The 2 failures were a Documents test
  isolation bug (RLS flag read at import), fixed in `9ea0d73`; the skip needs
  `TEST_API_DATABASE_URL`.
- Ruff: clean. Workspace tsc: clean after building `packages/contracts`
  (`apps/workspace/node_modules/.bin/tsc -p packages/contracts`). Web tsc:
  clean. Workspace lint: clean.
- Browser (Playwright): not yet run on the integrated stack.

## Hosted Supabase — DO NOT TOUCH

`20260930130000_procurement_supply_lane.sql` was applied to hosted Supabase
without a migration-history row. Do not rerun, drop, or hand-insert history.
Later: live schema dump → compare to clean local replay → reviewed mapping →
official `supabase migration repair`. No hosted writes were made here.

## Known risks

- Two job-part consumption entry points (see table).
- Technician template holds `inventory.read` (whole stock book) by the P5
  packet's explicit choice; van-only stock view is the better fit now that
  vans exist.
- Supply `documents_records` (business documents register) and the Documents
  workflow `document_files` are separate stores of file truth.
- Workspace tsc needs `packages/contracts` built first (dist is not committed).
