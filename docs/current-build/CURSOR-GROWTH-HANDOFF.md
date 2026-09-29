# Cursor growth handoff

Loyalty and marketing were hardened on top of Antigravity's implementation. The services were not rewritten. No further loyalty or marketing features belong on this branch.

READY_TO_INTEGRATE = YES

## Freeze

| | |
| --- | --- |
| BRANCH | `parallel/cursor-growth-hardening` |
| BASE SHA | `e48fd6001820ac716bff4ffbd0fda61edf9b178e` |
| HEAD SHA | `cebf928262de8976d8aaf49fda89afe4212ff3ff` is the freeze commit. The branch tip is the commit that writes this hash into the handoff. It changes no product code. |
| pushed checkpoint | `fcf7d14a534b344a34b46b59b3bc0e97c2d61a8b` (pushed, not force-pushed) |
| MIGRATION REPLAY RESULT | exit 0. 74 of 74 files in `infra/supabase/migrations` applied on a new local database `locah_growth_replay` at `localhost:54329`. `20260930160000_p3_growth_loyalty_marketing.sql` and `20260930161000_p3_growth_stamp_award_idempotency.sql` both applied. `loyalty_programs` and `stamp_awards` exist, `referral_codes_unique_code` exists, and `stamp_awards` has row security forced. Notices on older migrations are pre-existing `IF EXISTS` skips, not growth failures. Zero hosted Supabase writes. |
| DATABASE TEST RESULT | 34 passed, 0 skipped, on local `locah_growth_scratch` (`localhost:54329`). `test_growth_db.py`, `test_growth_rls.py`, `test_loyalty_lane.py`, `test_marketing_lane.py`, `test_permissions.py`. |
| PLAYWRIGHT RESULT | 14/14 passed. Desktop Chrome, `tools/acceptance/phase_b/p3_growth_workspace_ui.mjs`. Loyalty: programme, earn 200, redeem to 190, stamp card, voucher. Marketing: offer `DIWALI10`, campaign, audience, `1 with marketing consent`, Approve, fixture `Sent 1`, `Approximate · last touch`. No external calls. |
| RUFF | exit 0. All checks passed on the Python files changed since `e48fd60`. |
| TSC | exit 0. `tsc --noEmit -p apps/workspace`. No errors. |
| LINT | exit 0. `next lint` in `apps/workspace`. No ESLint warnings or errors. No unrelated failures to separate. |
| RLS | Forced on every loyalty and marketing table, including `stamp_awards`. `platform_api` policies. Proven in `test_growth_rls.py`, not skipped. |
| PERMISSIONS | `loyalty.read`, `loyalty.manage`, `marketing.read`, `marketing.create`, `marketing.approve`, `marketing.send`. Marketer may read and draft. Approve and send stay with the owner. |
| CLAUDE HOOKS | `python/core/platform_core/growth/contracts.py`. Orders, Payments, and Messaging were not modified. |
| PARTIAL | Public website loyalty card is not built. Checkout does not call `evaluate_offer`. Orders does not call earn or referral qualify. Payments does not fund a voucher. Messaging does not deliver the broadcast. |
| ACTIVATION_REQUIRED | Meta ads, Conversions API, Google Business Profile, and live WhatsApp delivery. Spend cap and broadcast dispatch stay local. |
| KNOWN MERGE RISKS | `20260930160000_p3_growth_loyalty_marketing.sql` was edited in place so the unique codes are indexes. A branch that still has the original `UNIQUE (lower(code))` table constraints will conflict. Shared files other lanes may also touch: `role_templates.py`, `permissions.py`, `packages/permissions/src/identifiers.ts`, `catalog/modules.py`, `plan_registry.py`, `workspace-nav.ts`, `ws-words.json`. Loyalty was added to the growth plan only. |

## Branch

| | |
| --- | --- |
| branch | `parallel/cursor-growth-hardening` |
| base | `e48fd6001820ac716bff4ffbd0fda61edf9b178e` (`origin/parallel/antigravity-growth`) |
| hardening | `c098deb6906b99d8bb423053080050fde75d4b6c` |
| pushed checkpoint | `fcf7d14a534b344a34b46b59b3bc0e97c2d61a8b` |
| head | `cebf928262de8976d8aaf49fda89afe4212ff3ff`, then the commit that records that hash |

Worktree used for the edit: `C:\Users\KausikGH\Documents\locah-cursor-growth`. The shared checkout was left alone.

## What changed, against the source

Canonical rules kept. Invented legal gates removed from `regulated.py`:

- subcategory `lawyer`: marketing is off. No owner bypass. Legal advertising stays a verify-at-build item.
- category `finance_insurance` or trait `finance_regulated`: restricted, still allowed. Reason is "No product selling or advice through LOCAH." No statutory disclosure checkbox.
- trait `minors_involved`: prohibited. "No marketing templates to minors."
- Meta targeting is a check, not a WhatsApp block, for `real_estate`, `finance_insurance`, subcategory `recruitment`, and trait `health_regulated`.
- Only those taxonomy keys and traits trigger a rule. Synonyms do not.

Frequency defaults (48 hours, 2 sends in 7 days) stay. The source requires frequency controls and does not set the numbers.

