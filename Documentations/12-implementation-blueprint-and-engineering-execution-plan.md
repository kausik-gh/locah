# Document 12 — Implementation Blueprint & Engineering Execution Plan

**Document:** 12
**Document Status:** Final Pre-Build Specification
**Version:** 1.4
**Date:** July 2026 (Version 1.2–1.3 amendments: September 1, 2026; Version 1.4 amendment: September 12, 2026)
**Authority:** Final governing implementation authority for Documents 01–12. Converts the approved platform model into an exact engineering execution plan from which implementation begins.
**Depends On:** `01-vision-document.md` · `02-product-experience-bible.md` · `03-business-kernel-specification.md` · `04-master-product-specification.md` · `05-user-context-journey-navigation-architecture-specification.md` · `06-role-permission-access-experience-matrix.md` · `07-business-type-configuration-profile-specification.md` · `08-plans-modules-entitlement-model.md` · `09-complete-page-by-page-product-experience.md` · `10-data-and-technical-architecture.md` Version 1.2 · `11-first-launch-scope-and-implementation-plan.md` Version 1.2

**Document Control**

| Version | Date | Change |
|---|---|---|
| 1.0 | July 2026 | Initial canonical implementation blueprint. Converts approved product model and architecture into engineering execution plan. Resolves FL-DEC-010, FL-DEC-011, FL-DEC-012, FL-DEC-013, FL-DEC-014 as engineering decisions. |
| 1.1 | July 2026 | Controlled correction pass: replaces the Node-oriented pg-boss mismatch with a Python-native PostgreSQL worker built on the transactional outbox; standardizes IDs on UUIDv4; updates Next.js authentication to the current `@supabase/ssr` cookie and Proxy pattern; and records the intentional Document 10 backend supersession by FastAPI/Python. No product, module, launch-scope, application-boundary, stage, or vertical-slice change. |
| 1.2 | September 1, 2026 | Additive amendment pass (Website Generation Overhaul & Workspace Cleanup work order). Records decisions made now, not retroactively: the AI content-authorship boundary (§12.6), the one-shot structured-intake generation model and its questionnaire (§12.7), and prebuilt-template ingestion as design-reference translation only — Option A (§12.8). Corrects two stale identifiers in §12.1–§12.2 to match the implemented `AIModelProvider.generate_structured` contract and the `platform_core/website/ai_provider.py` module path. No schema change; no change to the 13 seeded SectionTypes; no launch-scope change. `FL-DEC-015` (initial provider, budget, fallback policy) remains open — a temporary founder-authorized Gemini key is in place pending its formal closure. |
| 1.3 | September 1, 2026 | Additive amendment (media & storage implementation). Records how §15 was actually built: one `media` bucket rather than the four in §15.1; the Stage 2 `media_assets` column names retained over §15.2's; signed upload URLs minted with the **caller's JWT**, never a service-role key; upload permission derived from a declared `purpose` mapped onto existing canonical permissions rather than a new `media.*` identifier; and resolved asset URLs returned beside `content`, never inside it. See §15.5. Storage RLS tightened (migration `20260901020000`) — the pre-existing `media` bucket allowed anonymous insert/update. |
| 1.4 | September 12, 2026 | Additive amendment (documentation review). Records the live AI generation path as actually built — model, timeout, token ceiling, the section-catalogue prompt, the strict-envelope/lenient-content validation posture, persistence-failure fallback, and the `website_generation_jobs` drift from §12.4 — in a new §12.9, together with seven open defects against §§12.4–12.5. Corrects the §19.2 environment block. Adds §26, a stage-vocabulary errata reconciling the legacy "kernel stage" artifact naming with Document 11 §17. Corrects the stale **Version 1.1** header (the control table already ran to 1.3) and the Document 10 dependency pins. No schema change, no launch-scope change, no stage-definition change. |


---

# 0. Governance and Source Authority

## 0.1 Authority Order

Where documents conflict, the following governs:

1. **Document 08** — canonical Platform Core, optional modules, module IDs, Entitlements, and module boundaries.
2. **Document 09** — page-by-page product experience and product surfaces, except where Document 11 explicitly changes First Launch relevance.
3. **Document 10 Version 1.2** — technical and data architecture, module communication, tenant isolation, webhook durability, and provider boundaries, except for implementation choices explicitly superseded by this document.
4. **Document 11** — First Launch scope, launch depth, reference business models, implementation stages, and release sequencing.
5. **Document 12 Version 1.4** — final concrete implementation details and engineering execution authority. This document governs how systems are built and explicitly records any intentional supersession.

## 0.2 Resolved Engineering Decisions

The following decisions from Document 11 §26 are resolved by this document as engineering decisions that do not require further founder or commercial approval:

| Decision ID | Resolution |
|---|---|
| `FL-DEC-010` | Turborepo + pnpm workspaces. See Section 1. |
| `FL-DEC-011` | Supabase (managed PostgreSQL + Supabase Auth). See Section 6. |
| `FL-DEC-012` | PostgreSQL transactional outbox + a small Python-native PostgreSQL worker using safe row claiming, leases, retry/backoff, idempotency, and dead-letter handling. See Section 18. |
| `FL-DEC-013` | Canonical permission identifier scheme: `<resource>.<action>`. See Section 8. |
| `FL-DEC-014` | PostgreSQL full-text search (GIN indexes) for First Launch. See Section 14. |
| `FL-DEC-019` | Manager delegation ceiling: managers may grant up to but not beyond their own effective permissions. See Section 8. |

Other founder, commercial, feature, and production decisions remain governed and classified by Document 11 §26. They do not prevent repository bootstrap unless their affected implementation is reached.

### 0.2.1 Intentional Backend Architecture Evolution

Document 10 Version 1.1 specified or implied Node.js/TypeScript as the initial backend in some implementation-oriented passages. The approved final implementation decision is:

- Next.js/TypeScript for `apps/web`, `apps/workspace`, `apps/admin`, and frontend shared packages.
- FastAPI/Python for the authoritative modular-monolith backend in `apps/api`.
- Python for `apps/worker`.
- PostgreSQL/Supabase as the durable data and identity foundation.

Document 12 Version 1.1 intentionally supersedes Document 10 only for this backend language/framework and directly dependent implementation choices. This is an approved architecture evolution, not an accidental contradiction. It does not change Document 10's valid domain, data, security, module communication, RLS, webhook durability, or provider-boundary decisions.

## 0.3 What This Document Does Not Do

- Recreate the product vision.
- Redesign the module registry.
- Introduce business-type-specific architectures.
- Re-open approved First Launch scope.
- Silently restore legacy module IDs.
- Contradict Documents 08–11.
- Create microservices for future scale.
- Add infrastructure for architectural sophistication.

## 0.4 Implementation Can Begin

After this document, the combined Documents 01–12 are sufficient for a capable engineering team or coding AI to begin Stage 1 implementation and the first vertical slice without redesigning the product or architecture.

Broad architecture and product planning stops. Implementation begins. Unresolved decisions are handled only when their actual blocking point is reached.

---

# 1. Monorepo Structure

## 1.1 Tooling Decision

- **Monorepo tool:** Turborepo
- **Package manager:** pnpm workspaces
- **Repository:** One repository for the entire platform

**Rationale:** Turborepo provides efficient task caching and parallel execution for TypeScript and Python workloads. pnpm workspaces provide deterministic dependency management. One repository enforces the one-platform architectural principle.

## 1.2 Canonical Directory Tree

```
platform/                               <- repository root
|
+-- apps/                               <- deployable applications
|   +-- web/                            <- Next.js: public platform, marketplace, business websites, my activity
|   +-- workspace/                      <- Next.js: business workspace (authenticated operator surface)
|   +-- admin/                          <- Next.js: platform super admin
|   +-- api/                            <- FastAPI: modular-monolith backend
|   +-- worker/                         <- Python: PostgreSQL-backed async processor
|       +-- main.py                     <- worker process entry point and lifecycle
|       +-- outbox_consumer.py          <- domain/outbox event claiming and dispatch
|       +-- job_runner.py               <- asynchronous job claiming and execution
|       +-- scheduler.py                <- due schedule materialization
|       +-- claiming.py                 <- shared SKIP LOCKED and lease utilities
|
+-- packages/                           <- shared packages (TypeScript unless noted)
|   +-- ui/                             <- shared design system: tokens, primitives, components
|   +-- contracts/                      <- TypeScript API contracts, request/response types, event envelopes
|   +-- config/                         <- shared configuration schemas, environment validation
|   +-- validation/                     <- shared Zod schemas used by both frontend and API contracts
|   +-- api-client/                     <- generated/typed HTTP client for consuming the FastAPI backend
|   +-- auth/                           <- shared auth utilities: token handling, session helpers, auth context
|   +-- permissions/                    <- shared permission identifier registry (canonical string constants + types)
|   +-- observability/                  <- shared structured logging, tracing helpers, correlation ID utilities
|
+-- python/                             <- Python backend packages (internal)
|   +-- core/                           <- shared FastAPI infrastructure: context, auth middleware, DB sessions, DI
|   +-- domain_events/                  <- event envelope types, outbox helpers, publisher contracts
|   +-- testing/                        <- Python test helpers: fixtures, factories, RLS test utilities
|
+-- infra/                              <- infrastructure configuration
|   +-- supabase/                       <- supabase project config, linked projects per environment
|   |   +-- migrations/                 <- versioned PostgreSQL migration files (all modules, ordered)
|   |   +-- seed/                       <- environment-appropriate seed data scripts
|   |   +-- rls/                        <- RLS policy definitions (co-located with migrations for review)
|   +-- deploy/                         <- deployment configuration (CI/CD, environment manifests)
|
+-- tools/                              <- internal developer tooling and scripts
|   +-- codegen/                        <- contract generation, OpenAPI extraction scripts
|   +-- db/                             <- migration helpers, seed reset scripts, RLS validation scripts
|
+-- turbo.json                          <- Turborepo pipeline configuration
+-- pnpm-workspace.yaml                 <- pnpm workspace definition
+-- pyproject.toml                      <- Python workspace root (uv-based)
+-- .env.example                        <- documented environment variable template (no secrets)
+-- .github/workflows/                  <- CI/CD pipeline definitions
```

## 1.3 Package Purposes

| Path | Language | Purpose |
|---|---|---|
| `apps/web` | TypeScript/Next.js | Main platform website, Marketplace, Business Websites (dynamic routing), My Activity, guest consumer flows |
| `apps/workspace` | TypeScript/Next.js | Business Workspace — operator shell, module operational pages, settings, Website management |
| `apps/admin` | TypeScript/Next.js | Platform Super Admin — attributed support, operational tooling, Entitlement control |
| `apps/api` | Python/FastAPI | Authoritative backend — all business logic, authorization, module APIs, provider adapters, webhook ingestion |
| `apps/worker` | Python | PostgreSQL-backed processor — outbox event dispatch, asynchronous jobs, scheduled-job materialization, retries, dead-letter, indexing, notifications, and projections |
| `packages/ui` | TypeScript | Design system: tokens, Radix/headless primitives, shared compositions. Surface-specific assembly lives in each app. |
| `packages/contracts` | TypeScript | Canonical API request/response types, event envelope types, module public contract interfaces. Used by frontend apps and the api-client. |
| `packages/config` | TypeScript | Environment variable schemas (Zod), shared configuration constants |
| `packages/validation` | TypeScript | Shared Zod validation schemas — used in frontend forms and reflected in API contracts |
| `packages/api-client` | TypeScript | Typed HTTP client generated from FastAPI OpenAPI spec, used by frontend apps |
| `packages/auth` | TypeScript | `@supabase/ssr` browser/server clients, cookie session handling, Proxy refresh, access-token forwarding, display-only auth state |
| `packages/permissions` | TypeScript | Canonical permission identifier string constants and TypeScript types. The single source of canonical permission IDs. |
| `packages/observability` | TypeScript | Structured logging helpers, OpenTelemetry setup, correlation ID propagation |
| `python/core` | Python | FastAPI shared infrastructure: request context resolution, auth middleware, DB session factory, dependency injection providers |
| `python/domain_events` | Python | Domain event envelope model, outbox helper, publisher interface. Used by all modules inside `apps/api`. |
| `python/testing` | Python | pytest fixtures, database factories, RLS assertion helpers, test environment utilities |

## 1.4 Import and Dependency Rules

**TypeScript rules:**
- Apps may import from `packages/*` (one-way: apps depend on packages, not vice versa).
- `packages/ui` may not import from apps.
- `packages/contracts` must not import from `packages/ui`.
- `packages/api-client` must not contain business logic.
- `packages/permissions` must not import from any app.
- Apps must not import directly from other apps.

**Python rules:**
- `apps/api` modules never import from each other's internal code (modules use public contracts and domain events only).
- `apps/worker` imports shared Python packages and public module contracts.
- `python/core` must not import from any specific module.
- `python/domain_events` has no module-specific imports.

## 1.5 Prohibited Patterns

- No app imports from another app's source tree.
- No Python module imports another module's SQLAlchemy models, private service classes, or internal helpers.
- No frontend component imports business logic from `apps/api`.
- No `packages/permissions` importing from any module's implementation.
- No `packages/ui` importing API client code.
- No shared Python package importing module-specific domain types.

## 1.6 Naming Conventions

| Concern | Convention |
|---|---|
| Package names | `@platform/<name>` (e.g., `@platform/ui`, `@platform/contracts`) |
| Python internal packages | `platform_<name>` (e.g., `platform_core`, `platform_domain_events`) |
| Database migrations | `YYYYMMDDHHMMSS_<short_description>.sql` (chronological, Supabase CLI format) |
| Module directories (Python) | `apps/api/modules/<module_id>/` (e.g., `orders/`, `bookings/`) |
| Permission identifiers | `<resource>.<action>` — see Section 8 |
| Canonical module IDs | Exactly as Document 08: `offerings-catalog`, `orders`, `bookings`, etc. |
| Environment files | `.env.local` (development), `.env.test` (test), never committed with real secrets |


---

# 2. Runtime Application Boundaries

## 2.1 `apps/web` — Main Platform + Consumer Surface

**Technology:** Next.js App Router (TypeScript). **Deployment:** Edge-capable SSR/ISR.

**Responsibilities:**
- Platform marketing website (PLT-001 through PLT-010)
- Authentication entry (AUTH-001 through AUTH-003) — shared Supabase Auth flows
- Marketplace search, results, Business Profiles, Offering handoff (MKT-001, MKT-002, MKT-004, MKT-005 basic, MKT-007, MKT-008)
- Dynamic Business Website rendering — `/{business-slug}/*` routes
- My Activity (ACC-001 through ACC-005, ACC-007, ACC-008, ACC-011)
- Consumer transaction flows: cart, checkout, order confirmation, booking confirmation, membership enrolment
- Guest paths and Destination Intent preservation

**Routing namespace:** `/` (platform), `/search` (marketplace), `/{slug}/*` (business websites), `/activity/*` (my activity), `/auth/*` (authentication)

## 2.2 `apps/workspace` — Business Workspace

**Technology:** Next.js App Router (TypeScript). **Deployment:** Server-rendered, auth-required.

**Responsibilities:**
- Business Workspace shell and adaptive navigation (CORE-001 through CORE-016)
- Business Home dashboard / operational summary
- Website/content management, editing, preview, publish (WEB-001 through WEB-010, WEB-016)
- All module operational pages at First Launch depth (per Document 11 Section 4.2)
- Business settings, Locations, Team and Access, Module Management
- Notifications inbox
- Onboarding flows (ONB-001 through ONB-009)
- Commercial account / Entitlement recovery (COM-001 through COM-003, COM-006 through COM-009)

**Routing namespace:** `/b/{businessId}/*` — Business ID is the stable internal identifier, not the public slug.

## 2.3 `apps/admin` — Platform Super Admin

**Technology:** Next.js App Router (TypeScript). **Deployment:** Server-rendered, explicit admin auth required (separate elevated session).

