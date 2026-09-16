# Data & Technical Architecture

**Document:** 10
**Document Status:** Canonical foundation
**Version:** 1.2
**Date:** July 2026 (Version 1.2 amendment: September 1, 2026)
**Authority:** Technical architecture specification for implementation planning
**Depends On:** `01-vision-document.md` · `02-product-experience-bible.md` · `03-business-kernel-specification.md` · `04-master-product-specification.md` · `05-user-context-journey-navigation-architecture-specification.md` · `06-role-permission-access-experience-matrix.md` · `07-business-type-configuration-profile-specification.md` · `08-plans-modules-entitlement-model.md` · `09-complete-page-by-page-product-experience.md`
**Conflict resolution:** Where Documents 01–08 conflict with later approved decisions in Documents 05–09, this document reflects the latest approved canonical direction. The Conflict Register is in Section 36.

**Document Control**

| Version | Date | Change |
|---|---|---|
| 1.0 | July 2026 | Initial canonical Data & Technical Architecture. |
| 1.1 | July 12, 2026 | Refined synchronous and event-driven module communication, required durable webhook receipt before acknowledgement, clarified RLS and privileged backend access, and classified implementation-readiness decisions by actual blocking scope. |
| 1.2 | September 1, 2026 | Additive amendment (Website Generation Overhaul work order), recorded per Document 08 §25.3 — decisions made now. §11.3 and §11.4 gain the AI content-authorship boundary, the one-shot structured-intake generation model, and the design-reference-translation rule for prebuilt templates (Option A). No entity, schema, or contract change. |

---

# 1. Architectural Principles

These principles govern every technical decision and trade-off in this platform. They are not aspirational — they are gates for implementation planning.

**ARCH-001 — Modular monolith first.** The initial architecture is a well-structured monolith with clean internal boundaries. Progressive extraction to separate services occurs only when a specific, measurable scale requirement demands it — not to look sophisticated.

**ARCH-002 — Clear domain boundaries.** Every domain has an owner. A module never reads or writes another module's database tables and never imports or depends on another module's internal implementation details. Synchronous cross-domain communication may use an explicit, stable public service or interface contract when an immediate result is required. Asynchronous reactions, propagation, integration side effects, and decoupled workflows use domain events. Ownership and write authority remain strict regardless of communication mechanism.

**ARCH-003 — One platform, not one per Business type.** There is one codebase, one data store, one deployment. Business type is configuration data, not a code branch. If `if (businessType === 'salon')` appears in application logic, the architecture has failed. That logic belongs in configuration or capability checks.

**ARCH-004 — Multi-tenant by Business.** Business is the primary tenant boundary. Every Business-owned resource has a clear ownership path. Tenant isolation is enforced at the data layer wherever the database execution context supports RLS, in addition to server-side authorization and explicit tenant-scoped queries. Privileged connections that can bypass RLS require separate, explicit tenant enforcement.

**ARCH-005 — Location-aware where applicable.** Location is a subordinate scope within a Business. A Location never becomes its own tenant. Location variation lives inside one canonical Business entity.

**ARCH-006 — Server-authoritative security.** Authorization is always re-evaluated server-side. Hidden UI elements, frontend route guards, and client-supplied role claims are never the sole enforcement mechanism.

**ARCH-007 — Entitlement separate from permission.** Commercial Entitlement (what a Business may use) and user Permission (what a person may do) are independent gates. One gate passing does not imply another. This distinction must be maintained in data models, services, and enforcement points.

**ARCH-008 — Structured Website system.** The Website is a structured, configuration-driven rendering system, not a free-form visual builder or arbitrary code generator. AI generates structured Website configuration, not arbitrary source code.

**ARCH-009 — Provider abstraction.** External providers (payment, email, SMS, AI models, maps, search) are accessed through platform-owned interfaces. Provider-specific objects never become the canonical domain model.

**ARCH-010 — Event-capable architecture.** Meaningful domain actions emit events. Modules do not access another module's tables or internal code. Immediate cross-domain results use explicit, stable public service or interface contracts; asynchronous reactions, propagation, integration side effects, and decoupled workflows use domain events. Events must not imitate synchronous request/response behavior when a direct public contract is clearer and safer. The event infrastructure starts simple and can be upgraded without changing module code; this contract does not imply separate deployable services.

**ARCH-011 — AI as a governed platform capability.** AI acts through approved platform tools with permission checks, Entitlement checks, Business context boundaries, and audit. AI cannot bypass normal platform authorization.

**ARCH-012 — Progressive extraction only when scale genuinely requires it.** The architecture must not be decomposed into microservices before scale demands it. Every service boundary has a cost. That cost is only worth paying when a specific, proven requirement justifies it.

---

# 2. High-Level System Architecture

The platform comprises several distinct logical systems. All may be deployed as one application initially.

```
                    ┌─────────────────────────────────────┐
                    │       Public Platform Experience      │
                    │  Main Website · Marketplace · Auth   │
                    └─────────────────┬───────────────────┘
                                      │
         ┌────────────────────────────┼────────────────────────────┐
         │                           │                             │
 ┌───────▼──────┐          ┌─────────▼────────┐          ┌────────▼──────┐
 │  Business     │          │  Business         │          │ Platform      │
 │  Website      │          │  Workspace        │          │ Super Admin   │
 │  Runtime      │          │  (Authenticated)  │          │               │
 └───────┬──────┘          └─────────┬────────┘          └────────┬──────┘
         │                           │                             │
         └────────────────────────────┼────────────────────────────┘
                                      │
                    ┌─────────────────▼──────────────────┐
                    │      Backend Application Core        │
                    │  (Modular Monolith)                  │
                    │                                      │
                    │  Identity · Context · Business       │
                    │  Kernel · Modules · Entitlement       │
                    │  Authorization · Rendering           │
                    │  Marketplace/Search · AI Runtime     │
                    │  Events · Integrations               │
                    └──────┬──────┬──────┬──────┬────────┘
                           │      │      │      │
                     ┌─────▼┐ ┌───▼──┐ ┌▼────┐ ┌▼─────────────┐
                     │  DB  │ │ OBJ  │ │SRCH │ │  Job Queue   │
                     │(PG)  │ │Store │ │Index│ │  / Events    │
                     └──────┘ └──────┘ └─────┘ └──────────────┘
```

## 2.1 Public Platform Experience

The main platform website explains the two-sided ecosystem and serves as the entry point for consumers and prospective Business owners. The Consumer Marketplace enables search-first discovery of joined Businesses, offerings, and services. Authentication entry points preserve Destination Intent and resolve context after sign-in. These surfaces are public-facing and optimize for fast rendering, SEO, and consumer conversion.

## 2.2 Consumer Experience

My Activity aggregates a person's customer-side history across all Businesses — orders placed, bookings, queue activity, memberships as a customer, and reviews written. This context is explicitly separate from the Business Workspace. One Platform Identity can access both without mixing the activity histories.

## 2.3 Business Website Runtime

Each Business has a public-facing website rendered from structured configuration: page definitions, section types, content, design tokens, and module-contributed capabilities (ordering, booking, menus, gallery, reviews). The renderer is data-driven and Location-aware. It does not execute arbitrary stored code.

## 2.4 Business Workspace

The authenticated Business operating environment. Provides access to Platform Core capabilities and enabled optional module experiences. Navigation and available capabilities vary by Business Entitlement, enabled modules, configuration, Active Location, user role, and permissions. Supports Website management and AI-assisted experiences.

## 2.5 Platform Super Admin

A separate, explicitly elevated operating context for authorized internal actors. Provides platform operations, Business support and diagnosis, Entitlement corrections, and configuration support. Every action is attributed — the platform records who did what, to which Business, at which layer, and why. Silent impersonation is prohibited.

## 2.6 Backend / Application Core

The single backend application initially hosting all domain logic, business rules, authorization, module runtime, rendering, Marketplace/search, integration adapters, and AI orchestration. All surface layers interact with the backend through controlled interfaces; the backend owns all mutable state and enforces all authorization decisions server-side.

---

# 3. Deployment Shape

The recommended startup architecture is a **modular monolith** — one codebase with clean internal boundaries, deployed as a manageable set of processes.

## 3.1 Practical Startup Deployment

```
┌─────────────────────────────────────────────────────────────┐
│  Web / Frontend Application                                  │
│  Next.js — SSR/SSG for public surfaces + React for apps     │
│  Hosts: Platform Website, Marketplace, Business Websites,   │
│          Business Workspace, Consumer Account, Admin         │
└────────────────────────┬────────────────────────────────────┘
                         │
┌────────────────────────▼────────────────────────────────────┐
│  Backend / API Application                                   │
│  Single application, modular internals                       │
│  Handles: API, server actions, authorization, domain logic,  │
│           module runtime, rendering, webhook ingestion       │
└────────┬──────────┬──────────┬──────────┬───────────────────┘
         │          │          │          │
    ┌────▼───┐ ┌───▼───┐ ┌───▼───┐ ┌───▼────────────────┐
    │Primary │ │Object │ │Search │ │Background Job/Event │
    │DB (PG) │ │Storage│ │Engine │ │Queue Processor     │
    └────────┘ └───────┘ └───────┘ └────────────────────┘
         │
    ┌────▼───┐   ┌───────────────────────────────────┐
    │Cache   │   │External Provider Adapters          │
    └────────┘   │(AI, Payment, Email, SMS, Maps...)  │
                 └───────────────────────────────────┘
```

## 3.2 What Remains in One Codebase

All of the following remain in one codebase while retaining clean module boundaries:

- Platform Core logic (Identity, Business Kernel, Locations, Team, Settings, Notifications, Marketplace Presence, Website)
- All 21 optional Business module domains
- AI orchestration layer (not the AI model providers themselves)
- Entitlement and authorization services
- Website rendering engine
- Marketplace and search logic
- Event/job dispatch

## 3.3 What Remains as Infrastructure Dependency

These run as separate infrastructure processes but are not separate application services:

- Primary relational database (PostgreSQL)
- Object/file storage (S3-compatible)
- Search capability (starts with database full-text search; extracted to Typesense/Meilisearch at scale)
- Background job and event processor (starts with database-backed queue; extracted to dedicated broker at scale)
- Cache (Redis or equivalent, where caching is justified)
- CDN for public media assets

## 3.4 Extraction Criteria

A domain is extracted into a separate service only when a specific, measurable requirement is proven: independent scaling need, independent deployment need, separate team ownership, or performance isolation need — not for aesthetic architecture reasons.

---

# 4. Canonical Domain Model

The following entities are defined conceptually. Field inventories are not final; the intent, ownership, and relationships are stable.

## 4.1 Platform-Scoped Entities

