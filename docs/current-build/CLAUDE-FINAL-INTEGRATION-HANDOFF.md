# Claude — Phase B final integration handoff

Status: **WRAP CHECKPOINT** — core P1–P5 product coherent and green on the
integration branch; remaining depth is listed as PARTIAL / ACTIVATION_REQUIRED.
Git history on the branch is authoritative; this file is the summary.

| Field | Value |
| --- | --- |
| FINAL BRANCH | `claude/phase-b-final-integration` (pushed; never force-pushed) |
| HEAD at this update | see `git log -1` (this doc commit follows `e9628a9`) |
| MAIN | `origin/main` = `9c21d46` ("save"); integration is 86 ahead / 1 behind. **Not merged either way.** See §Main below. |
| Machines | Began on Windows; continued on macOS (`/Users/user25/gowtham/Personal_Projects/locah`) from `4040e5a`. |

## Source packets — all merged (do not re-merge)

| Packet | Branch | Head merged | Merge commit |
| --- | --- | --- | --- |
| A Memberships (P2-02) | `claude/p2-02-memberships-wip` | `88ca43c` | `7425356` |
| B Supply / B2B / recipes | `parallel/cursor-supply-b2b` | `0d3c80f` | `229a396` |
| C Inventory field | `parallel/cursor-inventory-field` | `7245f54` | `2c4bfc9` (+ `679dba3`) |
| D Projects / Jobs / Academics | `parallel/codex-projects-jobs-academics` | `e821a63` | `c40f853` |
| E Quotes | `parallel/cursor-quotes` | `b52002c` | `d7ed1a2` |
| F Queue + Tasks | `parallel/cursor-queue-tasks` | `25a0d69` | `472a0ea` |
| G Kitchen / KDS | `parallel/cursor-kitchen` | `ccf09ff` | `839b465` |
| H Dispatch / Crew | `parallel/cursor-dispatch` | `2b115c6` | `c111ce6` |
| I Growth (hardened) | `parallel/cursor-growth-hardening` | `8921222` | `7550111` |
| J Attendance | `parallel/codex-attendance` | `f8a1348` | `8ff25d7` |
| K Documents / Forms | `parallel/codex-documents-forms` | `d070a7e` | `74d7b26` |

Not merged, on purpose: `cashfree-sandbox` (`8b495b8`, self-described
UNREVIEWED/UNTESTED WIP in the payment kernel — port deliberately, never
wholesale) and `claude/compassionate-allen-hlpq6p` (a separate docs-only
Website creative audit lane).

## This session (2026-09-30, from `d531356`)

| Commit | What |
| --- | --- |
| `6258c1c` | **Final-slot race closed.** Website/WhatsApp guests who name no table/chair now hold a free one under lock (four guests used to "win" the only table); a class's own "places per session" binds (was ignored → unlimited public class bookings); one capacity lock per location+mode (a request naming the instructor used a different lock). Real concurrent tests, mutation-checked. |
| `3da68b9` | **Workforce schedules enforced.** Weekly hours, dated leave/one-off hours, breaks — stored before but never read — now bind every booking path (incl. resource+provider, which skipped the provider entirely) and the public availability answer; guests held to opening hours; member page rebuilt (day names, leave, remove). |
| `e11c175` | **Bookings depth**: unpaid online-deposit holds released; waitlist (join only when full, one offer at a time on WhatsApp, customer takes it through the booking path, expiry passes on); weekly series (edit one / change later all-or-nothing / end); no-show follow-up; Workspace booking page shows only legal moves (Arrived / No-show were missing). |
| `7e7c890` | **WhatsApp honest states + registration + calls.** Meta requires number registration (PIN) after Embedded Signup — LOCAH skipped it and called the number connected. Now: derived states with checklist, PIN registration, WABA template/quality webhooks (the policy existed; nothing used it), test message; calls recorded (no SDP/media/tokens), permission gate, calling state never inferred from messaging; PSTN provider-neutral boundary. |
| `7226f09` | One-time codes in Meta's **authentication preset** (copy-code button) — the custom-text OTP template would have been rejected by Meta. |
| `443d967` | `docs/current-build/WHATSAPP-CALLING-SETUP.md` (developer/demo + production merchant paths, activation checklist, sources checked 2026-09-30). |
| `c2d98c6` | Low stock → optional **draft** requisition (owner switch; never a PO). Fixed: saving one automation option wiped the others. |
| `e9628a9` (+1) | Academics enrol form no longer carries a guardian over to the next student (browser suite caught it); series "move this and later"; ledger regenerated. |

