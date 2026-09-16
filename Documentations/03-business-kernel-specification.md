# Business Kernel Specification v1
*Engineering foundation document — implementation-ready, not aspirational*

> ### ⚠ Reader notice — historical foundation document (added 2026-09-12)
>
> This document has **not been amended since July 2026**. Parts of it have since
> been superseded by approved decisions in Documents 05–12. The text below is
> deliberately left unchanged — this notice is **navigational, not an amendment**,
> and adds no new decision.
>
> **Before implementing anything from this document**, check the governing
> registers: **Document 09 §19**, **Document 10 §36**, **Document 11 §27**, and
> **Document 12 §0.1**. Where they conflict, **Document 12 governs**.
>
> Known-superseded content in this document:
>
> This is the **most superseded** document in the set. It is titled
> "implementation-ready", and it is no longer that. Do not implement from it
> without checking each item below.
>
> | Content here | Governing position |
> |---|---|
> | **ULID** identifiers (§1.1, and the "Why ULID" rationale) | **UUIDv4** stored as PostgreSQL `uuid`, via `gen_random_uuid()` — **Document 12 §5.4**. Chronology comes from explicit timestamps, never from identifier values. |
> | Roles `owner` / `manager` / `staff` / `delivery_partner` (§5.1) | Invariant roles are **Primary Owner, Manager, Member**. Job functions (including Delivery Partner) are **permission templates** — Document 06 §4; `D10-CONFLICT-002` |
> | `catalog-orders` as one module (§2.4) | Separate `offerings-catalog` and `orders` — Document 08 §22; `D10-CONFLICT-004` |
> | `booking-calendar`, `analytics-basic` and other legacy module IDs | Document 08's canonical 21-module registry — `D11-CONFLICT-010` |
> | `business-profile` and `website` as installable modules (§2.4) | Both are **Platform Core**, not optional modules — Document 08 §6; `D10-CONFLICT-003` |
> | Capability computation without Entitlement input (§1.7) | **Commercial Entitlement is a first-class input** to capability computation — Document 08 §3.5; `D10-CONFLICT-001` |
> | Hard delete on module uninstall (§2.2) | Deactivation **retains** data; hard delete is a separate explicit action — Document 08 §7.4; `D10-CONFLICT-005` |
> | Events as the **exclusive** cross-module mechanism (§3.1, Rule 6) | Immediate cross-domain needs use **stable public contracts**; events govern asynchronous effects. Cross-module table access and event request/response stay prohibited — Document 10 §9.2; `D10-CONFLICT-009` |
> | Blanket prohibition on service-role bypass (§5.2, Rule 22) | Narrowly enumerated, tenant- or platform-scoped, minimum-privilege, **separately audited** privileged operations are permitted server-side — Document 10 §6.3; `D10-CONFLICT-011` |
> | Admin impersonation (§5.3) | Prohibited. Super Admin work uses **explicit attributed** Admin context — Document 06 `ADMIN-ACCESS-003`; `D10-CONFLICT-008` |
> | Supabase Auth and RLS as fixed implementation (§§5.2, 6.2) | Treated as the **initial implementation choice**; JWT auth, tenant isolation, and privileged-credential governance stay vendor-agnostic — `D10-CONFLICT-007` |
>
> What **remains governing** from this document: Business as the tenant root, the
> thin-Business/modules-carry-the-type shape, the module contract concept, the
> event-bus and audit-log foundations, and the JSONB settings/metadata split.

---

Scope discipline stated once, up front, because it governs every decision below: **the kernel is the only thing that has to be right on day one.** Everything in this document is buildable incrementally, but the *shape* of the kernel — domain model, module contract, event system, permission model — cannot be retrofitted cheaply later. Where a choice trades a little extra day-one effort for avoiding a future rewrite, this document always takes that trade.

---

## 1. Core Domain Model

### 1.1 Business — the root entity

`Business` is the single source of truth every renderer, module, and AI context reads from. It is intentionally thin — most of what makes a business "a salon" vs. "a bakery" lives in installed modules, not on this entity.

```typescript
interface Business {
  id: string;                    // ULID, not auto-increment — sortable, globally unique, safe to expose in URLs
  slug: string;                  // public URL segment, unique, mutable with redirect history
  identity: BusinessIdentity;
  profile: BusinessProfile;
  type: BusinessType;
  configuration: BusinessConfiguration;
  settings: BusinessSettings;    // JSONB — see Section 6
  metadata: BusinessMetadata;    // JSONB — see Section 6
  state: BusinessState;
  status: BusinessStatus;
  visibility: BusinessVisibility;
  capabilities: BusinessCapability[];   // derived, cached — see 1.9
  installedModules: InstalledModule[];  // see Section 2
  createdAt: DateTime;
  updatedAt: DateTime;
}
```