### PlatformIdentity
- **Purpose:** One global authenticated identity for one human. Not a permanent user type. A person may act in consumer context, Business context, or Admin context.
- **Ownership:** Platform-scoped.
- **Key relationships:** Has zero or more BusinessMemberships; has one optional ConsumerProfile; may have PlatformAdminGrant.
- **Important:** Never duplicated merely because context changes. A person does not need a separate "merchant account" to also be a consumer.

### PlatformAdminGrant
- **Purpose:** Records explicit elevated platform administration authority for a PlatformIdentity.
- **Ownership:** Platform-scoped.
- **Key relationships:** Belongs to PlatformIdentity.
- **Notes:** Distinct from BusinessMembership. Entry is explicit; not persistent by default.

## 4.2 Business-Scoped Entities

### Business
- **Purpose:** The root tenant entity. One canonical source of truth for Business identity, state, modules, and configuration. Many surfaces render from this one entity.
- **Ownership:** Platform-scoped root; all Business resources scope to it.
- **Key relationships:** Has BusinessIdentity, BusinessProfile, one or more Locations, BusinessMemberships, ModuleStates, Entitlements, CommercialRelationship.
- **Scope:** Business-scoped root — it IS the tenant.

### BusinessIdentity
- **Purpose:** Legal name, display name, Business type reference, registration details (GST, FSSAI), and lifecycle state.
- **Ownership:** Business-scoped.
- **Notes:** `BusinessState` (onboarding/active/dormant/closed), `BusinessStatus` (in_good_standing/under_review/suspended), and `BusinessVisibility` (private/unlisted/discoverable) are separate axes — never one collapsed enum.

### BusinessProfile
- **Purpose:** Public-facing identity content — description, logo, cover, contact, branding/theme, computed trust and statistics.
- **Ownership:** Business-scoped.
- **Key relationships:** Part of Business; references media Assets; owned by Business.

### BusinessTypeProfile
- **Purpose:** A versioned recommendation bundle for a Business category (restaurant, clinic, salon, gym, etc.). Contains recommended modules, suggested terminology, suggested dashboard emphasis, onboarding hints.
- **Ownership:** Platform-scoped (data-driven, not code-branching).
- **Notes:** Advisory only — never grants Entitlement, activates modules, or assigns permissions. `if (businessType === 'salon')` in application logic is a banned pattern.

### BusinessMembership
- **Purpose:** Records that a PlatformIdentity is a member of a Business with a specific core role, Location scope, and permission configuration.
- **Ownership:** Business-scoped.
- **Key relationships:** Belongs to PlatformIdentity and Business; has core Role, PermissionTemplate reference, explicit permission grants, and Location scope.
- **Scope:** Business-scoped; no membership carries across Businesses.

### Role
- **Purpose:** Invariant Business membership authority posture. Exactly three: Primary Owner, Manager, Member. Delivery Partner is an assignment-scoped mode modeled separately.
- **Ownership:** Platform-defined.
- **Notes:** Not configurable by Businesses. Job functions (Accountant, Receptionist, Doctor, Trainer, Cashier) are permission templates, not roles.

### PermissionTemplate
- **Purpose:** Named, reusable preset of permission grants appropriate to a job function. Assigned to a BusinessMembership.
- **Ownership:** Platform-defined (standard templates) or Business-defined (custom templates).

### PermissionGrant
- **Purpose:** Records that a BusinessMembership may perform a specific action on a specific resource type, optionally within a Location scope.
- **Ownership:** Business-scoped.
- **Key relationships:** Belongs to BusinessMembership; may reference module ID and action.

### Location
- **Purpose:** An operational Location or service area of a Business. A Business has one or more Locations from day one.
- **Ownership:** Business-scoped.
- **Key relationships:** Belongs to Business; has address, geo coordinates, opening hours, service areas, per-Location configuration.
- **Notes:** Location is a subordinate scope, never its own tenant. Multiple Locations are modeled from the start — do not assume single-Location and retrofit later.

## 4.3 Commercial Entitlement Entities

### CommercialRelationship
- **Purpose:** Records the Business's overall arrangement with the platform — current Plan, billing state, and commercial history.
- **Ownership:** Business-scoped.

### Plan
- **Purpose:** A commercial packaging mechanism that grants a set of Entitlements and allowances. Not a fixed industry bundle.
- **Ownership:** Platform-scoped.

### CommercialEntitlement
- **Purpose:** A Business-scoped commercial right to use a named module, capability tier, quantity, or allowance during a defined period.
- **Ownership:** Business-scoped.
- **Key relationships:** Has source (Plan/Add-on/Trial/Promo/Manual), subject (module ID or capability ID), effective period, state, and optional allowances.
- **Important:** Separate from Permission, Module activation, and Configuration readiness. Effective Entitlement is the union of all active, non-expired grants minus explicit commercial restrictions.

### Trial
- **Purpose:** A temporary Entitlement to a defined module, capability tier, or allowance. Has defined start, expiry, and conversion path.
- **Notes:** Trial expiry does not destroy Business data.

### UsageRecord
- **Purpose:** Tracks a measured activity or resource count against an allowance dimension.
- **Notes:** Measurement does not imply billing. Billable usage exists only under an explicitly approved commercial policy.

## 4.4 Module State Entities

### ModuleDefinition
- **Purpose:** The canonical registry entry for a platform module — its ID, version, declared data contracts, public service/interface contracts, UI contracts, event contracts, configuration schema, and dependency declarations.
- **Ownership:** Platform-scoped.