**Responsibilities:**
- Platform operational dashboard
- Business inspection, support, and attributed correction (ADM-001 through ADM-005, ADM-007 through ADM-013, ADM-016 through ADM-019)
- Entitlement adjustment (attributed, governed by FL-DEC-021)
- Provider state inspection
- Webhook/job/dead-letter visibility
- Audit log access
- Health and observability dashboards

**Routing namespace:** `/admin/*` — entirely separate from workspace and consumer namespaces.

## 2.4 `apps/api` — FastAPI Modular-Monolith Backend

**Technology:** Python 3.12+, FastAPI, SQLAlchemy 2.x (async). **Deployment:** Container — single application process (can scale horizontally).

**Responsibilities:**
- All authoritative server-side business logic
- Context resolution and tenant authorization on every request
- Module API routers
- Provider adapter orchestration (payments, AI, email, SMS, storage)
- Webhook ingestion endpoints
- Internal scheduled/triggered coordination where synchronous

## 2.5 `apps/worker` — Async Job Processor

**Technology:** Python 3.12+, SQLAlchemy 2.x async/asyncpg, and a small platform-owned PostgreSQL-backed worker. **Deployment:** Container — one or more worker process instances.

**Responsibilities:**
- Transactional outbox event consumption and fan-out
- Asynchronous job execution: notifications, search indexing, projections, media processing, AI generation, and webhook processing
- Due scheduled-job materialization: membership renewal reminders and other explicitly registered schedules
- Dead-letter handling
- Retry with exponential backoff
- Lease expiry recovery and safe replay
- Worker health reporting

**Architecture:** PostgreSQL is the durable source of truth. The worker independently claims domain/outbox events, asynchronous jobs, and due schedules with `FOR UPDATE SKIP LOCKED`, short leases, and transactional state transitions. Multiple worker instances are safe. Redis is not required. For each handler, the worker invokes the relevant Python application service shared with `apps/api`; only the invocation entry point differs.

---

# 3. Shared Package Architecture

## 3.1 `packages/ui` — Design System

```
packages/ui/
+-- tokens/         <- design tokens: colors, typography, spacing, radii, shadows
+-- primitives/     <- headless/accessible base components (Radix UI foundation)
+-- components/     <- composed UI components built on primitives
|   +-- button/
|   +-- input/
|   +-- dialog/
|   +-- table/
|   +-- badge/
|   +-- card/
|   +-- ...
+-- layouts/        <- shared layout patterns (page shell, sidebar, header)
+-- icons/          <- icon set (Lucide or approved equivalent)
```

Rules: Components must be accessible (WCAG 2.1 AA minimum). Components must be responsive. No business logic inside UI components. All tokens must be CSS custom properties to allow theme overriding. Surface-specific compositions live in the consuming app, not in `packages/ui`.

## 3.2 `packages/contracts` — API Contracts

```
packages/contracts/
+-- api/            <- request/response types per domain
+-- events/         <- canonical domain event envelope types
+-- modules/        <- public module contract interfaces
```

Rules: Pure TypeScript types — no runtime logic. Generated from the FastAPI OpenAPI spec wherever possible to prevent drift.

## 3.3 `packages/permissions` — Canonical Permission Registry

```
packages/permissions/
+-- identifiers.ts  <- all canonical permission identifier string constants
+-- types.ts        <- TypeScript types: PermissionIdentifier, PermissionAction, etc.
+-- templates.ts    <- built-in template definitions (job function to permission set)
```

This is the single source of truth for permission string values. The Python backend must produce the identical string values (validated in contract tests). No business logic — only constants and types.

## 3.4 `packages/auth` — Auth Utilities

Contents: `@supabase/ssr` browser and server client factories, cookie adapters, session-refresh Proxy utilities, access-token forwarding helpers, auth display state, and Destination Intent redirects.

```
packages/auth/
+-- browser.ts          <- createBrowserClient(url, publishableKey)
+-- server.ts           <- request-scoped createServerClient with cookie getAll/setAll
+-- proxy.ts            <- getClaims-based session refresh and response cookie/header propagation
+-- access-token.ts     <- token retrieval for forwarding to FastAPI; never authorization
+-- redirects.ts        <- Destination Intent validation and auth redirects
+-- context.tsx         <- client display state only
```

Rules: Use `@supabase/supabase-js` with `@supabase/ssr`; do not use deprecated Next.js auth-helper packages. Create a new server client per request and use the browser client only in browser code. No Business authorization logic belongs here. Next.js authentication state may determine signed-in presentation, but FastAPI independently verifies the access token and authoritatively derives Business, Location, membership, permission, Entitlement, module, and resource context.

---

# 4. Backend Modular-Monolith Architecture

## 4.1 Directory Structure

```
apps/api/
+-- main.py                  <- FastAPI application factory, router registration, lifespan
+-- dependencies.py          <- shared FastAPI dependency providers
+-- middleware/
|   +-- auth.py              <- JWT verification, identity extraction
|   +-- context.py           <- request context resolution
|   +-- correlation.py       <- correlation ID injection
|
+-- platform_core/           <- Platform Core groups (not optional modules)
|   +-- identity/            <- svc-identity-auth, PlatformIdentity management
|   +-- business/            <- core-business-identity, Business lifecycle
|   +-- profile/             <- core-business-profile, BusinessProfile management
|   +-- locations/           <- core-locations, Location CRUD and switching
|   +-- team/                <- core-team-access, membership, roles, templates, invitations
|   +-- settings/            <- core-settings, Business-wide configuration
|   +-- website/             <- core-website, structured website model and rendering
|   +-- workspace/           <- core-workspace, aggregate loading, navigation assembly
|   +-- notifications/       <- core-notifications, in-platform notification inbox
|   +-- marketplace/         <- core-marketplace-presence, Business indexing projection
|
+-- modules/                 <- optional Business modules
|   +-- offerings_catalog/
|   +-- orders/
|   +-- bookings/
|   +-- payments/
|   +-- memberships/
|   +-- customer_relationships/
|   +-- leads/
|   +-- inventory/
|   +-- fulfilment/
|   +-- workforce/
|
+-- services/                <- shared platform services
|   +-- entitlement/         <- svc-entitlement-billing
|   +-- capability/          <- svc-capability-evaluation
|   +-- ai_runtime/          <- svc-ai-runtime
|   +-- search/              <- svc-search-discovery
|   +-- media/               <- svc-media
|   +-- realtime/            <- svc-realtime
|   +-- communication/       <- svc-communication-delivery
|   +-- payment_providers/   <- svc-payment-providers adapter
|   +-- statistics/          <- svc-statistics-trust
|
+-- events/                  <- domain event definitions and outbox publisher
|   +-- definitions/         <- canonical event type definitions per domain
|   +-- outbox.py            <- transactional outbox publisher
|
+-- webhooks/                <- inbound webhook ingestion routers
    +-- payment/
    +-- ...
```

## 4.2 Module Internal Layering

Each module follows a consistent internal structure:

```
modules/orders/
+-- domain/
|   +-- entities.py          <- Order, OrderLineItem, OrderStatus (pure domain objects)
|   +-- value_objects.py     <- PriceSnapshot, LineItemSnapshot, etc.
|   +-- events.py            <- OrderCreated, OrderConfirmed, OrderCancelled definitions
|
+-- application/
|   +-- commands.py          <- CreateOrder, ConfirmOrder, CancelOrder
|   +-- queries.py           <- GetOrder, ListOrders, GetOrderSummary
|   +-- services.py          <- OrderApplicationService (use cases)
|
+-- infrastructure/
|   +-- models.py            <- SQLAlchemy ORM models for orders_* tables
|   +-- repository.py        <- OrderRepository (database access)
|
+-- api/
|   +-- router.py            <- FastAPI router
|   +-- schemas.py           <- Pydantic request/response DTOs
|   +-- dependencies.py      <- Module-specific FastAPI dependencies
|
+-- contracts/
|   +-- public.py            <- Public service interface (what other modules may call)
|   +-- events.py            <- Event subscription handlers (idempotent)
|
+-- __init__.py              <- module registration, router export
```

## 4.3 Cross-Module Communication Rules

**When an immediate result is needed (synchronous):**

```python
# CORRECT: orders calls the offerings public contract
offering_summary = await offerings_catalog_contract.get_offering_summary(
    offering_id=line_item.offering_id,
    business_id=context.business_id
)

# INCORRECT: orders imports offerings internal model
from modules.offerings_catalog.infrastructure.models import OfferingModel  # BANNED
```

**When a reaction is needed (asynchronous):**

```python
# CORRECT: orders emits an event; fulfilment subscribes
await outbox.publish(
    OrderFulfilmentRequested(
        order_id=order.id,
        business_id=order.business_id,
        fulfilment_mode=order.fulfilment_mode,
    ),
    session=session  # same transaction as the order state mutation
)

# INCORRECT: orders writes directly to fulfilment table
session.add(FulfilmentJobModel(...))  # BANNED
```

## 4.4 Key Cross-Module Contract Examples

**Orders to Offerings:**
```python
class OfferingsCatalogContract:
    async def get_offering_summary(
        self, offering_id: UUID, business_id: UUID
    ) -> OfferingSummary: ...
    # Returns price, title, type, location availability snapshot
    # NEVER returns raw ORM row; returns DTO only
```

**Bookings to Workforce:**
```python
class WorkforceContract:
    async def get_provider_availability(
        self, provider_id: UUID, business_id: UUID, location_id: UUID,
        date_range: DateRange, service_ids: list[UUID]
    ) -> ProviderAvailabilitySlots: ...
```

**Bookings to Payments:**
```python
class PaymentsContract:
    async def initiate_payment(
        self, payable_type: str, payable_id: UUID, business_id: UUID,
        amount: Money, method: PaymentMethod
    ) -> PaymentInitiation: ...
```

**Customer Relationships event subscription:**
```python
class CustomerRelationshipsEventHandlers:
    async def on_order_created(self, event: OrderCreated) -> None:
        # idempotent: create or update CustomerContact projection
        # writes only to customer_relationships tables

    async def on_booking_confirmed(self, event: BookingConfirmed) -> None:
        # idempotent: add interaction to customer timeline
```

## 4.5 Request Context Object

```python
@dataclass
class RequestContext:
    identity_id: UUID
    active_context: OperatingContext        # PERSONAL / BUSINESS / ADMIN
    business_id: UUID | None
    location_id: UUID | None
    membership: BusinessMembership | None
    effective_permissions: frozenset[str]   # canonical permission identifiers
    effective_entitlements: EntitlementSet
    module_states: dict[str, ModuleState]
    is_super_admin: bool
    correlation_id: str
```

The context is resolved once per request by `middleware/context.py` after JWT verification. It is injected into application services — never rebuilt inside business logic.

## 4.6 Transaction Boundaries

A database transaction spans one domain operation. The outbox event must be written in the same transaction as the domain state mutation:

```python
async def create_order(self, command: CreateOrder, ctx: RequestContext) -> Order:
    async with self.db.begin() as session:
        # 1. Validate (no writes)
        offering = await self.offerings_contract.get_offering_summary(...)

        # 2. Domain mutation
        order = Order.create(...)
        session.add(order_model)

        # 3. Outbox event in SAME transaction
        await self.outbox.publish(OrderCreated(...), session=session)

        # commit: both order and outbox event commit atomically
    return order
```


---

# 5. Database and Schema Implementation

## 5.1 Database Choice

**PostgreSQL via Supabase managed infrastructure.** Supabase provides the PostgreSQL instance, Supabase Auth, Supabase Storage, and the RLS execution environment. FastAPI is the authoritative application backend.

## 5.2 Schema Strategy

Use **one PostgreSQL schema (`public`)** initially, with table naming conventions that encode module ownership. Module ownership is enforced by application-layer rules and code review.

## 5.3 Table Naming Convention

```
<module_id_snake>_<entity_name>

Examples:
  platform_identities              <- Platform Core: identity
  business_memberships             <- Platform Core: team
  businesses                       <- Platform Core: business identity
  business_locations               <- Platform Core: locations
  business_module_states           <- Platform Core: module management
  commercial_entitlements          <- Platform Core: entitlement
  website_pages                    <- Platform Core: website
  website_sections                 <- Platform Core: website
  offerings_catalog_offerings      <- Module: offerings-catalog
  orders_orders                    <- Module: orders
  orders_order_line_items          <- Module: orders
  bookings_bookings                <- Module: bookings
  payments_payment_attempts        <- Module: payments
  memberships_plans                <- Module: memberships
  memberships_enrolments           <- Module: memberships
  customer_relationships_contacts  <- Module: customer-relationships
  leads_leads                      <- Module: leads
  inventory_records                <- Module: inventory
  fulfilment_jobs                  <- Module: fulfilment
  workforce_providers              <- Module: workforce
  platform_audit_events            <- Platform-scoped audit
  platform_outbox_events           <- Platform-scoped outbox (domain events)
  platform_async_jobs              <- Platform-scoped async job queue
  platform_scheduled_jobs          <- Platform-scoped scheduled job registry
  platform_processed_events        <- Platform-scoped handler idempotency ledger
  platform_dead_letter_events      <- Platform-scoped dead-letter store
```

## 5.4 ID Strategy

- **Canonical identifier format:** UUIDv4 stored as PostgreSQL `uuid`.
- **Database entity primary keys:** Database-generated with PostgreSQL's standard `gen_random_uuid()` default.
- **Application-created envelope IDs:** Python `uuid.uuid4()` or browser `crypto.randomUUID()` when an identifier must exist before persistence, including correlation, causation, event, and client idempotency IDs.
- **External-facing IDs:** UUIDv4 only. No sequential integers are exposed.
- **Foreign keys:** PostgreSQL `uuid` columns referencing canonical UUID primary keys.
- **Ordering:** Never infer chronology from UUID values. Use explicit timestamps plus ID as a deterministic tie-breaker.
- **Rationale:** UUIDv4 is natively supported by PostgreSQL/Supabase and every application runtime. It avoids custom extensions, fictional `gen_ulid()` functions, and an additional identifier library. Sortable IDs do not justify that infrastructure at First Launch.

## 5.5 Standard Column Conventions

Every Business-scoped table must include:

```sql
id             uuid          PRIMARY KEY DEFAULT gen_random_uuid(),
business_id    uuid          NOT NULL REFERENCES businesses(id),
created_at     timestamptz   NOT NULL DEFAULT now(),
updated_at     timestamptz   NOT NULL DEFAULT now(),
deleted_at     timestamptz   NULL,       -- soft deletion; NULL = active
version        integer       NOT NULL DEFAULT 1  -- optimistic concurrency where needed
```

Every Location-scoped table adds:

```sql
location_id    uuid          NOT NULL REFERENCES business_locations(id)
```

## 5.6 Timestamps

All timestamps are `timestamptz` (UTC stored, timezone-aware). Business hours, booking times, and consumer-facing times are stored in UTC and converted to the relevant Location timezone at presentation. `updated_at` is maintained by a PostgreSQL trigger on every Business-scoped table.

## 5.7 Status and State Columns

- **Status fields:** `text` with `CHECK` constraints against an explicit allowed set, not PostgreSQL `ENUM` types.
- **Rationale:** Adding a new status value to an ENUM requires a table rewrite in some PostgreSQL versions. TEXT + CHECK is simpler for schema evolution.
- **Pattern:** `status text NOT NULL CHECK (status IN ('pending', 'confirmed', 'cancelled', 'completed'))`

## 5.8 JSONB Rules

JSONB is permitted for: module configuration (validated at write time), Website section content (validated against SectionType schema), provider adapter metadata, Business settings overrides, BusinessTypeProfile recommendation configuration, audit event before/after snapshots.

JSONB is **prohibited** for: replacing normalized relational entities, cross-module data sharing, queryable Business operational data (normalize it), generic entity tables with type discriminators.

## 5.9 Index Strategy

Required GIN indexes for full-text search:

```sql
CREATE INDEX idx_marketplace_businesses_search
    ON marketplace_business_projections USING GIN(search_vector);

CREATE INDEX idx_marketplace_offerings_search
    ON marketplace_offering_projections USING GIN(search_vector);
```

Required B-tree indexes:

```sql
CREATE INDEX idx_<table>_business_id ON <table>(business_id);
CREATE INDEX idx_<table>_active ON <table>(business_id) WHERE deleted_at IS NULL;
CREATE INDEX idx_outbox_status_created ON platform_outbox_events(status, created_at)
    WHERE status = 'pending';
CREATE INDEX idx_bookings_location_time ON bookings_bookings(location_id, starts_at, ends_at)
    WHERE deleted_at IS NULL AND status NOT IN ('cancelled');
```

## 5.10 Foreign Key Rules

- Foreign keys reference canonical entity IDs within the same module.
- **Cross-module references** use UUID columns with descriptive names but no database foreign key constraint (enforced at application layer). This preserves module independence.
- Exception: Platform Core cross-references (e.g., `business_id` on every table) use real FK constraints because Business is the tenant root.

## 5.11 Soft Deletion

Business-owned entities use soft deletion: `deleted_at timestamptz NULL`. `deleted_at IS NULL` predicates must be present in all active-record queries. Module deactivation never hard-deletes Business data.

## 5.12 Optimistic Concurrency

Use `version integer NOT NULL DEFAULT 1` on entities where concurrent modification must be prevented. Apply to: Order, Booking, Membership, Inventory stock levels, WebsiteVersion, BusinessModuleState.

## 5.13 Projection Tables

```sql
-- Marketplace search projection (owned by core-marketplace-presence)
marketplace_business_projections (
    business_id uuid PRIMARY KEY,
    slug text NOT NULL,
    display_name text NOT NULL,
    description text,
    primary_location_id uuid,
    search_vector tsvector,
    indexed_at timestamptz,
    ...
)

-- Consumer activity projection
consumer_activity_projections (
    id uuid PRIMARY KEY,
    identity_id uuid NOT NULL,
    business_id uuid NOT NULL,
    activity_type text NOT NULL,
    resource_type text NOT NULL,
    resource_id uuid NOT NULL,
    occurred_at timestamptz NOT NULL,
    summary jsonb,
    ...
)
```

## 5.14 Migration Strategy

**Tooling:** Supabase CLI migrations. Migration files in `infra/supabase/migrations/`.

**Naming:** `YYYYMMDDHHMMSS_<short_description>.sql`

**Ownership:** Each module owns its migration files. Platform Core migrations precede module migrations in chronological order. Module migration files must not reference another module's tables in FKs.

**Forward-only policy:** All production migrations are forward-only. No rollback SQL in production migration files. Rollback is a code redeploy, not a schema rollback.

**Destructive change policy:** Never drop a column without a two-migration strategy. Never rename a column in place. Destructive migrations require an explicit data retention note.

**Seed files in `infra/supabase/seed/`:**
- `00_platform.sql` — module registry, roles, section types, business type profiles
- `01_plans.sql` — development/test commercial Plan seeds
- `02_reference_fixtures.sql` — 11 reference business fixtures for testing only
- Production seeds contain only real platform configuration; no test data or development grants.

---

# 6. Authentication, Identity, Session, Tenancy, and Context

## 6.1 Auth Technology Decision

**Supabase Auth** for: User signup, login, session tokens (JWTs), email verification, password reset, OAuth.

**FastAPI** for: All business logic authorization decisions, server-side context resolution (Business, Location, membership, permissions, Entitlements), JWT verification via Supabase's JWKS endpoint.

**Important rules:**
- Supabase direct client never performs business authorization.
- RLS is a defense backstop only. Application authorization is always the primary mechanism.
- Supabase service-role key is server-only, never in frontend bundles.

## 6.2 Platform Identity Model

```sql
platform_identities (
    id               uuid PRIMARY KEY,   -- mirrors Supabase auth.users.id
    supabase_user_id uuid UNIQUE NOT NULL,
    display_name     text,
    avatar_asset_id  uuid,
    phone_verified   boolean NOT NULL DEFAULT false,
    email_verified   boolean NOT NULL DEFAULT false,
    created_at       timestamptz NOT NULL DEFAULT now(),
    updated_at       timestamptz NOT NULL DEFAULT now()
)

consumer_profiles (
    id               uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    identity_id      uuid UNIQUE NOT NULL REFERENCES platform_identities(id),
    preferences      jsonb,
    created_at       timestamptz NOT NULL DEFAULT now(),
    updated_at       timestamptz NOT NULL DEFAULT now()
)

platform_admin_grants (
    id               uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    identity_id      uuid NOT NULL REFERENCES platform_identities(id),
    granted_at       timestamptz NOT NULL,
    granted_by       uuid NOT NULL REFERENCES platform_identities(id),
    revoked_at       timestamptz,
    reason           text NOT NULL,
    is_active        boolean GENERATED ALWAYS AS (revoked_at IS NULL) STORED
)
```

## 6.3 Frontend Authentication Flow

Authentication uses the current Supabase SSR pattern for Next.js (`@supabase/ssr` + `@supabase/supabase-js`). Deprecated `@supabase/auth-helpers-*` packages are not used.

1. User visits app (`apps/web` or `apps/workspace`)
2. Next.js Proxy/middleware refreshes the cookie-backed Supabase session via a request-scoped `createServerClient` and `getClaims()` / `getUser()`
3. If no session: redirect to `/auth/sign-in` with Destination Intent in query param
4. Sign in / Sign up: Supabase Auth issues a session; `@supabase/ssr` persists it in HTTP-only cookies through `setAll` cookie adapters
5. Server Components and Server Actions read the session through `packages/auth/server.ts`; Client Components use `packages/auth/browser.ts`
6. Frontend forwards the Supabase access token to FastAPI in the `Authorization: Bearer <token>` header via `packages/auth/access-token.ts`
7. FastAPI independently verifies the JWT via Supabase JWKS, re-derives authoritative application context, and serves the response

Next.js session state is presentation and routing convenience only. Business permissions, Entitlements, module state, and tenant scope are never inferred from frontend auth state.

## 6.4 Backend Context Resolution Chain

```python
async def resolve_request_context(request: Request) -> RequestContext:
    # Step 1: Verify JWT
    jwt_payload = await verify_supabase_jwt(request.headers.get("Authorization"))
    if not jwt_payload:
        raise AuthenticationRequired()

    # Step 2: Map to Platform Identity
    identity = await identity_repo.get_by_supabase_id(jwt_payload["sub"])
    if not identity:
        raise IdentityNotFound()

    # Step 3: Resolve Operating Context
    operating_context = resolve_operating_context(request, identity)

    # Step 4 (Business context only): Validate Business membership
    if operating_context.is_business:
        business = await business_repo.get(operating_context.business_id)
        if not business or business.deleted_at:
            raise BusinessNotFound()

        membership = await membership_repo.get_active(
            identity_id=identity.id,
            business_id=operating_context.business_id
        )
        if not membership:
            raise MembershipRequired()

        # Step 5: Resolve Location scope
        location_id = resolve_location_context(request, membership)
        if location_id and not membership.allows_location(location_id):
            raise LocationAccessDenied()

        # Step 6: Resolve effective permissions
        effective_permissions = permission_service.resolve(membership)

        # Step 7: Resolve Entitlements
        entitlements = await entitlement_service.get_effective(operating_context.business_id)

        # Step 8: Resolve Module states
        module_states = await module_registry.get_states(operating_context.business_id)

    # Step 9: Super Admin elevation
    is_super_admin = await admin_grant_repo.is_active(identity.id)

    return RequestContext(
        identity_id=identity.id,
        active_context=operating_context.type,
        business_id=operating_context.business_id,
        location_id=location_id,
        membership=membership,
        effective_permissions=effective_permissions,
        effective_entitlements=entitlements,
        module_states=module_states,
        is_super_admin=is_super_admin,
        correlation_id=request.headers.get("X-Correlation-Id") or str(uuid4())
    )
```

**What must be re-derived server-side (never trusted from client):**
Membership status, effective permissions, Entitlement state, module activation state, whether Business ID belongs to authenticated identity, Location scope authorization, Super Admin status.

## 6.5 Guest Paths

Guest paths are limited to: Public Business Website browsing, Marketplace search/profile viewing, Session-scoped cart, Guest checkout (order created with email/phone only), Booking initiation (where allowed), Lead/enquiry submission.

Guest-to-authenticated linking: only through verified identifier matching (phone or email verification). No weak matching.

## 6.6 Destination Intent

```
Consumer attempts: /coffee-garden/order/booking-123
-> Not authenticated -> redirect to /auth/sign-in?destination=/coffee-garden/order/booking-123
-> Sign in / sign up
-> Redirect to intended destination
-> Re-evaluate authorization at the destination (not from the redirect)
```

The destination URL is validated before redirect — only platform-owned domains and paths are permitted.

---

# 7. RLS and Tenant Isolation

## 7.1 RLS Policy Categories

| Table category | RLS behavior |
|---|---|
| Business-scoped (e.g., orders, bookings) | `business_id = current_business_id()` |
| Location-scoped (e.g., inventory) | `business_id = current_business_id()` (location scope enforced application-side first) |
| Platform-global read (e.g., module_definitions) | Read for all authenticated users; write only by privileged service role |
| Consumer-scoped (e.g., consumer_activity_projections) | `identity_id = auth.uid()` |
| Public read (e.g., marketplace projections) | Anonymous read on explicitly discoverable records only |

## 7.2 RLS Session Context Functions

```sql
SELECT set_config('app.current_business_id', $1::text, true);
SELECT set_config('app.current_identity_id', $2::text, true);

CREATE OR REPLACE FUNCTION current_business_id() RETURNS uuid AS $$
    SELECT current_setting('app.current_business_id', true)::uuid;
$$ LANGUAGE sql STABLE;
```

The FastAPI DB session factory sets these config values after context resolution.

## 7.3 Service-Role / Privileged Access Rules

1. Service-role connection is used only for: migrations, seeding, admin correction tools, outbox/worker background jobs, platform projections.
2. Every service-role query touching Business-scoped data must include explicit `WHERE business_id = $authorized_business_id` predicate.
3. Service-role credential is never exposed in frontend bundles, committed environment files, or AI tool inputs.

## 7.4 FastAPI DB Connection Strategy

- **User-scoped requests:** Connection pool that sets session variables at connection checkout. RLS policies apply.
- **Worker/background jobs:** Privileged connection pool (service role). RLS does NOT apply. Business scope must be explicitly enforced via application-level predicates.

## 7.5 Required Automated Isolation Tests

```python
async def test_business_a_cannot_read_business_b_orders(): ...
async def test_location_scoped_member_cannot_access_unauthorized_location(): ...
async def test_consumer_cannot_access_workspace_data(): ...
async def test_ordinary_member_cannot_access_admin_endpoints(): ...
async def test_super_admin_action_is_attributed(): ...
async def test_direct_db_business_isolation(): ...
```

These tests are mandatory before any stage exit gate.


---

# 8. Permission and Entitlement Implementation

## 8.1 Canonical Permission Identifier Grammar

```
<resource>.<action>
```

Grammar rules: lowercase, dot-separated, no spaces or hyphens. Resource names match canonical domain terms. Actions: `read`, `create`, `update`, `delete`, `cancel`, `refund`, `publish`, `manage`, `invite`, `configure`, `export`, and domain-specific verbs where needed.

Module resource prefix convention: Core resources use no prefix (e.g., `locations.read`, `team.invite`). Module resources use a module-derived prefix (e.g., `orders.create`, `bookings.cancel`, `payments.refund`).

## 8.2 First Launch Permission Catalogue

```
# Platform Core
business.read          business.update        business.publish       business.close
locations.read         locations.create       locations.update       locations.delete
team.read              team.invite            team.update_role       team.remove
team.manage_templates
settings.read          settings.update
website.read           website.edit           website.publish        website.unpublish
modules.read           modules.enable         modules.configure      modules.deactivate
notifications.read     notifications.manage_preferences
marketplace.read       marketplace.configure

# Module: offerings-catalog
offerings.read         offerings.create       offerings.update
offerings.archive      offerings.manage_availability

# Module: orders
orders.read            orders.create          orders.update_status
orders.cancel          orders.refund_coordinate

# Module: bookings
bookings.read          bookings.create        bookings.update
bookings.cancel        bookings.manage_availability

# Module: payments
payments.read          payments.refund        payments.manage_connection    payments.export

# Module: memberships
memberships.read       memberships.create_plan       memberships.update_plan
memberships.manage_enrolment                         memberships.cancel_enrolment

# Module: customer-relationships
customers.read         customers.update       customers.manage_notes    customers.export

# Module: leads
leads.read             leads.create           leads.update_status
leads.assign           leads.delete

# Module: inventory
inventory.read         inventory.adjust       inventory.export

# Module: fulfilment
fulfilment.read        fulfilment.update_status    fulfilment.manage_config

# Module: workforce
workforce.read         workforce.create       workforce.update
workforce.manage_availability                 workforce.deactivate

# Sensitive / Owner operations
commercial.read        commercial.manage
```

## 8.3 Built-in Permission Templates (First Launch)

| Template ID | Job function | Included permissions |
|---|---|---|
| `tmpl_store_manager` | Store / operations manager | Full orders.*, bookings.*, customers.*, leads.*, inventory.*, fulfilment.*, offerings.read, workforce.read, website.read |
| `tmpl_cashier` | Cashier / checkout | orders.read, orders.update_status, payments.read |
| `tmpl_content_editor` | Content / marketing | offerings.*, website.edit, website.read, marketplace.read |
| `tmpl_inventory_manager` | Inventory / stock | inventory.*, offerings.read |
| `tmpl_booking_coordinator` | Reception / bookings | bookings.*, customers.read, workforce.read, notifications.read |
| `tmpl_workforce_manager` | Staff / workforce | workforce.*, bookings.read, locations.read |
| `tmpl_lead_handler` | Sales / enquiry | leads.*, customers.read, offerings.read |

**Template rules:** Templates are convenience only. They do not grant authority — explicit grants do. When a Manager assigns a template, they may only assign permissions they themselves hold. Custom template authoring UI (CORE-012) is Later.

## 8.4 Primary Owner Invariants

The following are Primary Owner-only and cannot be delegated: `business.close`, `commercial.manage` (unless FL-DEC-021 permits), ownership transfer. Super Admin cannot silently act as Primary Owner.

## 8.5 Manager Delegation Ceiling

```
Manager may grant any permission they themselves hold.
Manager may NOT grant permissions beyond their own effective set.
Manager may NOT create another Manager with broader permissions than their own.
Manager may NOT assign a template that contains permissions they do not hold.
```

Enforced server-side:
```python
async def assign_permissions(self, target_membership_id, permission_set, ctx):
    if not ctx.is_primary_owner:
        excess = permission_set - ctx.effective_permissions
        if excess:
            raise PermissionDelegationError(f"Cannot grant permissions not held: {excess}")
```

## 8.6 Permission Persistence

```sql
business_membership_permission_grants (
    id               uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    business_id      uuid NOT NULL REFERENCES businesses(id),
    membership_id    uuid NOT NULL REFERENCES business_memberships(id),
    permission       text NOT NULL,
    location_ids     uuid[],          -- NULL = all allowed locations
    granted_by       uuid NOT NULL REFERENCES platform_identities(id),
    granted_at       timestamptz NOT NULL DEFAULT now()
)

business_membership_applied_templates (
    id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    membership_id   uuid NOT NULL REFERENCES business_memberships(id),
    template_id     text NOT NULL,
    applied_at      timestamptz NOT NULL,
    applied_by      uuid NOT NULL REFERENCES platform_identities(id),
    customized      boolean NOT NULL DEFAULT false
)
```

## 8.7 Permission Caching and Invalidation