## Cross-module wiring (cumulative)

| Contract | Status | Proof |
| --- | --- | --- |
| Order → Kitchen (one KOT); Kitchen → Recipe/BOM → Inventory | DONE | `9ea0d73`; demo gate |
| Membership → Attendance; session pack ↔ Bookings | DONE | `1fc8684`, `145c75f`; test_p2_memberships |
| Academics → Attendance roster | DONE | test_attendance_postgres |
| Dispatch → Messaging / fulfilment | DONE | `952f9c2` |
| Sale → Loyalty / referral | DONE | `06ef456` |
| Quote → Project / Order; token → order advance; acceptance code → WhatsApp (preset) | DONE (invoice target PARTIAL) | `6bd9441`, `187fd8c`, `1f6beba`, `7226f09` |
| Compliance → Task; AMC → Jobs; Jobs → Inventory (one contract) | DONE | `b49a675`, `8fc4e76` |
| Queue turn soon → WhatsApp | DONE | `4e1dd6d` |
| **Workforce schedule → Bookings** | DONE | `3da68b9` |
| **Bookings → Waitlist → Messaging (offer) → Bookings (claim)** | DONE | `e11c175` |
| **Bookings → Automation (hold release, no-show)** | DONE | `e11c175` |
| **Inventory low stock → Procurement draft (opt-in)** | DONE | `c2d98c6` |
| Documents secure request → customer | Share-link only (honest; not sent automatically) | UI says "Share this private link once" |

## Verification (macOS, local stack, 2026-09-30, final code)

- **Migration replay**: brand-new DB via `tools/acceptance/stack/db.sh`
  (CI shim + **89 migrations** + seed, `ON_ERROR_STOP`): clean. Newest
  `20261001110000_whatsapp_connection_calling.sql`. No duplicate versions.
- **Full API + worker suite** on that fresh DB as CI runs it (RLS role
  `platform_api`, `TEST_API_DATABASE_URL` set, `-n 8`):
  **1296 passed, 0 failed, 0 skipped** (was 1276; +20 new).
- **Ruff** clean. **Mypy** (`mypy --explicit-package-bases .`): **0 errors in 581 files**.
- **Workspace** tsc + lint clean; **Web** tsc + lint clean.
- **Permissions**: Python `ALL_PERMISSIONS` = TS `identifiers.ts` = **158** (none added).

### Browser (Playwright Chromium, one integrated local stack, live worker, final code)

| Suite | Result |
| --- | --- |
| P1-10D1 Payments | **84/84** |
| P1-10B Identity / My Activity (incl. 390 px) | **14/14** |
| P1-08 WhatsApp journeys | **30/30** |
| P2-02 Memberships | **24/24** |
| P2 Quotes | **15/15** |
| P2 Queue board | **5/5** |
| P5 Projects / Jobs / Academics (guardian at 390 px) | **13/13** (12/13 first run → academics form bug fixed) |
| **Demo gate** (gym, restaurant, field service; 390 px) | **17/17** |
| Manual browser checks this session | Workforce member page (desktop + 390 px); waitlist offer → customer takes it on the site → Workspace series (Repeat → 4, Move +60 min) + Arrived/No-show; WhatsApp Connection panel (TEST / SANDBOX, checklist, simulated call recorded) |

Not re-run on macOS this session: kitchen, dispatch, tasks, supply,
documents, growth browser suites (green on Windows at `7cde444`; their
code was not changed here).

## Status by area (for the final report)

- **Bookings**: one engine; final-slot race proven for class seat, pooled seat,
  unnamed exclusive table, provider, instructor-vs-none; hours, provider
  schedules, buffers, capacity, holds, waitlist, reschedule, cancel,
  recurrence (edit one / later / end), arrival, no-show — built and tested.
  Remaining PARTIAL: mode-specific website flows (FR-BK-03: the site's booking
  page is still one appointment form), booking horizon/min-notice, owner
  override for expired members, staff create form in Workspace.