### BusinessModuleState
- **Purpose:** Records the operational lifecycle of a module for a specific Business.
- **Ownership:** Business-scoped.
- **Key relationships:** Belongs to Business and references ModuleDefinition; holds module configuration (JSONB, validated against module's configSchema).
- **Dimensions (independent, not collapsed):** Registry availability, Entitlement state, Activation state, Configuration state, Applicability, Operational health.

## 4.5 Website Entities

### Website
- **Purpose:** The structured digital presence for a Business. Every Business has one (core-website from Platform Core).
- **Ownership:** Business-scoped.
- **Notes:** Rendered from structured configuration, not from arbitrary stored source code.

### WebsitePage
- **Purpose:** A named page within a Business Website with defined Sections and layout.
- **Ownership:** Business-scoped within Website.

### WebsiteSection
- **Purpose:** A typed, configured content block within a WebsitePage — hero, about, offerings list, booking widget, gallery, reviews, contact, etc.
- **Ownership:** Business-scoped.
- **Notes:** Configuration is structured and schema-validated against SectionType. Not arbitrary HTML or code.

### SectionType
- **Purpose:** Platform-defined or module-contributed definition of a Website section — its schema, allowed layout variants, rendering component, and required capabilities.
- **Ownership:** Platform-scoped or module-defined.

### WebsiteTheme
- **Purpose:** Design token configuration for a Business Website — color palette, typography choices, spacing, and other visual variables within the allowed design token surface.

## 4.6 Offering and Commerce Entities

### Offering
- **Purpose:** Something a Business provides — a product, menu item, service, class, package, or consultation. Typed (product / service / class / package / subscription-plan).
- **Source module:** `offerings-catalog`.

### Order
- **Purpose:** A customer's purchase intent and lifecycle for one or more Offerings.
- **Source module:** `orders`.

### Booking
- **Purpose:** An advance scheduled appointment, reservation, session, or class for a service-type Offering.
- **Source module:** `bookings`.

### QueueEntry
- **Purpose:** A walk-in token or check-in record for a queue at a Location.
- **Source module:** `queue-operations`.

### Payment
- **Purpose:** A record of a payment attempt and outcome for a merchant-customer transaction.
- **Source module:** `payments`.
- **Notes:** Provider-specific data stays in providerMetadata (JSONB). Canonical payment state is platform-owned.

### Invoice
- **Purpose:** A billing document issued by a Business to a customer.
- **Source module:** `invoicing`.

### Fulfilment
- **Purpose:** The record of physical or digital delivery for an Order — pickup, local delivery, or shipping/courier.
- **Source module:** `fulfilment`.

## 4.7 Customer and Relationship Entities

### CustomerContact
- **Purpose:** A record of a person who has interacted with a Business — their contact information, interaction history, notes, and segments.
- **Ownership:** Business-scoped. Distinct from PlatformIdentity — the same person appears as CustomerContact in each Business they've engaged with.
- **Source module:** `customer-relationships`.

### Lead
- **Purpose:** An enquiry or prospect not yet a Customer.
- **Source module:** `leads`.

### Membership (Customer)
- **Purpose:** A customer's active subscription to a Business-defined plan or package. Distinct from the Business's platform commercial plan.
- **Source module:** `memberships`.

## 4.8 Operations Entities

### WorkforceMember
- **Purpose:** An operational staff profile — schedules, service assignments, calendar availability. Distinct from BusinessMembership (access control).
- **Source module:** `workforce`.

### InventoryRecord
- **Purpose:** Stock level tracking for a product-type Offering at a Location.
- **Source module:** `inventory`.

## 4.9 AI Entities

### AIEmployeeConfiguration
- **Purpose:** Configuration of an enabled AI employee for a Business — its enabled tools, approved actions, channel connections, escalation policy, and autonomy limits.
- **Notes:** Entitlement alone does not authorize any AI tool. Tool authorization is explicitly configured and separately enforced.

### AIInteractionRecord
- **Purpose:** An audit record of an AI employee action — what it did, which tool it used, outcome, and whether human approval was required.

## 4.10 Platform Audit and Observability Entities

### AuditEvent
- **Purpose:** An attributable record of a consequential platform action — actor, context, target, action, before/after state, reason, and timestamp.
- **Ownership:** Platform-scoped; append-only.
- **Notes:** Required for all Super Admin actions, Entitlement changes, permission changes, sensitive exports, and AI actions.

### DomainEvent
- **Purpose:** An event emitted by a module when a meaningful domain action occurs — `order.created`, `booking.confirmed`, `payment.completed`, etc.
- **Ownership:** Platform event log; business-scoped in filter.
- **Notes:** The event log is append-only. Events are the asynchronous inter-module mechanism for reactions, propagation, integration side effects, and decoupled workflows. They are not substitutes for synchronous public contracts and must not be used to imitate request/response behavior.

---

# 5. Identity and Context Model

A single Platform Identity may simultaneously be a consumer, a member of one or more Businesses, and — where authorized — a Platform Super Admin. There are never duplicate identities for different contexts.

## 5.1 Context Resolution

Every request evaluates the full access chain server-side:

1. **Authenticated identity** — who is this?
2. **Active operating context** — Personal, Business, Admin?
3. **Active Business** — which Business is in scope?
4. **Active Location** — which Location scope (if applicable)?
5. **BusinessMembership** — is this identity a member here? In what state?
6. **Core Role** — Primary Owner / Manager / Member?
7. **Effective Permissions** — what actions are granted?
8. **Effective Entitlement** — what is the Business commercially allowed?
9. **Module State** — is the module entitled, enabled, configured, and ready?
10. **Resource / Workflow State** — is this specific resource actionable now?

No step may be skipped. Remembered context from a cookie or cached UI never grants authority.

This chain is evaluated in server-side application services regardless of database credential type. User-scoped database access additionally uses RLS as a tenant-isolation backstop. Code using privileged database access must establish and validate equivalent scope explicitly because that connection may bypass RLS.

## 5.2 My Activity vs Business Workspace

| Context | Contains | Must not contain |
|---|---|---|
| My Activity (Personal) | Orders placed as customer, bookings as customer, queue activity, customer memberships, reviews written | Business payments received, Business-managed orders, team actions, Website changes |
| Business Workspace | Orders managed, payments received, bookings handled, operational history, team actions, module activity, commercial state | Operator's personal purchases, bookings, reviews as a customer |

---

# 6. Multi-Tenancy

Business is the primary tenant boundary. Every Business-owned resource must have an unambiguous ownership path to a Business entity.

## 6.1 Data Scoping Categories

| Scope category | Example entities | Isolation requirement |
|---|---|---|
| **Business-scoped** | Orders, Bookings, Offerings, CustomerContacts, Invoices, Website config, Module state | Strictly isolated; no cross-Business reads without explicit platform mechanisms |
| **Location-scoped** | Location configuration, Inventory, QueueEntries, Workforce schedules | Isolated within owning Business by Location ID |
| **Consumer-scoped** | PlatformIdentity, ConsumerProfile, My Activity projections | Isolated to the authenticated identity |
| **Platform-scoped** | ModuleDefinitions, Plans, SectionTypes, BusinessTypeProfiles | Read-access to Businesses where appropriate; writes restricted to platform operations |
| **Cross-Business platform data** | Consumer Marketplace index, aggregate trust statistics | Produced by platform processes; individual Business data not exposed as raw cross-Business joins |

## 6.2 Defense-in-Depth Principles

1. **Server-side scope resolution.** Every API handler resolves the authorized Business scope from the authenticated identity and validated context, not from a client-supplied Business ID alone.
2. **Authorization checks.** Normal Business-scoped operations validate authenticated identity, Active Business, Location scope where applicable, permission, Entitlement, module activation/configuration/applicability, and resource/workflow state before data access.
3. **Tenant-aware queries.** Every application-issued query touching Business-scoped data includes an explicit `business_id` predicate matching the authorized scope, including code running with privileged access.
4. **RLS as a contextual backstop.** Where the database execution context supports and is subject to RLS, database policies enforce tenant isolation as a defense layer if application checks are defective. RLS does not protect a query executed through credentials or roles that bypass it.
5. **Aggregates, not raw cross-Business joins.** Platform-level data is produced by controlled background processes.
6. **Auditability.** Sensitive reads and writes, including privileged operations, are logged with actor, context, resource, reason, and outcome.

## 6.3 Database Execution Contexts and Privileged Access

Database access uses one of three explicit execution contexts:

| Context | Intended use | Required controls |
|---|---|---|
| **User-scoped** | Default request-path operations performed for an authenticated identity | Server authorization chain; explicit Business/Location predicates; tenant isolation through RLS wherever supported by the connection context |
| **Public read-scoped** | Published Business Websites and intentionally public Marketplace projections | Read-only access to explicitly published fields; no mutable access or cross-tenant enumeration |
| **Privileged system-scoped** | Narrowly defined server-side jobs, migrations, administration, platform projections, or operations that genuinely require elevated database access | Server-only credential; explicit Business or platform scope; minimum necessary access; attribution and audit where sensitive |

A privileged connection capable of bypassing RLS is a high-trust infrastructure capability, not a normal application convenience. Privileged credentials must never be exposed to clients, embedded in frontend code, supplied to AI tools, or logged. Code using privileged access must explicitly establish and validate tenant scope before accessing Business-owned data. Where the operation acts for a user or Business, the normal authorization chain still applies; bypassing RLS does not bypass identity, Location, permission, Entitlement, module/configuration state, or resource-state checks.

Privileged access is restricted to enumerated operations and reviewed as part of infrastructure security. Routine Business Workspace, consumer, Website-management, and module operations use user-scoped or public read-scoped execution paths rather than service-role-style bypass.

---

# 7. Location Architecture

A Business has one or more Locations from day one. Location is a subordinate scope — never a separate tenant.

```
Business
└── Location A (primary)
└── Location B (branch)
└── Location C (delivery hub)
```

## 7.1 Inheritance and Override

- **Business-wide** settings are defaults.
- **Location configuration** provides explicit overrides for dimensions that meaningfully differ (hours, capacity, service area, staff availability, selected Offerings).
- **Location cannot expand** beyond Business Entitlement — adding Locations does not grant additional module access.
- **One business, multiple Locations is modeled from day one.** The Location array is present on Business even when only one Location exists.

## 7.2 Location-Scoped Data Examples

| Domain | Business-wide | Location-specific |
|---|---|---|
| Branding | Always Business-wide | No per-Location brand |
| Website | One Website per Business; Location-aware sections display different hours/availability | |
| Offerings | Defined Business-wide; availability configured per Location | |
| Opening hours | Business default | Hours are Location-specific |
| Inventory | Tracked per Location | Inventory is Location-scoped |
| Bookings | Calendar and availability per Location and Workforce member | |
| Queue | Per Location and queue type | |

---

# 8. Platform Core Architecture

Platform Core is the universal foundation every Business receives. It is not optional, not installable as a module, and not commercially differentiated except where an advanced capability is explicitly tiered.

| Core group | Canonical ID | Technical responsibilities |
|---|---|---|
| Business Identity | `core-business-identity` | Business root entity, lifecycle state machine, slug management, ULID-based IDs, type profile linkage |
| Business Profile | `core-business-profile` | Public profile content, media references, Trust statistics (derived async), branding tokens |
| Website/Public Presence | `core-website` | Structured Website entity, pages, sections, navigation, theme, domain configuration, rendering pipeline |
| Workspace Foundation | `core-workspace` | Authenticated Business shell, context resolution, module navigation assembly, permission-aware rendering |
| Settings | `core-settings` | Business-wide configuration (JSONB-typed), settings API, Business-type defaults, Location settings foundation |
| Location Foundation | `core-locations` | Location entities, geo, hours, service areas, Location context switching, Location-scoped queries |
| Team, Roles & Access | `core-team-access` | BusinessMembership lifecycle, core roles, permission templates, permission grants, invitation flow |
| Module Management | `core-module-management` | Module registry reads, Entitlement discovery, enablement UI, configuration launch, lifecycle management |
| Basic Notifications | `core-notifications` | In-platform notification inbox, essential event-triggered notifications, notification preferences |
| Marketplace Presence | `core-marketplace-presence` | Business Marketplace profile projection, visibility configuration, Marketplace search indexing trigger |

## 8.1 Shared Platform Services

These services underpin Platform Core and are not Business-installable:

| Service | Canonical ID | Purpose |
|---|---|---|
| Identity/Auth | `svc-identity-auth` | Platform Identity and session management |
| Tenant/Access Enforcement | `svc-tenancy-access` | Tenant isolation conventions, RLS policy management, user-scoped session binding, and governance of narrowly allowed privileged execution paths |
| Module Registry | `svc-module-registry` | Module manifest registry and version management |
| Entitlement & Billing | `svc-entitlement-billing` | Commercial Entitlement authority, platform billing state |
| Event/Audit | `svc-event-audit` | Domain event bus, event log, dead-letter queue |
| Rendering | `svc-rendering` | Business Aggregate loading, renderer dispatch |
| Capability Evaluation | `svc-capability-evaluation` | Layered availability computation |
| AI Runtime | `svc-ai-runtime` | Shared AI model connection, context formatting, tool dispatch, audit |
| Search/Discovery | `svc-search-discovery` | Search index management and query abstraction |
| Media | `svc-media` | Asset storage, CDN integration, variant generation |
| Realtime | `svc-realtime` | Event fan-out, WebSocket/SSE for live UI updates |
| Statistics/Trust | `svc-statistics-trust` | Derived Business statistics, Trust Score computation (async) |
| Communication Delivery | `svc-communication-delivery` | Channel and provider abstraction for notifications/messaging |
| Payment Providers | `svc-payment-providers` | Payment provider adapter abstraction (merchant + platform billing) |

---

# 9. Module Architecture

Optional modules are the extension mechanism of the platform. Each module is self-contained but uses platform infrastructure.

## 9.1 Module Contribution Surface

Each module may contribute:

| Contribution type | Example |
|---|---|
| Domain logic & data | Module-owned tables; a module reads and writes only its own tables |
| Workspace navigation | New sidebar item(s), workspace pages/views |
| Website/public capabilities | Module-contributed SectionTypes (booking widget, menu, review list) |
| Marketplace actions | Public action CTAs from Marketplace profile (Book, Order, Join queue) |
| Permissions | Module-specific permission actions available for grant |
| Configuration | Module configSchema; Business-level and Location-level configuration |
| Events | Module emits and subscribes to domain events |
| Background jobs | Module-specific scheduled or event-triggered background work |
| AI tools/capabilities | Named tools an AI employee may use when explicitly authorized |

## 9.2 Module Communication Contract

Modules never:
- Import another module's internal code, private types, or implementation details
- Read or write another module's database tables
- Bypass a module's public contract to reach its persistence layer
- Use domain events to simulate synchronous request/response, including emit-and-wait-for-reply patterns

When an immediate result is required, synchronous cross-domain communication may:
- Call an explicit, stable public service or interface contract
- Use module-published query or command interfaces declared in the ModuleDefinition
- Use platform-provided read models or services such as `BusinessAggregate`, `svc-entitlement-billing`, or `svc-capability-evaluation`
- Return only contract-defined data transfer objects, never raw rows from the owning module's tables

For asynchronous reactions, propagation, integration side effects, and decoupled workflows:
- The owning module emits a domain event after its own state is committed
- Subscribers react idempotently and write only to their own tables
- The outbox pattern is used where event publication must be atomic with a local domain write (Section 28.3)

Modules always own their tables and internal implementation. They expose stable public contracts where another domain requires an immediate answer or command, and emit events for meaningful actions other domains may need to react to asynchronously. These boundaries apply inside the modular monolith and do not require network calls or premature microservices.

## 9.3 Module Availability Evaluation

A module is usable only when ALL of the following conditions are satisfied:

```
Module Definition exists in registry
AND Commercial Entitlement is active (not expired, not suspended)
AND Business has explicitly enabled the module (activation)
AND Configuration is complete and valid
AND Module is applicable at the current Location (if Location-scoped)
AND User has permission to perform the specific action
AND Resource/workflow state permits the action
```

These are independent gates. Failing any gate produces a distinct experience — not a generic "access denied."

---

# 10. Canonical Module Boundaries

The 21 canonical optional modules from Document 08 §21.2, with their key technical relationships:

| Module | Key technical relationships |
|---|---|
| **Offerings Catalog** | Provides canonical Offering identities and public query contracts. Other modules store Offering IDs or approved snapshots; they do not define their own product schema or read Offerings tables directly. |
| **Orders** | Resolves Offerings through the Offerings public contract and stores approved line-item snapshots. Emits `order.*` events. Fulfilment reacts asynchronously; payment initiation may call the Payments public contract when an immediate result is required. |
| **Bookings** | May reference service-type Offerings. Resolves provider availability synchronously through the Workforce public availability contract when required. Emits `booking.*` events for downstream reactions. |
| **Queue Operations** | Operates independently; asynchronous reactions use Bookings/Workforce events, while immediate availability or state checks use their public contracts. |
| **Customer Relationships** | Receives `order.created`, `booking.confirmed`, etc., to build customer history. Never owns transactional records directly. |
| **Leads** | Captures enquiries; emits `lead.*` events. May convert to CustomerContact via event-driven workflow. |
| **Inventory** | References product-type Offerings. Tracks stock per Location. Subscribes to `order.fulfilled` for deductions. |
| **Payments** | Attaches to Orders, Invoices, Bookings, and Memberships through stable IDs and public contracts. Uses provider adapter. Emits `payment.*` events to propagate outcomes. |
| **Invoicing** | Operates independently from Payments. Online collection calls the Payments public contract; payment outcomes propagate through `payment.*` events. |
| **Fulfilment** | Normally acts on Orders. Modes (pickup, local delivery, shipping) may need Location or provider configuration. |
| **Memberships** | Customer-plan management. Renewal scheduling uses jobs/events; a charge attempt uses the Payments public contract. Emits `membership.*` events. |
| **Loyalty** | Requires Customer Relationship + eligible event sources. Payments is one earn source, not the only one. |
| **Workforce** | Provides provider profiles, schedules, and availability through public contracts and events. Bookings, Queue, and Payroll never read Workforce tables directly. |
| **Payroll** | Consumes Workforce data through its public contract or an event-maintained Payroll read model. May call Payments through a public payout contract. Owned tables remain separate. |
| **Messaging** | Optional external channels beyond Core Notifications. Provider-abstracted via `svc-communication-delivery`. |
| **Marketing** | Builds audiences through the Customer Relationships public query contract or an event-maintained projection. Uses Messaging through its public delivery contract. |
| **Reviews** | Requires eligible completed transaction/interaction evidence (data dependency). Emits `review.*` events for Trust Score. |
| **Analytics** | Consumes event-maintained projections and platform statistics contracts. Richer module data improves output; no false hard dependencies or direct module-table reads. |
| **Business Passport** | Extends Business Profile with verified credentials. Horizon 3+. |
| **Business Community** | Platform-density-dependent (Horizon 3+). |
| **B2B Network** | Graph-driven supplier/partner discovery (Horizon 3+). |

## 10.1 Stable Contract Principle

Modules needing immediate authoritative data or an immediate command from another domain use stable public service or interface contracts. Modules needing derived or eventually consistent data subscribe to domain events and maintain their own read-model projections. Aggregated data may come from platform-provided read models such as BusinessAggregate or the consumer activity projection. Direct cross-module table reads, writes, and joins are prohibited regardless of deployment shape.

---

# 11. Structured Website Architecture

## 11.1 Core Model

The Website is rendered from a hierarchy of structured, schema-validated configuration:

```
Website
└── Navigation (structured link tree)
└── Theme (design token overrides within allowed surface)
└── Page[]
    └── SEO metadata
    └── Section[]
        └── SectionType (platform-defined or module-contributed)
        └── LayoutVariant (from allowed variants for this type)
        └── Content (JSONB, validated against SectionType schema)
        └── Media references (Asset IDs, not embedded URLs)
        └── Module data binding (e.g., "show Offerings from offerings-catalog")
```

## 11.2 What Businesses May Configure

- Edit text content within sections
- Change media (logo, cover, gallery images)
- Adjust branding tokens within the allowed design token surface
- Reorder sections, add supported section types, remove sections
- Choose supported layout variants
- Manage navigation links and structure
- Configure module-contributed sections (e.g., which Offerings appear in a menu section)

## 11.3 What Businesses May Not Do by Default

- Insert arbitrary HTML or JavaScript
- Define new section types
- Override platform security policies via Website configuration
- Store freeform generated source code as the Website model

## 11.4 AI Website Generation

AI-assisted Website generation produces **structured Website configuration** (Page and Section JSON matching defined schemas), not arbitrary source code. The result is:

1. Generated as a draft Website configuration
2. Presented to the Business owner for review
3. Published only after explicit Business confirmation

AI-generated content does not bypass normal Website schema validation.

> **Amendment — 2026-09-01 (Website Generation Overhaul work order; additive, dated per Document 08 §25.3). Decided now.**
>
> **Content-authorship boundary.** AI authorship is confined to content within
> already-defined structure: section copy, image *selection* (by Asset ID) from
> supplied or curated assets, `layout_variant` choice from a section type's existing
> `allowed_variants`, section ordering, and `theme` token *suggestions*. AI never
> authors platform mechanics — cart/checkout, stock or availability display,
> navigation/route semantics, order or booking confirmation, module data bindings,
> permission gates, entitlement, or commercial state. Those are fixed platform code.
> A generation response that reaches beyond content fails validation and is repaired
> deterministically.
>
> **One-shot structured intake.** Generation is driven by a skippable,
> business-type-aware questionnaire that feeds exactly one provider call per Business
> (`AIModelProvider.generate_structured`, see Document 12 §12.2/§12.7), not a
> multi-turn conversation. Skipped fields are filled by the deterministic fallback,
> never a second call. This bounds cost and keeps output safe.
>
> **Prebuilt templates (Option A).** External design references are translated into a
> `WebsiteTheme` definition and additional layout variants for the existing section
> types. Raw external HTML/CSS/JS is never stored or rendered — this is §11.3
> applied to the template pipeline. Anything an existing section type cannot
> represent is flagged for a decision, not resolved by inventing a new section type.

## 11.5 Rendering Principle

The Website renderer:
1. Loads the BusinessAggregate (Business + active module data + computed capabilities), assembled through public contracts and owned read models rather than cross-module table access
2. Resolves the requested page and Location context
3. Renders each Section using its registered SectionType component
4. Injects module-contributed data (Offerings, availability, reviews) where sections reference it
5. Applies the Business theme tokens
6. Returns server-rendered HTML (SSR/ISR for public performance and SEO)

The renderer formats and filters. It does not compute business rules. Capability checks come from the pre-computed BusinessAggregate.

---

# 12. Business Website Routing and Domains

## 12.1 URL Structure

| Route pattern | Purpose |
|---|---|
| `{slug}.platform.com` | Platform-provided Business subdomain |
| `{slug}.platform.com/{location-path}` | Location-specific pages where configured |
| `custom-domain.com` | Future custom domain support (DNS verified, mapped to Business) |

## 12.2 Business Workspace Routing

Business Workspace routes use a stable internal Business ID:

```
app.platform.com/b/{businessId}/...
```

Public slug is for human-readable URLs. Stable internal ID is for workspace routes. The two are kept separate to allow slug changes without breaking internal routes.

## 12.3 Module-Contributed Routes

Optional modules may contribute both public Website routes and workspace routes. Route contribution is declared in the ModuleDefinition, not discovered at runtime. New modules do not require platform routing changes.

---

# 13. Marketplace and Search Architecture

The Marketplace is search-first. It is not a directory. Discovery surfaces search results, not paginated lists.

## 13.1 What is Searchable

| Searchable data | Owner |
|---|---|
| Business profile (name, description, categories, tags) | Core Business Profile |
| Locations and geo coordinates | Core Location Foundation |
| Offerings (name, description, category, price range) | Offerings Catalog module |
| Service types and capabilities | Business capabilities |
| Trust attributes (response time, fulfillment rate) | `svc-statistics-trust` |
| Marketplace visibility setting | Core Marketplace Presence |

Only Businesses with `BusinessVisibility = discoverable` and `BusinessState = active` appear in Marketplace search results. There are no unclaimed Business listings.

## 13.2 Search Architecture Evolution

```
Phase 1 (MVP):
  PostgreSQL full-text search (tsvector / GIN index)
  → Zero additional infrastructure
  → Sufficient for thousands of Businesses
  → Acceptable for initial city-and-category search

Phase 2 (Scale):
  External search engine behind svc-search-discovery abstraction
  → Typesense / Meilisearch / Elasticsearch behind existing interface
  → Index maintained by event-driven indexing job
  → Application code unchanged

Phase 3 (Quality):
  Dedicated search engine with:
  → Faceted filtering (category, location, rating, availability)
  → Geo-radius search
  → Relevance tuning
  → Future: personalisation/ranking signals
```

The search contract is provider-agnostic from day one. The upgrade path from Phase 1 to Phase 3 does not require changes to application logic.

## 13.3 No Complex Recommendation Engine at MVP

MVP search is query-first with basic relevance sorting (Trust Score, recency, profile completeness). Collaborative filtering and machine-learning ranking are deferred.

---

# 14. Consumer Activity Architecture

My Activity aggregates a user's customer-side interactions across Businesses in their Personal Context.

## 14.1 What My Activity Contains

- Orders placed as a customer (across all Businesses)
- Bookings made as a customer (across all Businesses)
- Queue activity and history
- Customer Memberships as a customer of a Business
- Reviews written
- Saved/favourited Businesses
- Consumer-facing notification history

## 14.2 Activity Projection Pattern

My Activity is not a single giant table duplicating all module data. Instead:

```
Module event emitted (order.created, booking.confirmed, review.submitted)
    → Consumer Activity Projection Service subscribes
    → Writes a lightweight activity record:
        { identityId, businessId, activityType, resourceType, resourceId,
          occurredAt, summary }
    → My Activity renders from the projection
    → Detail views fetch through the originating module's public contract with appropriate scope
```

This approach keeps module data ownership clear, provides fast activity list rendering, and fetches full details from the authoritative source when needed.

## 14.3 Separation Guarantee

Consumer activity is scoped to the PlatformIdentity. It never includes Business operational data. The projection service explicitly filters by activityType — only consumer-role activities are projected.

---

# 15. Authorization Architecture

Authorization is server-authoritative. No client-side control is the enforcement mechanism.

## 15.1 Access Evaluation Chain

A request evaluates the following sequence server-side:

```
Request received
→ Authenticated identity? (no → reject)
→ Active context resolved? (no → reject)
→ Business membership active? (no → reject)
→ Location scope satisfied? (no → reject)
→ Commercial Entitlement active? (no → entitlement gate)
→ Module enabled, configured, applicable? (no → appropriate module state response)
→ User has permission for this action? (no → permission gate)
→ Resource/workflow state allows? (no → state constraint response)
→ Allow: proceed
```

## 15.2 Deny-by-Default

The default for any resource or action that has not been explicitly granted is **deny**:
- New module actions: no access until explicitly granted
- Staff/Member role: no access to any module — every grant is explicit
- Cross-Business reads: deny without explicit platform mechanism

## 15.3 What Is Never Trusted

- Client-supplied Business IDs as the sole authorization basis
- Hidden buttons or navigation as authorization
- Frontend route guards as the only enforcement layer
- Cached authorization decisions after membership/permission changes

## 15.4 Database Enforcement Alignment

The Section 15.1 chain gates every protected operation before database access. User-scoped connections bind the authenticated context to RLS-compatible database session context wherever supported. Privileged system-scoped access is permitted only for the enumerated operations in Section 6.3 and must explicitly validate Business and Location scope plus every applicable permission, Entitlement, module/configuration, and resource-state condition because RLS may not apply.

---

# 16. Commercial Entitlement Architecture

## 16.1 Entitlement Service Responsibilities

The `svc-entitlement-billing` service is the single source of truth for Commercial Entitlement:

```
Responsibilities:
  - Maintain CommercialRelationship and CommercialEntitlement records
  - Evaluate Effective Entitlement for a Business
  - Record Entitlement changes with full attribution
  - Expose entitlement check interface to other services/modules

Not responsible for:
  - Granting user permissions
  - Activating modules
  - Configuring anything
```

## 16.2 Entitlement Sources and Evaluation

```
Effective Entitlement
= Platform Core (always included)
+ Active base-plan grants
+ Active add-on grants
+ Active trial grants
+ Active promotional grants
+ Active manual Super Admin grants (attributed)
+ Active custom-agreement grants
− Explicit commercial restrictions/suspensions
```

## 16.3 Centralized Check Interface

Every module that needs to check Entitlement calls the entitlement service through a stable interface:

```typescript
checkEntitlement(businessId, subject) → EntitlementResult {
  entitled: boolean,
  source: EntitlementSource,
  expiresAt?: DateTime,
  allowance?: Allowance,
  usedAllowance?: number
}
```

Modules never implement their own commercial logic.

## 16.4 Entitlement Is Not Permission

| Entitlement | Permission |
|---|---|
| Business-scoped commercial right | User-scoped action authority |
| "This Business may use the Bookings module" | "This user may cancel a booking" |
| Granted by plans, add-ons, trials, Admin | Granted by core role, template, explicit grant |
| Does not create membership | Does not create commercial access |
| Checked by entitlement service | Checked by authorization service |

---

# 17. Payment Architecture

Two financial domains are permanently separate and must never be merged.

## 17.1 Merchant / Customer Payments

```
Customer
→ Business Website or Marketplace transaction
→ payments module
→ svc-payment-providers adapter
→ Razorpay / other provider
→ Business merchant / linked account
→ Business settlement destination
→ Order / Booking / Invoice payment state updated
```

**Key canonical concepts:**
- `MerchantConnection` — Business's relationship with a payment provider
- `MerchantOnboardingState` — KYC/verification progress
- `PaymentAttempt` — a single attempt to collect payment
- `PaymentStatus` — canonical outcome (pending/completed/failed/refunded)
- `RefundRecord` — customer refund against a payment
- `SettlementReference` — provider's record of Business payout
- `ProviderAccountReference` — provider-internal ID (stored in providerMetadata, not canonical domain)

**The normal architecture does not route customer funds through the founder's bank account for manual redistribution.** Business funds go to the Business's merchant/linked account and settlement destination.

## 17.2 Platform Billing

```
Business
→ Platform commercial billing
→ svc-payment-providers platform billing adapter
→ Platform billing provider
→ Platform billing account
→ Confirmed commercial outcome
→ svc-entitlement-billing: Entitlement updated
→ Capability evaluation updated
```

Platform billing is entirely separate from merchant payment processing.

## 17.3 Provider Abstraction

The `svc-payment-providers` adapter:
- Maps provider-specific objects and states to canonical payment concepts
- Handles provider-specific webhook payloads and signature verification
- Executes the inbound webhook receipt pipeline in Section 20: verify authenticity, check idempotency, durably persist the receipt or durable queue record, acknowledge success, then map and apply business effects asynchronously
- Abstracts KYC/onboarding flows per provider
- Makes it possible to add a second payment provider without changing domain logic

Razorpay (or any other provider) is an implementation choice behind this adapter. Provider-specific names never appear in canonical domain entities.

---

# 18. External Integration Architecture

## 18.1 Adapter Model

All external provider integrations are accessed through platform-owned adapter interfaces. Canonical business logic depends on platform interfaces, not vendor APIs:

```
Application logic
    → Platform interface (e.g., PaymentProvider, EmailProvider)
        → Concrete adapter (e.g., RazorpayAdapter, ResendAdapter)
            → External provider API
```

## 18.2 Integration Categories

| Category | Interface | Initial providers (examples) |
|---|---|---|
| Payment providers | `PaymentProvider` | Razorpay (initial) |
| Email delivery | `EmailProvider` | Resend, Postmark, SES |
| SMS delivery | `SMSProvider` | MSG91, Twilio |
| WhatsApp/messaging | `MessagingProvider` | WhatsApp Business API (Meta) |
| Maps / geocoding | `MapProvider` | Google Maps, Mapbox |
| Delivery / logistics | `DeliveryProvider` | Shiprocket, Dunzo, Delhivery |
| AI model providers | `AIModelProvider` | Google Gemini, Anthropic, OpenAI |
| Object storage | `StorageProvider` | Supabase Storage, AWS S3 |
| Search engine | `SearchProvider` | Typesense, Meilisearch, Elasticsearch |
| Push notifications | `PushProvider` | FCM, APNs |

## 18.3 Abstraction Calibration

Not every integration needs deep abstraction at MVP:
- **High abstraction priority:** Payment providers (regulatory complexity, likely multi-provider), AI model providers (rapid evolution), Search (likely migration path)
- **Light abstraction:** Email and SMS (interface is simple; swap is straightforward)
- **Minimal abstraction:** Maps geocoding at MVP (swap is unlikely; interface is small)

---

# 19. Event and Background Job Architecture

## 19.1 When to Process Asynchronously

| Use case | Why async |
|---|---|
| Notification delivery | Not on the critical request path; may involve external providers |
| Search index updates | Eventual consistency acceptable; source of truth remains the primary DB |
| AI generation / website draft creation | Can take seconds; user doesn't need to wait synchronously |
| Trust Score / statistics recomputation | Derived data; computed after events settle |
| Image/media processing | CPU-intensive; not user-blocking |
| Payment webhook handling | Verify authenticity, check idempotency, durably persist receipt or commit it to a durable queue, then acknowledge success quickly; canonical business effects run asynchronously afterward |
| External synchronization | External latency is unpredictable |
| Scheduled reminders and follow-ups | Time-triggered, not request-triggered |

## 19.2 Infrastructure Approach

```
MVP:
  Database-backed job queue (pg-boss / Inngest / BullMQ)
  + PostgreSQL LISTEN/NOTIFY or polling for event fan-out
  → Sufficient for early volume
  → Retries, dead-letter, visibility via admin tooling

Scale (when measured load demands):
  Dedicated job queue (BullMQ / Redis)
  → Behind the same EventBus interface
  → Modules unchanged when infrastructure upgrades

Enterprise (if genuine need):
  Message broker (RabbitMQ, Google Pub/Sub, etc.)
  → Only when multi-region or multi-process fan-out is proven necessary
```

Kafka-scale infrastructure is explicitly rejected for MVP.

## 19.3 Dead-Letter Queue

Failed jobs and events that exceed retry limits go to a dead-letter store visible in Platform Admin. Silently dropped events are production incidents, not acceptable behavior.

For webhooks, dead-letter handling applies to asynchronous business-effect processing after the receipt was durably recorded. A failure to durably record the receipt is an ingestion failure and must not receive a provider success acknowledgement.

---

# 20. Webhook Architecture

## 20.1 Principles

| Principle | Requirement |
|---|---|
| **Canonical receipt order** | Receive → verify provider signature/authenticity → perform idempotency/duplicate check → durably persist receipt/event or commit it to a durable queue → return provider-required success acknowledgement → process business effects asynchronously → record outcome, retry failures, and dead-letter when necessary |
| **Signature verification** | Verify provider signature/authenticity immediately after receipt and before idempotency handling, persistence, acknowledgement, or business-effect processing; reject invalid requests |
| **Idempotency** | Use a provider-scoped idempotency key. After verification, detect an existing durable receipt; acknowledge a valid duplicate without re-running business effects |
| **Raw event retention** | Durably store the raw payload and receipt metadata at ingest before returning success to the provider; canonical processed state may be updated asynchronously |
| **Durability before acknowledgement** | Durable receipt or durable queue commit must succeed before the provider-required success acknowledgement. If persistence fails, do not acknowledge success; return the appropriate failure so the provider can retry |
| **Asynchronous processing** | Business effects run asynchronously after durable receipt and acknowledgement; acknowledgement does not wait for downstream business logic |
| **Provider event mapping** | Map provider-specific event types to canonical domain events via the provider adapter |
| **Failure and retry** | Failed asynchronous processing is retried with exponential backoff; persistent failures go to dead-letter |
| **Audit** | Record webhook receipt at ingest and business-effect processing outcome separately |

---

# 21. AI Architecture

AI is a governed platform capability, not a plugin bolted onto one module.

## 21.1 AI Layers

| Layer | Description | Authorization requirement |
|---|---|---|
| **Embedded AI assistance** | Inline suggestions within workflows | Included in feature; no extra Entitlement |
| **AI generation / configuration** | Generating Website structure, initial content drafts | Output is a draft requiring human publish action |
| **AI insights** | Read-only analysis and reporting | Tied to Analytics module or AI employee Entitlement |
| **AI employees** | Configured AI agents with tools and possible write actions | Explicit per-employee Entitlement + explicit tool authorization |

## 21.2 AI Platform Layer (svc-ai-runtime)

```
AI Employee Request
    → svc-ai-runtime
        → AIModelProvider abstraction (model API call)
        → Business context loading (BusinessAggregate read-only view)
        → Tool dispatch with authorization check:
            Is this tool in the approved list for this AIEmployeeConfiguration?
            Does the tool's domain require Entitlement?
            Does the configuration have permission for the tool's action?
        → Action execution via platform service interface (not direct DB call)
        → AIInteractionRecord written (audit)
        → Result / escalation / human approval if required
```

## 21.3 AI Authorization Rules

| Rule | Why |
|---|---|
| AI does not bypass normal platform authorization | AI employees are governed actors, not superusers |
| AI does not access privileged bypass credentials or unrestricted database access | AI uses platform tool interfaces governed by normal authorization and explicit execution context, not raw unscoped DB queries |
| AI tool list is explicitly configured per Business per employee | Entitlement grants the employee; tools are separately authorized |
| AI actions affecting financial or sensitive state require approval-capable design | Human oversight is an architectural option, not an afterthought |
| AI interactions are audited | Every AI action goes to AIInteractionRecord and AuditEvent |
| AI context is bounded by Business scope | AI cannot read data from other Businesses |

## 21.4 Provider Abstraction

The `AIModelProvider` interface abstracts the underlying AI model provider. Application logic never calls provider SDKs directly.

---

# 22. Data Ownership and Lifecycle

## 22.1 Ownership Principles

| Data category | Owned by | Governed by |
|---|---|---|
| Business operational data | The Business | Platform terms; Business controls while active |
| Consumer data (PlatformIdentity, My Activity) | The person | Platform terms; consumer privacy rights |
| Platform data (module definitions, plan structures, event log) | The platform | Platform policy |
| Audit records | Platform | Platform policy; not deletable by Business |

## 22.2 Soft Deletion

The default deletion behavior is **soft deletion** — marking records as deleted with a `deleted_at` timestamp, not physically removing rows. Hard deletion is a separate, explicit, confirmed operation.

## 22.3 Lifecycle Events and Data Behavior

| Lifecycle event | Data behavior |
|---|---|
| Module deactivation | Data retained; new operations stop; read/export may remain |
| Trial expiry | Commercial access ends; data retained; recovery path offered |
| Commercial downgrade | Data retained; new creation above lower limits blocked; no auto-deletion |
| Business closure | Data retained for legal retention period per platform policy |

**Do not delete Business data merely because an Entitlement expires.** This is an explicit architectural rule.

---

# 23. File and Media Architecture

## 23.1 Model

```
Upload request
    → Validation (type, size, Business ownership claim)
    → Upload to object storage (svc-media → StorageProvider adapter)
    → Asset record created:
        { id, businessId, purpose, storageKey, mimeType, sizeBytes,
          publicUrl, createdAt, ... }
    → Optional async: thumbnail generation, optimization, format conversion
    → Asset variants stored with reference to parent Asset
```

## 23.2 Asset Entity

Media is referenced by `Asset.id` in all domain entities. Direct URLs are never embedded in domain JSON. This indirection enables CDN migration, image variant generation, access control on private assets, and deletion lifecycle management.

## 23.3 Access Control

| Asset type | Access |
|---|---|
| Public Business media (logo, cover, gallery) | Public CDN URL |
| Private Business documents (verification, contracts) | Signed URL, time-limited, Business-scoped |
| Website section media | Public CDN URL (published state) |
| AI-generated media drafts | Private until Business publishes |

---

# 24. Cache and Performance

## 24.1 Appropriate Cache Candidates

| Cache candidate | Cache type | Invalidation trigger |
|---|---|---|
| Public Business Website pages | CDN edge cache / ISR | Website configuration update event |
| Marketplace Business listing cards | CDN edge cache | Business profile update event |
| Business profile data (for rendering) | In-process or Redis | Business profile update event |
| Module configuration per Business | Short-lived in-process | Module state change event |

## 24.2 Authorization Caching Rules

- Permission checks are not cached between requests — always evaluated against current state
- Entitlement checks may be briefly cached (seconds, not minutes) with strict invalidation on Entitlement events
- Session-level context is encoded in the request, not cached in shared memory

---

# 25. Audit and Observability

## 25.1 Mandatory Audit Events

The following actions always produce AuditEvent records:

- All Platform Super Admin actions (investigation, configuration, Entitlement corrections, support actions)
- Entitlement changes (grant, revoke, suspension, modification)
- Permission and membership changes (invitation, role change, removal)
- Sensitive configuration changes (payment configuration, domain settings, security settings)
- Business closure or state changes (suspension, enforcement)
- AI employee actions where a tool was used or an action was taken
- Sensitive data exports or bulk operations

Audit records are append-only, attributed (actor identity + context), and include before/after state for configuration changes.

## 25.2 Observability Stack

| Layer | Approach |
|---|---|
| Structured logs | JSON-structured with request ID, Business ID where applicable, actor, and outcome |
| Error tracking | Error monitoring service (Sentry or equivalent) with Business context attached |
| Metrics | Application metrics (request duration, queue depth, error rate) |
| Job monitoring | Background job success/failure rates, dead-letter queue depth — visible in Admin |
| Provider/integration health | Health checks for external provider connectivity; alerting when provider unreachable |

## 25.3 What Is Never Logged

- User passwords or auth tokens
- Payment card numbers or provider-sensitive financial credentials
- Encryption keys or secrets

---

# 26. Security Fundamentals

## 26.1 Authentication

- One Platform Identity foundation shared across all surfaces
- Session tokens are short-lived JWTs; refresh tokens are rotated
- Phone-OTP-first for Business owners (appropriate for target user base)
- OAuth for future staff/admin SSO

## 26.2 Server-Side Authorization

Every protected operation re-validates server-side. No client control is the enforcement mechanism (defined in Section 15).

## 26.3 Tenant Isolation

Normal Business-scoped operations validate authenticated identity, Active Business, Location scope where applicable, permission, Entitlement, module/configuration state, and resource state. User-scoped database access uses explicit `business_id` predicates plus RLS wherever the execution context supports it. Privileged system-scoped access may bypass RLS and therefore requires separate explicit tenant scoping, minimum necessary access, and audit under Section 6.3. No cross-tenant read is permitted without an explicit platform mechanism.

## 26.4 Least Privilege

- Staff/Member defaults: no access to any module (explicit grants required)
- AI employees: no tools by default (explicit tool authorization required)
- Internal services and background workers: use the minimum credential tier; privileged access is limited to the job's explicit Business or platform scope
- Admin access: elevated access is explicit, contexted, and audited

## 26.5 Secret Management

- API keys, provider credentials, and encryption keys stored in secrets manager — not in source code or the primary database as plain text
- Secrets are rotated on schedule and when access is revoked
- Privileged database credentials are highest-trust server-side secrets: never client-exposed, logged, or supplied to AI tools

## 26.6 Encryption

- TLS for all data in transit (HTTPS everywhere)
- Database encryption at rest (provided by managed database service)

## 26.7 Webhook Verification

Every inbound webhook follows the Section 20 durable receipt pipeline. Signature/authenticity verification occurs before idempotency handling, persistence, provider success acknowledgement, or business-effect processing.

## 26.8 Rate Limiting and Abuse Protection

- Rate limiting on authentication endpoints (prevents brute force)
- Rate limiting on public-facing APIs (prevents scraping)
- Rate limiting on AI endpoints (cost and abuse protection)

## 26.9 Backup and Recovery

- Automated database backups with tested restoration procedures
- Point-in-time recovery capability for the primary database
- Recovery time and point objectives documented before production launch

---

# 27. Privacy Boundaries

## 27.1 Business Data Isolation

- One Business cannot read another Business's data through any application pathway
- Marketplace aggregations are platform-produced, not raw cross-Business joins
- Consumer activity is scoped to the identity; Business operational data is not mixed in

## 27.2 Consumer Privacy

- A consumer's My Activity data belongs to the consumer, not the Businesses they interacted with
- A Business cannot see that a specific PlatformIdentity is also registered on the platform unless that person has explicitly interacted with them

## 27.3 Super Admin Access

- Super Admin has broad operational authority, not casual unrestricted data access
- All Super Admin actions are attributed and audited
- Sensitive personal data is minimized/redacted even in Admin views
- No silent impersonation — Super Admin work is visible as elevated-context activity
- Super Admin authority does not imply blanket privileged database access; each operation uses the minimum execution context and records actor, target Business, reason, and outcome

## 27.4 AI Context Boundaries

- AI employees receive only the Business data needed for their configured tools
- AI cannot read data from other Businesses
- AI context does not include raw payment credentials or private keys

## 27.5 Minimum Necessary Data

Every feature accesses the minimum data necessary for its function. Data access controls are defined at the service interface level, not only at the UI level.

---

# 28. Data Consistency and Transactions

## 28.1 Strong Consistency Required (ACID transactions)

| Operation | Why |
|---|---|
| Order state transitions | Financial and customer commitment |
| Payment state updates | Financial record accuracy |
| Entitlement changes | Commercial access grant/revoke |
| Permission and membership changes | Security boundary |
| Inventory adjustments at checkout | Prevents overselling |
| Business closure/suspension | Platform integrity |

## 28.2 Eventual Consistency Acceptable

| Operation | Why |
|---|---|
| Search index updates | Source of truth is primary DB; index lag is acceptable |
| Analytics aggregation | Approximate near-real-time is fine |
| Trust Score recomputation | Derived metric; slight lag acceptable |
| Notification delivery | Delivery is best-effort; underlying event is recorded |
| Activity projections | My Activity can lag slightly |

## 28.3 Distributed Transaction Avoidance

The modular monolith architecture intentionally avoids distributed transactions. For asynchronous cross-domain effects:
- Keep each module's writes within its own tables in a local transaction
- Use the outbox pattern (write event to DB in same transaction as domain record; background worker dispatches)
- Use idempotent event consumers for cross-module effects
- Do not use two-phase commit across process boundaries

Inbound webhooks use the same durable-first discipline: the receipt record or durable queue/outbox enqueue commits before the HTTP success acknowledgement.

---

# 29. API Architecture

## 29.1 API Principles

| Principle | Application |
|---|---|
| **Server-authoritative** | Every API call validates authorization server-side before executing |
| **Business-scoped routes** | All Business-context APIs: `/b/{businessId}/...` |
| **Consistent error contracts** | Stable error shape: `{ code, message, details }` with appropriate HTTP status |
| **Idempotent commands** | State-changing operations support idempotency keys where retry is possible |
| **Pagination and filtering** | List endpoints support cursor-based pagination and server-side filtering |

## 29.2 Interface Categories

| Category | Style |
|---|---|
| Authenticated application APIs (workspace, consumer, admin) | Server actions (Next.js) or REST at MVP |
| Public Website reads (rendering, Marketplace) | Server-side data loading via SSR/ISR |
| Module boundaries (inter-module) | Synchronous: stable public service/interface contracts for immediate results; asynchronous: domain events with versioned payloads; never cross-module table access |
| Internal service interfaces (Entitlement, Capability, AI) | TypeScript service objects in monolith; REST/gRPC if extracted |
| Webhooks (inbound) | REST POST with signature verification, idempotent durable receipt before success acknowledgement, and asynchronous business-effect processing |

## 29.3 Style Decision

REST is the default. GraphQL is not adopted for initial internal APIs. If the consumer-facing Marketplace API benefits from flexible querying specifically, GraphQL is revisited at that point. Neither is a permanent lock-in.

---

# 30. Database Direction

## 30.1 Primary Database: PostgreSQL

The domain has strong relational requirements: strong entity relationships, ACID transactions for financial/security operations, RLS-capable tenant isolation, complex filtering and joins. RLS protects execution contexts subject to its policies; privileged server connections remain governed by Section 6.3.

**PostgreSQL is the recommended primary database.** Use a managed service (Supabase, AWS RDS, Cloud SQL) — do not self-host at startup scale.

## 30.2 Appropriate JSONB Use

| Appropriate JSONB use | Why |
|---|---|
| `WebsiteSection.content` | Content schema varies by SectionType; validated against per-type schema |
| `Business.settings` | User-facing preferences; not filtered at DB level |
| `Business.metadata` | Module-owned extension data; each module reads only its own keys |
| `BusinessModuleState.config` | Module configuration schema varies by module |
| `Payment.providerMetadata` | Provider-specific data; never queried directly |
| `DomainEvent.payload` | Event payloads vary by event type |

## 30.3 Inappropriate JSONB Use (Explicit Prohibitions)

JSONB is not appropriate for:
- Order line items with price, quantity, or product ID (need direct queries for reporting)
- Customer contact information (needs direct filtering and lookup)
- Order status (needs state machine enforcement and direct filtering)
- Any field used in WHERE clauses, sorted, or aggregated in reports

## 30.4 Prohibited Patterns

- A generic `entities` or `objects` table for all domain data — this becomes unqueryable
- One giant `module_data` JSON column storing all module-specific data — destroys type safety and queryability

---

# 31. Tech Stack Decision Boundary

## 31.1 Architectural Requirements (Stable Regardless of Vendor)

- A relational database with ACID transactions, RLS capability, and a secure way to bind authenticated context to tenant policies
- An event/job processing system with retry and dead-letter support
- Object storage for media assets
- Full-text or dedicated search capability
- AI model provider abstraction layer
- Server-side rendering framework for public Website performance and SEO
- Authentication provider supporting JWT-based sessions and multi-factor auth

## 31.2 Initial Implementation Choices

| Layer | Initial choice | Why | Extraction trigger |
|---|---|---|---|
| Database | PostgreSQL (via Supabase) | RLS, full-text search, managed service | Supabase SLA or pricing becomes limiting at scale |
| Authentication | Supabase Auth | Integrated with DB, supports phone OTP, JWT, OAuth | If auth provider flexibility is needed |
| File storage | Supabase Storage / S3-compatible | Managed, integrated | CDN performance or pricing |
| Backend framework | Node.js / TypeScript | Type safety across full stack | — |
| Frontend framework | Next.js | SSR/ISR for Business Websites (critical for SEO), RSC for workspace | — |
| Job queue | pg-boss (Postgres-backed) or BullMQ (Redis-backed) | Simple, observable, no separate infra at MVP | Volume growth |
| Search | PostgreSQL full-text (GIN) | Zero additional infrastructure for MVP | Quality or scale requirement for marketplace search |
| AI provider | Google Gemini (initial, via provider interface) | API availability, cost; interface allows swap | Provider quality, cost, or feature requirements |
| Cache | In-process or Redis | Only where specifically needed | Load-driven |

## 31.3 Repository Structure Direction

```
/apps
  /web              ← Next.js: all surfaces (platform website, marketplace,
                         business website, workspace, consumer, admin)
/packages
  /kernel           ← Business aggregate, capability computation, domain types
  /modules          ← One directory per optional module (21 + 13 AI + Core groups)
  /module-sdk       ← ModuleManifest contract, shared types, RLS policy generator
  /events           ← Event bus abstraction (transport-agnostic)
  /renderers        ← Shared renderer interfaces and implementations
  /ui               ← Component library (design system components)
  /db               ← Schema, migrations, RLS and privileged-execution conventions
  /auth             ← Auth helpers, RLS session-context binding, permission checks
/workers
  /event-processor  ← Background event fan-out and retry
  /statistics       ← Async trust score / statistics recompute
  /ai-context       ← AI employee execution workers
  /search-indexer   ← Search index sync worker
/infrastructure
  /migrations       ← Kernel and module migrations
```

---

# 32. Failure and Degraded Modes

The platform maintains core data integrity when external dependencies fail.

| Failure scenario | Expected behavior |
|---|---|
| **Payment provider unavailable** | Existing Business operational data accessible. Payment collection shows temporary unavailability. No Business data lost. Retry on recovery. |
| **Webhook receipt persistence fails** | Return a provider-appropriate failure, not success, so delivery can be retried. No canonical business effect runs until receipt is durably recorded. |
| **AI provider fails** | AI features show service-unavailable state. Non-AI platform capabilities unaffected. |
| **Search index delayed** | Marketplace search may lag. Platform degrades to querying primary DB directly (slower but functional). Search index catches up via replay. |
| **Messaging provider fails** | Notification delivery fails gracefully. Core Business operations (orders, bookings) continue. Retry on recovery. |
| **Background job fails** | Job enters dead-letter queue. Visible in Admin. Business data is not corrupted. Background effect retries or requires manual intervention. |
| **Cache layer unavailable** | Application falls back to database reads. Performance degrades but functionality is preserved. |
| **CDN unavailable** | Asset URLs fall back to origin. Business Websites remain functional. |

The architectural principle: **Core Business data does not become inaccessible merely because one external provider fails.**

---

# 33. Technical Anti-Patterns

The following patterns are explicitly rejected and should be treated as architecture defects if found:

| Anti-pattern | Why rejected |
|---|---|
| One database or application per Business type | Destroys the "one platform" principle |
| One codebase per Business | No. One platform, configuration-driven. |
| Arbitrary generated Website source code stored as the standard model | Security risk; impossible to update platform design |
| Frontend-only authorization | Hidden buttons are not authorization |
| Module activation as Entitlement substitute | A stale enabled state cannot bypass absent or expired commercial rights |
| Permission as Entitlement substitute | Neither replaces the other |
| Business type hard-coded in application logic | `if (businessType === 'salon')` in business logic is forbidden |
| Vendor-specific payment objects as canonical domain | Razorpay fields are not canonical platform domain language |
| Customer money through the founder manually | Normal flow uses Business merchant/linked account and settlement destination |
| AI with unrestricted database access | AI tools go through platform service interfaces with authorization checks |
| Premature microservices | Services extracted when a specific, measured requirement demands it — not aesthetics |
| Kafka-scale event infrastructure for MVP | Postgres-backed job queues are appropriate for MVP |
| Cross-module table reads or writes | Violates strict data ownership and turns module boundaries into conventions rather than enforceable contracts |
| Importing another module's internal implementation | Creates hidden coupling; cross-domain use must go through a stable public contract |
| Request/response simulated through events | Obscures failure semantics and latency; immediate results use a public service/interface contract |
| Acknowledging a webhook before durable receipt persistence | A crash can permanently lose the provider event after success was acknowledged |
| Privileged database bypass for routine application operations | RLS may not apply; use user-scoped access or an enumerated, explicitly tenant-scoped system operation |
| Duplicated consumer and Business identities | One Platform Identity; separate contexts |
| One giant table for all module data | Module data owned by each module in its own tables |
| JSON for every domain object | Real columns for anything queried, filtered, or reported |
| Deleting data automatically on downgrade | Commercial change does not destroy Business data |

---

# 34. Architecture Diagrams

## 34.1 Module Access Evaluation Flow

```
User requests module capability
    │
    ▼
Business has active Commercial Entitlement?
    NO → Entitlement gate
         → Show commercial recovery to Owner
         → Neutral state to others
    YES ▼
Module enabled by Business?
    NO → Show enablement path to authorized users
    YES ▼
Configuration complete and valid?
    NO → Show setup required state
    YES ▼
Applicable at this Location?
    NO → Location unavailability state
    YES ▼
User has permission for this action?
    NO → Permission gate (hidden or request-access)
    YES ▼
Resource/workflow state permits?
    NO → State constraint: explain and offer next action
    YES ▼
ALLOW ACTION
```

## 34.2 Business Website Rendering Flow

```
Incoming request for Business Website page
    │
    ▼
Tenant Resolution: slug → Business
    │
    ▼
Load BusinessAggregate:
  Business + active modules + capabilities
  (assembled through public contracts/read models,
   never cross-module table access)
    │
    ▼
Resolve requested Page from Website config
    │
    ▼
For each Section (in order):
  → Look up SectionType component
  → Inject module data if section references module
  → Apply Business theme tokens
    │
    ▼
Server-render HTML with SEO metadata
    │
    ▼
Return response to browser / CDN
```

## 34.3 Merchant Payment vs Platform Billing

```
MERCHANT / CUSTOMER PAYMENTS
──────────────────────────────────────────────────────────────
Customer → Business Website or Marketplace transaction
                          │
                     payments module
                          │
              svc-payment-providers adapter
                          │
              Razorpay / other provider
                          │
              Business merchant / linked account
                          │
              Business settlement destination
                          │
              Order / Booking / Invoice / Membership
              payment state updated

PLATFORM BILLING
──────────────────────────────────────────────────────────────
Business → Platform commercial billing
                          │
              svc-payment-providers (platform billing adapter)
                          │
              Platform billing provider
                          │
              Platform billing account
                          │
              Confirmed commercial outcome
                          │
              svc-entitlement-billing:
              Entitlement updated → Capability evaluation updated
```

Provider callbacks complete merchant-payment and platform-billing state through the durable inbound webhook pipeline in Section 20.

## 34.4 AI Governed-Action Flow

```
AI employee trigger (event subscription or user prompt)
    │
    ▼
svc-ai-runtime
    │
    ├── Load Business context (BusinessAggregate read-only view)
    │
    ├── AIModelProvider abstraction → model API call
    │
    └── AI requests tool use?
            │
            ├── Tool in approved list for this AIEmployeeConfiguration?
            │      NO → Deny tool; log attempt; escalate or continue without
            │
            └── YES → Platform authorization check for tool's domain action
                           │
                           ├── FAIL → Deny; log
                           │
                           └── PASS → Human approval required by config?
                                          │
                                          ├── YES → Queue for human review;
                                          │         notify authorized member
                                          │
                                          └── NO → Execute tool via platform
                                                   service interface
                                                   │
                                                   └── Write AIInteractionRecord
                                                       + AuditEvent
```

## 34.5 Inbound Provider Webhook Receipt Flow

```
Provider POST webhook
    │
    ▼
Verify signature / authenticity
    │ INVALID → Reject; no success acknowledgement
    ▼
Idempotency / duplicate check
    │ DUPLICATE WITH DURABLE RECEIPT → Success acknowledgement;
    │                                  do not process again
    ▼
Durably persist receipt/event
or commit durable queue/outbox record
    │ PERSISTENCE FAILS → Return failure; provider retries
    ▼
Provider-required success acknowledgement
    │
    ▼
Process business effects asynchronously
    │
    ├── SUCCESS → Record outcome and emit domain events
    ├── FAILURE → Retry with backoff
    └── EXHAUSTED → Dead-letter and surface in Admin
```

---

# 35. Implementation-Readiness Checklist

Open decisions block only the affected work described below. They do not impose a blanket halt on unrelated canonical foundation work.

**A. Foundation Blocker** — must be resolved before the affected foundational implementation begins.  
**B. Feature Blocker** — does not block platform foundation, but must be resolved before implementing the affected feature or module.  
**C. Pre-Production Decision** — implementation may begin with an abstraction, placeholder, or development default, but the decision must be resolved before production launch or production traffic.  
**D. Commercial Decision** — does not block core technical implementation unless the affected commercial behavior is being implemented.

| Decision | Category | Status | Who decides | Exactly what it blocks | Does not block |
|---|---|---|---|---|---|
| MVP scope: which modules ship at launch | C — Pre-Production Decision | Deferred | Product/Founder | Final MVP vertical-slice selection, launch acceptance criteria, and final implementation sequencing | Kernel, identity, Business model, Platform Core, module SDK, and generic Workspace foundation |
| First optional modules to implement | B — Feature Blocker | Deferred | Product | Sequencing and implementation of the first optional module set | Platform Core, shared services, module registry, and generic module lifecycle |
| Repository structure: monorepo tool (Turborepo/Nx) | A — Foundation Blocker | Deferred | Engineering | Formal repository bootstrap, workspace tooling, and CI task graph | Product or domain decisions |
| Deployment environment: cloud provider, region | C — Pre-Production Decision | Deferred | Engineering/Founder | Production/staging infrastructure provisioning, regional deployment, and production compliance configuration | Local development, domain modeling, schemas, migrations, and application implementation |
| Managed PostgreSQL choice (Supabase vs. AWS RDS vs. other) | A — Foundation Blocker | Deferred | Engineering | Final database provisioning, connection strategy, provider-specific RLS/session binding, and migration runtime | Vendor-neutral domain/schema design and migration authoring |
| Authentication provider final choice | A — Foundation Blocker | Deferred | Engineering | Production identity/session integration and provider-specific authentication implementation | Canonical identity, context, permission, and authorization model design |
| Initial search approach (Postgres GIN vs. immediate Typesense) | B — Feature Blocker | Deferred | Engineering | Initial `svc-search-discovery` implementation and Marketplace indexing infrastructure | Non-search Platform Core and Marketplace page structure |
| Background job mechanism (pg-boss vs. BullMQ vs. Inngest) | A — Foundation Blocker | Deferred | Engineering | Durable worker runtime, retry/dead-letter implementation, webhook async effects, and event fan-out | Domain event contracts, outbox schema, kernel, identity, and synchronous request paths |
| Initial AI provider and model selection | B — Feature Blocker | Deferred | Product/Engineering | Live model adapter integration and production AI quality/cost tuning | AI governance, tool authorization, audit model, and provider-neutral runtime contracts |
| Payment provider implementation sequence (Razorpay, KYC flow) | B — Feature Blocker | Deferred | Founder/Business | Live merchant payment collection, provider onboarding/KYC, settlement, and provider webhook configuration | Payment domain model, provider interface, and unrelated order/booking workflows |
| Platform domain name and URL structure | C — Pre-Production Decision | Deferred | Founder | Production DNS, canonical public URLs, SEO metadata, and production redirect rules | Development routes, stable internal Business-ID routes, and slug-resolution implementation |
| Object storage CDN configuration | C — Pre-Production Decision | Deferred | Engineering | Production asset delivery, CDN invalidation, and origin/fallback configuration | Asset model, upload workflow, signed development URLs, and storage-provider abstraction |
| Initial Business types to support at launch | B — Feature Blocker | Deferred | Product/Founder | Launch BusinessTypeProfile seeds, type-specific onboarding content, terminology, and defaults | Generic Business kernel, profile schema, and configuration-profile framework |
| First AI employee to implement | B — Feature Blocker | Deferred | Product | First AI employee persona, tool bundle, channel, and feature implementation | AI runtime foundation, governance, configuration schema, and audit entities |
| Canonical permission identifier scheme | A — Foundation Blocker | Deferred | Engineering | Final PermissionGrant identifiers, permission registry, module permission registration, and authorization implementation | Three-role model, deny-by-default policy, and access-chain architecture |
| Free vs. paid launch strategy | D — Commercial Decision | Deferred | Founder/Commercial | Launch plan catalog, pricing/packaging, billing activation, and default commercial Entitlement grants | Entitlement evaluation engine, manual/trial test grants, and non-commercial platform foundation |

---

# 36. Conflict Register

Document 10 operates using the latest approved canonical direction. The following genuine conflicts with earlier documents are noted here; Documents 01–09 are not modified.

| ID | Conflict | Documents in tension | Governing resolution |
|---|---|---|---|
| `D10-CONFLICT-001` | Document 03 defines module capability computation without Entitlement input | Doc 03 §1.7 vs. Doc 05 `KIR-005` and Doc 06 `RPA-CONFLICT-005` | Document 08 §3.5 requires Entitlement as a first-class input to capability computation. This document adopts that requirement. Document 03 §1.7 requires amendment. |
| `D10-CONFLICT-002` | Documents 03 and 04 use `owner/manager/staff/delivery_partner` as roles; Document 04 adds Accountant and Receptionist as roles | Doc 03 §5.1 vs. Doc 05 `CTX-011` and Doc 06 §4 | Primary Owner, Manager, Member are the invariant roles. Job functions are permission templates. This document adopts the canonical direction from Documents 05 and 06. |
| `D10-CONFLICT-003` | Documents 03 and 04 list `business-profile` and `website` as installable modules | Doc 03 §2.4 vs. Doc 08 §6 | Document 08 §6 governs: both are Platform Core, not optional installable modules. |
| `D10-CONFLICT-004` | Document 03 references `catalog-orders` as a single module | Doc 03 §2.4 vs. Doc 08 §22 | Document 08 §22 governs: `offerings-catalog` and `orders` are separate canonical modules. |
| `D10-CONFLICT-005` | Document 03 assumes hard-delete on module uninstall | Doc 03 §2.2 vs. Doc 05 `KIR-003` and Doc 08 §7.4 | Document 08 §7.4 governs: deactivation with data retention is the default; hard delete is a separate explicit action. |
| `D10-CONFLICT-006` | Document 04 treats Trust Score as an installable module | Doc 04 §3 vs. Doc 08 §22 | Document 08 §22 governs: Trust Score is `svc-statistics-trust`, a shared service. |
| `D10-CONFLICT-007` | Document 03 describes Supabase Auth and Supabase RLS as concrete implementations | Doc 03 §5.2, §6.2 | This document treats Supabase Auth and PostgreSQL RLS as the initial implementation choice while keeping JWT-based auth, tenant-isolated enforcement, and privileged-credential governance vendor-agnostic. |
| `D10-CONFLICT-008` | Document 03 mentions Admin impersonation | Doc 03 §5.3 vs. Doc 06 `ADMIN-ACCESS-003` | Document 06 governs: silent impersonation is prohibited; Super Admin work uses explicit attributed Admin context. |
| `D10-CONFLICT-009` | Document 03 describes events as the exclusive module-to-module mechanism | Doc 03 §3.1 and Rule 6 vs. this document §§1, 9.2, 10.1 | Module ownership remains strict, but immediate cross-domain needs may use stable public service/interface contracts; events govern asynchronous reactions and side effects. Document 03 requires amendment. |
| `D10-CONFLICT-010` | Document 04 contains events-only language for cross-module features | Doc 04 Event Bus glossary and Appendix C §2 vs. this document §§1, 9.2, 29.2 | Replace events-only wording with the synchronous-public-contract/asynchronous-event distinction. This does not authorize direct table access or internal implementation imports. |
| `D10-CONFLICT-011` | Document 03 prohibits all service-role bypass in application code, including internal tools, while this document permits narrowly enumerated privileged system-scoped operations | Doc 03 §5.2 and Rule 22 vs. this document §§6.3, 15.4, 26.3 | This document governs: privileged bypass is never a routine application path, but may be used server-side for migrations, controlled background jobs, attributed administration, platform projections, or operations that genuinely require elevation. Such access must be explicitly tenant- or platform-scoped, minimum-privilege, and audited; normal authorization still applies when acting for a user or Business. Document 03 requires amendment. |

---

# Final Validation

| Validation requirement | Status |
|---|---|
| Modular monolith is the default starting architecture | Confirmed — Section 3 |
| Business is the primary tenant boundary | Confirmed — Sections 4.2, 6, 7 |
| One identity can have consumer and Business contexts | Confirmed — Sections 4.1, 5 |
| My Activity and Business Workspace remain separate | Confirmed — Sections 5.2, 14 |
| Location scoping is explicit and subordinate | Confirmed — Sections 7, 4.2 |
| Platform Core and optional modules are technically distinct | Confirmed — Sections 8, 9 |
| Cross-domain immediate results use public contracts; asynchronous effects use events; direct cross-module table access and event-based request/response are prohibited | Confirmed — Sections 1, 9.2, 10.1, 29.2 |
| Entitlement and permission remain independent gates | Confirmed — Sections 16.4, 15 |
| Website architecture is structured, not unrestricted | Confirmed — Section 11 |
| AI Website generation produces structured configuration, not arbitrary code | Confirmed — Section 11.4 |
| Marketplace is search-first | Confirmed — Section 13 |
| Only joined Businesses appear in Marketplace | Confirmed — Section 13.1 |
| Consumer activity aggregates across Businesses without mixing Business operational data | Confirmed — Section 14 |
| Merchant payments and platform billing are permanently separate | Confirmed — Section 17 |
| Customer funds do not default to founder settlement | Confirmed — Section 17.1 |
| Provider abstraction exists without over-engineering | Confirmed — Sections 17.3, 18 |
| Inbound webhook receipt is durably persisted before provider success acknowledgement; business effects retry asynchronously and dead-letter if exhausted | Confirmed — Sections 19.3, 20, 34.5 |
| AI cannot bypass authorization | Confirmed — Sections 21.2, 21.3 |
| Normal Business-scoped operations evaluate identity, Active Business, applicable Location, permission, Entitlement, module/configuration state, and resource state server-side | Confirmed — Sections 5.1, 6.2, 15.1 |
| RLS is applied where supported by the execution context; privileged database access is server-only, narrowly scoped, explicitly tenant-validated, and separately audited | Confirmed — Sections 6.2, 6.3, 15.4, 26.3 |
| Super Admin actions are attributed and audited | Confirmed — Sections 25.1, 27.3 |
| External failures degrade safely | Confirmed — Section 32 |
| No premature microservices | Confirmed — Sections 1, 3 |
| Open decisions block only their affected foundation, feature, production, or commercial work | Confirmed — Section 35 |
| Document is usable by a small team and AI coding agents | Confirmed — Sections 3, 31 |

---

**End of Document 10 — Data & Technical Architecture**