Cache effective permission set per membership_id for up to 5 minutes. Cache key: `perms:{membership_id}`. Invalidate immediately on any grant/revoke mutation, membership status change, or location scope change. Authorization revocations must invalidate the cache as part of the same transaction.

## 8.8 Server-Side Permission Check Helper

```python
def require_permission(permission: str):
    async def check(ctx: RequestContext = Depends(get_request_context)) -> RequestContext:
        if permission not in ctx.effective_permissions:
            raise PermissionDenied(permission)
        return ctx
    return check

def require_entitlement(module_id: str):
    async def check(ctx: RequestContext = Depends(get_request_context)) -> RequestContext:
        if not ctx.effective_entitlements.is_entitled(module_id):
            raise EntitlementRequired(module_id)
        return ctx
    return check

@router.post("/orders")
async def create_order(
    body: CreateOrderRequest,
    ctx: RequestContext = Depends(require_permission("orders.create")),
    _ent: RequestContext = Depends(require_entitlement("orders"))
):
    ...
```

## 8.9 Canonical Capability Evaluation Chain

```
Request arrives
-> [1] Identity verified (JWT valid, Platform Identity exists)
-> [2] Active context resolved (Personal / Business / Admin)
-> [3] Business exists and is not deleted/closed
-> [4] Membership is active (not pending, suspended, or removed)
-> [5] Location scope: requested location within membership scope
-> [6] Commercial Entitlement: Business entitled to this module/capability
-> [7] Module state: module is enabled + configured + applicable + healthy
-> [8] Permission: membership has the required permission identifier
-> [9] Resource/workflow state: the specific resource permits this action now
-> Allow
```

Each failed gate returns a distinct error code (see Section 10.6). Entitlement does not equal Permission at any point. Passing gate 6 does not imply gate 8.

---

# 9. Module Lifecycle Implementation

## 9.1 Module Lifecycle State Machine

```
ModuleDefinition (registry, status: available)
    |
    | Business gains Entitlement
    v
entitled
    |
    | Primary Owner / Manager explicitly enables
    v
enabled
    |
    | if configuration required
    v
configuring <----- reconfigure
    |
    | configuration valid and complete
    v
ready
    |
    | activation (first use or explicit)
    v
active <---------- re-enable after deactivation
    |
    +-- Deactivate -> deactivated -> (Re-enable) --------+
    |                                                     |
    +-- Entitlement lost -> entitlement_suspended --------+
                            |
                            | Entitlement restored -> active
```

## 9.2 BusinessModuleState Table

```sql
business_module_states (
    id                   uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    business_id          uuid NOT NULL REFERENCES businesses(id),
    module_id            text NOT NULL,
    activation_state     text NOT NULL CHECK (activation_state IN (
                             'not_enabled', 'enabled', 'configuring', 'ready',
                             'active', 'deactivated', 'entitlement_suspended', 'degraded'
                         )),
    configuration        jsonb,
    enabled_at           timestamptz,
    activated_at         timestamptz,
    deactivated_at       timestamptz,
    deactivated_reason   text,
    created_at           timestamptz NOT NULL DEFAULT now(),
    updated_at           timestamptz NOT NULL DEFAULT now(),
    UNIQUE (business_id, module_id)
)
```

## 9.3 Key Lifecycle Rules

- **Enable:** Entitlement check + dependency satisfaction check + not already enabled.
- **Configure:** Validate configuration against module's configSchema; transition to 'ready'.
- **Deactivate:** Stops new operations. Does NOT delete Business data. Historical reads remain.
- **Entitlement suspension:** Called when commercial entitlement expires. Business data retained. Recovery path: renew/upgrade plan.

---

# 10. API Design

## 10.1 REST Conventions

REST is the default. No GraphQL, no RPC-first design.

## 10.2 Versioning

API version prefix: `/v1/`. Breaking changes require `/v2/`. First Launch uses only `/v1/`.

## 10.3 URL Conventions

```
/v1/b/{business_id}/orders                           <- Business-scoped
/v1/b/{business_id}/locations/{location_id}/inventory <- Location-scoped
/v1/platform/businesses                              <- Platform-scoped
/v1/me/orders                                        <- Consumer-scoped
/v1/public/{business_slug}/website                   <- Public
/v1/public/marketplace/search                        <- Public marketplace
/v1/admin/businesses/{business_id}                   <- Admin
/v1/webhooks/payments/{provider}                     <- Inbound webhooks
```

Rules: Business ID is always in the path for Business-scoped resources. Use plural nouns for collections. Use kebab-case for multi-word resources. No verb-based paths for CRUD. Action endpoints use sub-resource verbs: `POST /orders/{id}/cancel`.

## 10.4 Pagination

Cursor-based pagination for all list endpoints. The opaque cursor encodes the ordered tuple `(created_at, id)` (or another endpoint-specific stable sort field plus `id`). UUIDv4 values are tie-breakers, not chronological keys. Default page size: 25. Maximum: 100.

```json
{
  "data": [...],
  "pagination": { "cursor": "eyJjcmVhdGVkX2F0IjoiMjAyNi0wNy0xMlQwODowMDowMFoiLCJpZCI6IjU1MGU4NDAwLWUyOWItNDFkNC1hNzE2LTQ0NjY1NTQ0MDAwMCJ9", "has_more": true, "total": null }
}
```

## 10.5 Standard Response Envelope

Success: `{ "data": {...}, "meta": {"correlation_id": "..."} }`

Error: `{ "error": {"code": "PERMISSION_DENIED", "message": "...", "details": {...}}, "meta": {"correlation_id": "..."} }`

## 10.6 Machine-Readable Error Codes

| HTTP Status | Error Code | Meaning |
|---|---|---|
| 401 | `AUTHENTICATION_REQUIRED` | No valid JWT |
| 401 | `SESSION_EXPIRED` | JWT expired |
| 403 | `PERMISSION_DENIED` | Permission gate failed |
| 403 | `ENTITLEMENT_REQUIRED` | Commercial Entitlement gate failed |
| 403 | `MODULE_NOT_ACTIVE` | Module not enabled/configured |
| 403 | `LOCATION_ACCESS_DENIED` | Location scope gate failed |
| 403 | `MEMBERSHIP_REQUIRED` | No active Business membership |
| 404 | `RESOURCE_NOT_FOUND` | Resource does not exist or is not visible |
| 409 | `CONFLICT` | Optimistic lock failure, duplicate, or state conflict |
| 409 | `DUPLICATE_REQUEST` | Idempotency key already processed |
| 422 | `VALIDATION_ERROR` | Request body validation failed |
| 429 | `RATE_LIMITED` | Rate limit exceeded |
| 503 | `SERVICE_UNAVAILABLE` | Temporary system unavailability |

## 10.7 Idempotency Keys

Required for: order creation, payment initiation, booking creation, membership enrolment. Header: `Idempotency-Key: <client-generated-uuid-v4>`. Server stores key + response for 24 hours. Duplicate request returns the cached response without re-executing.

```sql
idempotency_records (
    id               uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    idempotency_key  text NOT NULL,
    business_id      uuid NOT NULL,
    endpoint         text NOT NULL,
    response_code    integer NOT NULL,
    response_body    jsonb NOT NULL,
    created_at       timestamptz NOT NULL DEFAULT now(),
    expires_at       timestamptz NOT NULL,
    UNIQUE (idempotency_key, business_id, endpoint)
)
```

## 10.8 Correlation IDs

Every request receives a UUIDv4 `correlation_id`. Accept a valid caller-provided UUID or generate one with `uuid4()`. All log entries include it. Outbox events and jobs preserve the originating `correlation_id`; derived events/jobs set `causation_id` to the identifier that caused them. Set `X-Correlation-Id` on every response.

## 10.9 Rate Limiting

| Endpoint class | Rate limit |
|---|---|
| Authentication (sign-in, sign-up) | 10 requests/minute per IP |
| Public API | 60 requests/minute per IP |
| Authenticated API | 300 requests/minute per identity |
| AI generation | 5 requests/minute per Business |
| Webhook ingestion | 1000/minute per provider |

## 10.10 Representative Endpoint Patterns

```
# Business
GET    /v1/b/{business_id}
PATCH  /v1/b/{business_id}
POST   /v1/b/{business_id}/publish

# Offerings
GET    /v1/b/{business_id}/offerings
POST   /v1/b/{business_id}/offerings
GET    /v1/b/{business_id}/offerings/{offering_id}
PATCH  /v1/b/{business_id}/offerings/{offering_id}
POST   /v1/b/{business_id}/offerings/{offering_id}/archive

# Website
GET    /v1/b/{business_id}/website
PUT    /v1/b/{business_id}/website/draft
POST   /v1/b/{business_id}/website/publish
GET    /v1/b/{business_id}/website/pages
POST   /v1/b/{business_id}/website/pages

# Orders (Idempotency-Key required on POST)
GET    /v1/b/{business_id}/orders
POST   /v1/b/{business_id}/orders
GET    /v1/b/{business_id}/orders/{order_id}
POST   /v1/b/{business_id}/orders/{order_id}/confirm
POST   /v1/b/{business_id}/orders/{order_id}/cancel
POST   /v1/b/{business_id}/orders/{order_id}/complete

# Bookings (Idempotency-Key required on POST)
GET    /v1/b/{business_id}/bookings
POST   /v1/b/{business_id}/bookings
GET    /v1/b/{business_id}/bookings/{booking_id}
POST   /v1/b/{business_id}/bookings/{booking_id}/confirm
POST   /v1/b/{business_id}/bookings/{booking_id}/cancel

# Availability
GET    /v1/b/{business_id}/availability?offering_id=&date=&location_id=

# Payments
GET    /v1/b/{business_id}/payments
POST   /v1/b/{business_id}/payments/{payment_id}/refund

# Memberships
GET    /v1/b/{business_id}/membership-plans
POST   /v1/b/{business_id}/membership-plans
GET    /v1/b/{business_id}/memberships

# Leads
GET    /v1/b/{business_id}/leads
POST   /v1/b/{business_id}/leads
POST   /v1/b/{business_id}/leads/{lead_id}/move-stage

# Consumer (My Activity)
GET    /v1/me/orders
GET    /v1/me/bookings
GET    /v1/me/memberships
GET    /v1/me/notifications
POST   /v1/me/notifications/mark-read
```


---

# 11. Dynamic Multi-Page Business Website Architecture

## 11.1 Core Data Model

```sql
websites (
    id                   uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    business_id          uuid UNIQUE NOT NULL REFERENCES businesses(id),
    published_version_id uuid REFERENCES website_versions(id),
    custom_domain        text,
    status               text NOT NULL DEFAULT 'draft'
        CHECK (status IN ('draft', 'published', 'unpublished')),
    created_at           timestamptz NOT NULL DEFAULT now(),
    updated_at           timestamptz NOT NULL DEFAULT now()
)

website_versions (
    id                   uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    website_id           uuid NOT NULL REFERENCES websites(id),
    business_id          uuid NOT NULL,
    version_type         text NOT NULL CHECK (version_type IN ('draft', 'published')),
    navigation           jsonb NOT NULL,
    theme                jsonb NOT NULL,
    generated_by         text,
    generation_job_id    uuid,
    published_at         timestamptz,
    created_at           timestamptz NOT NULL DEFAULT now(),
    updated_at           timestamptz NOT NULL DEFAULT now()
)

website_pages (
    id                   uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    website_version_id   uuid NOT NULL REFERENCES website_versions(id),
    business_id          uuid NOT NULL,
    slug                 text NOT NULL,
    title                text NOT NULL,
    page_type            text NOT NULL,
    seo_title            text,
    seo_description      text,
    og_image_asset_id    uuid,
    is_published         boolean NOT NULL DEFAULT true,
    sort_order           integer NOT NULL DEFAULT 0,
    created_at           timestamptz NOT NULL DEFAULT now(),
    updated_at           timestamptz NOT NULL DEFAULT now(),
    UNIQUE (website_version_id, slug)
)

website_sections (
    id                   uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    page_id              uuid NOT NULL REFERENCES website_pages(id),
    business_id          uuid NOT NULL,
    section_type_id      text NOT NULL,
    layout_variant       text,
    content              jsonb NOT NULL,
    module_binding       jsonb,
    sort_order           integer NOT NULL DEFAULT 0,
    is_visible           boolean NOT NULL DEFAULT true,
    created_at           timestamptz NOT NULL DEFAULT now(),
    updated_at           timestamptz NOT NULL DEFAULT now()
)

website_section_types (
    id                   text PRIMARY KEY,
    label                text NOT NULL,
    description          text,
    content_schema       jsonb NOT NULL,
    allowed_variants     text[] NOT NULL,
    contributing_module  text,
    requires_module      text,
    created_at           timestamptz NOT NULL DEFAULT now()
)
```

## 11.2 Route Strategy

| Route pattern | Application | Purpose |
|---|---|---|
| `/` | `apps/web` | Platform marketing home |
| `/search` | `apps/web` | Marketplace search |
| `/search/business/{slug}` | `apps/web` | Marketplace Business Profile |
| `/auth/*` | `apps/web` | Authentication flows |
| `/activity/*` | `apps/web` | My Activity (consumer) |
| `/{business-slug}` | `apps/web` | Business Website home |
| `/{business-slug}/{page-slug}` | `apps/web` | Business Website page |
| `/{business-slug}/checkout` | `apps/web` | Cart and checkout |
| `/{business-slug}/book` | `apps/web` | Booking flow |
| `/{business-slug}/join` | `apps/web` | Membership enrolment |
| `/{business-slug}/enquire` | `apps/web` | Lead/enquiry form |
| `/b/{businessId}/*` | `apps/workspace` | Business Workspace |
| `/admin/*` | `apps/admin` | Platform Admin |

**Reserved slugs (cannot be Business slugs):**
```
search, auth, activity, api, admin, static, _next, health, webhooks,
about, terms, privacy, help, support, blog, pricing, marketplace,
app, b, public, sitemap.xml, robots.txt
```

## 11.3 Route Resolution in `apps/web`

```
GET /{path-segment}/...

1. Check if path-segment is a reserved platform route -> serve platform route
2. Query businesses WHERE slug = path-segment AND deleted_at IS NULL
3. If no Business found -> 404
4. If Business found but not discoverable/active -> 404 (not leaked)
5. Load published WebsiteVersion for Business
6. Match path-segment[1] against page slugs in the published version
7. If no matching page -> 404
8. Render the page via SSR/ISR
```

## 11.4 Default Generated Pages

The AI generation and deterministic fallback produce an initial page set adapted to the Business. The page count is **not fixed**:

| Business type | Typical initial pages |
|---|---|
| Restaurant | Home, Menu, About, Contact, Reservations (if bookings enabled) |
| Retail shop | Home, Products, About, Contact |
| Salon/spa | Home, Services, Team, About, Contact, Book |
| Hotel/homestay | Home, Rooms, About, Contact, Reservations |
| Gym/studio | Home, Plans, Classes, About, Contact |
| Professional service | Home, Services, About, Contact, Enquire |
| Education centre | Home, Courses, About, Contact |

Terminology adapts to Business type configuration. A Business Website is a real multi-page structured site, not a profile page.

## 11.5 Draft / Published Version Lifecycle

```
AI generation job
-> creates website_version (version_type='draft')
-> creates pages + sections

Owner in Workspace
-> views draft preview (rendered from draft version, not public)
-> edits content/sections/navigation/theme
-> saves (updates draft records)

Owner clicks Publish
-> POST /v1/b/{business_id}/website/publish
-> server validates:
   - all required sections present
   - all required content fields filled
   - Business profile prerequisites met
-> transaction:
   - copy current draft version records to a new 'published' version
   - set websites.published_version_id = new published version
   - set websites.status = 'published'
   - emit WebsitePublished event
-> outbox event triggers:
   - ISR revalidation
   - Marketplace search index update
```

There is always one published version and one working draft. Editing the draft does not change the live site.

## 11.6 Preview Flow