`20260930160000` was edited in place. Postgres rejects `UNIQUE (business_id, lower(code))` inside a table constraint, so the migration could not be applied. Referral codes, gift vouchers, and offer codes now use unique indexes on `lower(code)` / `upper(code)`. That was the one edit to another agent's migration.

Follow-up migration `20260930161000` adds `stamp_awards` so a stamp visit is recorded once. The old check looked up a reward code that is never stored that way, so a replay could stamp again.

Loyalty and marketing handlers now `commit()`. With `API_DATABASE_URL` set, the request session rolls back on the way out, so a flush-only write never reached the database.

## RLS

Every tenant-owned loyalty and marketing table, including `stamp_awards`, has `business_id`, `ENABLE ROW LEVEL SECURITY`, `FORCE ROW LEVEL SECURITY`, a `public` select policy on `current_business_id()`, and a `platform_api` write policy with the same check. `platform_api` is granted select/insert/update/delete. `anon` is revoked.

`apps/api/tests/test_growth_rls.py` connects as the owner, `SET ROLE platform_api`, and checks cross-business isolation plus an empty result with no business GUC. Not skipped.

## Permissions

| permission | who |
| --- | --- |
| `loyalty.read` | owner (all permissions); marketer template |
| `loyalty.manage` | owner |
| `marketing.read` | owner; marketer |
| `marketing.create` | owner; marketer (draft campaigns and offers) |
| `marketing.approve` | owner only |
| `marketing.send` | owner only |

Identifiers are in `python/core/platform_core/permissions.py` and `packages/permissions/src/identifiers.ts`. The marketer template lives in `role_templates.py` (`READY_AHEAD`, phase P3, offered when marketing or loyalty is operational). It does not get approve, send, or customer export. The older Doc 12 template lists were not extended.

## Module registry

`loyalty` and `marketing` were already in the module catalogue, the entitlement registry, and the SQL seed. They were not duplicated. Both are `built=True`. `loyalty` is on the growth plan next to marketing (`loyalty.core`). Foundation does not include either. Workspace nav shows Loyalty, Campaigns, and Offers when the module is operational and the actor has `loyalty.read` or `marketing.read`.

## Tests

Local disposable Postgres only: `localhost:54329` / database `locah_growth_scratch`. Bootstrap, every migration, and `seed/00_platform.sql`. No hosted Supabase.

From `apps/api`, with `TEST_DATABASE_URL=postgresql+asyncpg://postgres@localhost:54329/locah_growth_scratch`:

`tests/test_growth_db.py` `tests/test_growth_rls.py` `tests/test_loyalty_lane.py` `tests/test_marketing_lane.py` `tests/test_permissions.py`

**34 passed, 0 skipped.** Proved on the real database: earn once, redeem, expiry, stamp reward once, referral once, voucher isolation, campaign isolation, consent exclusion, frequency guard, dispatch refused before owner approval, attribution label `Approximate · last touch`, spend cap, RLS.

## Playwright

`tools/acceptance/phase_b/p3_growth_workspace_ui.mjs` on desktop Chrome (`channel: 'chrome'`, headless). Local API, local mock auth, no external calls.

14/14 passed on business `3f1a3237-082c-4575-a3f3-06447573a975`:

- Loyalty: save programme "Desk points", earn ₹200 → 200 points, redeem 10 → 190, stamp card, voucher form.
- Marketing: offer `DIWALI10`, create campaign, save audience and offer, consent count `1 in the audience, 1 with marketing consent`, owner Approve, fixture send `Sent 1`, attribution `Approximate · last touch`.

Screenshots: `acceptance-out/phase_b/growth-ui/` (gitignored).

## Claude integration hooks

`python/core/platform_core/growth/contracts.py`. Orders, Payments, and Messaging were not modified. The owning lane calls the function when its own event is final.

| event | hook |
| --- | --- |
| Eligible completed transaction | `LoyaltyPointsService.earn_points` — idempotency key stable per sale, `source_type` `order` or `pos` |
| Friend's first eligible purchase | `ReferralService.qualify_first_purchase` — a second call returns `qualified=False` |
| Coupon check at checkout | `OfferService.evaluate_offer` — does not take payment |
| Approved broadcast | `WhatsAppBroadcastOrchestrator.dispatch_campaign` — fixture record only; status must already be `APPROVED` by `marketing.approve` |
| Gift voucher after payment | `GiftVoucherService.issue_voucher` — records the balance; Payments captures the money |

## Still partial

- Public website loyalty card is not built. `site=("loyalty",)` does not render a card.
- Checkout does not call `evaluate_offer` yet. Orders does not call earn or referral qualify. Payments does not fund a voucher. Messaging does not deliver the broadcast.
- Frequency numbers are product defaults, not a statutory rule.

## ACTIVATION_REQUIRED

- Meta ads and the Conversions API. Spend is capped locally. `provider_status` stays `ACTIVATION_REQUIRED`. No live Meta call.
- Google Business Profile. The adapter is a stub.
- WhatsApp delivery of an approved broadcast. Dispatch records recipients in the fixture transport (`MESSAGING_SANDBOX`).
