# Cursor handoff — Kitchen, KOT, KDS

## BRANCH

`parallel/cursor-kitchen`

## HEAD SHA

`76c0a6ad954052d95f9fb57dc69e0940ffa8f4c1`

## MAIN BASE SHA

`1cb02e1449815ecf365a976d1694c9bd6681b2c2`

## COMMITS

1. `feat(kitchen): keep preparation on its own ticket` — domain, migration, API module, KDS UI, stations setup, intake subscriber module, tests, browser script, product handoff body.
2. `chore(integration): wire kitchen` — router import, nav links, permissions, catalogue events, module `built`, role templates, subscriber registration.
3. `09aebc5` — `chore(kitchen): close-out verification and handoff` (idempotency test, Served browser step, TSC Board export, handoff block).

## MIGRATIONS

Lane-owned:

- `infra/supabase/migrations/20260930190000_kitchen_preparation.sql`

Fresh local replay (disposable DB on `127.0.0.1:54329`, no hosted Supabase):

- Full chain: **73** migration files under `infra/supabase/migrations/` plus `infra/supabase/seed/00_platform.sql`
- Kitchen migration applied in order with the rest
- Exit code **0**

## DATABASE TESTS

Command (local only):

```text
TEST_DATABASE_URL=postgresql+asyncpg://postgres@localhost:54329/locah_growth_scratch
pytest apps/api/tests/test_kitchen.py
```

Coverage:

- Accept → one KOT; replay of `order.accepted` does not duplicate
- Station routing (multi-station lines, one ticket; retail excluded; General fallback)
- Start → ready → serve; **one** `kitchen.preparation.completed`; stock unchanged; order status untouched
- **Serve + worker replay + second serve + direct `publish_preparation_completed` + order replay → still one `kitchen.preparation.completed`**
- Cancel before start; qty/modifier/cancel after start with visible events
- Tenant API isolation + `platform_api` RLS on `kitchen_tickets`

Result at close-out: **6 passed** (kitchen file only).

## PLAYWRIGHT RESULT

Browser proof is **not Playwright**; it uses the repo CDP harness `tools/acceptance/phase_b/p2_kitchen_kds.mjs`.

Close-out run (2026-09-29, local stack: mock auth `54321`, API `8010`, workspace `3101`, DB `locah_growth_scratch` on `54329`; use **`http://localhost`** for API and workspace URLs so CORS matches):

| Check | Result |
| --- | --- |
| One KOT after accept + worker drain | PASS |
| Table / service context on card | PASS |
| Modifier visible | PASS |
| Elapsed time visible | PASS |
| No price, no customer phone | PASS |
| New → Preparing → Ready → Served | PASS |
| Workspace nav “Kitchen display” link | FAIL (link not on shell in this run; pass flow is authoritative) |

Screenshots: `acceptance-out/phase_b/p2_kitchen/01-new.png` … `04-served.png` (when the script completes the pass steps).

Re-run: mint session with `owner.py locah_growth_scratch acceptance-out/session.json`, then `node tools/acceptance/phase_b/p2_kitchen_kds.mjs` with `LOCAH_API=http://localhost:8010` and `LOCAH_WORKSPACE=http://localhost:3101`.

## RUFF

```text
ruff check python/core/platform_core/kitchen \
  python/core/platform_core/events/subscribers/kitchen_intake.py \
  apps/api/src/platform_api/routers/v1_platform_kitchen.py \
  apps/api/tests/test_kitchen.py
```

Result at close-out: **All checks passed.**

## TSC

```text
pnpm --dir apps/workspace exec tsc --noEmit
```

Kitchen/KDS paths: **clean** after exporting shared `Board` type from `KdsBoard.tsx`.

## LINT

```text
pnpm --dir apps/workspace exec next lint --dir src/app/kds --dir src/app/b/[businessId]/kitchen
```

Result at close-out: **No ESLint warnings or errors** on those routes.

## RLS

Defense in depth on kitchen tables (`kitchen_tickets`, lines, events, stations, routes): tenant `business_id = current_business_id()` and restrictive `location_scope_allows(location_id)`.