**Why ULID, not UUID v4 or serial int:** ULIDs are lexicographically sortable by creation time (useful for default ordering without an extra index/column) while remaining globally unique and non-guessable (unlike serial ints, which leak business count and are enumerable). This single choice removes a category of future migration pain.

> **Superseded — Document 12 §5.4 (recorded 2026-09-12).** The platform standardised
> on **UUIDv4** stored as a PostgreSQL `uuid`, generated by `gen_random_uuid()`. The
> ULID rationale above is retained as history and is **not** the implemented decision;
> UUIDv4 avoids a custom extension, a fictional `gen_ulid()`, and an extra identifier
> library, and sortable IDs did not justify that infrastructure at First Launch.
> Chronology is derived from explicit timestamps plus ID as a tie-breaker, never from
> identifier values.

### 1.2 Business Identity — who they legally/practically are

```typescript
interface BusinessIdentity {
  legalName: string | null;      // optional at signup, required before certain modules (Payments, Invoicing)
  displayName: string;           // what renders everywhere publicly
  ownerId: string;                // references BusinessMember with role=owner
  category: string;               // e.g. "home_food" — references BusinessType.id
  subCategory: string | null;     // e.g. "pickles_and_thokku"
  registrationDetails: RegistrationDetails | null;  // GST/FSSAI/etc — nullable, extends toward Digital Passport later
}
```

### 1.3 Business Profile — the public-facing content

```typescript
interface BusinessProfile {
  description: string;
  logoAssetId: string | null;
  coverAssetId: string | null;
  contact: ContactInfo;
  locations: BusinessLocation[];       // see 1.10 — array from day one, even if v1 only ever populates one
  branding: BusinessBranding;          // theme selection + overrides, see Section 4
  statistics: BusinessStatistics;      // derived/cached, see 1.9
  trust: BusinessTrust;                // derived/cached, see 1.9
}
```

### 1.4 Business Type — the manifest that drives everything

```typescript
interface BusinessType {
  id: string;                    // "home_food", "salon", "clinic" — stable, never reused
  label: string;
  defaultModules: string[];      // module ids provisioned at signup
  requiredModules: string[];     // subset of defaultModules that cannot be uninstalled
  onboardingSchema: OnboardingSchema;   // drives the adaptive onboarding flow
  defaultPageSections: PageSectionTemplate[];
}
```

**This table is data, populated by seed/migration, never by application code branching on a category string.** The single engineering rule this whole document exists to protect: *if you ever find yourself writing `if (business.type === 'salon')` inside a module or the kernel, the architecture has failed and something belongs in `BusinessType` config or a module capability check instead.*

### 1.5 Business Configuration vs. Business Settings vs. Business Metadata — three distinct JSONB surfaces, not one junk drawer

This distinction is worth being explicit about because "just put it in JSONB" is exactly how kernels rot:

- **`configuration`** — structural choices that affect which modules/capabilities are active (e.g. `{ deliveryEnabled: true, bookingRequiresApproval: false }`). Read by the kernel and modules to make behavioral decisions. Changes here can trigger capability recalculation (1.9).
- **`settings`** — user-facing preferences that don't change behavior, only presentation/defaults (e.g. `{ defaultCurrency: "INR", weekStartsOn: "monday" }`). Read by renderers, never by business logic branching.
- **`metadata`** — arbitrary, module- or vertical-specific extension data that doesn't warrant a first-class column (e.g. a clinic's `{ insuranceAccepted: [...] }`). Owned per-key by whichever module wrote it; the kernel never reads into `metadata` directly — only modules read the keys they themselves own.

Enforcing this split in code review (not just documentation) is one of the 30–50 principles in Section 8.

### 1.6 Business State vs. Status vs. Visibility — three axes, not one enum

A single `status` enum tempting to reach for (`draft | live | suspended | archived`) conflates three genuinely independent questions and becomes unmanageable within a year. Model them separately:

