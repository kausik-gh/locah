# Stage 5 — Inventory & Offerings Catalog Kernel

Modules: `offerings-catalog`, `inventory` (Doc 11 §9.1, §10.3)

Procurement, suppliers, and purchase orders are **explicitly deferred** per Doc 11 §10.3.

## APIs

Base: `/v1/platform/businesses/{business_id}/`

### Product categories

| Method | Path | Permission |
|--------|------|------------|
| GET | `/product-categories` | `offerings.read` |
| POST | `/product-categories` | `offerings.create` |
| GET | `/product-categories/{id}` | `offerings.read` |
| PATCH | `/product-categories/{id}` | `offerings.update` |
| POST | `/product-categories/{id}/archive` | `offerings.archive` |

### Products (offerings)

| Method | Path | Permission |
|--------|------|------------|
| GET | `/products` | `offerings.read` |
| POST | `/products` | `offerings.create` |
| GET | `/products/{id}` | `offerings.read` |
| PATCH | `/products/{id}` | `offerings.update` |
| POST | `/products/{id}/archive` | `offerings.archive` |
| POST | `/products/{id}/restore` | `offerings.update` |
| GET | `/products/{id}/variants` | `offerings.read` |
| POST | `/products/{id}/variants` | `offerings.update` |

### Inventory

| Method | Path | Permission |
|--------|------|------------|
| GET | `/inventory` | `inventory.read` |
| GET | `/inventory/export` | `inventory.export` |
| POST | `/inventory/adjust` | `inventory.adjust` |
| POST | `/inventory/opening-stock` | `inventory.adjust` |

List filters: `?status=`, `?search=`, `?category_id=`, `?track_inventory=`, `?location_id=`, `?offering_id=`, `?stock_status=`

## Events

Emit: `offering.created`, `offering.updated`, `offering.archived`, `offering.restored`, `offering.variant.created`, `product_category.created`, `product_category.updated`, `product_category.archived`, `inventory.stock.updated`, `inventory.stock.low`, `inventory.stock.zero`, `inventory.stock.replenished`, `inventory.adjusted`, `inventory.opening_stock.set`

Order-driven reservation/deduction/reversal deferred until Stage 6+ Orders module (Doc 11 §10.3).

## Tests

`apps/api/tests/test_inventory_kernel.py`

---

# Stage 5 Engineering Report

## 1. Executive Summary

Stage 5 implements the **Inventory & Offerings Catalog Kernel** for First Launch scope. Businesses can manage typed product offerings (categories, products, variants), track stock per location with manual adjustments and opening stock, and receive low/out-of-stock state — all scoped to a single business with authorization, audit, and transactional outbox integration.

**Procurement (suppliers, purchase orders) is intentionally excluded** per Doc 11 §10.3 deferred list.

## 2. Implemented Components

| Component | Role |
|-----------|------|
| `CategoryService` | Product category CRUD and archive |
| `OfferingService` | Product/offering lifecycle, variants, SKU dedup |
| `InventoryService` | Stock records, opening stock, adjustments, export |
| `OfferingResolver` | Category/product/variant lookup and serialization |
| `InventoryResolver` | Stock status computation, record lookup |
| `validation/offering.py` | Category and product payload validation |
| `validation/inventory.py` | Adjustment and opening-stock validation |
| `v1_platform_offerings.py` | Categories and products REST API |
| `v1_platform_inventory.py` | Inventory REST API |

## 3. Database Changes

Migration: `infra/supabase/migrations/20260727060000_stage5_inventory_offerings_kernel.sql`

| Table | Purpose |
|-------|---------|
| `offerings_catalog_categories` | Hierarchical product categories |
| `offerings_catalog_offerings` | Typed offerings with pricing, tax, UOM, track_inventory |
| `offerings_catalog_variants` | Product variants/options |
| `inventory_records` | Location-specific stock balances (optimistic `version`) |
| `inventory_movements` | Immutable movement ledger |

Partial unique indexes on SKU (business-scoped). Partial unique indexes on inventory `(offering, variant?, location)` handling NULL variant_id. RLS read policies on all tables (Doc 12 §tenant isolation).

## 4. Domain Models

- `OfferingCategory` — name, slug, parent_id, sort_order, status (Doc 12 `offerings_catalog_*` naming)
- `Offering` — offering_type, title, sku, barcode, pricing, tax_rate, track_inventory, low_stock_threshold, visibility (Doc 11 §9.1)
- `OfferingVariant` — name, sku, price_amount per variant (Doc 11 §9.1 variants/options)
- `InventoryRecord` — quantity_on_hand, quantity_reserved, per location (Doc 11 §10.3)
- `InventoryMovement` — opening_stock, adjustment (+ schema placeholders for order-driven types) (Doc 04 event catalog)

## 5. Services

See §2. `InventoryService` validates offering `track_inventory=true`, location ownership via `LocationResolver`, and variant-offering consistency before mutating stock.

## 6. APIs

Documented above. Product endpoints use `/products` for workspace ergonomics; events retain canonical `offering.*` naming (Doc 12 §marketplace projections).

## 7. Authorization Integration

Reuses `require_business_actor()` with existing permissions (Doc 12 §inventory / offerings-catalog):

- `offerings.read/create/update/archive`
- `inventory.read/adjust/export`

No parallel authorization system introduced.

## 8. Audit Integration

All mutations record via `AuditService.record()` with resource types `product_category`, `product`, `product_variant`, `inventory_record`. Actions: created, updated, archived, restored, adjusted, opening_stock.

## 9. Outbox Integration

Domain events published through `OutboxService.publish()` in the same transaction. Worker registers handlers in `KNOWN_HANDLERS` (Doc 12 §22). Stock transitions emit Doc 04 canonical events: `inventory.stock.updated`, `inventory.stock.low`, `inventory.stock.zero`, `inventory.stock.replenished`.

