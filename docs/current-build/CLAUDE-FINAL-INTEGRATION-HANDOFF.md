# Claude — Phase B final integration handoff

Status: **IN PROGRESS** — core gate green; continuing P1–P5 depth.
Git history on the branch is authoritative; this file is the summary.

| Field | Value |
| --- | --- |
| FINAL BRANCH | `claude/phase-b-final-integration` (pushed; never force-pushed) |
| HEAD at this update | `4eec9d3` + this doc commit (see `git log -1`) |
| MAIN | `origin/main` = `9c21d46` ("save"), diverged from the merge base `1cb02e1`. **Not merged either way.** Inspect `git show --stat 9c21d46` deliberately before any main merge. |
| Machines | Integration began on Windows (`C:/Users/KausikGH/...`); continued on macOS from `4040e5a` (2026-09-29/30). |

## Source packets — all merged (do not re-merge)

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

`parallel/antigravity-growth` is an ancestor of the hardened Growth head — not
merged separately. `cashfree-sandbox` (`8b495b8`, self-described UNREVIEWED /
UNTESTED WIP touching the payment kernel) is **not merged**; it needs a
dedicated review and deliberate port, never a wholesale merge.

## Cross-module wiring

| Contract | Status | Commit / proof |
| --- | --- | --- |
| Order → Kitchen (one KOT) | DONE | packet G; test_kitchen, test_integration_restaurant |
| Kitchen → Recipe/BOM → Inventory | DONE | `9ea0d73`; 1000 g → 700 g once; replay/re-accept unchanged; demo gate |
| Membership → Attendance eligibility; check-in → session-pack use | DONE | `1fc8684`, `145c75f`; demo gate (card code, paid/unpaid) |
| Academics → Attendance roster | DONE | test_attendance_postgres |
| Dispatch → Messaging / fulfilment | DONE | `952f9c2`; test_integration_dispatch_messaging |
| Sale → Loyalty earn / referral qualification | DONE | `06ef456` |
| Quote → Project / Order conversion | DONE | `6bd9441`; demo gate (quote → project) |
| Compliance due → shared Task | DONE | `b49a675` |
| Membership AMC visit → Jobs job card | DONE | `b49a675` |
| Queue → Messaging | DONE | packet F |
| Quote → Payments (`quote.payment_handoff`) | **PARTIAL** — published; converted orders use the existing deposit/advance flow; no dedicated Payments consumer yet | — |
| Jobs → Inventory part use | **PARTIAL (in progress)** — two entry points on one ledger (P5 `StockService.consume_for_job`, Inventory Field `consume_for_job`); technician holds `inventory.read` to pick parts | see "Next" |
| Membership recurring delivery → Orders/Kitchen/Dispatch; session pack ↔ Bookings; fee plan ↔ Academics; payment → renewal-ladder suppression | to audit (unit tests exist in test_p2_memberships; cross-module audit not done) | — |
| Documents domain contracts | related_type/related_id hooks only | — |

## Verification (macOS, fresh local stack, 2026-09-30)

Local stack: PostgreSQL 18.4 built from source into `~/.local/locah-pg`
(port 54329, trust auth, localhost only); `pnpm` via corepack; `uv sync
--all-packages`; packages built; API/Workspace/Web via `.claude/launch.json`
`accept-*-posix` entries; worker via `tools/acceptance/stack/worker.sh`.
Chromium: Playwright's cached build (`CHROME_PATH` for cdp-based scripts).

- **Migration replay**: 87 migrations + seed onto a brand-new DB, `ON_ERROR_STOP=1`:
  clean. Newest `20260930240000_documents_forms.sql`. No duplicate versions.
- **Full API + worker suite** (as CI: `DATABASE_URL` + `API_DATABASE_URL` on the
  RLS role `platform_api`, `TEST_API_DATABASE_URL` set, fresh DB, `-n 8`):
  **1270 passed, 0 failed, 0 skipped** (`4eec9d3`). The earlier "1256/2/1"
  run did not use the RLS role; on it 4 tests failed (fixed in `d851b32`).
- **Ruff** clean. **Mypy** (CI invocation `mypy --explicit-package-bases .`):
  **0 errors in 569 files** (was 68, fixed in `4eec9d3`).
- **Workspace** tsc + lint clean (after `pnpm --filter "./packages/*" build`).
  **Web** tsc + lint clean.