```typescript
type BusinessState = 'onboarding' | 'active' | 'dormant' | 'closed';        // lifecycle stage
type BusinessStatus = 'in_good_standing' | 'under_review' | 'suspended';    // platform trust/compliance standing
type BusinessVisibility = 'private' | 'unlisted' | 'discoverable';          // who can find it — separate from whether it's live
```

A business can be `active` + `in_good_standing` + `unlisted` (fully operational, just opted out of marketplace discovery) — that combination is common and must be expressible without hacks.

### 1.7 Business Capabilities — derived, not stored as truth

```typescript
type BusinessCapability = 'can_receive_orders' | 'can_take_bookings' | 'can_process_payments' | 'can_appear_in_marketplace' | ...;
```

Capabilities are **computed** from `(installedModules, configuration, status)` — never hand-set. A business "can receive orders" if and only if the Orders module is installed, active, and status permits it. This computed layer is what every permission check and renderer condition against — never against raw module lists — so that the *rule* for "what makes a business order-capable" lives in exactly one function, not scattered across every consumer.

### 1.8 Business Members, Roles, Permissions — see Section 5 in full; the entity shape:

```typescript
interface BusinessMember {
  id: string;
  businessId: string;
  userId: string;
  role: BusinessRole;             // 'owner' | 'manager' | 'staff' | 'delivery_partner'
  modulePermissions: ModulePermissionGrant[];  // fine-grained overrides, see Section 5
  status: 'active' | 'invited' | 'removed';
}
```

### 1.9 Statistics, Health, Trust — derived state, computed asynchronously, never inline

```typescript
interface BusinessStatistics {
  responseTimeMinutesP50: number;
  fulfillmentRate: number;
  repeatCustomerRate: number;
  updatedAt: DateTime;             // staleness must be visible — never silently cached forever
}

interface BusinessTrust {
  score: number;                   // 0–100
  breakdown: TrustSignalBreakdown; // per-signal contribution, for transparency and debugging
  lastComputedAt: DateTime;
}
```

**Engineering rule:** these are never computed synchronously in a request path. They're recomputed by a background worker reacting to events (Section 3) and cached on the `Business` row for fast reads — the kernel never blocks a page render on a trust-score recalculation.

### 1.10 Locations, Assets, Documents — supporting entities