```
Owner clicks Preview
-> GET /v1/b/{business_id}/website/preview-token (short-lived signed token, 10 min)
-> apps/web: GET /{slug}?preview_token=<token>
-> Render from draft version (not public)
-> No public caching of preview responses
```

> **Amendment — 2026-09-01 (Website Generation Overhaul work order; additive, dated per Document 08 §25.3).**
> The template-based preview additionally supports an **inline click-to-edit** layer
> (Document 09 CORE-005/006/007): click an image to replace it in place, double-click
> text to edit it inline. Both paths call the **existing** section content-update API
> with the same schema validation and content-safety checks as Workspace editing —
> this is additive UI over existing endpoints, not new backend surface. Any genuinely
> missing endpoint is flagged, not silently added.

## 11.7 SSR / ISR / Cache Strategy

| Content type | Rendering strategy |
|---|---|
| Business Website pages (published) | ISR with revalidation on WebsitePublished event (`revalidatePath`) |
| Marketplace search results | SSR (dynamic queries) |
| Business Marketplace Profile | ISR with revalidation on profile updates |
| Platform marketing pages | SSG (static generation at build) |
| Workspace (authenticated) | SSR, no public caching |
| Preview | SSR, no caching |

## 11.8 SEO and Sitemap

Each Business Website page gets: `<title>` from `seo_title` or `title + " | " + business_display_name`, `<meta name="description">` from `seo_description`, canonical URL, OG tags, OG image. Per-Business sitemap at `/{slug}/sitemap.xml`.

## 11.9 Module-Aware Page Composition

Sections with `module_binding` load data from the relevant module at render time through the module's public read contract. The renderer never queries module tables directly. If the bound module is not active, the section renders a placeholder.

---

# 12. AI-Assisted Website Generation

## 12.1 Production-Safe Generation Flow

```
1. Business completes essential onboarding data (name, type, location, offerings)
2. Owner triggers generation (or system auto-triggers)
3. Website Generation Job created (status: pending) and inserted into `platform_async_jobs` (`job_type = 'website.generate'`)

Worker picks up job:
-> [1] Load BusinessAggregate (read-only)
-> [2] Assemble generation prompt context
-> [3] Retrieve applicable SectionTypes and page schemas
-> [4] Call provider.generate_structured(prompt, WEBSITE_GENERATION_SCHEMA, model_config, timeout_seconds)
-> [5] Validate response against WebsiteGenerationSchema (strict JSON Schema)
-> [6] Policy validation (no arbitrary code, no external URLs, no excessive claims)
-> [7] On validation failure: deterministic template repair
-> [8] Save as website_version (version_type='draft', generated_by='ai_generation')
-> [9] Emit WebsiteDraftGenerated event

Failure handling:
-> AI provider timeout/failure -> retry (up to 3 attempts, exponential backoff)
-> Retries exhausted -> fall back to deterministic template generation
-> Deterministic fallback ALWAYS produces a valid draft
-> Never block Business creation because AI generation failed

Owner:
-> Previews draft in Workspace
-> Edits content/sections/theme as needed
-> Explicitly publishes (owner action required)
```

> **Amendment — 2026-09-01 (Website Generation Overhaul work order; additive, dated per Document 08 §25.3).**
> Step [4] above previously read `Call svc-ai-runtime.generate_website_draft(context, schemas)`.
> There is no `generate_website_draft` method and no `svc-ai-runtime` package. The
> implemented contract is `AIModelProvider.generate_structured(prompt, schema, model_config, timeout_seconds)`
> (§12.2), invoked once per Business by `platform_core/services/website_generation.py`
> with `WEBSITE_GENERATION_SCHEMA` and `model_config={"purpose": "website.generate"}`,
> three attempts with exponential backoff, then `build_deterministic_draft(...)`. The
> flow is otherwise unchanged. See §12.7 for why this is a single call, not a session.

## 12.2 Provider Abstraction

```python
# Implemented at: python/core/platform_core/website/ai_provider.py
class AIModelProvider(Protocol):
    async def generate_structured(
        self, prompt: str, schema: dict, model_config: dict, timeout_seconds: int
    ) -> dict: ...

# get_ai_provider() selects the concrete provider. Until FL-DEC-015 closes it
# returns UnavailableAIProvider() (callers fall back to build_deterministic_draft).
# The live Gemini provider activates on GEMINI_API_KEY presence; a second provider
# would be selected by an AI_PROVIDER env var when added.
```

> **Amendment — 2026-09-01 (Website Generation Overhaul work order; additive, dated per Document 08 §25.3).**
> The comment above previously read `Provider selection from config: AI_PROVIDER env var` /
> `Concrete: services/ai_runtime/providers/gemini.py, openai.py`. Those paths do not
> exist. The Protocol lives in `platform_core/website/ai_provider.py`; provider
> selection is `get_ai_provider()` in the same module. `AI_PROVIDER` is retained as
> the intended selector once more than one live provider exists, but is not read today.

## 12.3 Website Generation Schema (summary)

Generated output must be valid JSON matching WebsiteGenerationSchema:
- `pages`: array of page objects with `slug`, `title`, `page_type`, `sections`
- `navigation`: structured link tree
- `theme_hints`: design token suggestions

Each `section.content` is further validated against the specific `SectionType.content_schema`.

## 12.4 Generation Job Schema

```sql
website_generation_jobs (
    id               uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    business_id      uuid NOT NULL REFERENCES businesses(id),
    status           text NOT NULL DEFAULT 'pending'
        CHECK (status IN ('pending', 'running', 'completed', 'failed', 'fallback_used')),
    ai_provider      text,
    model_name       text,
    prompt_version   text NOT NULL,
    attempt_count    integer NOT NULL DEFAULT 0,
    error_detail     text,
    fallback_reason  text,
    result_version_id uuid REFERENCES website_versions(id),
    started_at       timestamptz,
    completed_at     timestamptz,
    created_at       timestamptz NOT NULL DEFAULT now()
)
```

## 12.5 Content Safety and Governance Rules

- No arbitrary HTML/JavaScript may be stored in section content.
- No external URLs may be stored as permanent content values.
- AI output is never directly written to `published_version` — only to `draft`.
- AI may not activate modules, grant permissions, or change commercial state.
- All AI generation jobs are logged with prompt version, provider, model, and outcome.
- Generation is subject to rate limiting (5 requests/minute/Business default).

## 12.6 AI Content-Authorship Boundary

> **Amendment — 2026-09-01 (Website Generation Overhaul work order; additive, dated per Document 08 §25.3). Decided now.**

AI authorship is confined to **content** within already-defined structure. It never authors platform mechanics.

| AI **may** author | AI **never** authors |
|---|---|
| Section copy (headlines, body, CTAs, SEO title/description) within each `SectionType.content_schema` | Cart, checkout, and payment flow behaviour |
| Choice of `layout_variant` from a SectionType's existing `allowed_variants` | Stock / availability display logic |
| Selection and ordering of sections from the 13 seeded `SectionType`s | Navigation structure semantics, route resolution, reserved-slug handling |
| Page set and navigation labels within `WEBSITE_GENERATION_SCHEMA` | Order/booking confirmation, tracking, and notification behaviour |
| `theme_hints` (token *suggestions* within the allowed design-token surface) | Module bindings' data contracts, permission gates, entitlement or commercial state |
| Image *selection* from Business-supplied or curated assets (by Asset ID) | New `SectionType`s, new layout variants, raw HTML/CSS/JS, external URLs as content |

Platform mechanics are fixed, tested code, identical for every Business, and are wired by the renderer and module contracts — not by generation output. This restates and sharpens §12.5, Document 10 §11.3/§11.4 (ARCH-008), and Document 11 §6.2: generation produces a **draft configuration**, and configuration cannot reach mechanics. A generation response containing anything in the right-hand column is a validation failure and is repaired deterministically, not published.

## 12.7 One-Shot Structured-Intake Generation Model

> **Amendment — 2026-09-01 (Website Generation Overhaul work order; additive, dated per Document 08 §25.3). This model was chosen now, deliberately.**

Generation is driven by a **structured questionnaire**, not a conversation. There is exactly **one** `generate_structured` call per Business per generation.

```
Structured questionnaire (business-type-aware, every field skippable)
  -> assemble only the answered fields into one prompt context
  -> ONE provider.generate_structured(prompt, WEBSITE_GENERATION_SCHEMA, model_config, timeout=30)
     (3 attempts, exponential backoff)
  -> validate -> map into Page / Section / navigation / theme records as a draft
  -> any skipped field: deterministic fallback fills it (build_deterministic_draft),
     never a second AI call
```

**Why this shape (recorded rationale):**

- **Cost is bounded and predictable** — one call per Business, no open-ended token spend from a chat loop.
- **Output is bounded and safe** — the model fills a strict JSON Schema once; it is never in a position to negotiate, re-scope, or be steered by end-user free text across turns.
- **Failure is simple** — one call either validates or falls back deterministically; there is no partial-conversation state to recover.

**Questionnaire rules:**

- Every question maps to content one of the 13 seeded `SectionType`s can actually render. No question asks about a capability the platform has no slot for.
- Two tiers: **universal** questions (asked for every Business) and **business-type-specific** questions (extending the `business_type_profiles` registry pattern per type).
- Every field is skippable, and every optional field is presented as a concrete **suggestion with an example**, never a blank box. A skipped field is filled by the existing deterministic fallback.
- Universal questions cover: logo (upload / generate placeholder / skip), hero image (upload / curated set / generate / skip), tone (concrete slider pairs, e.g. warm ↔ minimal), colour (curated preset palettes — logo-colour extraction is explicitly deferred to a later pass), what to lead with, contact/location display (extending, not duplicating, existing Business/Location data), social links, hours, and words to prefer or avoid.
- Business-type-specific questions are per-item and all-optional, e.g. home food: per menu item — name, description, optional health benefits, dietary tags, spice level, serving size; salon/spa/services: per service — description, duration hint, differentiator; retail: per product — description, materials/care; clinic/professional: per service — description, what to expect.

**Explicitly out of scope for this pass:** per-field "improve this with AI" helpers, single-section regeneration, and any multi-turn chat with the end user. If those are wanted later they are a separate, recorded decision.

## 12.8 Prebuilt Template Ingestion — Option A (design-reference translation only)

> **Amendment — 2026-09-01 (Website Generation Overhaul work order; additive, dated per Document 08 §25.3). Decided now.**

Externally-sourced design references (e.g. a founder-supplied export) are translated into the **existing** theme and `SectionType` system. Raw external HTML / CSS / JS is **never** placed in the rendering path — this is the same rule as §12.5 and Document 10 §11.3, applied to templates.

- **Intake location:** `infra/templates/inbound/` (a founder drops an export here). The pipeline is **idle** until something is present — it never blocks generation or any other work.
- **Extraction target:** design decisions only — palette, type choices, spacing rhythm, section composition — expressed as (a) a new `theme` definition in `website_versions.theme` JSONB, and (b) new **layout variants** added to existing `SectionType.allowed_variants`.
- **Boundary:** if an export contains something the current 13 `SectionType`s cannot represent, that is **flagged back for a decision**, not resolved by inventing an arbitrary new section type. New `SectionType`s remain a schema/architecture decision shown before applied (Document 10 §11.3 "Businesses may not define new section types" applies to the pipeline too).


## 12.9 Live Generation Path — Implemented Parameters, Validation Posture, and Open Defects

> **Amendment — 2026-09-12 (additive, dated per Document 08 §25.3). Records how the path
> was actually built, following its first end-to-end run against a live model.**

§§12.1–12.8 describe the governing model and remain correct in intent. This section records
the implemented parameters and the three places where implemented behaviour differs from the
earlier text, so that neither the document nor the code is read as the other.

### 12.9.1 Implemented call parameters

Sources: `platform_core/services/website_generation.py`, `platform_core/website/ai_provider.py`.

| Parameter | Implemented value | Note |
|---|---|---|
| Model | **`gemini-3.6-flash`** | Default, overridable by `GEMINI_MODEL`. The previously assumed `gemini-2.0-flash` was retired by the provider and now returns 404. `gemini-flash-latest` is the non-retiring alias but has been 503-flaky under load, so a concrete pin plus the retry/fallback path is preferred. |
| Timeout | **75 s** | **Supersedes the `timeout=30` shown in §12.7.** A full 3–5 page generation routinely needs 30–50 s; 30 s produced systematic timeouts that were indistinguishable from model failure. |
| `max_output_tokens` | **16384** (set by the caller) | The provider's own default is 8192, which truncates a multi-page draft. |
| `temperature` | 0.6 | Provider default. |
| Attempts | 3, exponential backoff | Unchanged from §12.1. |
| Structured output | `response_mime_type=application/json`, with the JSON Schema embedded in the prompt | The provider guarantees only *parseable* JSON. The hard guarantee remains the caller's `validate_generation_payload`. |

### 12.9.2 The section catalogue is part of the prompt

`WEBSITE_GENERATION_SCHEMA` describes only the envelope (`pages`, `navigation`,
`theme_hints`), so a model given the schema alone invents section types and content
fields. The prompt therefore carries `SECTION_CATALOGUE_PROMPT`: the 13 seeded
`SectionType`s with their exact content fields and `allowed_variants`, the live-data rule,
and the allowed `page_type` values.

This is the prompt-side expression of §12.6 — the model is *told* the vocabulary rather
than trusted to guess it, which is also the cheaper posture, because a drifted response
costs a retry. Note the token consequence: the catalogue is a large, static block sent on
every call. It belongs in the stable, cacheable portion of the prompt, and it must never be
assembled per-Business from live data.

**Any change to the catalogue is a prompt change and must bump
`website_generation_jobs.prompt_version`.** This did not happen when the catalogue was
introduced — see `D12-AI-002`.

### 12.9.3 Validation posture — strict envelope, lenient content

§12.1 step [5] reads "strict JSON Schema" and step [7] "on validation failure:
deterministic template repair". The implemented posture is two-tier, because rejecting a
whole draft over one drifted field discards an otherwise good site:

| Path | Posture | Behaviour on drift |
|---|---|---|
| AI generation — `validate_generation_payload` → `validate_section_content(lenient=True)` | Strict envelope, **lenient per field** | Unknown keys dropped; wrong-typed values dropped; over-long strings truncated; `page_type` synonyms coerced by `_coerce_page_type` (e.g. `landing` → `home`). A section that loses a **required** field is dropped, not fatal. |
| Manual owner edits — `validate_section_patch`, `validate_page_patch` | **Strict** | Rejected with a validation error. |

**This does not widen §12.6.** Everything in §12.6's right-hand column remains
unrepresentable: dropping an unknown key is precisely the mechanism by which a response
reaching beyond content fails to be stored. The only correction is that repair happens at
**field** granularity *before* falling back, rather than the entire draft falling back.

Stated as a rule, so it is not re-litigated: **lenient applies only to the AI path, only to
content within a known `SectionType`, and never to a manual edit.** Widening it further
requires a recorded decision.

### 12.9.4 Persistence failure is a third fallback trigger

§12.1's failure handling covers provider timeout and failure only. A *validated* draft can
still be rejected by the database — a CHECK or enum the model drifted past — and in
SQLAlchemy that rejection poisons the worker's session, which kills retry and dead-letter
handling for the job. The AI draft is therefore written inside a savepoint
(`session.begin_nested()`); on any write failure the savepoint is rolled back and the
deterministic draft is written instead, with
`fallback_reason = "AI draft rejected on write: …"`.

Fallback triggers are therefore:

1. provider unavailable (no `GEMINI_API_KEY`) — fails fast, no retry delay;
2. provider error, timeout, or unparseable output after 3 attempts;
3. **a validated draft rejected on persistence.**

All three end at `build_deterministic_draft`, which always produces a valid draft. The
invariant from §12.1 holds unchanged: **AI failure never blocks Business creation.**

### 12.9.5 `website_generation_jobs` — drift from the §12.4 DDL

The live table carries three things the §12.4 DDL does not show:

| Addition | Purpose | Source |
|---|---|---|
| `intake JSONB` | The owner's questionnaire answers, persisted on the job so the single `generate_structured` call can use them and a later "regenerate with more detail" can pre-fill | migration `20260901010000_website_generation_intake.sql` |
| `status = 'superseded'` | An explicit questionnaire-driven generation replaces an auto-enqueued bootstrap job the worker has not yet claimed — the owner's answers must win over the bootstrap draft | same migration |
| `triggered_by uuid` | Actor attribution for the audit record | Stage 2 |

§12.4's DDL should be read as superseded by the migrations on these three points.

### 12.9.6 Open defects in the live path

These are recorded, not fixed. Each is a divergence from a rule this document already
states, so none of them is a new requirement.

| ID | Defect | Rule it violates | Severity |
|---|---|---|---|
| `D12-AI-001` | `job.model_name` is set to the literal string `"structured"` rather than the model actually used. **The model is therefore not recorded on any generation job**, so a bad generation cannot be attributed to a model version. | §12.5 — "logged with prompt version, provider, **model**, and outcome" | P1 |
| `D12-AI-002` | `prompt_version` is hardcoded `"v1"` and was not bumped when `SECTION_CATALOGUE_PROMPT` was added. Generations are no longer attributable to the prompt that produced them. | §12.4's purpose for `prompt_version` | P1 |
| `D12-AI-003` | No token, latency, or cost accounting is captured. AI spend is not attributable per Business or per generation, and there is no basis for the `FL-DEC-015` budget decision. | §12.5 governance intent; Document 10 §11.4 cost discipline | P1 — blocks `FL-DEC-015` |
| `D12-AI-004` | The 5 requests/minute generation limit **is** implemented, but keyed by **client IP** (first hop of `X-Forwarded-For`), not by Business. Several Businesses behind one NAT share a bucket; one Business on two networks gets double. The endpoint itself is permission-gated (`website.edit` via `require_business_actor`), so this is **not** an anonymous-abuse path — the exposure is an authenticated actor burning provider spend past the documented ceiling, which `D12-AI-003` makes undetectable. | §12.5 — "5 requests/minute/**Business**" | P1 |

> **Wider note on the same mechanism (not AI-specific).** `client_key()` trusts the first
> hop of a caller-supplied `X-Forwarded-For` header unconditionally. For the
> permission-gated buckets that is a fairness problem. For the **anonymous** buckets —
> `public_write` (guest checkout, booking intake) and `public_read` (marketplace, search)
> — it means the rate limit is **bypassable by any caller that sets the header**, unless a
> trusted proxy is guaranteed in front of the API and strips or rewrites it. Either
> guarantee that proxy and document it as a deployment requirement under §19/§20, or
> derive the key from the socket peer with a configured trusted-proxy allowlist. This is
> a **P0 for the public buckets** and is tracked here only because §12.5's limit shares
> the mechanism; the fix belongs to §21.1's security gates, not to §12.

| ID | Defect | Rule it violates | Severity |
|---|---|---|---|
| `D12-AI-005` | The rate-limit window store is an in-process `dict`, so limits reset on restart and do not hold across replicas. | §17.5 Redis necessity decision should be revisited before horizontal scaling | P2 |
| `D12-AI-006` | `platform_core/services/ai_runtime/` still exists — a Stage 1 `AiRuntimeProvider` / `StubAiRuntimeProvider` skeleton superseded by `platform_core/website/ai_provider.py`. §12.2's amendment states no such package exists; it does, and a new agent may extend the wrong abstraction. **Delete it.** | §12.2 | P2 |
| `D12-AI-007` | The retry loop sleeps after its final attempt, adding a pointless ~4 s to every fallback. | — | P3 |
| `D12-AI-008` | `_apply_intake_assets` stitches only `hero_image_asset_id`, and only onto a `hero` or `about` section. A questionnaire-supplied **logo** has no visible placement path into the draft. **Verify before claiming the questionnaire's logo answer is honoured.** | §12.7 questionnaire rules | P2 — unverified |

### 12.9.7 Key handling

The Gemini API key currently in use is a **temporary founder-authorised key that is known
to need rotation before any public traffic.** `FL-DEC-015` (provider, budget, fallback
policy) remains formally open; the live path recorded above is an authorised interim
implementation, **not** its closure. See Document 11 §26 (2026-09-12 status block).


---

# 13. Frontend Implementation

## 13.1 Next.js App Router Conventions

| Concern | Convention |
|---|---|
| Server Components | Default for data-fetching pages and layouts |
| Client Components | Only where interactivity, hooks, or browser APIs are needed. Marked with `"use client"`. |
| Server Actions | Used for form mutations running server-side |
| Data fetching | Server Components fetch directly from FastAPI (server-to-server) |
| Loading UI | `loading.tsx` files for suspense boundaries; skeleton components |
| Error handling | `error.tsx` files for error boundaries |
| Not found | `not-found.tsx` files |

## 13.2 Server vs Client Component Boundaries

Server Components handle data fetching. Client Components handle interaction. Never fetch data inside Client Components when Server Components can do it.

```
app/
+-- layout.tsx                     <- Server Component: global layout
+-- [slug]/
|   +-- page.tsx                   <- Server Component: renders website page from API
|   +-- checkout/
|   |   +-- page.tsx               <- Server Component: loads cart state
|   |       +-- CheckoutForm.tsx   <- Client Component: interactive form, payment UI
|   +-- book/
|       +-- page.tsx               <- Server Component: loads availability
|           +-- BookingCalendar.tsx <- Client Component: interactive calendar
```

## 13.3 Forms and Validation

- **Form library:** `react-hook-form` for complex forms.
- **Validation:** Zod schemas from `packages/validation` — shared between frontend and API contract types.
- **Server-side validation:** All form submissions are re-validated server-side regardless of frontend validation.

## 13.4 State Management

| State type | Tool |
|---|---|
| Server state (remote data) | Server Components / Next.js fetch cache |
| Auth session state | `@supabase/ssr` cookie session via `packages/auth` (browser client in Client Components; server client in Server Components, Server Actions, and Proxy) |
| Form state | `react-hook-form` |
| Simple UI state (modal open, tab) | `useState` |
| Cross-component UI state (cart, notification count) | React Context (light, scoped) |
| Global state | Avoid — derive from server or URL state |

No Redux, Zustand, or global state management library unless a genuine need arises.

## 13.5 Permission-Aware UI

```typescript
function OrderActions({ order, permissions }: Props) {
    const canCancel = permissions.includes('orders.cancel');
    if (!canCancel) return null;  // visual only; server enforces
    return <Button onClick={() => cancelOrder(order.id)}>Cancel</Button>;
}
```

Permission checks in UI are for progressive disclosure only. Server-side enforcement is always the authority.

## 13.6 Realtime Updates

For live operational data (order board, booking calendar, notification counts): use Supabase Realtime (PostgreSQL LISTEN/NOTIFY via Supabase channels). Scope subscriptions by `business_id`. Fallback: poll every 30 seconds if Realtime subscription drops.

## 13.7 Supabase SSR Auth Integration

Each Next.js app (`apps/web`, `apps/workspace`, `apps/admin`) uses the current supported Supabase SSR pattern:

| Concern | Implementation |
|---|---|
| Browser session reads/writes | `packages/auth/browser.ts` → `createBrowserClient()` from `@supabase/ssr` |
| Server session reads/writes | `packages/auth/server.ts` → request-scoped `createServerClient()` with `cookies().getAll()` / `setAll()` |
| Session refresh | `apps/*/src/proxy.ts` (or `middleware.ts` where applicable) imports `packages/auth/proxy.ts`, calls `getClaims()` / `getUser()`, and propagates refreshed cookies on the response |
| API authorization | Server Components and Server Actions call FastAPI with `Authorization: Bearer <access_token>` from `packages/auth/access-token.ts` |
| Package dependencies | `@supabase/supabase-js`, `@supabase/ssr` — not `@supabase/auth-helpers-nextjs` or `@supabase/auth-helpers-react` |

```typescript
// packages/auth/server.ts
import { createServerClient } from '@supabase/ssr'
import { cookies } from 'next/headers'

export async function createSupabaseServerClient() {
  const cookieStore = await cookies()
  return createServerClient(
    process.env.NEXT_PUBLIC_SUPABASE_URL!,
    process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!,
    {
      cookies: {
        getAll: () => cookieStore.getAll(),
        setAll: (cookiesToSet) => {
          cookiesToSet.forEach(({ name, value, options }) =>
            cookieStore.set(name, value, options)
          )
        },
      },
    }
  )
}
```

FastAPI remains the authority for Business permissions, Entitlements, module state, and tenant scope. Frontend auth state must never be treated as authorization proof.

---

# 14. Marketplace and Search Implementation

## 14.1 Search Decision

**First Launch: PostgreSQL full-text search with GIN indexes** (FL-DEC-014 resolved). Sufficient for thousands of Businesses. The `svc-search-discovery` abstraction ensures migration requires no application-layer changes.

## 14.2 Search Projection Schema

```sql
marketplace_business_projections (
    business_id          uuid PRIMARY KEY REFERENCES businesses(id),
    slug                 text NOT NULL,
    display_name         text NOT NULL,
    description          text,
    business_type        text,
    characteristics      text[],
    primary_category     text,
    tags                 text[],
    primary_location_id  uuid,
    city                 text,
    lat                  numeric(10,7),
    lng                  numeric(10,7),
    is_discoverable      boolean NOT NULL DEFAULT false,
    indexed_at           timestamptz NOT NULL DEFAULT now(),
    search_vector        tsvector
)

marketplace_offering_projections (
    id                   uuid PRIMARY KEY,
    business_id          uuid NOT NULL REFERENCES businesses(id),
    offering_type        text NOT NULL,
    title                text NOT NULL,
    description          text,
    price_from           numeric(12,2),
    currency             text,
    category             text,
    tags                 text[],
    location_ids         uuid[],
    is_active            boolean NOT NULL DEFAULT true,
    indexed_at           timestamptz NOT NULL DEFAULT now(),
    search_vector        tsvector
)
```

## 14.3 Search Vector Maintenance

```sql
CREATE OR REPLACE FUNCTION update_business_search_vector() RETURNS TRIGGER AS $$
BEGIN
    NEW.search_vector := to_tsvector('english',
        coalesce(NEW.display_name, '') || ' ' ||
        coalesce(NEW.description, '') || ' ' ||
        coalesce(array_to_string(NEW.tags, ' '), '') || ' ' ||
        coalesce(NEW.city, '')
    );
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;
```

## 14.4 Joined-Business-Only Enforcement

Only Businesses with `businesses.state = 'active'`, `businesses.visibility = 'discoverable'`, a valid published Website, and passed profile completeness threshold appear in Marketplace search. Enforced in both the indexing job (only indexing eligible Businesses) and the search query (`is_discoverable = true` predicate).

## 14.5 Indexing Triggers (Worker Events)

| Event | Indexing action |
|---|---|
| `business.profile.updated` | Update `marketplace_business_projections` |
| `website.published` | Mark Business as indexable; trigger re-index |
| `business.visibility.changed` | Update `is_discoverable` flag |
| `offering.created/updated/archived` | Update `marketplace_offering_projections` |
| `business.suspended` | Set `is_discoverable = false` |

## 14.6 Search Extraction Criteria

Migrate from PostgreSQL FTS to external search engine when: > 50,000 indexed Businesses, search queries consistently > 200ms p95, faceted filtering required, or PostgreSQL CPU usage attributable to search exceeds 30%.

---

# 15. Media and Storage Implementation

## 15.1 Supabase Storage Buckets

| Bucket | Access | Purpose |
|---|---|---|
| `business-public` | Public read | Business logos, cover images, Offering images, Website media |
| `business-private` | Private | Internal Business documents |
| `platform-assets` | Public | Platform UI assets |
| `user-avatars` | Public | Consumer/member profile photos |

## 15.2 Asset Indirection

Domain data never stores raw provider URLs. It stores **asset IDs** that resolve through `svc-media`:

```sql
media_assets (
    id               uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    business_id      uuid,
    identity_id      uuid,
    bucket           text NOT NULL,
    storage_path     text NOT NULL,
    mime_type        text NOT NULL,
    file_size_bytes  bigint,
    alt_text         text,
    width            integer,
    height           integer,
    deleted_at       timestamptz,
    created_at       timestamptz NOT NULL DEFAULT now()
)
```

## 15.3 Upload Authorization Flow

```
1. Client: POST /v1/media/upload-url { bucket, content_type, business_id? }
2. Server: validates identity, membership, file type
3. Server: calls Supabase Storage createSignedUploadUrl()
4. Server: returns { upload_url, asset_id } (asset record pre-created)
5. Client: uploads directly to Supabase Storage signed URL
6. Client: POST /v1/media/upload-complete { asset_id }
7. Server: verifies upload succeeded; updates asset status
```

The API server never handles binary file content.

## 15.4 File Type Allowlist

Permitted: `image/jpeg`, `image/png`, `image/webp`, `image/gif` (static only). Max: 10MB per file. Vector/SVG uploads disabled (XSS risk). PDF deferred.

## 15.5 Implementation Amendment

> **Amendment — 2026-09-01 (media & storage build; additive, dated per Document 08 §25.3).**
> §15.1–§15.4 above stand as the design. These are the points where the built
> system deliberately differs, recorded rather than quietly diverged.

| §15 says | Built as | Why |
|---|---|---|
| Four buckets (`business-public`, `business-private`, `platform-assets`, `user-avatars`) | One public `media` bucket | Only public Business media exists at First Launch. The other three are added when something needs them; splitting early buys nothing and multiplies RLS surface. |
| `media_assets(identity_id, bucket, storage_path, file_size_bytes, …)` | The Stage 2 table's names kept: `uploader_identity_id`, `storage_key`, `size_bytes`; `bucket`, `width`, `height`, `purpose`, `deleted_at` added | The table already shipped in `20260713100000` with data-free but live DDL. Renaming columns to match prose is churn; the shape is equivalent. |
| "Server calls Supabase Storage `createSignedUploadUrl()`" | Server calls the Storage REST sign endpoint **with the caller's own JWT** | This project has a standing rule that no service-role client exists anywhere. Storage RLS scopes a signed-in caller to their own `{supabase_user_id}/` prefix; business ownership of an asset is authoritative in `media_assets`, which only the API writes. |
| (silent on permissions) | Upload declares a `purpose`; each purpose maps to an existing canonical permission — `website`→`website.edit`, `brand`/`profile`→`business.update`, `offering`→`offerings.update` | Doc 12 §8.2 has no `media.*` permission and adding one is a registry change. An unmapped purpose raises rather than falling open. |
| (silent on read-back) | Resolved public URLs are returned as `section.assets[key] = {url, alt_text}`, **never merged into `section.content`** | `validate_section_content` rejects fields absent from the SectionType schema, so injecting a URL into `content` would break the next PATCH round-trip. |

**Storage RLS (migration `20260901020000`).** The `media` bucket predated this
work, was created outside version control, and carried `media_insert` /
`media_update` policies granted to role `public` with only a `bucket_id` check
— i.e. any anonymous caller could write or overwrite any object, with no size
or MIME limit. Nothing referenced the bucket and `media_assets` was empty. The
policies are now: public `SELECT` (published Business media is public by
design), and `INSERT`/`UPDATE`/`DELETE` for role `authenticated` restricted to
the caller's own uid prefix. Bucket limits are set to 10MB and the §15.4 image
allowlist.

**Still open:** image dimensions (`width`/`height`) are stored but never
populated — no processing pipeline exists. Deriving them needs either a client
measurement passed on upload or a worker job; neither is built.

---

# 16. Notifications Implementation

## 16.1 Core Notifications Architecture

```sql
platform_notifications (
    id               uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    identity_id      uuid NOT NULL REFERENCES platform_identities(id),
    business_id      uuid,
    notification_type text NOT NULL,
    title            text NOT NULL,
    body             text,
    action_url       text,
    read_at          timestamptz,
    created_at       timestamptz NOT NULL DEFAULT now(),
    expires_at       timestamptz
)
```