## 10. Resolver Design

- `OfferingResolver` — business-scoped lookup, operable gate (draft/active vs archived), serialization
- `InventoryResolver` — record lookup, `stock_status()` (`available` / `low_stock` / `out_of_stock`), track_inventory gate

Follows Stage 3–4 resolver conventions.

## 11. Validation Rules

| Rule | Source |
|------|--------|
| Business ownership on all refs | Doc 10 tenant isolation |
| Duplicate SKU per business | Doc 11 commerce credibility |
| track_inventory required for stock ops | Doc 11 §9.1 / §10.3 dependency |
| Location belongs to business | Reuses Location Kernel |
| Non-negative stock after adjustment | Doc 11 §10.3 integrity |
| Reason required for adjustments | Doc 11 §10.3 audit |
| Opening stock once per offering/location | First Launch controlled depth |

## 12. Search Design

- Products: `title`, `sku`, `barcode` ILIKE
- Categories: `name` ILIKE
- Inventory list: product title/sku ILIKE + optional `stock_status` filter (computed post-query)

Cursor pagination deferred platform-wide (Stage 3–4 precedent).

## 13. Performance

Indexes on `business_id`, `category_id`, `location_id`, `offering_id`, movement ledger `(inventory_record_id, created_at DESC)`. Inventory list uses single JOIN (Offering + InventoryRecord) to avoid N+1.

## 14. Testing Summary

`apps/api/tests/test_inventory_kernel.py`:

- Category and product CRUD, SKU dedup, archive/restore
- Opening stock, adjustment, low/out-of-stock transitions, negative guard
- Business isolation (404 cross-tenant)
- Outbox and audit presence for inventory mutations

## 15. Files Created

| Path |
|------|
| `infra/supabase/migrations/20260727060000_stage5_inventory_offerings_kernel.sql` |
| `python/core/platform_core/validation/offering.py` |
| `python/core/platform_core/validation/inventory.py` |
| `python/core/platform_core/resolvers/offering_resolver.py` |
| `python/core/platform_core/resolvers/inventory_resolver.py` |
| `python/core/platform_core/services/category.py` |
| `python/core/platform_core/services/offering.py` |
| `python/core/platform_core/services/inventory.py` |
| `apps/api/src/platform_api/routers/v1_platform_offerings.py` |
| `apps/api/src/platform_api/routers/v1_platform_inventory.py` |
| `apps/api/tests/test_inventory_kernel.py` |
| `apps/api/docs/stage-5-inventory-offerings-kernel.md` |

## 16. Files Modified

| Path | Change |
|------|--------|
| `python/core/platform_core/models.py` | Stage 5 domain models |
| `apps/api/src/platform_api/main.py` | Router registration |
| `apps/worker/src/platform_worker/outbox_consumer.py` | Known event handlers |

## 17. Architectural Compliance

| Decision | Justification |
|----------|---------------|
| Separate `offerings-catalog` + `inventory` tables | Doc 12 §566–575 module table naming |
| No procurement/suppliers | Doc 11 §10.3 deferred |
| Reuse Location Kernel for stock location | Doc 11 §10.3 location-specific stock |
| Transactional outbox + audit on every mutation | Doc 04 §event-driven, Doc 12 §outbox |
| RLS read policies | Doc 10 tenant isolation |
| Movement types include order placeholders in schema only | Doc 11 §10.3 order-driven deduction deferred until Orders |
| API path `/products` with event `offering.*` | Doc 12 marketplace projection contract |

## 18. Implementation Decisions

1. **Stock status is computed**, not stored — avoids drift; aligns with Doc 04 event-driven projections.
2. **Partial unique index for NULL variant_id** — PostgreSQL NULL uniqueness handled explicitly.
3. **Opening stock conflict if quantity > 0** — prevents accidental overwrite; adjustments used thereafter.
4. **Category events use `product_category.*`** — distinct from offering events for audit clarity.
5. **Variants create via nested route** — matches Doc 09 page model; full variant PATCH deferred to keep scope minimal.

## 19. Future Dependencies

| Dependency | When |
|------------|------|
| Orders module | reservation/deduction/reversal movement types (Doc 11 §10.3) |
| Public availability projection | Website/Marketplace without exposing internal qty (Doc 11 §10.3) |
| Location availability on offerings | Doc 11 §9.1 location assortment |
| Import/export merchandising | Doc 11 §9.1 deferred |
| Procurement kernel | Doc 11 §10.3 deferred |

## 20. Risks

| Risk | Mitigation |
|------|------------|
| Order module double-decrement | Movement ledger + explicit order consumer later |
| SKU collision across variants vs products | Separate partial unique indexes per table |
| Low-stock threshold at offering vs record level | Record inherits offering default; record override supported |

## 21. Verification Checklist

- [ ] `npx supabase db reset` applies migration cleanly
- [ ] `uv run pytest apps/api/tests/test_inventory_kernel.py -q`
- [ ] `pnpm lint` and `pnpm typecheck` pass
- [ ] Owner can CRUD products and adjust inventory
- [ ] Cross-business access returns 404
- [ ] Outbox events reach `completed` via worker

## 22. Integration Matrix

| Engine | Integration |
|--------|-------------|
| Identity / Business Context | Business-scoped routes via `require_business_actor` |
| Location Kernel | `LocationResolver` validates stock location |
| Authorization | Existing permission identifiers |
| Audit | `AuditService` on all mutations |
| Outbox | `OutboxService` + worker handler registry |
| Entitlements | `inventory.core`, `offerings-catalog.core` in plan registry (enforcement at module layer future) |
