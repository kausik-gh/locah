# Stage 3 — Discovery (Marketplace)

Capability: `core-marketplace-presence` · svc-search-discovery · Doc 08 §6.1 · Doc 09 §3 · Doc 10 §13 · Doc 11 §13 / §17.3 · Doc 12 §14

> Note: Kernel Stage 3 (Locations/People) is a separate frozen deliverable (`stage-3-location-people-kernel.md`). This document is product Stage 3 — Marketplace Discovery per Document 11 §17.3.

---

## Scope verification (pre-implementation)

**Confirmed:** `Business.visibility` is already the three-state model `private` / `unlisted` / `discoverable` (migration `20260713010000_stage1e_platform_foundation.sql` CHECK constraint; validation in `business_settings.py`). `public` is not treated as discoverable.

**Confirmed:** `core-marketplace-presence` is Platform Core (Document 08 §6.1), seeded in `module_definitions` with the same Stage 1 continuity pattern as other Core IDs — not redesigned as an optional module.

> Doc 11 §17.3 (Stage 3 scope/entry/exit): Marketplace search entry; Business/Offering indexing (event-driven + reconciliation); joined-Business-only eligibility enforced twice; basic Location/type refinement; Marketplace Business Profile; Website/Offering handoff preserving Destination Intent; indexing health + Admin recovery. Exit proves eligible businesses appear, ineligible do not, stale-index and index-recovery paths work.

> Doc 12 §14 (Marketplace and Search Implementation): Postgres GIN full-text is the resolved First Launch decision (FL-DEC-014); projection tables with trigger-maintained `search_vector`; eligibility gate at index and query time; no FK-joined live search against module tables.

> Doc 10 §13 / §10.1: provider-agnostic `svc-search-discovery`; search reads projections only.

> Doc 08 §6.1: Marketplace Presence (`core-marketplace-presence`) is Platform Core — every Business receives it; not an optional installable module.

> Doc 09 §3: page families MKT-001 Home, MKT-002 Search, MKT-004 Results, MKT-005 Filters & Location, MKT-007 Marketplace Business Profile, MKT-008 Offering handoff. MKT-003 Categories (Post-MVP) and MKT-006 Map (Future) deferred.

---

## APIs

| Method | Path | Auth |
|--------|------|------|
| GET | `/v1/public/search?q=&location=&type=` | public |
| GET | `/v1/public/businesses/{slug}` | public |
| GET | `/v1/b/{business_id}/marketplace` | `marketplace.read` |
| POST | `/v1/b/{business_id}/marketplace/opt-in` | `marketplace.configure` |
| POST | `/v1/b/{business_id}/marketplace/visibility` | `marketplace.configure` |
| GET | `/v1/admin/marketplace/indexing` | Super Admin |
| GET | `/v1/admin/marketplace/indexing/{business_id}` | Super Admin |
| POST | `/v1/admin/marketplace/indexing/{business_id}/reindex` | Super Admin |

Public UI: `apps/web` `/marketplace`, `/search`, `/marketplace/[slug]`  
Workspace UI: `apps/workspace` `/b/{businessId}/marketplace`  
Admin UI: `apps/admin` `/marketplace/indexing`

## Events

Consumed (re-index triggers): `website.published`, `business.profile.updated`, `business.visibility.changed`, `business.suspended`, `offering.*`, `location.created|updated|archived`

Emitted: `marketplace.indexed`, `marketplace.deindexed`, `marketplace.index_failed`, `marketplace.reindex_triggered` (admin audit/outbox)

Async jobs: `marketplace.reconcile`, `marketplace.reindex`

## Tests

- `apps/api/tests/test_marketplace_indexing.py`
- `apps/api/tests/test_marketplace_search.py`
- `apps/api/tests/test_marketplace_recovery.py`

---

# Stage 3 Engineering Report

## 1. Executive Summary

Stage 3 implements **Marketplace Discovery** for First Launch: Postgres GIN projection search, joined-Business-only eligibility enforced at index and query time, event-driven + reconciliation indexing, public search/profile APIs, MKT-001/002/004/005/007/008 consumer pages, Workspace discoverability opt-in, and Admin indexing recovery. Frozen Business Presence, Offerings, Locations, Outbox, Audit, Authorization, and Worker infrastructure were reused without duplication. Categories browse, map discovery, ML ranking, and external search engines were not implemented (Doc 11 §13.1 / §18.3–18.4 deferred).

## 2. Implemented Components