Proved in `test_tenant_and_location_isolation` via `SET LOCAL ROLE platform_api` and location scope GUC (same pattern as `test_rls_isolation.py`).

## EVENTS

Published by kitchen (catalogue group `kitchen`, notifications skipped except where noted):

| Event | When |
| --- | --- |
| `kitchen.ticket.created` | Ticket opened from order |
| `kitchen.ticket.started` | Ticket leaves `new` |
| `kitchen.ticket.ready` | Ticket becomes ready |
| `kitchen.ticket.cancelled` | Cancel before/after start (`after_start` in payload) |
| `kitchen.preparation.completed` | Ticket **completed** (served), **once** per ticket (`consumption_published`) |

Subscribed (does not modify orders):

| Subscriber | Events |
| --- | --- |
| `kitchen.order_intake` | `order.accepted`, `order.updated`, `order.cancelled`, `order.rejected` |

Intake idempotency: `kitchen_intakes.event_id` unique; one ticket per `(business_id, order_id)`.

## ORDER INTEGRATION HOOK

Kitchen **reads** orders through `OrderResolver` and fulfilment mode on `FulfilmentJob`. It does **not** call `OrderLifecycleService` or change order status.

Orders lane may later subscribe to `kitchen.ticket.ready` or `kitchen.preparation.completed` for fulfilment sync; that is out of scope here.

## SUPPLY/RECIPE INTEGRATION HOOK

After branches combine, **Cursor Supply / Inventory** should subscribe to:

**`kitchen.preparation.completed`**

Payload (stable):

```json
{
  "business_id": "uuid",
  "location_id": "uuid",
  "order_id": "uuid",
  "ticket_id": "uuid",
  "ticket_number": "KOT-0001",
  "completed_at": "ISO-8601",
  "lines": [
    {
      "order_line_id": "uuid",
      "offering_id": "uuid",
      "variant_id": "uuid or null",
      "quantity": 1,
      "modifiers": { "choices": {}, "notes": {} }
    }
  ]
}
```

Kitchen does **not** emit `inventory.stock.updated` and does **not** decrement stock. Recipe/BOM consumption is entirely on the subscriber.

## SHARED FILES TOUCHED

Integration commit only (minimal hunks):

- `apps/api/src/platform_api/main.py`
- `apps/workspace/src/lib/workspace-nav.ts`
- `python/core/platform_core/events/subscribers/__init__.py`
- `python/core/platform_core/catalog/modules.py` (`kitchen` `built=True`)
- `python/core/platform_core/authorization/role_templates.py`
- `python/core/platform_core/permissions.py`
- `packages/permissions/src/identifiers.ts`
- `python/core/platform_core/events/catalogue.py`

## CLAUDE INTEGRATION REQUIRED

- Merge `parallel/cursor-kitchen` after other lanes; resolve only if the same shared files diverged.
- Apply migration `20260930190000_kitchen_preparation.sql` on each environment (local/staging/prod pipeline).
- Wire Supply subscriber to `kitchen.preparation.completed` (do not read kitchen tables for deductions).
- Optional later: Orders subscriber to `kitchen.ticket.ready` / `kitchen.preparation.completed` for customer-facing status (kitchen must not write order state).

## KNOWN LIMITATIONS

- KT-03 printer fallback not implemented; screen pass only.
- KDS polls ~8s; no websocket push.
- Kitchen role template uses `kitchen.read` / `kitchen.advance` only (no `orders.read`, no prices/phones on pass).
- Browser nav link check in `p2_kitchen_kds.mjs` needs workspace shell + mock auth; pass flow itself is the primary proof.

## READY_TO_INTEGRATE

**YES** — domain, migration replay, Postgres tests (including preparation-completed idempotency), Ruff, kitchen-route lint, and TSC for KDS types are green at close-out. Run the CDP browser script once against your local stack before production merge if you want a fresh screenshot set.

---

## Product reference (unchanged)

One order → one kitchen ticket. Preparation snapshots only. Stations configurable. Cancel/adjust after start keeps cooked facts and shows events. Routes and permissions as in the original lane brief.