`BusinessLocation` (address, geo point, hours, service radius — array per business from day one, even though v1 UI only exposes one, to avoid a schema migration when multi-branch ships). `BusinessAsset` (uploaded media: images/video, with a `purpose` enum — logo/cover/gallery/product — rather than separate columns per purpose, so new asset purposes don't require migrations). `BusinessDocument` (verification documents, certificates — the seed of the Digital Passport, deliberately modeled from day one even though the passport feature itself is Horizon 3+, because retrofitting document storage onto a live system is painful and this costs almost nothing to include now).

---

## 2. Module Architecture

### 2.1 What is a module

A module is a **self-contained unit of business capability** that declares four contracts and nothing else touches the kernel directly:

```typescript
interface ModuleManifest {
  id: string;                      // "orders", "booking", "ai-whatsapp-manager"
  version: string;                 // semver
  dataContract: {
    ownedTables: string[];         // tables this module exclusively writes to
    extendsBusinessMetadataKeys: string[]; // metadata keys this module owns
  };
  uiContract: {
    dashboardWidgets: WidgetDefinition[];
    publicPageSections: SectionDefinition[];
  };
  eventContract: {
    emits: string[];               // event types this module can emit
    subscribesTo: string[];        // event types this module reacts to
  };
  dependencies: string[];          // other module ids required to be installed first
  requiredPermissions: Permission[];
  configSchema: JSONSchema;        // validates per-business module configuration
}
```

### 2.2 Module lifecycle

`registered → installable → installed(pending_config) → active → (optionally) suspended → uninstalled`

- **Installation**: kernel validates `dependencies` are already installed, validates `configSchema` against submitted config, writes an `InstalledModule` row, emits `module.installed`.
- **Activation**: separate from installation deliberately — a module can be installed (tables provisioned, config saved) but not yet active (e.g. Payments installed but merchant hasn't completed KYC) — renderers and capability checks (1.7) only honor `active` modules.
- **Configuration**: module-specific config lives in `InstalledModule.config` (JSONB, validated against the module's own `configSchema` — never a kernel-level schema, since the kernel must not know what any given module's config looks like).
- **Dependency resolution**: enforced at install time only (not continuously) — if a dependency is later uninstalled while a dependent module is active, the kernel blocks the uninstall and surfaces which dependents require it.
- **Versioning**: modules are versioned independently; the kernel stores `InstalledModule.moduleVersion` per business, allowing gradual rollout of a new module version across the merchant base rather than a global flip.
- **Marketplace distribution** (Horizon 4, per the strategic blueprint — architected for now, not activated): the manifest shape above is exactly what an external developer would submit; internal modules are simply manifests with `publisher: 'platform'`.
- **Removal**: soft-uninstall by default (deactivate, retain data for a grace period) — hard delete of module data is a separate, explicit, confirmed action, never a side effect of uninstalling.
- **Migration**: each module owns its own schema migrations for its own tables (Section 6) — the kernel never runs a migration on a module's behalf, preserving the "modules don't require kernel changes to evolve" property.

### 2.3 Module Registry

A `modules` table (the manifest, versioned) + a `business_modules` table (which business has which module, at which version, with what config, in what lifecycle state) — this is the literal data-model expression of "business type is just a bundle of modules."

### 2.4 Reference modules (illustrative, not exhaustive)

`website` (core), `catalog-orders`, `booking-calendar`, `inquiry-leads`, `inventory`, `crm`, `payments`, `whatsapp-notifications`, `ai-whatsapp-manager`, `reviews`, `analytics-basic` — each conforming to the exact same `ModuleManifest` shape regardless of how simple or complex.

---

## 3. Event System

### 3.1 Principle

**Every meaningful business action is an event. Modules never call each other's functions directly — they emit and subscribe.** This is the single mechanism that lets "hundreds of categories without rewriting the core" be true rather than aspirational.

### 3.2 Event shape

```typescript
interface BusinessEvent {
  id: string;               // ULID
  businessId: string;
  type: string;              // "order.created", "appointment.confirmed", "review.submitted"
  payload: Record<string, unknown>;
  emittedByModule: string;
  occurredAt: DateTime;
  causationId: string | null;  // the event/command that caused this one — for tracing chains
  correlationId: string;       // groups events from one logical business action
}
```

### 3.3 Example flow: `order.created`

1. Catalog-Orders module writes the `orders` row, then emits `order.created` with `{ orderId, businessId, customerId, totalAmount, items }`.
2. Event bus persists the event (append-only `events` table — this table is itself the audit log, Section 1 doesn't need a separate one) and fans it out to subscribers.
3. **CRM module** subscribes to `order.created` → updates `customers.lastOrderAt`, increments `customers.orderCount`.
4. **Statistics worker** subscribes → recomputes `BusinessStatistics.fulfillmentRate` asynchronously (debounced, not per-event).
5. **WhatsApp-Notifications module** subscribes → sends order confirmation.
6. **AI Marketing module** (once installed) subscribes → may later correlate with `inventory.low_stock` events to suggest a clearance offer, entirely independent of Orders knowing Marketing exists.

### 3.4 Delivery guarantees, retries, failure

- **At-least-once delivery**, idempotent consumers required (every subscriber handler must be safe to run twice on the same event — enforced via an `event_id` idempotency check on the consumer side, not assumed).
- **Retry policy**: exponential backoff, 5 attempts, then to a dead-letter table (`failed_events`) surfaced in the admin platform (Section 8's admin-observability principle) — a silently dropped event is treated as a production incident, not a log line.
- **Ordering**: guaranteed only *within* a single `businessId` + event `type` pair, not globally — this is a deliberate, documented relaxation that keeps the implementation simple (a single Postgres-backed queue partitioned by business, not a globally-ordered log) and is sufficient because cross-business ordering is never a real requirement.

### 3.5 Realtime updates

Dashboard "new order appeared without refresh" is powered by the same event bus — the kernel publishes select event types to a realtime channel (Postgres `LISTEN/NOTIFY` → Supabase Realtime, or equivalent) scoped to `businessId`, which the dashboard subscribes to on load. **Realtime is a subscriber to the same events everything else reacts to, not a separate system** — this avoids the common failure mode of realtime and "true" state silently diverging.

### 3.6 Implementation choice at MVP scale

Postgres as the event log (`events` table) + Postgres `LISTEN/NOTIFY` or a polling worker for fan-out, not a separate message broker (Kafka/RabbitMQ) at this stage — the pattern (events, subscribers, retries, idempotency) is what matters architecturally; the infrastructure can be upgraded to a dedicated broker later **without changing a single module's code**, because modules only ever interact with an abstract `EventBus` interface, never the underlying transport.

---

## 4. Rendering Architecture

### 4.1 Principle

**One `Business` aggregate, many renderers. Renderers read; they never write, and they never contain business logic.**

```typescript
interface BusinessRenderer<TOutput> {
  render(business: BusinessAggregate, context: RenderContext): TOutput;
}
```

Where `BusinessAggregate` is the fully-assembled read model (Business + installed modules' public data + computed capabilities) — assembled once by a `BusinessAggregateLoader`, then handed to whichever renderer needs it, so every surface renders from an identical shape of data.

### 4.2 The renderers

- **PublicSiteRenderer** → server-rendered HTML/Next.js pages from `profile`, active modules' `publicPageSections`, and `branding` (Design Bible tokens applied here).
- **MarketplaceListingRenderer** → a condensed projection (card view) of the same aggregate, plus marketplace-specific ranking data (Trust Score).
- **DashboardRenderer** → the merchant-facing app; reads the aggregate scoped to the authenticated member's permissions (Section 5), renders each installed module's `dashboardWidgets`.
- **AdminRenderer** → reads the aggregate with elevated scope (no permission filtering on read, full audit log visibility).
- **CustomerPortalRenderer** → a business-agnostic renderer that reads *across* many businesses' aggregates for a given customer (order history, favourites) — the one renderer that legitimately spans multiple `Business` aggregates at once, and is called out explicitly because it's the one exception to "one business per render" and needs its own care around the data-ownership boundary discussed in the strategic blueprint (merchant-owned vs. platform-owned customer data).
- **AIContextRenderer** → serializes the aggregate into a structured context object for AI employees (Section 6, prior blueprint) — same source data, formatted for model consumption instead of DOM/JSON-for-humans.
- **DeveloperAPIRenderer** → the external-facing REST/GraphQL representation (Section 7) — versioned independently of internal renderers so internal refactors never break third-party integrations.

### 4.3 The rule that keeps this from rotting

**A renderer may format, filter by permission, and paginate. It may never compute a business rule.** If a renderer needs to decide "is this business allowed to show a Book Now button," that decision comes from `business.capabilities` (already computed by the kernel, 1.7), never from the renderer re-deriving it from raw module state. Violating this is the single fastest way to end up with six slightly-different definitions of "is this business bookable" scattered across six renderers — explicitly called out as a banned pattern in Section 8.

---

## 5. Permission System

### 5.1 Two layers: coarse role, fine module-grant

```typescript
type BusinessRole = 'owner' | 'manager' | 'staff' | 'delivery_partner';
type PlatformRole = 'customer' | 'admin' | 'developer';

interface ModulePermissionGrant {
  moduleId: string;
  actions: ('read' | 'write' | 'manage')[];  // 'manage' includes config/uninstall rights
}
```

- **Owner**: implicit `manage` on every installed module, cannot be revoked, exactly one per business (transferable, never dual).
- **Manager**: `write` by default on all modules unless explicitly restricted; can invite/remove `staff`.
- **Staff**: no access by default — every module grant is explicit (safer default for a segment where "staff" often means a family member or part-timer who shouldn't see revenue by default).
- **Delivery partner**: a restricted role scoped to exactly the Orders/Delivery modules, read access to assigned orders only — modeled as a distinct role rather than a restricted staff grant because its permission shape is fundamentally different (no dashboard access at all, a purpose-built minimal view).

### 5.2 Enforcement point

**Permissions are enforced once, in the kernel's data-access layer (via Postgres Row Level Security, consistent with the multitenancy approach), never re-implemented per-renderer or per-API-route.** A renderer or API handler that bypasses RLS by using a service-role key to "make things easier" is a banned pattern (Section 8) — every merchant-scoped read/write goes through the RLS-enforced path, no exceptions, including internal admin tools (which use a distinct, explicitly-audited elevated role, not a silent bypass).

### 5.3 Platform-level roles

`admin` (internal, full read + moderation write, every action audit-logged), `developer` (Horizon 4, scoped to the module they've published — can read aggregate/API data only within the permission scope a merchant explicitly grants when installing their module), `customer` (scoped to their own `CustomerPortalRenderer` data plus whatever a business's `visibility`/`capabilities` expose publicly).

---

## 6. Database Design

### 6.1 Relational core + JSONB edges — restated, made concrete

Every entity in Section 1 that needs querying/filtering/reporting is a real table with real columns. `configuration`, `settings`, `metadata` (1.5) are the only sanctioned JSONB catch-alls at the `Business` level; every module is free to use JSONB *within its own owned tables* for genuinely variable, module-specific shape (e.g. `order_items.variant_selections jsonb`), but core relational facts (`order_items.product_id`, `.quantity`, `.price_at_order`) are always real columns — never buried in JSON — because reporting/analytics (and eventually the Business Graph) depend on being able to query them directly.

### 6.2 Multitenancy

Single Postgres database, `business_id` as a tenant key on every business-scoped table, enforced via **Row Level Security** policies keyed off `auth.uid()` → `business_members.user_id` → `business_members.business_id`. Every table gets a policy of the shape:

```sql
create policy "tenant_isolation" on orders
  using (business_id in (
    select business_id from business_members where user_id = auth.uid()
  ));
```

Module-owned tables inherit this same pattern — the kernel provides a reusable policy-generation convention (Section 9's Module SDK) so every new module gets correct tenant isolation without a developer hand-writing RLS from scratch each time, which is where isolation bugs actually happen in practice.

### 6.3 Polymorphism

Used sparingly and only where genuinely polymorphic (e.g. `assets` table with a `purpose` enum rather than `logo_asset`/`cover_asset`/`gallery_asset_1` columns; `notifications` with a `channel` + `payload jsonb` rather than per-channel tables). Avoided for anything with real relational shape (orders, appointments, products stay dedicated tables, never a generic `entities` polymorphic table — the "everything is a generic entity" pattern looks flexible early and becomes unqueryable and untypeable within a year).

### 6.4 Search

Postgres full-text search (`tsvector` columns + GIN indexes) on business profile/catalog data for MVP-scale marketplace search — sufficient for tens of thousands of businesses. A dedicated search service (Elasticsearch/Typesense/Meilisearch) is a Horizon 2–3 upgrade once faceted search (rating/distance/availability filters combined with full-text) outgrows what Postgres GIN indexes comfortably handle — the migration path is clean specifically because the `MarketplaceListingRenderer` (4.2) already reads from one abstracted query interface, not raw SQL scattered across the codebase.

### 6.5 Media

Assets stored in object storage (Supabase Storage/S3-compatible), referenced by `id` from the `assets` table, never as raw URLs embedded in JSONB blobs — this indirection is what makes CDN migration, image-variant generation (thumbnails), and access-control on private documents (Business Documents, 1.10) possible later without a data migration.

### 6.6 Indexing baseline

Every foreign key indexed by default (not optional). `(business_id, created_at)` composite indexes on every high-write table (orders, appointments, events) since "recent activity for this business" is the single most common query shape across the whole product. Partial indexes for common filtered queries (e.g. `where status = 'pending'`) rather than filtering large indexes at query time.

---

## 7. API Philosophy

- **Internal (merchant dashboard, admin, public site)**: Next.js Server Actions / RSC data fetching directly against the kernel's data-access layer (RLS-enforced) — no need for a separate internal REST API at MVP scale; adding one prematurely is unnecessary indirection for calls that never leave the same deployment.
- **External-facing (Developer Platform, Horizon 4)**: a versioned REST API (`/v1/...`) generated from the same `ModuleManifest` contracts modules already implement internally — this is only credible because internal modules were built against the same contract shape from day one (2.1), so "expose it externally" is a permissions and rate-limiting layer, not new engineering.
- **Realtime**: WebSocket/Supabase Realtime subscriptions scoped to `business_id`, layered on the event bus (3.5) — never a bespoke polling mechanism per feature.
- **Webhooks**: outbound, for merchants/developers who want to receive events into their own systems (e.g. a merchant piping orders into their own accounting tool) — implemented as just another event-bus subscriber (an internal "webhook dispatcher" module that matches the exact same `ModuleManifest` shape as any other module), not a special-cased system.
- **Authentication**: Supabase Auth (JWT-based), phone-OTP-first for merchants (matches the target user's comfort level far more than email/password), OAuth for any future staff/admin SSO needs.
- **Authorization**: enforced at the data layer (RLS, Section 5.2), never trusted from a client-supplied role claim alone — every write path re-validates against the database's own permission state.
- **Versioning**: internal APIs (Server Actions) version implicitly with deploys (no external consumers to break); the external Developer API versions explicitly (`/v1`, `/v2`) with a documented deprecation window once it exists.

---

## 8. Engineering Principles

Thirty-eight rules, grouped, meant to be enforced in code review, not just documented:

**On the kernel and business logic**
1. `Business` is the single source of truth; no renderer, cache, or module may hold a conflicting copy of core identity/state.
2. No business-type-specific code (`if business.type === X`) is permitted in the kernel, ever — that logic belongs in `BusinessType` config or a module.
3. Business capabilities (1.7) are always computed, never hand-set or cached indefinitely without an invalidation path.
4. The kernel never blocks a request on a derived/statistical computation (trust score, analytics) — those are always async.
5. `configuration`, `settings`, and `metadata` are not interchangeable — enforce the distinction from Section 1.5 in review.

**On modules**
6. Modules never import or call another module's code directly — only the event bus and the kernel's public data-access layer.
7. A module's owned tables are never written to by any other module.
8. Every module ships a `configSchema`; unvalidated module config is a merge blocker.
9. Module dependency cycles are rejected at manifest-registration time, not discovered at runtime.
10. A module must be safely uninstallable (soft, with grace period) without corrupting kernel state.
11. New business categories are additions to `business_types` data, never new module code paths.
12. Modules must degrade gracefully if a dependency is installed-but-inactive (never assume "installed" implies "active").

**On events**
13. Every meaningful business action emits an event — "meaningful" is defined as anything another module could plausibly need to react to, now or later.
14. Event consumers must be idempotent; "this event was already processed" is a normal code path, not an edge case.
15. Failed event processing goes to a visible dead-letter queue, never a silent catch-and-log.
16. Event payloads are versioned; a consumer must handle payload shape changes without crashing.
17. No module reaches into another module's database tables to "just check something quickly" instead of subscribing to an event — this is the single most common architecture-erosion shortcut and is explicitly banned.

**On rendering**
18. Renderers format and filter; they never compute business rules.
19. Every renderer reads from the same `BusinessAggregate` shape — no renderer maintains its own bespoke query for "what is this business."
20. Public-facing renderers never expose data a business's `visibility`/permissions wouldn't otherwise allow.
21. A UI change (new dashboard widget, new page section) should never require a kernel schema change — if it does, the module boundary was drawn wrong.

**On permissions and data**
22. All merchant-scoped data access goes through RLS; no service-role bypass in application code, including internal tools.
23. Staff permissions default to none, not "everything except X" — least privilege by default.
24. Every write that changes money, orders, or bookings is logged in a way that's independently auditable from the `events` table.
25. Customer data ownership (merchant-owned vs. platform-owned, per the strategic blueprint) is enforced at the schema/RLS level, not as a UI-only convention.

**On database**
26. Every foreign key is indexed; this is checked in migration review, not left to "add it when it's slow."
27. JSONB is for genuinely variable or module-private data only — anything queried/reported on gets a real column.
28. No polymorphic "generic entity" tables for anything with real relational shape.
29. Migrations are owned per-module (or kernel, for kernel tables) — no cross-cutting migration touches another module's tables.
30. Every table has `created_at`/`updated_at`; soft-delete (`deleted_at`) is the default over hard delete for anything customer- or merchant-visible.

**On API and integration**
31. Internal and external APIs are versioned independently; an internal refactor must never silently break a third-party integration.
32. Webhooks and external integrations are themselves event-bus subscribers, not special-cased systems.
33. Authorization is always re-validated server-side; a client-supplied role or permission claim is never trusted alone.

**On process and longevity**
34. If a shortcut is taken to hit an MVP deadline, it is logged as tech debt with an explicit owner and a trigger condition for when it must be revisited — not left implicit.
35. No feature ships without its data model surviving a "what does this look like with 50 modules and 10,000 businesses" mental test.
36. Prefer configuration and metadata-driven extension over conditionals, every time there's a real choice between them.
37. A new engineer should be able to build a new module against the SDK (Section 9) without reading kernel source code — if they can't, the module contract is leaking implementation detail.
38. Every kernel-level decision in this document requires an explicit, written justification to change — "it would be faster this way" is not sufficient justification on its own; "here is what breaks later if we don't" is the required bar.

---

## 9. Monorepo Structure

```
/apps
  /merchant-dashboard        # Next.js — dashboard renderer surface
  /public-site               # Next.js — public/marketplace renderer surface (SSR/ISR heavy)
  /admin                     # Next.js — admin renderer surface
  /customer-portal           # Next.js — cross-business customer surface (Horizon 2+)

/packages
  /kernel                    # Business aggregate, capability computation, state machine
    /domain                  # entity types (Section 1)
    /aggregate-loader        # assembles BusinessAggregate for renderers
    /capabilities            # capability computation logic (1.7)

  /modules                   # every module, self-contained
    /website
    /catalog-orders
    /booking-calendar
    /inquiry-leads
    /crm
    /payments
    /whatsapp-notifications
    /ai-whatsapp-manager
    /reviews
    /analytics-basic
    (each module: /schema (its own tables/migrations), /events (emits/subscribes),
     /dashboard-widgets, /public-sections, /manifest.ts)

  /module-sdk                 # the ModuleManifest contract, shared types, RLS policy
                               # generator, event-bus client — what a module author
                               # (internal or, eventually, external) builds against

  /events                     # event bus abstraction, retry/dead-letter handling,
                               # realtime fan-out — transport-agnostic (3.6)

  /renderers                  # shared renderer interfaces + implementations
                               # for surfaces not tied to one app (AI context, API)

  /ui                         # design-bible-derived component library (Section 4
                               # of the Design Bible), shared across all /apps

  /db                         # Supabase/Postgres schema source of truth, migration
                               # tooling, RLS policy conventions

  /auth                       # auth helpers, permission-checking utilities shared
                               # across apps and modules

/workers
  /event-processor            # background event fan-out + retry worker
  /statistics                 # async trust score / business statistics recompute
  /ai-context                 # AI employee execution workers

/infrastructure
  /migrations                 # kernel + module migrations, module-namespaced
  /terraform (or equivalent)  # environment provisioning
```

**Why modules live under `/packages/modules` rather than each being its own top-level app:** they're not independently deployed at this stage (all render inside the shared `/apps`), but they are independently *owned* — a module's schema, events, and UI contributions are self-contained enough that this structure survives the eventual move to independently-versioned/externally-published modules (Horizon 4) without a directory reshuffle.

---

## 10. Build Order to MVP

Each milestone exists to de-risk one specific architectural claim before the next milestone depends on it — this order is not arbitrary.

**Weeks 1–2 — Kernel skeleton, no modules yet.**
`Business`, `BusinessType`, `BusinessMember` tables + RLS policies; capability computation stub; ULID-based IDs throughout. *Why first:* every other milestone assumes this exists and is correct — get the multitenancy/RLS pattern right once, here, before any module copies it.

**Weeks 3–4 — Module registry + one real module (Website/Profile).**
`modules`, `business_modules` tables; `ModuleManifest` contract implemented for the simplest possible module (Business Profile + public page rendering, no transactional logic). *Why second:* proves the module contract end-to-end (install → configure → activate → render) on the lowest-risk module before adding transactional complexity.

**Weeks 5–6 — Event bus + second module (Catalog/Orders) reacting through it.**
Event table, fan-out worker, idempotent consumer pattern; Catalog-Orders module emits `order.created`; a minimal CRM module subscribes and updates a customer record. *Why third:* proves modules-never-call-each-other-directly with a real, meaningful cross-module interaction, before more modules make retrofitting this pattern expensive.

**Weeks 7–8 — Dashboard renderer + realtime.**
`DashboardRenderer`, `BusinessAggregateLoader`, dashboard widget contract; realtime order updates via the same event bus (3.5). *Why fourth:* proves the "one aggregate, many renderers" claim with a second, structurally different renderer (public site vs. dashboard) before building the rest.

**Week 9 — WhatsApp-link ordering module + first real merchant onboarding.**
The MVP-scoped transactional flow from the strategic blueprint, built entirely on the kernel/module/event patterns proven in weeks 1–8 — no new architectural risk here, this week is about proving the *product*, not the kernel.

**Weeks 10–12 — Admin renderer (minimal), permission system hardening, first production merchants live.**
Basic admin view (business list, verification status, manual health checks); staff role + delivery-partner role tested with real permission grants; dead-letter queue visibility. *Why here, not earlier:* admin and fine-grained permissions matter once there's real data and real staff accounts to protect — building them against synthetic data earlier would be guesswork.

**Beyond Week 12:** every subsequent module (Booking, Inventory, AI WhatsApp Manager, etc., per the strategic blueprint's horizons) is now a **repeatable, de-risked process** — implement `ModuleManifest`, write RLS via the SDK's generator, subscribe to/emit events, ship a dashboard widget and/or public section. The point of weeks 1–12 is that this sentence is actually true by week 13, not aspirational.