| Component | Role |
|-----------|------|
| `marketplace_business_projections` / `marketplace_offering_projections` | Search projections (Doc 12 §14.2) |
| `marketplace_index_health` | Consent + indexing status for Admin |
| Trigger-maintained `search_vector` | GIN FTS (Doc 12 §14.3) |
| `evaluate_eligibility` | Joined-Business-only gate |
| `SearchDiscoveryProvider` / `PostgresGinSearchProvider` | Provider-agnostic search (Doc 10 §13.2) |
| `MarketplaceIndexingService` | Re-index, de-index, reconcile |
| `MarketplaceSearchService` | Search + MKT-007 profile + handoff |
| `MarketplacePresenceService` | Explicit opt-in; never auto-discoverable |
| Routers | `v1_public_search`, `v1_marketplace`, admin indexing |
| Worker | Outbox re-index triggers + reconcile/reindex jobs |
| apps/web | MKT-001/002/004/005/007/008 |
| apps/workspace | Marketplace Presence settings |
| apps/admin | Indexing health + manual re-index |

## 3. Database Changes

Migration: `infra/supabase/migrations/20260728000000_stage3_marketplace_discovery.sql`

- Projection tables with GIN indexes on `search_vector`
- Partial indexes for discoverable city/type refinement
- BEFORE INSERT/UPDATE triggers for tsvector maintenance
- `marketplace_index_health` for staleness/consent/failure visibility
- RLS policies aligned with other platform tables

No live search joins against offerings/website module tables (Doc 10 §10.1).

## 4. Domain Models

ORM: `MarketplaceBusinessProjection`, `MarketplaceOfferingProjection`, `MarketplaceIndexHealth` in `platform_core.models`.

Reused without modification: `Business`, `BusinessProfile`, `BusinessLocation`, `Offering` / `OfferingVariant`, `Website` / `WebsiteVersion` (`published_version_id`), Outbox, Audit.

## 5. Services

- **Indexing** — eligibility → upsert/delete projections → emit outbox; `_upsert_offerings` only when eligible
- **Search** — provider query on projections → live `evaluate_eligibility` filter → result states `results` / `no_results` / `sparse_market`
- **Presence** — consent gate for `discoverable`; preferences path cannot set discoverable directly

## 6. APIs

Public search and Marketplace Business Profile under `/v1/public/*`. Workspace settings under `/v1/b/{id}/marketplace*`. Admin recovery under `/v1/admin/marketplace/indexing*`. Response envelope `{ data, meta }` preserved.

## 7. Authorization Integration

- Public search/profile: no auth
- Opt-in / visibility: `marketplace.configure` via Authorization Engine (`require_business_actor`)
- Settings read: `marketplace.read`
- Admin: Super Admin grant (`require_super_admin`)
- Primary Owner receives all permissions including marketplace.* via role registry

## 8. Audit Integration

- `business.visibility.changed` (opt-in and opt-out)
- `marketplace.reindex_triggered` (Admin manual)
- `marketplace.index_failed` (when actor present)

## 9. Outbox Integration

Existing Outbox consumer dispatches `MARKETPLACE_INDEX_TRIGGERS` to `MarketplaceIndexingService.reindex_business`. Emits `marketplace.indexed` / `deindexed` / `index_failed`. Dead letters surfaced on Admin listing.

## 10. Resolver Design

No separate entity resolver required beyond slug lookup via existing `BusinessService.get_by_slug` for MKT-007. Search provider abstracts projection reads (swappable without call-site changes — Doc 10 §13.2).

## 11. Validation Rules

- Eligibility: `state=active`, `status=in_good_standing`, `visibility=discoverable`, published Website (`published_version_id`), profile public facts (description or tagline)
- Opt-in requires `confirmed=true`; cannot set discoverable via generic preferences
- Visibility values only `private` / `unlisted` / `discoverable`
- Action projection: Order/Book/Contact/Visit Website only when capability flags active (Doc 09 §3.4)

## 12. Performance

GIN indexes on both projection tables; partial indexes for discoverable filters. Search limited (1–50). Public pages use short revalidate windows. Reconciliation scans bounded `limit` (default 100).

## 13. Testing Summary

| Suite | Coverage |
|-------|----------|
| `test_marketplace_indexing.py` | Ineligible not indexed; opt-in indexes + outbox; opt-out deindexes |
| `test_marketplace_search.py` | Relevance, no-results, type filter, query-time eligibility against stale projection, sparse/no-result states |
| `test_marketplace_recovery.py` | Reconcile repairs drift, Admin re-index audited, failure/dead-letter visibility, unauthenticated opt-in denied |

## 14. Files Created

- `infra/supabase/migrations/20260728000000_stage3_marketplace_discovery.sql`
- `python/core/platform_core/marketplace/` (`eligibility.py`, `search_provider.py`)
- `python/core/platform_core/services/marketplace_*.py`
- `apps/api/src/platform_api/routers/v1_public_search.py`, `v1_marketplace.py`
- `apps/api/tests/test_marketplace_*.py`
- `apps/web/src/app/marketplace/**`, `apps/web/src/app/search/**`, `apps/web/src/lib/marketplace-api.ts`
- `apps/workspace/src/app/b/[businessId]/marketplace/**`
- `apps/admin/src/app/marketplace/indexing/**`
- `apps/api/docs/stage-3-marketplace-discovery.md`