`core-notifications` is the in-platform notification inbox. It is **not** the deferred `messaging` module.

## 16.2 Transactional Delivery

First Launch transactional delivery: order confirmations, booking confirmations, payment receipts, verification codes, password reset, membership enrolment, critical provider/payment failure alerts.

Channels are provider-abstracted. Email provider (Resend/Postmark/SES) and SMS provider (MSG91/Twilio) configured per environment.

## 16.3 Event-Driven Notification Creation

Notifications are created by the worker in response to domain events. Example:

```python
class NotificationEventHandlers:
    async def on_order_created(self, event: OrderCreated) -> None:
        # Send consumer order confirmation (in_app + email)
        # Send business new order alert (in_app)
```

---

# 17. Cache, Redis, and Realtime

## 17.1 Conservative Cache Usage

Redis is optional infrastructure. PostgreSQL is the source of truth. Redis added only where it provides measurable benefit.

## 17.2 What Is Cached

| Data | Cache layer | TTL | Invalidation |
|---|---|---|---|
| Permission grants per membership | In-process LRU (or Redis) | 5 minutes | Immediate on grant/revoke change |
| Entitlement state per Business | In-process LRU (or Redis) | 10 minutes | Immediate on Entitlement change |
| Module state per Business | In-process LRU (or Redis) | 5 minutes | Immediate on state change |
| Published website pages | Next.js ISR cache | Until revalidated | On publish event |

## 17.3 Cache Safety Rules

- Permission sets must be invalidated immediately on any grant/revoke change.
- Entitlement state must be invalidated immediately on commercial state change.
- Never serve a cached permission result after membership suspension.
- Never cache Business-private data in shared caches accessible to multiple Businesses.

## 17.4 Cache Keys

```
perms:{membership_id}              -> permission set for this membership
entitlements:{business_id}         -> entitlement set for this Business
module_states:{business_id}        -> module state map for this Business
```

All cache keys include the scope identifier.

## 17.5 Redis Necessity Decision

Redis is added when needed for: rate limiting across multiple API instances, shared session state across horizontal API instances, or real-time Pub/Sub beyond what Supabase Realtime provides. Redis is **never** the canonical source of truth for business state.


---

# 18. Transactional Outbox and Worker Architecture

PostgreSQL is the durable canonical source for all asynchronous work. The Python worker in `apps/worker` is a small platform-owned processor — not Celery, not Redis-backed, not pg-boss, and not a Node.js worker. It distinguishes three lanes:

| Lane | Purpose | Durable store | Typical producers |
|---|---|---|---|
| **Domain/outbox events** | Canonical business facts emitted atomically with state mutations | `platform_outbox_events` | `apps/api` modules inside the same DB transaction |
| **Asynchronous jobs** | Imperative background work (notifications, indexing, webhooks, AI, media) | `platform_async_jobs` | API request handlers, outbox handlers, webhook ingestion |
| **Scheduled jobs** | Time-triggered work materialized into async jobs when due | `platform_scheduled_jobs` | API registration, recurring reminders |

Redis is not required to run the worker. Multiple worker instances are safe via `FOR UPDATE SKIP LOCKED` claiming and short leases.

## 18.1 Outbox Schema (Domain Events)

```sql
platform_outbox_events (
    id               uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    business_id      uuid,
    event_type       text NOT NULL,
    event_version    text NOT NULL DEFAULT '1.0',
    payload          jsonb NOT NULL,
    correlation_id   uuid,
    causation_id     uuid,
    status           text NOT NULL DEFAULT 'pending'
        CHECK (status IN ('pending', 'processing', 'completed', 'failed', 'dead_letter')),
    attempt_count    integer NOT NULL DEFAULT 0,
    max_attempts     integer NOT NULL DEFAULT 5,
    next_attempt_at  timestamptz NOT NULL DEFAULT now(),
    leased_until     timestamptz,
    leased_by        text,
    last_error       text,
    created_at       timestamptz NOT NULL DEFAULT now(),
    processed_at     timestamptz
)

CREATE INDEX idx_outbox_pending ON platform_outbox_events(status, next_attempt_at)
    WHERE status IN ('pending', 'failed');
```

Domain events are written in the **same transaction** as the business mutation. The outbox row is the durable canonical event source; handlers must be idempotent.

## 18.2 Async Job Schema

```sql
platform_async_jobs (
    id               uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    business_id      uuid,
    job_type         text NOT NULL,
    payload          jsonb NOT NULL,
    correlation_id   uuid,
    causation_id     uuid,
    status           text NOT NULL DEFAULT 'pending'
        CHECK (status IN ('pending', 'processing', 'completed', 'failed', 'dead_letter')),
    attempt_count    integer NOT NULL DEFAULT 0,
    max_attempts     integer NOT NULL DEFAULT 5,
    next_attempt_at  timestamptz NOT NULL DEFAULT now(),
    leased_until     timestamptz,
    leased_by        text,
    last_error       text,
    created_at       timestamptz NOT NULL DEFAULT now(),
    completed_at     timestamptz
)

CREATE INDEX idx_async_jobs_pending ON platform_async_jobs(status, next_attempt_at)
    WHERE status IN ('pending', 'failed');
```

Async jobs are imperative work units. Example `job_type` values: `notification.deliver`, `search.reindex_business`, `website.generate`, `media.process_image`, `webhook.process_payment`.

## 18.3 Scheduled Job Schema

```sql
platform_scheduled_jobs (
    id                   uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    business_id          uuid,
    schedule_type        text NOT NULL,
    payload              jsonb NOT NULL,
    run_at               timestamptz NOT NULL,
    status               text NOT NULL DEFAULT 'pending'
        CHECK (status IN ('pending', 'materialized', 'cancelled')),
    materialized_job_id  uuid REFERENCES platform_async_jobs(id),
    recurrence_key       text,
    created_at           timestamptz NOT NULL DEFAULT now()
)

CREATE INDEX idx_scheduled_jobs_due ON platform_scheduled_jobs(run_at)
    WHERE status = 'pending';
```

The scheduler lane materializes due rows into `platform_async_jobs` (for example `membership.renewal_reminder`). Complex recurrence beyond explicit `run_at` registration is deferred.

## 18.4 Python-Native Worker Implementation

**Selected approach:** a small PostgreSQL-backed Python worker using SQLAlchemy 2.x async + asyncpg. No external queue framework is required at First Launch.

**Python dependencies (worker + shared backend):** `fastapi`, `sqlalchemy[asyncio]`, `asyncpg`, `pydantic`, `httpx`, `python-jose` (JWT), `structlog` / `opentelemetry` as configured. Explicitly excluded unless a demonstrated need arises: `celery`, `redis`, `pg-boss`, Kafka, RabbitMQ.

```python
# apps/worker/main.py
import asyncio
import os
import socket

from platform_core.db import create_worker_session_factory
from outbox_consumer import poll_and_dispatch_outbox
from job_runner import poll_and_execute_jobs
from scheduler import materialize_due_schedules

async def main() -> None:
    worker_id = f"{socket.gethostname()}-{os.getpid()}"
    session_factory = create_worker_session_factory(role="service")

    while True:
        async with session_factory() as session:
            await asyncio.gather(
                poll_and_dispatch_outbox(session, worker_id),
                poll_and_execute_jobs(session, worker_id),
                materialize_due_schedules(session, worker_id),
            )
        await asyncio.sleep(settings.WORKER_POLL_INTERVAL_SECONDS)
```

Worker handlers invoke the same Python application services used by `apps/api`; only the entry point differs. Observability fields (`correlation_id`, `causation_id`, `worker_id`, `job_type` / `event_type`, `attempt_count`, `duration_ms`) are logged on every claim, success, retry, and dead-letter transition.

## 18.5 Claiming and Processing Strategy

Claiming uses PostgreSQL row locks with `FOR UPDATE SKIP LOCKED`, short leases, and transactional status transitions. Expired leases are reclaimable by any worker instance.

```python
# apps/worker/claiming.py
LEASE_SECONDS = 120

async def claim_outbox_batch(session: AsyncSession, worker_id: str, limit: int = 10) -> list[OutboxEvent]:
    result = await session.execute(
        text("""
            UPDATE platform_outbox_events
            SET status = 'processing',
                leased_until = now() + make_interval(secs => :lease_seconds),
                leased_by = :worker_id
            WHERE id IN (
                SELECT id
                FROM platform_outbox_events
                WHERE status IN ('pending', 'failed')
                  AND next_attempt_at <= now()
                  AND (leased_until IS NULL OR leased_until < now())
                ORDER BY next_attempt_at
                FOR UPDATE SKIP LOCKED
                LIMIT :limit
            )
            RETURNING *
        """),
        {"worker_id": worker_id, "limit": limit, "lease_seconds": LEASE_SECONDS},
    )
    return [OutboxEvent.from_row(row) for row in result.mappings()]

async def process_outbox_event(event: OutboxEvent, session_factory) -> None:
    try:
        await dispatch_event_to_handlers(event)
        await outbox_repo.mark_completed(event.id)
    except Exception as exc:
        attempt_count = event.attempt_count + 1
        if attempt_count >= event.max_attempts:
            await outbox_repo.mark_dead_letter(event, final_error=str(exc))
        else:
            backoff = min(2 ** attempt_count * 30, 3600)
            await outbox_repo.mark_retry(event.id, backoff_seconds=backoff, error=str(exc))
```

The same claiming pattern applies to `platform_async_jobs`. Scheduled jobs are read with `FOR UPDATE SKIP LOCKED`, converted into async jobs, and marked `materialized` in the same transaction.

**Retry policy:** exponential backoff capped at 1 hour; default `max_attempts = 5`. **Replay:** Super Admin may requeue dead-letter rows into `pending` with a new `next_attempt_at`. **Correlation/causation:** preserved from the originating request or parent event/job.

## 18.4 Idempotency for Event Handlers

Every event handler must be idempotent. Handler completion is recorded in `platform_processed_events`:

```sql
platform_processed_events (
    id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    event_id      uuid NOT NULL,
    handler       text NOT NULL,
    processed_at  timestamptz NOT NULL DEFAULT now(),
    UNIQUE (event_id, handler)
)
```

```python
async def on_order_created(self, event: OrderCreated, session: AsyncSession) -> None:
    # Check if already processed
    existing = await self.processed_events_repo.get(
        event_id=event.id,
        handler='customer_relationships.on_order_created'
    )
    if existing:
        return  # Already processed

    await self._upsert_customer_contact(event, session)

    await self.processed_events_repo.mark(
        event_id=event.id,
        handler='customer_relationships.on_order_created',
        session=session
    )
```

## 18.5 Dead-Letter Handling

```sql
platform_dead_letter_events (
    id               uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    original_event_id uuid NOT NULL,
    event_type       text NOT NULL,
    business_id      uuid,
    payload          jsonb NOT NULL,
    final_error      text NOT NULL,
    dead_lettered_at timestamptz NOT NULL DEFAULT now(),
    resolved_at      timestamptz,
    resolved_by      uuid REFERENCES platform_identities(id),
    resolution_note  text
)
```

Dead-letter events are visible in the Super Admin dashboard. Operators can inspect, trigger replay, or mark as resolved.

## 18.6 Webhook Ingestion Pipeline

```python
@router.post("/v1/webhooks/payments/{provider}")
async def ingest_payment_webhook(provider: str, request: Request, ...) -> Response:

    raw_body = await request.body()
    adapter = payment_provider_adapters[provider]

    # Step 1: Verify signature FIRST
    if not adapter.verify_signature(raw_body, request.headers):
        raise HTTPException(status_code=400, detail="Invalid signature")

    # Step 2: Idempotency check
    provider_event_id = adapter.extract_event_id(raw_body)
    existing = await webhook_receipt_repo.get(provider, provider_event_id, session)
    if existing:
        return Response(status_code=200)  # Duplicate; acknowledge safely

    # Step 3: Durable receipt BEFORE success acknowledgement
    receipt = WebhookReceipt(provider=provider, provider_event_id=provider_event_id,
                             raw_payload=raw_body, received_at=utcnow())
    await webhook_receipt_repo.save(receipt, session)
    await session.commit()  # DURABLE

    # Step 4: Acknowledge success (business effects run asynchronously after this)
    await async_jobs_repo.enqueue(
        session,
        job_type='webhook.process_payment',
        payload={'receipt_id': str(receipt.id)},
        correlation_id=request.state.correlation_id,
    )
    return Response(status_code=200)
```

## 18.7 Event Versioning

```python
from uuid import uuid4

@dataclass
class OrderCreated:
    event_type: str = "order.created"
    event_version: str = "1.0"
    event_id: UUID = field(default_factory=uuid4)
    correlation_id: UUID | None = None
    causation_id: UUID | None = None
    occurred_at: datetime = field(default_factory=utcnow)
    business_id: UUID | None = None
    order_id: UUID | None = None
    # payload fields
```

Breaking payload changes require a new version string. Handlers declare the versions they support. Unrecognized versions go to dead-letter.

---

# 19. Environment Strategy

## 19.1 Environment Definitions

| Environment | Purpose | Data |
|---|---|---|
| `local` | Developer local development | Seed data + reference fixtures |
| `test` | Automated tests | Reset before each test suite run |
| `staging` | Pre-production validation | Synthetic data |
| `production` | Real Businesses and consumers | Real data; access restricted |

## 19.2 Environment Variables

```bash
# Supabase
SUPABASE_URL=https://...supabase.co
SUPABASE_ANON_KEY=...           # Safe to expose in browser
SUPABASE_SERVICE_ROLE_KEY=...   # SERVER ONLY
DATABASE_URL=...                # Server only

# API
NEXT_PUBLIC_API_URL=https://api.platform.com

# Auth
NEXT_PUBLIC_SUPABASE_URL=...
NEXT_PUBLIC_SUPABASE_ANON_KEY=...

# AI Provider
AI_PROVIDER=gemini
GEMINI_API_KEY=...              # Server only
OPENAI_API_KEY=...              # Server only (fallback)

# Payment (resolves when FL-DEC-003 closes)
PAYMENT_PROVIDER=razorpay
RAZORPAY_KEY_ID=...             # Server only
RAZORPAY_KEY_SECRET=...         # Server only

# Email / SMS
EMAIL_PROVIDER=resend
RESEND_API_KEY=...              # Server only
SMS_PROVIDER=msg91
MSG91_AUTH_KEY=...              # Server only

# Jobs / Worker
WORKER_POLL_INTERVAL_SECONDS=2
WORKER_CLAIM_BATCH_SIZE=10
WORKER_LEASE_SECONDS=120
# Worker uses DATABASE_URL above (same PostgreSQL connection as api)

# Observability
SENTRY_DSN=...
OTEL_ENDPOINT=...

# Platform
PLATFORM_DOMAIN=platform.com
NEXT_PUBLIC_PLATFORM_DOMAIN=platform.com
ENVIRONMENT=production
```


> **Amendment — 2026-09-12 (additive).** Corrections to the block above, as implemented.
> `.env.example` carries the same issues and should be corrected with it.
>
> - **`GEMINI_MODEL` is missing and is read in production.** It overrides the
>   `gemini-3.6-flash` default in `platform_core/website/ai_provider.py` (§12.9.1). Without
>   it in the template, the one control over a retired or flaky model is undiscoverable.
>   Add it.
> - **`OPENAI_API_KEY=... # Server only (fallback)` is misleading.** There is no OpenAI
>   provider, and the fallback for website generation is **deterministic**
>   (`build_deterministic_draft`), never a second model. Retain it only as a commented
>   placeholder, or remove it.
> - **`AI_PROVIDER` is not read today.** `get_ai_provider()` selects on `GEMINI_API_KEY`
>   presence alone. `AI_PROVIDER` becomes live when a second provider exists (§12.2).
> - **`PAYMENT_PROVIDER` / `RAZORPAY_KEY_ID` / `RAZORPAY_KEY_SECRET` must not be read as
>   merchant credentials.** Merchant collection uses **each Business's own** Razorpay
>   credentials, entered by the owner and stored encrypted on `MerchantConnection`.
>   Platform-level Razorpay keys, if any, belong to **platform billing** only. Conflating
>   the two would breach the §17 payments boundary and Document 08 §§17–18; label these
>   variables explicitly so no future change collapses the distinction.