- **Registries**: Python `ALL_PERMISSIONS` = TS `identifiers.ts` = 158, no
  duplicates, grammar ok. 14 role templates (business 2, location 6,
  assignment 6); every template permission known; modules' dependencies and
  surfaces known; 264 event types in 37 owner groups, one owner each; every
  router module mounted. **Open conflict**: the assignment-scoped technician
  template holds `inventory.read` (outside `ASSIGNMENT_PERMISSIONS`); being
  resolved with the Jobs → Inventory work. `customers.erase` has no owner words.

### Browser (Playwright/CDP, one integrated local stack, live worker)

| Suite | Result | When |
| --- | --- | --- |
| P1-10D1 Payments | **84/84** (×3) | `5a7ecf6`, `280a487` |
| P1-10B Identity / My Activity | **14/14** | this session |
| P1-08 WhatsApp journeys | **30/30** | this session |
| P2-02 Memberships | **24/24** (run at 00:05 IST) | `280a487` |
| Demo gate (gym, restaurant, field service) | **17/17** (×3, last on `4eec9d3` code) | this session |
| P5 Projects / Jobs / Academics | **12/12** | `d851b32` |
| Earlier on Windows (`7cde444`) | kitchen 10/10, dispatch 9/9, quotes 14/14, queue 5/5, tasks 4/4, supply 6/6, documents 6/6, growth 14/14, documents DB 3/3 | not re-run on macOS |

**Hydration warning** (reported on the Windows stack for customer/pay pages):
did **not** reproduce on the clean macOS stack — every console-error check
passed in 3 payments runs, and a probe of 9 owner/customer/pay pages with the
browser in Asia/Kolkata, UTC and America/Los_Angeles (servers in IST) logged
nothing. Nothing was suppressed. A genuine clock-in-render bug of the same
family was found and fixed in Memberships (`280a487`).

## Fixed this session (macOS)

- `5a7ecf6` Payments script reads the P2-02 members board (Needs you · plan ·
  ₹1,000 due · Payment pending; count 1) instead of a removed plan table; the
  board no longer prints an empty "·" for a member with no paid period.
- `280a487` Member page today/tomorrow come from the business's timezone
  (API `detail.today`), not the browser's UTC date — the skip-a-day form was
  defaulting to a day past cutoff between 00:00 and 05:30 IST.
- `d851b32` Job cards and academic batches: reads of someone else's record are
  404 on every DB path (as Tasks and RLS), writes 403. Three tests now make
  the business unlisted before calling public endpoints.
- `4eec9d3` Mypy 68 → 0.
- Harness portability: `cdp.mjs` per-platform Chrome + OS temp dir;
  `demo_gate.mjs` / `p5_projects_jobs_academics.mjs` use `psql` from PATH and
  Playwright from `tools/acceptance`; launch.json POSIX entries.

## Known risks / open items

- Jobs → Inventory: see table; technician `inventory.read`.
- `quote.payment_handoff` PARTIAL.
- Other screens compute "today" in UTC (khata entry date, bill payment date,
  invoice reports, production day, website enquiry form) — flagged as a
  separate task, not changed.
- Supply `documents_records` and Documents `document_files` are two stores of
  file truth.
- The acceptance API connects as `postgres` (RLS bypassed): browser suites do
  not exercise RLS; the pytest suite on the `platform_api` role does.
- Local-only branches on the Mac (`backup-before-reset` 22333ee,
  `web-builder-lovable` d8c143c) are not on GitHub; untouched.

## Hosted Supabase — DO NOT TOUCH

`20260930130000_procurement_supply_lane.sql` was applied to hosted Supabase
without a migration-history row. Do not rerun, drop, or hand-insert history.
Later: live schema dump → compare to clean local replay → reviewed mapping →
official `supabase migration repair`. No hosted writes were made.

## Next

1. Jobs → Inventory single path (Inventory Field job contract; returns via
   Jobs; technician picker = job location + own vans; drop technician
   `inventory.read`).
2. `quote.payment_handoff` through Payment Collect (no second payment system).
3. Membership cross-module contract audit; automation/WhatsApp end-to-end audit.
4. P1–P5 ledger regeneration, then Bookings depth, Workforce, Dispatch depth,
   Connector hub/Tally, Donations, Insights, My Activity composition, AI runtime.
5. Before any main merge: reconcile `9c21d46`; review `cashfree-sandbox`.