## 15. Files Modified

- `python/core/platform_core/models.py`
- `python/core/platform_core/services/business_settings.py` (block discoverable without opt-in; emit visibility.changed)
- `apps/api/src/platform_api/main.py`
- `apps/api/src/platform_api/routers/v1_admin.py`
- `apps/worker/.../outbox_consumer.py`, `job_runner.py`
- `apps/workspace/.../layout.tsx` (Marketplace nav)
- `apps/admin/src/app/page.tsx` (link)
- Permissions already included `marketplace.read` / `marketplace.configure`

## 16. Architectural Compliance

| Rule | Status |
|------|--------|
| Reuse Business/Profile/Location/Offering/Website | Yes |
| Reuse Outbox / Audit / Worker | Yes |
| Postgres GIN only (FL-DEC-014) | Yes |
| Projections-only search | Yes |
| Dual eligibility enforcement | Yes |
| No MKT-003 / MKT-006 | Yes |
| No ML ranking / sponsored / external search | Yes |
| Never auto-opt-in | Yes |
| Doc 08 Core (not optional module redesign) | Yes |

Citations: Doc 10 §10.1, §13; Doc 11 §13.1, §13.3, §17.3; Doc 12 §14.1–§14.5.

## 17. Implementation Decisions

| Decision | Citation |
|----------|----------|
| Postgres GIN FTS as First Launch search | Doc 12 §14.1 FL-DEC-014 |
| Provider Protocol over call sites | Doc 10 §13.2 |
| Eligibility at index + query | Doc 12 §14.4 |
| Explicit consent opt-in for discoverable | Doc 04 workflow / Doc 11 §13.3 |
| Marketplace Profile distinct from Website | Doc 09 §1.3 / §3 |
| Capability-backed action buttons only | Doc 09 §3.4 |
| Admin indexing health in launch scope | Doc 11 §17.3 |
| `marketplace_index_health` for consent + recovery | Doc 11 §17.3 exit tests |
| Opt-in may promote draft/onboarding → active | Needed for joined-Business active gate without silent discoverability |

## 18. Future Dependencies

- Categories browse page (MKT-003, Post-MVP)
- Map / spatial discovery (MKT-006, Future)
- Ranking/personalization / sponsored placements (deferred)
- Swappable search backend behind `SearchDiscoveryProvider` if scale requires
- Richer offering↔location assignment on offering projections (`location_ids` reserved)
- ISR tag invalidation on `marketplace.indexed` / `deindexed`

## 19. Risks

| Risk | Mitigation |
|------|------------|
| Projection drift after direct DB edits | `marketplace.reconcile` + Admin manual re-index |
| Indexing job failures | Health `failed` status + outbox `marketplace.index_failed` + dead-letter Admin view |
| Accidental discoverability | Consent flow required; preferences path rejects `discoverable` |
| Sparse early market UX | Explicit `sparse_market` search state (Doc 09 results states) |

## 20. Verification Checklist

- [x] Visibility three-state confirmed; not equating `public` to discoverable
- [x] `core-marketplace-presence` Platform Core
- [x] Projection schema + GIN + triggers
- [x] Event-driven indexing + reconciliation
- [x] Dual eligibility enforcement
- [x] Public search + MKT-007 profile
- [x] Destination Intent preserved on handoff
- [x] MKT-001/002/004/005/007/008 (not 003/006)
- [x] Admin indexing health + re-index + dead letters
- [x] Workspace opt-in consent
- [x] Audit + outbox events
- [x] Tests for indexing / search / recovery

## 21. Integration Matrix

| System | Integration |
|--------|-------------|
| Website publish | Outbox → re-index |
| Business visibility / profile | Outbox → re-index; opt-in path |
| Offerings / Locations | Outbox → re-index projections |
| Authorization | marketplace.read / configure |
| Worker | Outbox triggers + reconcile/reindex jobs |
| apps/web | Public Marketplace UI |
| apps/workspace | Opt-in settings |
| apps/admin | Recovery UI |

## 22. Scope Verification

**In scope (Doc 11 §17.3 / §13.1):** Marketplace search entry, indexing + reconciliation, joined-Business eligibility (twice), basic Location/type refinement, Marketplace Business Profile, Website/Offering handoff with Destination Intent, indexing health + Admin recovery, Workspace opt-in.

**Out of scope (not implemented):** MKT-003 Categories, MKT-006 Map, ML ranking/personalization, sponsored placements, advanced faceting beyond Location/type, external search engines (Typesense/Elasticsearch/Meilisearch), Memberships/Leads/Fulfilment/Workforce modules.