## 19.3 Secret Management Rules

- No secrets in source control.
- `.env.example` documents all variables without values.
- Actual values in `.env.local` (gitignored) for local development.
- Production/staging secrets in deployment platform's secrets system.
- `SUPABASE_SERVICE_ROLE_KEY` is only accessible to backend API and worker.
- Secrets are rotatable without downtime.

## 19.4 Local Development Setup

```bash
git clone <repo> && cd platform
pnpm install
uv sync
supabase start
supabase db reset    # applies all migrations + seeds
cp .env.example .env.local
# Edit .env.local with local Supabase URLs
pnpm dev             # Starts all apps: web, workspace, admin, api, worker
```

---

# 20. CI/CD and Deployment

## 20.1 Pipeline Overview

```
Pull Request:
-> Code formatting (Prettier + Ruff)
-> Linting (ESLint + Ruff)
-> Type checking (tsc --noEmit + mypy)
-> Unit + domain tests
-> RLS / tenant isolation tests
-> Contract tests
-> Migration validation (supabase db lint)
-> Build all apps (Turborepo)
-> Security scan (dependency audit)
All must pass before merge to main.

Main Branch:
-> Build Docker images (api, worker, web, workspace, admin)
-> Push to container registry
-> Deploy to staging
-> Apply migrations (staging)
-> Run integration tests (staging)
-> Smoke tests (staging)

Production Deploy:
-> Apply migrations (production)
-> Deploy api, worker, web, workspace, admin
-> Smoke tests (production)
-> Alert on failure -> rollback trigger
```

## 20.2 Deployment Platform

**Recommended: Railway or Render for First Launch** — both support containerized deployments, PostgreSQL managed integrations, and auto-deploy from container registry.

Supabase provides: PostgreSQL, Auth, Storage, Realtime. The compute (API, worker, frontend) runs on the chosen deployment platform.

## 20.3 Rollback Strategy

- **Roll forward preferred:** Fix the issue in a new deployment.
- **True rollback (code):** Revert the container tag to the previous version. Only viable if the migration is backward-compatible.
- **Database rollback:** Not used in production (forward-only migration policy).
- **Feature flags:** Critical path features may have a kill switch (environment variable toggle).

---

# 21. Testing Strategy

## 21.1 Test Layers

| Layer | Tool | Coverage target |
|---|---|---|
| Domain/unit tests | pytest | Domain entities, state machines, value objects, permission evaluation |
| Application service tests | pytest + in-memory fakes | Use case logic with fake repositories |
| Repository/integration tests | pytest + real test DB | SQL queries, migrations, RLS policies |
| API tests | pytest + httpx + test DB | Full request/response cycle |
| Contract tests | pytest | Public module interfaces, event payload shapes |
| RLS / tenant isolation tests | pytest + real test DB | Mandatory cross-tenant, cross-location, Admin isolation |
| Event/outbox tests | pytest | Outbox write + handler idempotency |
| Worker tests | pytest | Retry logic, dead-letter, idempotency |
| Webhook tests | pytest + httpx | Signature verification, idempotency, duplicate handling |
| Frontend component tests | Vitest + React Testing Library | Shared UI components, form validation |
| End-to-end tests | Playwright | Complete user journeys per reference model |
| Security tests | OWASP ZAP scan (CI) | Automated vulnerability scan on staging |

## 21.2 Reference Business Fixtures

All 11 reference business models have complete test fixtures:

```
python/testing/fixtures/
+-- 01_retail_commerce.py       <- Furniture/clothing retail
+-- 02_high_frequency_retail.py <- Supermarket/grocery
+-- 03_food_business.py         <- Restaurant/cafe
+-- 04_accommodation.py         <- Hotel/homestay
+-- 05_appointment_services.py  <- Salon/spa
+-- 06_membership_business.py   <- Gym/studio
+-- 07_professional_business.py <- Agency/lawyer
+-- 08_lead_driven.py           <- Real estate/car dealer
+-- 09_education_cohort.py      <- Tuition/coaching
+-- 10_repair_home_services.py  <- Plumber/electrician
+-- 11_rental_resource.py       <- Equipment/venue rental
```

Each fixture creates: a Business, Location, team members (Primary Owner, Manager, Member), representative Offerings, and relevant module state.

## 21.3 Authorization Test Matrix

Every protected endpoint must have tests for:

| Actor | Expected result |
|---|---|
| Unauthenticated | 401 |
| Consumer (no membership) | 403 MEMBERSHIP_REQUIRED |
| Member without required permission | 403 PERMISSION_DENIED |
| Member with permission, wrong Business | 403 or 404 |
| Member with permission, wrong Location | 403 LOCATION_ACCESS_DENIED |
| Business with expired Entitlement | 403 ENTITLEMENT_REQUIRED |
| Module not enabled | 403 MODULE_NOT_ACTIVE |
| Super Admin (attributed) | 200 with audit event |

## 21.4 Reservation Validation Tests

Separate test suites per booking mode:
- `test_appointment_booking.py` — overlapping slots, provider availability mismatch
- `test_accommodation_booking.py` — date-range capacity, concurrent reservations, night semantics
- `test_table_booking.py` — party size vs capacity, concurrent table reservation
- `test_class_session_booking.py` — session capacity, duplicate attendee prevention
- `test_rental_booking.py` — overlap detection, quantity/resource availability

Passing appointment tests does not count as accommodation or class test coverage.

---

# 22. Observability, Audit, and Operations

## 22.1 Structured Logging

Every log entry includes: `timestamp`, `level`, `correlation_id`, `identity_id` (if applicable), `business_id` (if applicable), `service`, `module`, `event`, `duration_ms`, `message`.

Security rule: Logs must never contain JWT tokens, API keys, payment card data, raw passwords, or service-role credentials.

## 22.2 Health Endpoints

```
GET /health/live   -> 200 if process is running
GET /health/ready  -> 200 if DB connection and required services are reachable
GET /health/worker -> 200 if worker is running and outbox processing lag < threshold
```

Unauthenticated. Do not expose internal configuration.

## 22.3 Audit Log

```sql
platform_audit_events (
    id               uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    event_type       text NOT NULL,
    actor_identity_id uuid NOT NULL REFERENCES platform_identities(id),
    actor_context    text NOT NULL,
    business_id      uuid,
    resource_type    text,
    resource_id      uuid,
    action           text NOT NULL,
    before_state     jsonb,
    after_state      jsonb,
    reason           text,
    ip_address       inet,
    user_agent       text,
    occurred_at      timestamptz NOT NULL DEFAULT now()
)
-- Append-only: no UPDATE or DELETE via application
```

Required audit events: all Super Admin actions, permission grants/revocations, Entitlement changes, module enable/deactivate, refund authorizations, Business suspension/reactivation, sensitive export actions, AI generation job outcomes, webhook dead-letter events.

## 22.4 Metrics and Alerts

| Metric | Alert threshold |
|---|---|
| API p95 response time | > 2s |
| Worker outbox processing lag | > 5 minutes |
| Dead-letter event count | > 10 events in 1 hour |
| Payment webhook ingestion failure rate | > 5% |
| DB connection pool exhaustion | > 80% utilization |
| AI generation failure rate | > 20% over 5 minutes |
| Failed auth attempts (by IP) | > 20 in 1 minute |

---

# 23. Backup, Recovery, and Failure Handling

## 23.1 PostgreSQL Backup

Supabase provides daily automated backups with point-in-time recovery (PITR). PITR must be enabled before staging receives real data and before production launch. Restore to a fresh Supabase project from backup once per month. Test that the application boots and reference fixture journeys pass.

## 23.2 Provider Outage Handling

| Provider | Failure behavior |
|---|---|
| AI generation provider | Worker retries 3x; falls back to deterministic template; marks job `fallback_used` |
| Payment provider | Webhook events dead-lettered for replay; offline payment methods remain available |
| Email provider | Delivery retried via worker (up to 5 attempts, 24h window); in-platform notifications always available |
| SMS provider | Retried; falls back to email if configured |
| Supabase Realtime | Frontend falls back to polling |

## 23.3 Worker Backlog

If the worker falls behind: alert fires when processing lag exceeds threshold, scale worker horizontally (additional Python worker instances claim separate rows via `FOR UPDATE SKIP LOCKED`), and short leases prevent duplicate processing across instances.

---

# 24. Version 1.1 Controlled Consistency Audit

This section records the post-correction audit for Document 12 Version 1.1. Only directly related implementation inconsistencies were corrected. Product scope, module classification, First Launch stages, and vertical slices are unchanged.

| Check | Result |
|---|---|
| 1. No pg-boss references remain | Pass |
| 2. No fake Python pg-boss APIs remain | Pass |
| 3. Worker implementation is genuinely Python-native | Pass — `apps/worker` with SQLAlchemy async + PostgreSQL claiming |
| 4. Transactional outbox remains canonical | Pass — domain events written atomically with mutations |
| 5. Redis remains optional and non-canonical | Pass — Section 17.5 unchanged |
| 6. ID generation is consistent everywhere | Pass — UUIDv4 / `gen_random_uuid()` / `uuid4()` / `crypto.randomUUID()` |
| 7. No undefined `gen_ulid()` references remain | Pass |
| 8. Supabase auth libraries and SSR patterns are current | Pass — `@supabase/ssr` cookie + Proxy pattern |
| 9. FastAPI remains authoritative | Pass — context, permissions, Entitlements resolved server-side |
| 10. Document 10 backend conflict is explicitly recorded | Pass — Section 0.2.1 |
| 11. No accidental return to Node.js backend occurs | Pass — backend is FastAPI/Python only |
| 12. No product scope changes introduced | Pass |
| 13. No module classification changes introduced | Pass |
| 14. No new broad unresolved planning layer created | Pass |
| 15. Repository bootstrap remains immediately actionable | Pass — Section 1, 19.4, Document 11 stages |

Implementation stages and vertical slices remain governed by Document 11. Document 12 Version 1.1 supplies the engineering mechanics those stages execute against.

---

# 25. Final Build-Readiness Check

**Can implementation now begin from Documents 01–12, with Document 12 Version 1.4 as the final implementation authority?**

**YES.**

Broad pre-build planning is complete. A capable engineering team or coding AI can begin Stage 1 repository bootstrap and the first vertical slice immediately using:

- Document 11 for scope, stages, gates, and vertical-slice sequencing
- Document 12 Version 1.4 for monorepo layout, FastAPI modular-monolith structure, Python worker mechanics, database conventions, auth integration, API design, and deployment/testing expectations
- Documents 01–10 for product, experience, entitlement, and data-architecture authority (with Document 10 backend language superseded only as recorded in Section 0.2.1)

**Repository-bootstrap blockers:** None introduced by this correction pass. Founder/commercial decisions classified in Document 11 §26 (for example `FL-DEC-003` payment provider, `FL-DEC-021` Super Admin Entitlement policy) remain governed at their natural implementation point and do not block monorepo bootstrap, schema foundation, identity shell, or Stage 1 vertical-slice start.


---

# 26. Stage Vocabulary and Build-Artifact Naming Errata

> **Amendment — 2026-09-12 (additive, dated per Document 08 §25.3). Naming reconciliation
> only: no scope, schema, or stage-definition change. Document 11 §17 remains the sole
> stage authority.**

## 26.1 The collision

Document 11 §17 defines the canonical implementation stages:

| Stage | Name |
|---|---|
| 1 | Platform Foundation |
| 2 | Business Presence |
| 3 | Discovery |
| 4 | Commerce |
| 5 | Reservations |
| 6 | Relationships, Leads, Memberships, and Workforce Completion |
| 7 | Platform Completion |
| 8 | Launch Validation |

Build artifacts in the repository do **not** consistently use that vocabulary. An earlier
"kernel stage" numbering (1–9) was used for migration filenames and the engineering notes
in `apps/api/docs/`, and both schemes now coexist under the same `stageN` prefix in the
same directories — for example `20260727040000_stage3_location_people_kernel.sql` and
`20260728000000_stage3_marketplace_discovery.sql`, which belong to different stages in
different systems.

The practical consequence is the one that matters: **a stage number read off a migration
filename, a commit message, or an `apps/api/docs/` note is not necessarily a Document 11
stage**, so "which stage are we in" cannot be answered from artifact names. That ambiguity
is the reason this errata exists.

## 26.2 Rule going forward

`stageN` in any **new** migration, document, branch, or commit message refers to the
**Document 11 §17** stage. The legacy "kernel stage" vocabulary is **closed** — do not
extend it, and do not introduce a third scheme.

Applied migration filenames are **not** renamed: they are immutable once applied, and
renaming them would break migration history for no product gain.

## 26.3 Errata map

The right-hand column is **derived** from each artifact's content rather than from a prior
record. It is written down so the ambiguity is resolved once instead of rediscovered, and
should be confirmed at the next review rather than treated as previously approved.

| Artifact (legacy label) | Document 11 stage it actually serves |
|---|---|
| `20260727040000_stage3_location_people_kernel.sql`, `apps/api/docs/stage-3-location-people-kernel.md` | **Stage 1** — Platform Foundation (Locations from day one, Team & Access) |
| `20260727050000_stage4_customer_relationships_kernel.sql`, `stage-4-customer-relationships-kernel.md` | **Stage 6** — Customer Relationships at Basic depth |
| `20260727060000_stage5_inventory_offerings_kernel.sql`, `stage-5-inventory-offerings-kernel.md` | **Stage 2** (Offerings foundation) and **Stage 4** (Inventory, Basic) |
| `20260727070000_stage6_orders_kernel.sql`, `stage-6-orders-kernel.md` | **Stage 4** — Commerce |
| `20260727080000_stage7_bookings_kernel.sql`, `stage-7-bookings-kernel.md` | **Stage 5** — Reservations |
| `stage-8-finance-accounting-scope-verification.md` | Scope-verification note; maps to **no** Document 11 stage |
| `20260727090000_stage9_payments_kernel.sql`, `stage-9-payments-kernel.md` | **Stage 4** — Commerce (Payments) |
| `20260728000000_stage3_marketplace_discovery.sql`, `stage-3-marketplace-discovery.md` | **Stage 3** — Discovery *(already aligned)* |
| `20260729000000_stage4_fulfilment_commerce.sql`, `stage-4-commerce-completion.md` | **Stage 4** — Commerce *(already aligned)* |
| `20260730000000_stage5_workforce_booking_providers.sql`, `stage-5-reservations-completion.md` | **Stage 5** — Reservations *(already aligned)* |
| `20260731000000_stage6_leads_memberships_kernel.sql` | **Stage 6** *(aligned; the `_kernel` suffix is vestigial)* |
| `20260801000000_stage7_core_notifications.sql`, `20260802000000_stage7_rls_role_separation.sql`, `20260802010000_stage7_rls_infra_tables.sql`, `20260803000000_stage7_website_draft_supersede.sql`, `20260804000000_stage7_full_module_registry.sql` | **Stage 7** — Platform Completion *(already aligned)* |
| `20260901000000_razorpay_merchant_credentials.sql`, `20260901010000_website_generation_intake.sql`, `20260901020000_media_storage.sql` | Unprefixed, and correctly so — corrective/additive work inside Stages 2 and 4 |

## 26.4 Consequence for stage claims

A stage is complete only when Document 11's **exit criteria** for it are demonstrated — not
when a migration bearing its number has been applied. Because the numbering above is
ambiguous, **no stage claim should cite a migration filename as its evidence.** Cite the
Document 11 §17 exit criterion and the test or runtime observation that satisfies it.

---
