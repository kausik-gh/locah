# Cursor supply lane handoff

Claude reconciles this into the master ledger. This file is the lane record.

BRANCH: parallel/cursor-supply-b2b

BASE SHA: 84eead219d3dfe6625f21f8207dc66eade076297

COMMITS:
1. 76ddb6ce58ec7b49e32d2f372e4e0520c94b1214 feat(procurement): add the supply domain beside inventory
2. ec640fc379e9acf7ac2a5b357288faca815fe768 feat(procurement): add buying, expense and donation screens
3. 16743718003bc3f6c367e01dd0c45124e6549d78 chore(integration): wire cursor supply modules

## Modules functionally implemented

- Suppliers, supplier items, price agreements (historical PO price stays pinned)
- Requisitions with the demand arithmetic kept on the row
- Purchase orders, approval, send, counter-offer that does not change the line until the buyer accepts
- Goods receipts that call StockService.receive, including partial receipt and idempotent replay
- Supplier bills as payables, not a second payment engine
- Recipes / BOM and one-time consumption through InventoryService.adjust_stock
- Incoming B2B demand as a sealed copy on the supplier business
- Expenses and totals
- Connector pairing, mapping, fixture sync, and a block on bidirectional sync without a conflict policy
- Documents records
- Donations linked to a payment id, without collecting money here
- Supplier fill rate from ordered versus received quantities

## Partial

- Workspace covers Buying home, incoming demand, a supplier form, expenses, and donations. Purchase-order approval, receipt, recipes, documents, and connectors have services and no screen yet.
- Recipes, documents, and connectors are not marked built.
- Assignment-scoped roles are not granted these permissions. Primary owners receive them through ALL_PERMISSIONS. Store-keeper and accountant grants wait on Claude's role-scope engine.

## Activation required

- ChitBridge live transport. The sealed copy function is the boundary. No live ChitBridge call was made.
- Tally. Mapping and fixture sync only. Not production verified.
- Off-network supplier magic links and WhatsApp delivery. Not built in this packet.
- Cashfree / Meta / paid AI. Not called.

## Migration

infra/supabase/migrations/20260930130000_procurement_supply_lane.sql

Applied to the hosted project database behind DATABASE_URL during this lane, so the tables are already there. It was not applied through a dedicated test database.

## API

Mounted in apps/api/src/platform_api/main.py:

- GET /v1/platform/businesses/{id}/buying
- GET /v1/platform/businesses/{id}/buying/incoming
- POST /v1/platform/businesses/{id}/suppliers
- GET/POST /v1/platform/businesses/{id}/expenses and /expenses/summary
- GET /v1/platform/businesses/{id}/donations
- POST /v1/platform/businesses/{id}/donations/causes
- POST /v1/platform/businesses/{id}/donations/gifts

Purchase orders, receipts, recipes, connectors, and documents are service methods without routes yet.

## Events

procurement.requisition.created, procurement.po.approved, procurement.po.sent, procurement.po.countered, procurement.goods_received, supplier.bill.created, recipe.consumed, trade.message.received, expense.created, donation.received, connector.sync.completed, document.recorded

## Permissions

procurement.read, procurement.create, procurement.approve, procurement.receive, procurement.cost, supplier.read, expenses.read, expenses.write, connectors.read, connectors.manage, documents.read, documents.write, donations.read, donations.write

## Tests

apps/api/tests/test_supply_lane.py

4 passed (demand math, pack/MOQ, recipe explosion, aggregate example).
4 skipped. Those need a database: tenant isolation, the buy-to-receipt replay, and one-time recipe consumption.

They were not run. The test guard refuses a remote DATABASE_URL, and TEST_DATABASE_URL is not set. Do not point them at the hosted database.

## Playwright

Not run.

## Shared files touched

- python/core/platform_core/permissions.py
- python/core/platform_core/events/catalogue.py
- python/core/platform_core/catalog/modules.py (built=True for procurement, expenses, donations)
- apps/api/src/platform_api/main.py
- apps/workspace/src/lib/workspace-nav.ts

## Claude integration required

- Cherry-pick or merge the domain commits, then keep the wiring commit if those shared files have not moved. If they have, re-apply the router include, the three nav items, and the three built flags by hand.
- Grant procurement / expense / donation permissions on the role templates Claude owns. This lane did not edit them.
- Supplier bills should later post through the shared ledger. They are recorded here and not paid here.

## Known merge risks

main.py, workspace-nav.ts, permissions.py, the event catalogue, and catalog/modules.py.

## Known product limitations

A sent purchase order does not increase stock. Only a goods receipt does.
A counter-offer is a separate row until the buyer accepts it.
The supplier sees buyer label, item, quantity, and price. Not the buyer's customers.
Bidirectional connector sync refuses to run until a conflict policy exists.
The migration's trade function is the only cross-tenant write, and it inserts a copy. It does not read the buyer's purchase order.