- **Workforce**: one truth (`workforce_members`) used by Bookings, Jobs,
  Academics, Dispatch, Tasks, Queue, Attendance; schedules enforced for
  Bookings. Not built: shift rota planning, assignment rules. **No payroll**
  (FUTURE).
- **WhatsApp internal automation**: COMPLETE (sandbox-proven).
- **Cloud API adapter**: built to current Meta docs, mock-tested;
  **never exercised against Meta** → ACTIVATION_REQUIRED.
- **Embedded Signup**: built (browser flow + server steps incl. registration);
  ACTIVATION_REQUIRED (LOCAH Meta app).
- **Meta App Review / Tech Provider**: ACTIVATION_REQUIRED (business action).
- **Templates**: library en/ta/hi (Tamil/Hindi need native review, VB-22);
  OTP in authentication preset; Meta's decisions ingested by webhook.
- **Webhooks**: signed, verify-token, idempotent, tenant-routed (number/WABA);
  messages, statuses, echoes, calls, call permissions, template status, quality.
- **Calling API**: signalling/settings/permissions/records built;
  **CALLING_ACTIVATION_REQUIRED** — no WebRTC call runtime to answer.
- **PSTN telephony**: provider-neutral boundary; ACTIVATION_REQUIRED (no vendor chosen).
- **AI receptionist / AI employee runtime**: NOT_STARTED, deliberately (no call
  transport; brief puts AI runtime last).
- **Connector hub / Tally**: foundation exists (connections with direction,
  authority, secret reference, health; idempotent sync runs; external-ID
  mappings); Tally runtime ACTIVATION_REQUIRED.

## Ledger

`docs/current-build/business-os-implementation-ledger.md` regenerated from
`tools/ledger/` (WRAP block in `progress.py`). Gate counts:
P1 143 complete / 96 partial / 0 not started / 22 activation;
P2 35 / 108 / 55 / 9; P3 6 / 9 / 44 / 15; P4 7 / 22 / 47 / 8; P5 7 / 60 / 29 / 1.

## Main

`origin/main` has one commit the integration branch lacks, `9c21d46`
("save"): an **older copy of the Kitchen packet** (migration identical;
router, models, snapshot, tests, KDS script and handoff older than packet G
as merged) plus `TECHNOVA2026/` presentation files (PDF, PPTX) and an
`.agents/skills/apple-design` link. A dry run (`git merge-tree`) shows six
add/add conflicts, all Kitchen files. Reconciliation when merging to main:
keep the **integration** versions of the six Kitchen files; take the
TECHNOVA2026 files (and decide on the `.agents` link). Not done here —
merging to main is the owner's call.

## Hosted Supabase — DO NOT TOUCH

`20260930130000_procurement_supply_lane.sql` was applied to hosted Supabase
without a migration-history row. Do not rerun, drop, or hand-insert history.
Later: live schema dump → compare to a clean local replay → reviewed mapping →
official `supabase migration repair`. Two new migrations this session
(`20261001090000_bookings_depth.sql`, `20261001110000_whatsapp_connection_calling.sql`)
are **local only** — nothing was applied to any hosted database.

## Known risks / open items

- Quote → invoice target has no consumer; WhatsApp RFQ intake not wired.
- Offers not applied at website checkout; vouchers not funded; broadcasts use
  the fixture transport.
- Other screens compute "today" in UTC (khata entry date, bill payment date,
  invoice reports, production day, website enquiry form) — flagged earlier.
- Supply `documents_records` and Documents `document_files`: two stores.
- Acceptance API connects as `postgres` (RLS bypassed in browser suites); the
  pytest suite runs on the RLS role.
- The website booking page offers only pay-at-business, so unpaid-hold
  release applies to online-deposit bookings made elsewhere (staff, future
  Cashfree link).
- Local-only branches `backup-before-reset` (22333ee) and
  `web-builder-lovable` (d8c143c) are on this Mac only; untouched.

## Next (exact)

1. Mode-specific booking flows on the website (FR-BK-03: table → party size,
   stay → date range, class → sessions with places left) on the one engine.
2. Owner decisions: Meta Tech Provider enrolment + App Review; call runtime;
   PSTN vendor; Cashfree review/port (`cashfree-sandbox`).
3. Main reconciliation per §Main, then merge (owner's call).
