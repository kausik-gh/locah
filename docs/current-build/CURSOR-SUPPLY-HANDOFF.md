# Cursor supply lane handoff

Claude reconciles this into the master ledger. This file is the lane record.

BRANCH: parallel/cursor-supply-b2b

MAIN SHA MERGED: 1cb02e1449815ecf365a976d1694c9bd6681b2c2

Earlier base, before this integration: 84eead219d3dfe6625f21f8207dc66eade076297

## Commits

1. 76ddb6ce58ec7b49e32d2f372e4e0520c94b1214 feat(procurement): add the supply domain beside inventory
2. ec640fc379e9acf7ac2a5b357288faca815fe768 feat(procurement): add buying, expense and donation screens
3. 16743718003bc3f6c367e01dd0c45124e6549d78 chore(integration): wire cursor supply modules
4. 4be74ac55408724fa2f6ff8ca59b76d147d2a712 docs: record the cursor supply lane handoff
5. dc58774 merge origin/main into parallel/cursor-supply-b2b
6. 4bceb912880d0612858527d07c8ce9bcafaae2e7 wip(cursor): checkpoint supply lane changes

The integration commit that follows this note is on the same branch. Do not rewrite the four original commits.

## Modules functionally implemented

- Suppliers, supplier items, price agreements (historical PO price stays pinned)
- Requisitions with the demand arithmetic kept on the row
- Purchase orders, approval, send, counter-offer that does not change the line until the buyer accepts
- Goods receipts that call StockService.receive, including partial receipt and idempotent replay
- Supplier bills stay open. `ledger_posting_intent` names a later shared-ledger `purchase` and a `payment_made` settlement. Buying does not mark a bill paid.
- Recipes / BOM and one-time consumption through InventoryService.adjust_stock
- Incoming B2B demand as a sealed copy on the supplier business
- Expenses and totals
- Connector pairing, mapping, fixture sync, and a block on bidirectional sync without a conflict policy
- Documents records
- Donations linked to a payment id, without collecting money here
- Supplier fill rate from ordered versus received quantities

## Role grants

Applied on the current role templates, not a rebuilt assignment-scope engine.

- Owner: every permission, through ALL_PERMISSIONS
- Manager: procurement read, create, approve, receive, cost; supplier read; expenses read
- Store keeper: procurement read, create, receive; supplier read. Not approve. Not cost.
- Accountant: expenses read and write; procurement read and cost; supplier read; connectors read and manage; documents read and write; donations read and write. Not approve. Not receive.
- Cashier: no procurement permissions

## Partial

- Workspace covers Buying (requirement, explanation, approve and send, receipt), incoming demand, expenses, and donations.
- Recipes, documents, and connectors have services and are not marked built.
- Purchase-order, receipt, recipe, connector, and document routes beyond the Buying prepare / approve / receive actions are still service methods.
- Supplier bills are not posted into the shared ledger yet. Status stays open.
- ChitBridge, Tally, and Meta are ACTIVATION_REQUIRED. Fixture verified, not production verified.
- No paid AI and no Cashfree calls.

## Migration replay

Local disposable Postgres on 127.0.0.1:54330, database locah_supply_replay. Fresh replay of ci-bootstrap.sql, every file in infra/supabase/migrations sorted by name, then infra/supabase/seed/00_platform.sql. 74 files, exit 0. Claude's P2 migrations sort before 20260930130000, so the supply migration applied once beside them. Notices only.

## Tests

Local database only. DATABASE_URL and API_DATABASE_URL were unset. TEST_DATABASE_URL pointed at postgresql://postgres@127.0.0.1:54330/locah_supply_replay.

`apps/api/tests/test_supply_lane.py` plus `test_permissions.py`, `test_roles_and_scope.py`, and `test_stock_depth.py`:

44 passed, 0 skipped, 0 failed.

Supply file: 11 passed, 0 skipped. That includes tenant isolation for procurement and expenses, the sealed B2B RLS check through role platform_api, buy → approve → send → receive 10 good and 2 damaged (stock 70 → 80, replay stays, second receipt of 20 completes at 100), and recipe consumption 20 → 17 with replay staying at 17. A purchase order, a counter-offer, and a supplier bill move no stock.

Ruff on the changed Python files passed. Workspace `tsc --noEmit` passed.

## Playwright

Desktop Chrome, 1440×900, script `tools/acceptance/phase_b/supply_buying.mjs`. It does not edit the existing acceptance scripts.

6/6 checks passed for business "Supply 295619": Buying opened, supplier saved, explanation read "Required 100. Safety stock 0. Usable 70. Confirmed inbound 0. Net 30. Pack 1, minimum 1, so buy 30.", approve and send, receipt of 10 good and 2 damaged, Arriving became 1, Expenses rendered, Donations rendered, no page errors.

The same database row afterwards: quantity_on_hand 80, one receipt movement. Opening stock is not a receipt movement. The damaged 2 did not enter Inventory.

## Shared files touched

Auto-merge of origin/main kept both sides. No conflict markers.

- python/core/platform_core/permissions.py
- python/core/platform_core/authorization/role_templates.py
- python/core/platform_core/authorization/permission_registry.py
- packages/permissions/src/identifiers.ts
- python/core/platform_core/events/catalogue.py
- python/core/platform_core/catalog/modules.py
- apps/api/src/platform_api/main.py
- apps/workspace/src/lib/workspace-nav.ts

## HOSTED MIGRATION STATE REQUIRES RECONCILIATION

Do not re-execute `infra/supabase/migrations/20260930130000_procurement_supply_lane.sql` on the hosted project. Do not delete the hosted tables. Do not edit migration history from this lane.

- Project ref: pmwyaqmwxfbnfulqbqmk (Supabase, port 5432). This is the database behind the repo DATABASE_URL.
- When: 29 Sep 2026, during the first supply lane, through a temporary script that was not committed.
- What happened: the first apply created the tables, then stopped on a comment the statement splitter treated as a boundary. That comment was fixed in the file. The partial tables were dropped and the file was applied again. The second run completed (the script printed that it applied and exited 0).
- File SHA-256: 58d1ea5c1ad5ad33d796687da654cf3a839af288ed5826c528919a2be76cc860
- Read-only check on 29 Sep 2026: all 25 expected tables exist, `procurement_post_trade` exists and is SECURITY DEFINER, 50 policies exist, and row level security is on for every one of those tables.
- `supabase_migrations.schema_migrations` has 63 rows. The newest version is 20260929120000. Version 20260930130000 is not recorded. Later repository versions after 20260929120000 are also absent from history. This pass did not check whether those other objects exist live.

Safe reconciliation, from docs/audits/supabase-database-audit-2026-09.md (Schema Drift): dump the live schema, diff it against a clean replay, then use `supabase migration repair` only with a reviewed mapping. Do not repair history blindly. A later official migrate must not CREATE these tables again.

## Known product limitations

A sent purchase order does not increase stock. Only a goods receipt does, and only the good quantity.
A counter-offer is a separate row until the buyer accepts it.
The supplier sees buyer label, item, quantity, and price. Not the buyer's customers.
Bidirectional connector sync refuses to run until a conflict policy exists.
The migration's trade function is the only cross-tenant write, and it inserts a copy. It does not read the buyer's purchase order.
