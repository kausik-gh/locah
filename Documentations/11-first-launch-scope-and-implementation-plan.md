# Document 11 — First Launch Scope & Implementation Plan

**Document:** 11  
**Document Status:** Canonical launch-scope and implementation-planning specification  
**Version:** 1.2  
**Date:** July 2026 (Version 1.1 amendment: September 1, 2026; Version 1.2 amendment: September 12, 2026)  
**Authority:** Governing definition of the platform's First Launch Version, launch capability depth, deliberate deferrals, implementation sequence, and launch-readiness gates  
**Depends On:** `01-vision-document.md` · `02-product-experience-bible.md` · `03-business-kernel-specification.md` · `04-master-product-specification.md` · `05-user-context-journey-navigation-architecture-specification.md` · `06-role-permission-access-experience-matrix.md` · `07-business-type-configuration-profile-specification.md` · `08-plans-modules-entitlement-model.md` · `09-complete-page-by-page-product-experience.md` · `10-data-and-technical-architecture.md` Version 1.2  
**Terminology:** **First Launch Version** is the governing term. “MVP” appears only when referencing older documents whose relevance labels or decisions use that term.

---

# 0. Document Control and Governance

## 0.1 Document Control

| Version | Date | Change |
|---|---|---|
| 1.0 | July 2026 | Initial canonical First Launch scope, module-depth classification, reference-workflow validation, and dependency-aware implementation plan. |
| 1.1 | September 1, 2026 | Additive amendment (Website Generation Overhaul work order), recorded per Document 08 §25.3 — decisions made now. §6.2 gains the AI content-authorship boundary, the one-shot questionnaire-driven generation model, and the design-reference-translation rule for prebuilt templates; §13.2 cross-references them. `FL-DEC-015` remains open (temporary founder-authorized Gemini key in place). No First Launch scope, module-depth, or sequencing change. |
| 1.2 | September 12, 2026 | Additive **decision-status** pass (documentation review), recorded per Document 08 §25.3. §26 gains a status block recording that `FL-DEC-010`–`FL-DEC-014` and `FL-DEC-019` were closed by Document 12 §0.2 and are implemented, and that `FL-DEC-003`, `FL-DEC-006`, `FL-DEC-015`, and `FL-DEC-016` remain formally open while implementation has already committed to a direction. Document 10 dependency pins corrected from Version 1.1 to Version 1.2. No First Launch scope, module-depth, sequencing, or gate change. |

## 0.2 Governance Order

This document applies the following authority:

1. Approved decisions in later canonical documents supersede conflicting older assumptions.
2. Document 08 governs the canonical distinction between Platform Core, optional Business modules, AI employee modules, and shared services.
3. Document 09 governs page families, experience surfaces, interaction states, and page-by-page behavior.
4. Document 10 Version 1.2 governs data and technical architecture, module communication, tenant isolation, webhook durability, provider boundaries, and implementation-readiness categories.
5. This document governs what is included in the actual **First Launch Version**, the depth at which it must work, what is deferred, and the order in which it should be implemented.
6. Where Document 09 uses “MVP Essential,” “Conditional MVP,” “Post-MVP,” or similar relevance labels, this document's First Launch classification is the release-scope overlay. Document 09's page-family definitions remain canonical.
7. This document completes the launch-module selection and release-sequencing inputs deferred by Document 09 and the scope decisions deferred by Document 10 §35. It does not amend those source documents; genuine supersessions are recorded in Section 27.

This document does not:

- rename or duplicate canonical modules;
- convert Business types into hard-coded products or module bundles;
- define a separate architecture for an industry;
- silently invent pricing, provider commitments, regulatory policies, or AI autonomy;
- treat all 21 optional modules as First Launch scope;
- reduce the First Launch Version to an infrastructure-only or demonstration release.

## 0.3 Canonical Launch-Depth Terms

| Term | Meaning |
|---|---|
| **Platform Core — First Launch Required** | A universal capability every launched Business receives. It must be functionally usable and cannot be treated as an optional module. |
| **A. First Launch — Full/Launch-Ready** | Production-ready for every First Launch workflow explicitly assigned to the module. “Full” means complete at the approved launch boundary, not feature-complete for all future industry depth. |
| **B. First Launch — Basic/Controlled Depth** | Production-ready for a deliberately narrow operational subset required by First Launch workflows. The module is real and usable, but advanced depth is explicitly deferred. |
| **C. Later Release** | The full optional module is not shipped in the First Launch Version. Any Core or cross-cutting function with similar language remains available where separately defined. |
| **D. Future Ecosystem** | Strategically later capability that depends on platform scale, ecosystem density, or substantially deeper operating maturity. |

## 0.4 Interpretation Rules

- A launch-depth label is metadata on a canonical module ID, not a new module.
- `bookings` supports business-adapted “Bookings,” “Reservations,” or similar terminology; no separate `reservations` module is created.
- `core-notifications` is not the deferred `messaging` module.
- Workspace operational summaries are not the deferred full `analytics` module.
- `core-team-access` is not `workforce`.
- AI-assisted initial Website generation is not an AI employee module.
- Business-Type Profiles recommend configuration, terminology, and modules. They do not grant Entitlement, activate modules, assign permissions, or establish separate data models.

---

# 1. First Launch Definition and Objective

## 1.1 First Launch Definition

The First Launch Version is the first production release made available to real Businesses and real consumers, capable of supporting real public discovery, real Business configuration, real Website publication, and real customer activity.

It must:

- operate against production data and production security controls;
- support real Business owners and authorized team members;
- support real consumers, including guest and authenticated paths where applicable;
- support real merchant payment collection through approved provider flows where online payment is selected;
- preserve Business and consumer activity correctly;
- provide support, recovery, audit, monitoring, and failure handling;
- be usable repeatedly after onboarding, not only during a staged demo.

The First Launch Version is not accepted if it only proves:

- repository structure;
- database schemas;
- generated screenshots or static prototypes;
- fake payment states;
- pre-seeded businesses with no owner-operable configuration;
- a Website that cannot be edited and published;
- a dashboard that cannot perform Business operations;
- Marketplace cards that do not hand off into a functioning Business Website and action.

## 1.2 Core Product Proof

The First Launch Version must prove one connected platform loop across both sides of the platform.

```text
BUSINESS LOOP

Sign up
→ Create Business
→ Provide essential information and operating characteristics
→ Receive AI-assisted generated setup and structured Website
→ Preview something useful early
→ Review recommended capabilities
→ Choose and configure relevant modules
→ Create/manage offerings and public content
→ Edit and publish the Website
→ Become discoverable in Marketplace search
→ Receive real customer activity
→ Operate through the adaptive Business Workspace
→ Return regularly to manage work, exceptions, and next actions
```

```text
CONSUMER LOOP

Enter platform
→ Search for a Business, product, service, or need
→ Discover a joined Business or Offering
→ Inspect the Marketplace result and Business Profile
→ Visit the Business Website
→ Perform the supported action
→ Receive confirmation/status
→ See resulting personal activity in My Activity where applicable
```

## 1.3 First Launch Success Condition

The release succeeds only if the complete loop works without founder-operated hidden steps for normal cases. Super Admin may provide attributed support, configuration correction, and troubleshooting, but must not manually perform every Business's routine operation.

Minimum proof:

1. A new Business can reach a useful generated Website before completing every advanced setup option.
2. The Primary Owner can change Business information, offerings, Website content, prices, availability, and relevant operational configuration.
3. The Website can be published and discovered through search.
4. A consumer can complete at least one supported transaction or interaction relevant to the Business.
5. The Business can manage the resulting activity in Workspace.
6. The consumer can see supported personal activity without entering the Business operating context.
7. Payment, permission, Location, Entitlement, provider, and failure states are truthfully represented.

## 1.4 Release Outcomes to Measure

The exact numeric thresholds require founder approval, but launch telemetry must make these outcomes measurable:

- Business onboarding completion and time-to-first-useful-preview;
- Website publish rate;
- Marketplace discoverability rate for eligible Businesses;
- search-to-Website handoff;
- Website action completion by action type;
- repeat Business Workspace use;
- pending-action resolution time;
- order, booking, membership, and lead workflow completion;
- payment success/failure/refund rates;
- support incidents, dead-letter events, and recovery time;
- permission, Location, and tenant-isolation failures;
- consumer return to My Activity.

---

# 2. Scope-Control Principles

## 2.1 Horizontal Platform, Controlled Launch Depth

The platform is horizontal. The First Launch Version validates shared primitives against varied Business models without attempting to replace mature vertical systems.

The First Launch must not become:

- a complete hotel property-management system;
- a complete school or learning-management ERP;
- a hospital information system or clinical records system;
- a warehouse, procurement, or supply-chain ERP;
- a Salesforce-scale CRM;
- a proprietary delivery network;
- a full accounting or taxation suite;
- a payroll and human-resources system;
- a free-form Website development agency;
- an unrestricted Wix/Webflow-style visual builder.

## 2.2 Strong Shared Primitives

Breadth is achieved through reusable primitives:

- one Business and Location model;
- typed Offerings;
- shared order and payment foundations;
- shared reservation concepts with mode-specific rules;
- structured Websites;
- capability-driven Marketplace actions;
- adaptive terminology and navigation;
- modular Entitlement, activation, configuration, permission, and resource-state gates;
- shared events and public service contracts under Document 10.

## 2.3 Scope Admission Rule

A proposed launch feature is admitted only if at least one condition is true:

1. It is required to complete the Business or consumer loop.
2. It is required by one or more approved reference workflows and can be implemented as a reusable platform primitive.
3. It is required for security, payment safety, support, observability, recovery, legal operation, or data integrity.
4. It is required to prevent a First Launch module from being misleading or unusable.

“A future Business might want it” is not sufficient.

## 2.4 Scope Change Rule

Any addition after this document is approved must state:

- affected canonical Core group/module/page family;
- reference workflow it unblocks;
- dependency and implementation cost;
- test and operational burden;
- which existing First Launch item is displaced or whether the launch date changes;
- whether it requires founder, product, security, payment, or commercial approval.

## 2.5 Approved Launch-Breadth Posture

The First Launch Version deliberately validates multiple horizontal primitives across all 11 reference models rather than proving only one narrow vertical loop. The approved 5 Full + 5 Basic optional-module scope in Sections 8–10 is therefore intentional.

This breadth does not authorize full vertical depth. It is constrained by:

- one canonical architecture;
- shared typed primitives;
- controlled module depth;
- explicit stage and readiness gates;
- the vertical-ERP exclusions in Section 2.1;
- the scope-change rule in Section 2.4.

Reducing or expanding this approved module set is a formal launch-scope change.

---

# 3. First Launch In-Scope and Deferred Summary

## 3.1 Explicitly In Scope

The First Launch Version includes:

- all 10 canonical Platform Core groups at usable launch depth;
- Platform Identity/Auth and context resolution;
- generation-first progressive Business onboarding;
- adaptive Business Workspace and operational Home;
- AI-assisted structured Website generation, editing, preview, and publishing;
- search-first Marketplace for joined Businesses and their Offerings;
- My Activity for supported consumer interactions;
- five Full/Launch-Ready optional modules:
  - `offerings-catalog`;
  - `orders`;
  - `bookings`;
  - `payments`;
  - `memberships`;
- five Basic/Controlled-Depth optional modules:
  - `customer-relationships`;
  - `leads`;
  - `inventory`;
  - `fulfilment`;
  - `workforce`;
- essential transactional delivery and Core Notifications;
- basic operational insights in Workspace Home;
- commercial account and Entitlement/recovery essentials;
- required founder/Super Admin support and operational tooling;
- audit, tenant isolation, webhook durability, observability, backup, recovery, and provider-failure handling.

## 3.2 Explicitly Deferred

The First Launch Version deliberately defers:

- full `queue-operations`;
- full `invoicing`;
- `loyalty`;
- full optional external-channel `messaging`;
- `marketing`;
- `reviews`;
- full dedicated `analytics`;
- `payroll`;
- `business-passport`;
- `business-community`;
- `b2b-network`;
- all 13 autonomous or semi-autonomous AI employee modules unless a later approved decision explicitly promotes one;
- advanced recommendation feeds and personalization;
- sophisticated Marketplace ranking and mature Trust scoring;
- map-first discovery;
- sponsored Marketplace placement;
- custom report builders, forecasting, attribution, and cohorts;
- proprietary logistics, driver fleets, or courier-marketplace operations;
- advanced warehouse, procurement, supplier, batch, expiry, forecasting, and transfer functions;
- complex CRM automation;
- complete PMS, ERP, LMS, HIMS, accounting, or payroll depth;
- platform wallet, escrow, split settlement, BNPL/credit, and unnecessary multi-currency complexity;
- unrestricted page-building or arbitrary code generation;
- Developer Platform and ecosystem marketplace capabilities.

## 3.3 Deferred Does Not Mean Absent

| Deferred full module | Required First Launch function that remains |
|---|---|
| `messaging` | `core-notifications`, transactional confirmation/status delivery, and provider delivery through shared platform services where required |
| `analytics` | Operational summaries, counts, alerts, and immediately useful metrics in `core-workspace` |
| `invoicing` | Payment receipts and transaction records where required; not a full invoice lifecycle |
| `reviews` | Business-provided public information and controlled trust/status information; no consumer review workflow |
| `fulfilment` advanced depth | Basic pickup, Business-managed delivery, zones, charges, and status under the launch-depth `fulfilment` module |
| full CRM | Basic customer record/history in `customer-relationships` and basic pipeline in `leads` |
| full Workforce | Provider profiles, service association, and availability needed by bookings/classes |

In-platform Core Notifications are mandatory. External email/SMS delivery is included only for security, verification, and transactional confirmations/statuses that the approved launch journey requires, using approved providers and consent/policy controls. Businesses do not receive general-purpose channel connection, campaign, template-management, or delivery-analytics tooling until `messaging`.

---

# 4. Experience Surfaces Required at First Launch

| Surface | First Launch responsibility | Canonical Document 09 anchors |
|---|---|---|
| Main Platform Website | Explain discovery + Business platform; route to Search, Sign In, and Create Business | `PLT-001`–`PLT-004`, `PLT-006`–`PLT-010` |
| Authentication | Shared identity, verification, recovery, and Destination Intent | `AUTH-001`–`AUTH-003` |
| Marketplace | Universal search, results, basic Location/type refinement, Business Profile, Offering handoff | `MKT-001`, `MKT-002`, `MKT-004`, basic `MKT-005`, `MKT-007`, `MKT-008` |
| My Activity | Lightweight personal context for orders, bookings, memberships, payments/receipts, notifications, and profile/settings | `ACC-001`–`ACC-005`, `ACC-007`, `ACC-008`, `ACC-011` |
| Business Website | Structured public presence plus module-contributed action flows | `WEB-001`–`WEB-010`, `WEB-012`, `WEB-014`, `WEB-016` |
| Business Onboarding | Generate useful setup early, then refine and configure progressively | `ONB-001`–`ONB-009` |
| Business Workspace | Real content management, operations, configuration, action queues, and adaptive navigation | `CORE-001`–`CORE-016`, with launch depth defined here |
| Commercial Experience | Current plan/relationship, payment method, billing history, Entitlement recovery, and controlled changes | `COM-001`–`COM-003`, `COM-006`–`COM-009` as applicable to approved strategy |
| Platform Super Admin | Business inspection/support, Website assistance, Entitlements, provider state, issues, audit, health | `ADM-001`–`ADM-005`, `ADM-007`–`ADM-013`, `ADM-016`–`ADM-019` at launch-required depth |

The First Launch does not require every page family in Document 09. It requires every page family necessary to complete the in-scope workflows and recover their known states.

## 4.1 Document 09 Page-Family Launch Overlay

Document 09 page-family definitions remain canonical. This table changes only their First Launch depth.

| Page family/area | First Launch depth |
|---|---|
| `PLT-001`–`PLT-004`, `PLT-006`–`PLT-010` | Required; `PLT-005` AI marketing/employee detail is Later |
| `AUTH-001`–`AUTH-003` | Required |
| `MKT-001`, `MKT-002`, `MKT-004`, `MKT-007`, `MKT-008` | Required |
| `MKT-005` | Basic Location and type/Offering refinement only |
| `MKT-003`, `MKT-006` | Later/Future |
| `ACC-001`–`ACC-003` | Required Core My Activity shell/profile/settings |
| `ACC-004` | Required because `orders` is First Launch Full |
| `ACC-005` | Required because `bookings` is First Launch Full |
| `ACC-007` | Required because `memberships` is First Launch Full |
| `ACC-008` | Required because `payments` is First Launch Full |
| `ACC-011` | Required for orders, bookings, memberships, payments/receipts, and platform/transactional notifications |
| `ACC-006`, `ACC-009`, `ACC-010` | Deferred with Queue, Reviews, and saved/followed features |
| `WEB-001`–`WEB-006`, `WEB-016` | Required structured Website foundation |
| `WEB-007` | Promoted to real First Launch cart, checkout, and confirmation depth |
| `WEB-008` | Required at Basic tracking/fulfilment-status depth |
| `WEB-009`, `WEB-010` | Promoted to First Launch multi-model booking/reservation depth |
| `WEB-012` | Promoted to First Launch Memberships depth |
| `WEB-014` | Promoted to First Launch Basic Leads/enquiry depth |
| `WEB-011`, `WEB-013`, `WEB-015` | Deferred with Queue, Reviews, and full Invoicing/payment-link experience |
| `ONB-001`–`ONB-009` | Required |
| `CORE-001`–`CORE-011`, `CORE-013`–`CORE-016` | Required |
| `CORE-012` | Built-in template assignment is available through `CORE-010`/`CORE-011`; custom template authoring/merging UI remains Later |
| `AI-004` | Required for governed generation review; other AI employee/operation families remain Later/Future unless separately approved |
| `AI-001`–`AI-003`, `AI-005`–`AI-017` | Later/Future; no autonomous or semi-autonomous AI employee is required |
| `COM-001`–`COM-003`, `COM-006`–`COM-009` | Required only to the depth applicable to the approved commercial strategy |
| `COM-004`, `COM-005` | Later unless the approved launch strategy specifically requires trials or usage views |
| `ADM-001`–`ADM-005`, `ADM-007`–`ADM-012`, `ADM-016`–`ADM-019` | Required |
| `ADM-013` | Promoted to launch-required merchant payment-onboarding investigation depth |
| `ADM-006`, `ADM-014`, `ADM-015` | Later |
| `ADM-020`, `ADM-021` | Future |

## 4.2 Optional-Module Workspace Page Depth

| Module | First Launch Workspace pages/experiences | Deliberately deferred page depth |
|---|---|---|
| `offerings-catalog` | List, editor, categories, variants/options, status and Location availability | Advanced import/export and merchandising |
| `orders` | Board/list, detail, history, state actions, cancellation/refund coordination | Advanced returns and wholesale tooling |
| `bookings` | Calendar/list, detail, availability, policies, confirmation/cancellation | Waitlist, queue, advanced recurrence, vertical PMS views |
| `payments` | Connection/onboarding state, overview, transactions, refund detail/actions, settings, reconciliation state | Standalone payment links, multi-provider optimization, advanced payout analytics |
| `memberships` | Plans, members, detail, validity, renewal state | Advanced dunning, family/corporate plans, attendance systems |
| `customer-relationships` | Customer list, detail, cross-interaction timeline | Segments UI, advanced import/merge, automation |
| `leads` | Four-state pipeline, detail, capture source/context, follow-up, won/lost conversion | Proposal stage, complex pipeline builder, scoring/automation |
| `inventory` | Overview, stock detail, adjustment, low/out-of-stock alerts | Procurement, suppliers, warehouse and forecasting pages |
| `fulfilment` | Board/list, job detail, pickup/delivery mode, zones/charges, statuses | Partner marketplace, route optimization, performance suite |
| `workforce` | People/providers, profile, service association, schedules/availability, Location applicability | HR, leave, payroll, performance, shift optimization |
| All C/D modules | No full module Workspace pages at First Launch | Their Document 09 page families remain Later/Future |

---

# 5. Reference Business Models

## 5.1 Purpose

Reference Business models are validation lenses, not an allowlist, product edition, architecture, automatic module bundle, or promise of complete vertical depth.

Other Businesses may join through the generic type/characteristics path. “Other / Not sure” remains a valid onboarding choice.

## 5.2 Reference Validation Matrix

| # | Reference model | Representative examples | First Launch path | Primary canonical modules | Controlled boundary |
|---:|---|---|---|---|---|
| 1 | Retail commerce | Furniture, clothing, electronics | Products → discovery → purchase or enquiry → payment → order → fulfilment | `offerings-catalog`, `orders`, `payments`, basic `inventory`, `fulfilment`, `leads` | No procurement, warehouse ERP, credit, or advanced shipping network |
| 2 | High-frequency retail | Supermarket, grocery | Products → stock → cart → checkout → COD/online → pickup/delivery | `offerings-catalog`, `orders`, `payments`, basic `inventory`, `fulfilment`; `customer-relationships` through order-event projection | No advanced replenishment, batch/expiry, supplier, or route optimization |
| 3 | Food business | Restaurant, café, home-food seller | Menu → order → payment/COD → pickup/Business delivery; optional table reservation | `offerings-catalog`, `orders`, `payments`, basic `inventory`, `fulfilment`, `bookings` | No kitchen-display ERP, aggregator fleet, or full restaurant-management suite |
| 4 | Accommodation | Hotel, homestay | Room/unit offering → dates/guests → availability → reservation → deposit/full/pay-at-property | `offerings-catalog`, `bookings`, `payments`, basic `customer-relationships` | No full PMS, housekeeping, channel manager, rate/yield engine, or folio accounting |
| 5 | Appointment-based services | Salon, spa, consultant | Service → provider/availability → slot → booking → payment/deposit | `offerings-catalog`, `bookings`, `payments`, basic `workforce`, `customer-relationships` | No clinical records or deep practice-management system |
| 6 | Membership-based business | Gym, studio, club | Plan/class → enrolment → payment → validity → class/session booking | `offerings-catalog`, `memberships`, `payments`, `bookings`, basic `workforce` | No payroll, access hardware, complex training plans, or full gym ERP |
| 7 | Professional/general business | Agency, lawyer, accountant | Website/search → service → enquiry → lead follow-up | `offerings-catalog`, basic `leads`, `customer-relationships` | No matter/case management, document practice suite, or Salesforce-scale CRM |
| 8 | Lead-driven business | Real estate, car dealer, interior designer | Listing/service → enquiry → lead → contact → qualify → won/lost | `offerings-catalog`, basic `leads`, `customer-relationships`; optional `orders`/`payments` where suitable | No brokerage MLS, dealer-management, quotation ERP, or sales automation |
| 9 | Education/cohort business | Tuition centre, coaching centre, academy | Course/class/plan → enrolment/payment → membership validity → scheduled class | `offerings-catalog`, `memberships`, `payments`, `bookings`, basic `workforce` | No student information system, grading, attendance ERP, LMS, or parent portal suite |
| 10 | Repair/home services | Plumber, electrician, appliance repair | Service request → lead or booking → provider/schedule → completion → payment | `offerings-catalog`, `leads` or `bookings`, `payments`, basic `workforce`, `customer-relationships` | No field-service route optimization, parts ERP, or dispatch marketplace |
| 11 | Rental/resource business | Equipment, vehicle, venue rental | Resource → period availability → reservation → deposit/full payment → return/completion | `offerings-catalog`, `bookings`, `payments`, basic `inventory` where quantity-based | No fleet telemetry, damage claims system, dynamic pricing, or complete rental ERP |

## 5.3 Validation Rule

Each model must pass:

1. onboarding without irrelevant mandatory steps;
2. useful generated Website output;
3. correct terminology without changing canonical IDs;
4. creation of representative Offerings;
5. public discovery;
6. at least one credible supported action;
7. Business-side operational management;
8. correct consumer activity where applicable;
9. truthful boundary messaging for deferred vertical depth;
10. permission and Location behavior appropriate to the model.

---

# 6. Platform Core — First Launch Requirements

All 10 Platform Core groups from Document 08 are required.

| # | Core group | Canonical ID | Required First Launch depth | Deliberately deferred depth |
|---:|---|---|---|---|
| 1 | Business Identity | `core-business-identity` | Create/resume Business; lifecycle and visibility; name, type/characteristics, contact identity, slug; creator becomes Primary Owner | Complex legal entity management and jurisdiction-specific registration automation |
| 2 | Business Profile | `core-business-profile` | Description, logo, cover/media, contact, hours summary, public details, profile completeness, Marketplace-ready projection | Mature Trust Score, advanced verification, and Business Passport credentials |
| 3 | Website/Public Presence | `core-website` | AI-generated structured Website; Home/About/Contact/Locations; sections, theme variants, navigation, preview, publish, SEO essentials, module-contributed experiences | Arbitrary layout canvas, custom code, unrestricted HTML/JS, agency/reseller model |
| 4 | Workspace Foundation | `core-workspace` | Context-aware shell, Business/Location switchers, adaptive navigation, operational Home, search/command entry, permission-aware rendering, setup/recovery states | Full custom dashboards, dedicated full Analytics module, ecosystem workspaces |
| 5 | Settings | `core-settings` | Business information, operational defaults, terminology/configuration, publication, transaction, provider, and security settings relevant to launch | Exhaustive enterprise policy administration |
| 6 | Location Foundation | `core-locations` | One-or-more-Location model from day one; address/service area, hours, availability scope, public selection, Workspace switching, member scope | Advanced territory optimization and enterprise branch hierarchy |
| 7 | Team, Roles & Access | `core-team-access` | Primary Owner/Manager/Member; invitation, activation, removal, Location scope, explicit grants, built-in launch templates, deny-by-default | Custom template builder/merging and advanced approval/delegation UX unless separately approved |
| 8 | Module Management | `core-module-management` | Catalog of launch modules, dependency explanation, Entitlement state, explicit enable/configure/deactivate/re-enable, readiness validation | Third-party module marketplace and developer installation |
| 9 | Basic Notifications | `core-notifications` | In-platform operational inbox, transactional and setup alerts, provider/payment exceptions, preferences for required channels | Full external-channel campaign messaging, rich template management, broad delivery analytics |
| 10 | Marketplace Presence | `core-marketplace-presence` | Joined-Business projection, explicit discoverability, search indexing, basic Location/type/Offering signals, Website handoff | Unclaimed listings, recommendation feed, mature personalization, sponsored ranking, map-first discovery |

## 6.1 Shared Launch Foundations Beyond the 10 Core Groups

The following shared services/systems are also launch-required:

- `svc-identity-auth`;
- `svc-tenancy-access`;
- `svc-module-registry`;
- `svc-entitlement-billing`;
- `svc-event-audit`;
- `svc-rendering`;
- `svc-capability-evaluation`;
- `svc-ai-runtime` only to the depth required for governed Website generation;
- `svc-search-discovery`;
- `svc-media`;
- `svc-realtime` where live operational updates require it;
- `svc-statistics-trust` only for controlled operational/quality statistics, not mature Trust scoring;
- `svc-communication-delivery` for required transactional delivery;
- `svc-payment-providers`.

## 6.2 Generation-First Progressive Onboarding

The required sequence is:

```text
Create account
→ Create Business
→ Essential Business identity
→ Type and operating characteristics
→ Initial Location/operating model
→ AI generates structured setup and Website draft
→ Owner previews useful result
→ Platform recommends relevant capabilities
→ Owner explicitly chooses
→ Entitlement/activation/configuration gates resolve
→ Publish and enter Workspace
→ Continue contextual setup progressively
```

The generated result:

- is a draft, never a silent publication;
- uses structured sections and allowed variants;
- may use early Offerings when available;
- is editable;
- cannot purchase, enable, or authorize optional modules without explicit action;
- must degrade to deterministic templates if the AI provider is unavailable;
- must not block Business creation or later manual editing.

> **Amendment — 2026-09-01 (Website Generation Overhaul work order; additive, dated per Document 08 §25.3). Decided now.**
>
> - **AI authors content only.** The generated result's copy, image selection,
>   layout-variant choice, and section ordering are AI-authored; cart/checkout,
>   stock display, navigation semantics, and order/booking confirmation are fixed
>   platform code and are never AI-authored. (Document 12 §12.6.)
> - **One call, driven by a questionnaire.** Generation is fed by a skippable,
>   business-type-aware questionnaire and makes exactly one provider call per
>   Business — not a conversation with the owner. Skipped fields use the
>   deterministic fallback, not a second call. This was chosen deliberately to keep
>   cost bounded and output safe. (Document 12 §12.7.)
> - **Templates are design references.** A prebuilt template is translated into a
>   theme definition and new layout variants for existing section types; raw
>   external HTML/CSS/JS is never rendered. The pipeline is idle until a founder
>   supplies an export. (Document 12 §12.8.)
> - `FL-DEC-015` stays open. A temporary founder-authorized Gemini key is in place;
>   the provider, budget, and fallback policy still require formal closure. The
>   deterministic fallback remains mandatory regardless.

## 6.3 Platform Commercial Essentials

The Entitlement engine, commercial relationship record, recovery states, manual/test grants, and plan-aware capability evaluation are required even if the founder selects a free First Launch strategy.

Exact pricing, plan names, paid packaging, trial duration, and billing activation remain unresolved founder/commercial decisions. Merchant/customer Payments and platform billing remain separate.

## 6.4 AI Scope at First Launch

The four canonical AI layers have different launch treatment:

| AI layer | First Launch treatment |
|---|---|
| Embedded assistance | Permitted only where already canonical, bounded, non-blocking, reviewable, and useful inside an in-scope workflow; it must not become a launch dependency unless explicitly specified |
| Generation/configuration | Required for the initial structured Website draft and generation review; deterministic/manual fallback is mandatory |
| AI insights | Deferred beyond ordinary Core operational summaries; Core dashboard insights are not an AI insights product |
| AI employees | All 13 separately governed AI employee modules remain Later/Future unless a later approved scope change promotes one |

Any AI action remains subject to Business context, Entitlement where applicable, permission/tool authorization, observability, and audit. AI scope must not delay the core launch.

---

# 7. Business Workspace — Operational Control Centre

## 7.1 Workspace Purpose

The Business Workspace is where owners and authorized team members run the Business. It is not a statistics-only dashboard.

The Workspace must permit authorized users to:

- edit Business phone, address, service area, hours, description, logo, media, and public information;
- manage structured Website content, navigation, branding controls, preview, and publishing;
- add, edit, archive, categorize, price, and make available products, menu items, services, rooms, plans, classes, and resources;
- manage orders and their states;
- manage reservations/bookings, availability, cancellation, and status;
- manage basic stock where applicable;
- manage payment state and refunds where authorized;
- manage membership plans, enrolments, validity, and payment linkage;
- inspect customer records and interaction history at launch depth;
- capture and progress basic leads;
- manage provider/staff profiles and availability required by launch workflows;
- view and act on notifications, exceptions, configuration tasks, and provider problems;
- manage Locations, team access, enabled modules, commercial recovery, and Business settings.

## 7.2 Workspace Home Contract

`CORE-001` must answer:

1. **What is happening?**
2. **What needs attention?**
3. **What should I do next?**

Possible cards or action blocks include:

- orders today and by active state;
- pending order actions;
- bookings/reservations and exceptions;
- payment/revenue snapshot;
- failed/pending/refund payment actions;
- low/out-of-stock alerts;
- active/expiring membership activity;
- new or overdue leads;
- Website publication and Marketplace indexing health;
- incomplete setup/configuration;
- Location-specific exceptions;
- Core Notifications and operational errors.

These are operational compositions from Core and enabled modules, not a substitute for the later `analytics` module.

## 7.3 Adaptive Navigation

Navigation is computed from:

```text
Platform Core
+ Entitlement
+ enabled/configured module contributions
+ Business and Location configuration
+ user role, permission, and Location scope
+ current data/resource state
+ progressive-complexity policy
```

Examples:

| Business | Adaptive labels/emphasis |
|---|---|
| Restaurant | Menu · Orders · Reservations · Delivery |
| Hotel | Rooms · Reservations · Payments |
| Gym | Plans · Memberships · Classes · Members |
| Supermarket | Products · Orders · Inventory · Delivery |
| Professional service | Services · Enquiries · Customers |

The underlying modules, routes, authorization, and data ownership remain canonical and shared.

## 7.4 Permission Minimum

Launch must support:

- Primary Owner, Manager, Member;
- Business-wide or selected-Location membership;
- built-in permission templates appropriate to the launch modules;
- explicit permission grants;
- owner-only commercial and ownership actions;
- neutral no-access, wrong-Location, configuration-required, Entitlement-required, and suspended states;
- server-side enforcement independent of navigation visibility.

Advanced custom template authoring and template merging may remain later, but the canonical permission identifier scheme is a Foundation Blocker and must be resolved before authorization implementation.

---

# 8. Canonical Optional Module Classification

## 8.1 Complete 21-Module Classification

| # | Canonical module | ID | First Launch classification | Primary rationale |
|---:|---|---|---|---|
| 1 | Offerings Catalog | `offerings-catalog` | A — Full/Launch-Ready | Shared foundation for what a Business sells, provides, reserves, or enrols customers into |
| 2 | Orders | `orders` | A — Full/Launch-Ready | Required for real commerce and Business-side operations |
| 3 | Bookings | `bookings` | A — Full/Launch-Ready | Required to validate appointment, accommodation, table, class, and rental reservation models |
| 4 | Queue Operations | `queue-operations` | C — Later Release | Live walk-in queues are not required to prove the selected launch loops |
| 5 | Customer Relationships | `customer-relationships` | B — Basic/Controlled Depth | Required for useful cross-interaction Business context without building a full CRM |
| 6 | Leads | `leads` | B — Basic/Controlled Depth | Required for enquiry-driven Businesses that do not transact immediately |
| 7 | Inventory | `inventory` | B — Basic/Controlled Depth | Required to keep product commerce credible without warehouse ERP depth |
| 8 | Payments | `payments` | A — Full/Launch-Ready | Required for real online/deposit/refund flows while supporting approved offline methods |
| 9 | Invoicing | `invoicing` | C — Later Release | Full receivables/invoice lifecycle is not required for launch proof |
| 10 | Fulfilment | `fulfilment` | B — Basic/Controlled Depth | Required for pickup and Business-managed delivery without proprietary logistics |
| 11 | Memberships | `memberships` | A — Full/Launch-Ready | Required for gyms, clubs, studios, packages, and cohort-style enrolment |
| 12 | Loyalty | `loyalty` | C — Later Release | Retention mechanics are not required to prove core transaction loops |
| 13 | Workforce | `workforce` | B — Basic/Controlled Depth | Required for provider/service association and reservation availability |
| 14 | Payroll | `payroll` | D — Future Ecosystem | Separate financial/HR depth and compliance burden |
| 15 | Messaging | `messaging` | C — Later Release | Full external-channel module is deferred; Core and transactional notifications remain |
| 16 | Marketing | `marketing` | C — Later Release | Campaign orchestration is not required for operational launch |
| 17 | Reviews | `reviews` | C — Later Release | Review eligibility, moderation, and trust systems add launch risk |
| 18 | Analytics | `analytics` | C — Later Release | Operational insights remain in Core; deep analysis is later |
| 19 | Business Passport | `business-passport` | D — Future Ecosystem | Depends on verification depth and ecosystem trust maturity |
| 20 | Business Community | `business-community` | D — Future Ecosystem | Depends on network density and moderation maturity |
| 21 | B2B Network | `b2b-network` | D — Future Ecosystem | Depends on Business graph density and new B2B workflows |

**Validation count:** 5 Full + 5 Basic + 7 Later + 4 Future = 21 canonical optional modules.

---

# 9. First Launch — Full/Launch-Ready Module Depth

## 9.1 Offerings Catalog — `offerings-catalog`

### Required

- typed Offerings:
  - product;
  - menu item;
  - service;
  - accommodation room/unit type or relevant reservable representation;
  - membership plan;
  - class/session type;
  - rental/resource;
  - general listing/service suitable for enquiry;
- title, description, category, media, active/draft/archived status;
- fixed, starting-from, variable, free, or enquiry-led price presentation as applicable;
- variants/options where needed for credible commerce;
- Location availability;
- orderable/bookable/enquiry-only behavior;
- Business Workspace list, create, edit, archive, and controlled bulk operations;
- public Website listing/detail;
- Marketplace search projection.

### Deferred

- advanced catalog import/merchandising;
- complex product information management;
- bundles/configurators beyond controlled options;
- dynamic pricing engines;
- industry-specific schemas that cannot be expressed through shared typed configuration.

### Dependencies and reference models

- Foundation for all 11 reference models.
- `orders` uses compatible orderable Offerings through public contracts.
- `bookings` uses compatible reservable Offerings through public contracts.
- `inventory` applies only to compatible stock-tracked Offerings.
- `memberships` owns membership lifecycle even when a plan has a public Offering representation.

## 9.2 Orders — `orders`

### Required end-to-end flow

```text
Browse
→ cart
→ checkout
→ select permitted payment method
→ order creation
→ Business acknowledgement/management
→ status progression
→ fulfilment or completion
→ cancellation/refund coordination where permitted
→ consumer history/status
```

Required capabilities:

- guest and authenticated consumer paths as approved by the action;
- Location-aware cart and availability;
- canonical line-item snapshots;
- price, tax/charge presentation appropriate to the policy approved under `FL-DEC-025`;
- online full payment, COD/pay-later/pay-at-Business methods where permitted;
- Business order list/board and detail;
- clear state transitions and audit;
- cancellation rules and refund coordination;
- My Activity order list/detail/status;
- Core Notification events;
- idempotent order creation and payment linkage.

### Deferred

- marketplace multi-Business cart;
- complex promotions engine;
- split orders across Businesses;
- advanced return merchandise authorization;
- wholesale order management;
- subscriptions represented as ordinary repeating orders.

### Dependencies and reference models

- Uses `offerings-catalog`.
- Calls `payments` synchronously when immediate payment initiation is required.
- Emits events for `fulfilment`, `inventory`, `customer-relationships`, notifications, and projections.
- Primary for retail, supermarket, food, furniture, and selected repair/rental flows.

## 9.3 Bookings — `bookings`

Bookings is the canonical module; “Reservations” is adaptive terminology.

Supporting multiple reservation modes is an approved horizontal-platform proof obligation, not a claim of complete hotel, restaurant, education, healthcare, or rental-system depth. Each mode shares the canonical foundation but has separately tested rules.

### Shared foundation

- reservable Offering/reference;
- Business and Location;
- reservation model/mode;
- start/end or scheduled time;
- capacity/resource constraints;
- availability evaluation;
- customer/guest details;
- status, confirmation, cancellation, reschedule policy where supported;
- deposit/full/pay-later linkage;
- Business management and consumer visibility;
- idempotent creation and conflict prevention.

### Required reservation modes

| Mode | Required launch representation | Important rule |
|---|---|---|
| Appointment | Service + time slot + optional provider | Provider and service availability may both constrain the slot |
| Accommodation | Room/unit type or named unit + date range + guest count + capacity | Night/date-range availability is not ordinary product stock |
| Table | Date/time + party size + capacity/table resource policy | Capacity and table rules differ from provider appointments |
| Class/session | Scheduled session + capacity + attendee | Capacity belongs to the session, not generic inventory |
| Rental/resource | Resource/resource type + availability period + quantity where applicable | Overlap and the approved `FL-DEC-018` completion boundary matter |

### Deferred

- complete hotel PMS and room operations;
- channel-manager synchronization;
- complex rate plans/yield management;
- waitlists and walk-in queueing;
- advanced recurring schedules;
- clinical appointment records;
- fleet telemetry, damage claims, and rental contracts;
- complex table-floor optimization.

### Dependencies and reference models

- May use reservable `offerings-catalog` entries.
- Uses `workforce` public availability contracts for provider-based and class workflows.
- Calls `payments` for deposits/full collection.
- Emits booking interaction events for `customer-relationships` and My Activity projections.
- Supports accommodation, appointment, restaurant table, gym/class, education/session, repair/home service, and rental/resource validation.

For quantity-based rental, interval/capacity availability is owned by `bookings`. `inventory` is used only when the Business also needs explicit physical-unit or consumable stock tracking; the same availability must not be double-decremented by both modules.

## 9.4 Payments — `payments`

### Required payment patterns

- online full payment;
- COD, pay later, or pay at Business where Business type, policy, and provider flow permit;
- deposit/partial upfront payment;
- refunds and canonical refund state;
- recurring payment integration only if `FL-DEC-005` approves the provider capability, policy, and launch use cases;
- merchant connection/onboarding state;
- payment attempt, status, failure, retry, and reconciliation visibility;
- Business transactions/refunds views;
- consumer payment/receipt visibility;
- payment linkage to Orders, Bookings, and Memberships;
- provider abstraction and production webhook processing.

For pay-at-property, pay-at-Business, and other approved offline balances, the canonical payment state must truthfully distinguish amount due, `pending_offline` or an equivalent approved state, and later recorded settlement. The platform must not mark an offline balance as paid merely because an Order or Booking was confirmed.

### Mandatory boundaries

- Merchant/customer payments are separate from platform billing.
- Customer funds settle through the Business's merchant/linked account and approved settlement destination.
- The founder's bank account is not a manual redistribution hub.
- Webhooks follow Document 10's durable-first sequence: verify → idempotency → durable receipt/queue → acknowledge → asynchronous effects → retry/dead-letter.
- Provider-specific objects remain adapter metadata, not canonical domain entities.

### Explicitly not included

- platform wallet;
- marketplace escrow;
- complex split payments;
- BNPL or platform credit;
- unnecessary multi-currency;
- founder-managed payout redistribution;
- standalone/ad-hoc payment-link creation and the public `WEB-015` payment-link/invoice experience;
- accounting-ledger or invoicing-suite depth.

### Dependencies and reference models

- Integrates through stable public contracts with `orders`, `bookings`, and `memberships`.
- Required across commerce, food, accommodation, appointments, gyms, education/cohorts, repair/home service, and rentals where online/deposit/recurring flows are used.
- Exact provider, KYC sequence, supported recurring method, refund mechanism, and COD policy are feature/production decisions in Section 26.

## 9.5 Memberships — `memberships`

### Required

- Business-defined plan creation;
- public plan presentation where selected;
- enrolment/purchase;
- start/end dates and validity;
- active, pending, paused where supported, expired, cancelled, and completed/consumed states as appropriate;
- fixed-duration models and, only where `FL-DEC-005` approves it, recurring models;
- payment linkage;
- manual/offline payment state where approved;
- renewal visibility;
- Business member list/detail;
- consumer membership visibility in My Activity;
- linkage to eligible class/session booking.

### Deferred

- full loyalty/rewards;
- advanced attendance;
- access-control hardware;
- complex family/corporate memberships;
- advanced freeze/credit rules;
- training plans or education progression;
- custom billing dunning beyond provider-supported basics.

If recurring collection is not approved under `FL-DEC-005`, fixed-duration Memberships and explicit manual renewal remain launch-ready; automatic renewal is deferred.

### Dependencies and reference models

- Calls `payments` for purchase/renewal where online or recurring.
- May expose a public Offering through `offerings-catalog`.
- Integrates with `bookings` for classes/sessions.
- Emits membership interaction events for `customer-relationships` and My Activity projections.
- Primary for gyms, studios, clubs, package-based services, and education/cohort models.

---

# 10. First Launch — Basic/Controlled-Depth Module Scope

## 10.1 Customer Relationships — `customer-relationships`

### Required

- Business-scoped customer record;
- verified contact details appropriate to interaction;
- timeline/summary of relevant orders, bookings, memberships, and enquiries;
- Business and Location context;
- basic notes and status where permitted;
- search and deduplication controls appropriate to launch;
- permission-aware access;
- event-maintained interaction projections from Orders, Bookings, Memberships, and Leads/enquiries, with authoritative detail fetched through owning-module public contracts.

### Deferred

- advanced segmentation;
- sales automation;
- arbitrary custom objects;
- sophisticated merge/matching;
- campaign orchestration;
- Salesforce-scale pipeline/reporting.

The same Platform Identity may correspond to separate CustomerContact records across Businesses. Businesses do not receive cross-Business consumer history.

**Dependencies/reference models:** consumes eligible interaction events from Orders, Bookings, Memberships, and Leads; supports every reference model with repeat or attributable customer interaction.

## 10.2 Leads — `leads`

### Required pipeline

```text
New enquiry
→ Contacted
→ Qualified
→ Won or Lost
```

Required fields/actions:

- source and originating context;
- Offering/listing/service reference where applicable;
- consumer contact and message;
- assignee where permitted;
- next follow-up date/basic reminder;
- notes;
- status transition history;
- Business Website enquiry capture;
- Workspace pipeline and detail;
- on Won, creation or linkage of the Business-scoped CustomerContact, retention of the Lead in interaction history, and optional handoff to an Order or Booking through its public contract where configured.

### Deferred

- complex stages and branching pipelines, including a Proposal stage;
- automated scoring;
- sequence automation;
- advanced forecasting;
- quotation/proposal suite;
- multi-touch attribution.

Primary for real estate, furniture/high-value commerce, professional services, interior design, repairs, and other enquiry-led Businesses.

**Dependencies/reference models:** uses Website/Marketplace capture context and may link to `customer-relationships`; optional Won handoffs use Orders/Bookings public contracts.

## 10.3 Inventory — `inventory`

### Required

- stock quantity;
- variant-level stock where applicable;
- Location-specific stock;
- available, low-stock, and out-of-stock states;
- manual adjustment with reason and audit;
- appropriate order-driven reservation/deduction/reversal;
- Workspace stock overview and alerts;
- public availability projection without exposing internal quantities unless configured.

### Deferred

- warehouse management;
- procurement and purchase orders;
- suppliers;
- batch/lot and expiry;
- demand forecasting;
- complex transfers;
- serial-number lifecycle;
- manufacturing or recipe/BOM management.

Inventory applies to compatible Offerings. Hotel room availability and service-provider availability are not modeled as ordinary stock.

**Dependencies/reference models:** requires compatible `offerings-catalog` entries and consumes approved Order events; primary for retail, supermarket, food stock where enabled, and physical rental units when `FL-DEC-018` requires unit tracking.

## 10.4 Fulfilment — `fulfilment`

### Required

- pickup;
- Business-managed delivery;
- delivery address;
- service/delivery zones where required;
- delivery charge configuration;
- fulfilment mode selection;
- preparation/ready/out-for-delivery/delivered or equivalent controlled statuses;
- basic customer-facing status;
- Business fulfilment list/detail;
- cancellation/failure outcome where required.

### Deferred

- proprietary driver network;
- driver marketplace;
- route optimization;
- courier aggregation breadth;
- warehouse shipping orchestration;
- complex returns logistics;
- proof-of-delivery hardware flows.

Third-party delivery integration may be added through the provider abstraction when approved, but is not required to claim launch readiness.

**Dependencies/reference models:** normally follows Orders and Location/zone configuration; primary for retail, supermarket, food, and furniture delivery.

## 10.5 Workforce — `workforce`

### Required

- operational provider/staff profile where needed;
- provider profiles independent of Workspace membership; optional Platform Identity linkage does not grant Workspace access;
- association to services/classes/resources;
- schedule and availability required by Bookings;
- Location applicability;
- active/inactive operational state;
- Workspace view/edit for authorized users.

### Deferred

- payroll;
- HR records;
- leave and attendance suite;
- performance management;
- shift optimization;
- recruitment;
- complex commission management.

Workforce does not grant Workspace access. `core-team-access` governs identity, membership, role, permission, and Location scope.

**Dependencies/reference models:** exposes availability through public contracts to Bookings; primary for appointments, classes, education sessions, and scheduled repair/home services.

---

# 11. Later and Future Modules

## 11.1 Later Release — C

| Module | ID | Why later | What remains available at First Launch | Later depth | Dependencies/reference impact |
|---|---|---|---|---|---|
| Queue Operations | `queue-operations` | Live walk-in queues are a distinct workflow not required for launch loops | Bookings/reservations and normal order statuses | Token/check-in, live board, estimates, display, queue history | May integrate with Bookings/Workforce; affects restaurants, clinics/services, and walk-in Businesses later |
| Invoicing | `invoicing` | Full invoice/receivable lifecycle adds tax, numbering, and accounting policy | Payment receipts and transaction records | Invoice creation, numbering, templates, receivables, payment collection | Online collection may use Payments; most relevant to professional, B2B, repair, and high-value commerce |
| Loyalty | `loyalty` | Requires stable customer and event history before reward economics | Membership validity and customer history | Earn/redeem rules, rewards, balances, abuse controls | Requires Customer Relationships plus eligible event sources; relevant to food, retail, supermarket, and membership Businesses |
| Messaging | `messaging` | Full external-channel operation requires channel compliance and template management | Core Notifications and required transactional delivery | Channel connections, templates, delivery logs, consent/compliance | Uses `svc-communication-delivery`; later benefits all models |
| Marketing | `marketing` | Campaign creation and attribution are not core operational proof | Public Website content and manual sharing | Audiences, campaigns, offers, automation, performance | Uses Customer Relationships and Messaging; later benefits most consumer-facing models |
| Reviews | `reviews` | Eligibility, fraud, moderation, and response policies need maturity | Published Business information and controlled platform status signals | Review collection, eligibility, moderation, response, metrics | Requires completed interaction evidence; later relevant across all public Businesses |
| Analytics | `analytics` | Deep reporting is not required to operate launch workflows | Core Workspace operational summaries and alerts | Trends, comparisons, cohorts, segmentation, attribution, forecasts, custom reports, advanced AI analysis | Consumes event/statistics projections; later relevant across all models |

## 11.2 Future Ecosystem — D

| Module | ID | What remains at First Launch | Explicitly deferred Future scope | Dependencies/reference impact |
|---|---|---|---|---|
| Payroll | `payroll` | No Payroll module; Workforce schedules and provider profiles only | Pay periods, payroll runs, statutory deductions, payslips, payout/reporting | Requires Workforce maturity, payout/compliance decisions, and jurisdiction-specific rules; later value for team-heavy models |
| Business Passport | `business-passport` | Core Business Profile and controlled platform status information | Verified credentials, issuer/evidence lifecycle, public Passport, portability | Requires verification ecosystem, credential issuers, and mature trust model; later trust value across Businesses |
| Business Community | `business-community` | No community module; ordinary support/help remains | Feed, posts, messaging, moderation, Business networking | Requires Business density, moderation, safety, and engagement model |
| B2B Network | `b2b-network` | No B2B Network module; Businesses may still publish ordinary Websites/Offerings | Supplier/partner discovery, connections, RFQs, B2B orders and graph workflows | Requires Business graph density and B2B transaction architecture; later value for retail, food, services, and B2B participants |

---

# 12. Basic Insights vs Full Analytics

## 12.1 Core Workspace Insights — First Launch

Core insights are operational and action-oriented:

- order volume and active-state counts;
- booking/reservation schedule and exceptions;
- payment/revenue snapshot from canonical payment data;
- failed/pending/refund attention;
- low-stock/out-of-stock alerts;
- active/expiring memberships;
- new/overdue leads;
- Website publish/configuration status;
- Marketplace indexing/discoverability status;
- incomplete setup and provider problems.

They must:

- respect Business, Location, permission, and available data;
- link to the operational page where action occurs;
- avoid invented zeroes when a module is unavailable;
- distinguish no data, no permission, not configured, and provider failure;
- use event projections or public contracts under Document 10, never direct cross-module table access.

## 12.2 Full Analytics — Later

The later `analytics` module covers:

- deep reports and trends;
- period comparisons;
- advanced segmentation;
- cohort and retention analysis;
- acquisition attribution;
- forecasting;
- configurable/custom reporting;
- advanced AI-driven analysis;
- richer cross-module analytical models.

Businesses must not operate blindly at launch merely because these capabilities are later.

---

# 13. Marketplace and Public Website Launch Depth

## 13.1 Search-First Marketplace

Required flow:

```text
Search
→ Results
→ Business or Offering
→ Marketplace Business Profile
→ Business Website
→ Supported action
```

Required:

- universal text query across eligible Business and Offering fields;
- basic Location and Business/Offering-type refinement;
- joined, active, discoverable Businesses only;
- sparse-market and no-result states;
- Business and Offering result types;
- capability-backed action labels;
- handoff that preserves Business, Offering, Location, and Destination Intent;
- Postgres full-text/GIN as the recommended First Launch default, subject to closure of `FL-DEC-014`; an external engine requires an explicit engineering decision;
- deterministic basic relevance, not machine-learning personalization.

Deferred:

- complex category portal;
- recommendation feed;
- mature personalization;
- map-first/spatial browsing;
- advanced faceting;
- sponsored placements;
- opaque Trust-driven ranking.

## 13.2 Structured Business Website

The Website adapts to the Business through:

- Core pages: Home, About/Business Information, Contact, Locations where relevant;
- typed structured sections;
- configurable layout variants;
- editable content;
- theme, branding, and navigation controls;
- module-contributed Offerings, cart/checkout, booking, membership, and enquiry experiences.

The same universal page structure is not forced on every Business. A lead-driven professional site may emphasize services and enquiries; a supermarket emphasizes Products and Orders; a hotel emphasizes Rooms and Reservations.

> **Amendment — 2026-09-01 (Website Generation Overhaul work order; additive, dated per Document 08 §25.3).** The AI's role in producing this adaptive structure is bounded to content: copy, image selection, layout-variant choice, and section ordering. The platform mechanics behind cart/checkout, stock display, navigation, and confirmation are fixed code, identical for every Business. Generation is a one-shot questionnaire, not a chat. See §6.2 and Document 12 §12.6–§12.8.

## 13.3 Publishing and Discovery Contract

A Business becomes discoverable only when:

- Business state/status permits it;
- required public profile data is valid;
- Website/public presence satisfies publication requirements;
- visibility is explicitly discoverable;
- Marketplace projection is successfully indexed;
- public actions shown are backed by enabled, configured, entitled, and operational capabilities.

---

# 14. My Activity — First Launch Depth

My Activity remains a lightweight consumer context, not a Business dashboard.

First Launch includes:

- profile and account settings;
- order history/status;
- booking/reservation history/status;
- membership validity/history;
- payment/receipt visibility where applicable;
- customer-side transactional and platform notifications;
- direct links back to the originating Business Website/action.

My Activity:

- does not expose Business operational data;
- does not mix operator history with personal purchases;
- progressively reveals only supported activity families;
- does not show empty module navigation for deferred interactions;
- may use lightweight projections while detail comes through originating module public contracts.

Basic lead/enquiry submission does not automatically create a new My Activity module family. Confirmation and follow-up may be delivered through the Business Website flow and consumer notifications until a later canonical consumer enquiry-history experience is approved.

Guest activity may link to an authenticated Platform Identity only after verification of the relevant phone/email identifier under Document 05. Weak matching by name, unverified contact data, device, or inference is prohibited.

---

# 15. End-to-End Reference Workflows

## 15.1 Workflow Matrix

| Workflow | Core involved | Optional modules | First Launch limitation | Later expansion |
|---|---|---|---|---|
| Supermarket | Identity, Profile, Website, Workspace, Locations, Notifications, Marketplace | Offerings, Orders, Payments, basic Inventory, Fulfilment, Customer Relationships | Basic stock and Business delivery only | Procurement, suppliers, expiry/batch, route optimization, loyalty, analytics |
| Retail commerce (including furniture) | Profile, Website, Workspace, Locations, Marketplace, Notifications | Offerings, Orders and/or Leads, Payments, basic Inventory, Fulfilment, Customer Relationships | Product purchase plus optional high-value enquiry; controlled variants and basic delivery | Advanced quotes, procurement/warehouse, returns, delivery planning, sales automation |
| Restaurant | Profile, Website, Workspace, Locations, Marketplace | Offerings, Orders, Payments, Fulfilment; optional Bookings; basic Inventory | Menu commerce and controlled table reservation; no kitchen ERP | Queue, loyalty, marketing, reviews, advanced restaurant operations |
| Hotel | Profile, Website, Workspace, Locations, Marketplace | Offerings, Bookings, Payments, Customer Relationships | Room/unit/date-range availability and reservation only | PMS, housekeeping, channel manager, rate engine, invoicing |
| Appointment Business | Profile, Website, Workspace, Marketplace | Offerings, Bookings, Payments, basic Workforce, Customer Relationships | Service/provider slots and controlled policies | Queue, messaging, marketing, reviews, advanced schedules |
| Professional Business | Profile, Website, Workspace, Marketplace, Notifications | Offerings, basic Leads, Customer Relationships | Basic enquiry and four-stage pipeline | Full CRM, automation, proposals, marketing |
| Gym | Profile, Website, Workspace, Marketplace, Notifications | Offerings, Memberships, Payments, Bookings, basic Workforce | Plans, validity, classes, provider availability | Loyalty, attendance/access integrations, payroll, analytics |
| Real Estate/Lead-Driven | Profile, Website, Workspace, Marketplace | Offerings, Leads, Customer Relationships | Listing/service enquiry and simple pipeline | MLS/dealer integrations, advanced CRM, attribution |
| Tuition/Coaching | Profile, Website, Workspace, Marketplace | Offerings, Memberships, Payments, Bookings, basic Workforce | Enrolment/validity and scheduled classes; no academic ERP | LMS, grading, attendance, parent portal, payroll |
| Repair/Home Service | Profile, Website, Workspace, Marketplace, Locations/service area | Offerings, Leads or Bookings, Payments, Workforce, Customer Relationships | Request or scheduled service; no optimized dispatch | Queue/dispatch, parts inventory depth, route optimization |
| Rental/Resource | Profile, Website, Workspace, Marketplace | Offerings, Bookings, Payments; basic Inventory where quantity-based | Period availability, reservation, payment, basic completion/return | Contracts, deposits/claims, telemetry, dynamic pricing |

## 15.2 General Retail Commerce Workflow

```text
Product/variant
→ Location availability
→ cart
→ checkout
→ online payment or approved offline method
→ Order
→ pickup or Business-managed fulfilment
→ Business Workspace management
→ consumer status/My Activity
```

For high-value or enquiry-led products, the alternative Lead path in Section 15.8 is validated after the Stage 6 Leads slice. Later: advanced merchandising, procurement/warehouse depth, complex returns, loyalty, and analytics.

## 15.3 Supermarket Workflow

```text
Product Offering
→ Location stock availability
→ cart
→ checkout
→ online payment or approved COD
→ Order
→ pickup or Business-managed delivery
→ stock adjustment
→ Business order management
→ customer status/My Activity
```

Later: procurement, supplier management, batch/expiry, advanced transfers, loyalty, route optimization.

## 15.4 Furniture Workflow

```text
Product/variant
→ enquiry OR cart/purchase
→ full or deposit payment
→ Order or Lead
→ basic fulfilment/delivery
→ completion
```

Later: advanced quotations, manufacturing/procurement, warehouse planning, sales automation.

## 15.5 Restaurant Workflow

```text
Menu item
→ cart
→ checkout
→ payment/COD
→ Order
→ pickup or Business-managed delivery
→ completion
```

Optional First Launch path:

```text
Table reservation
→ date/time
→ party size
→ capacity check
→ confirmation/deposit where configured
→ Business management
```

Later: live queue, kitchen-display depth, aggregator logistics, loyalty, marketing, reviews.

## 15.6 Hotel Workflow

```text
Room/unit type
→ dates + guests
→ date-range/capacity availability
→ reservation
→ deposit/full/pay-at-property
→ confirmation
→ Business reservation management
→ cancellation/completion
```

Room availability is reservation capacity, not normal product stock. Later: PMS, housekeeping, folio, channel manager, rate/yield system.

## 15.7 Appointment Workflow

```text
Service
→ optional provider
→ Location/date/slot availability
→ booking
→ full/deposit/pay-at-Business
→ confirmation
→ Business management
→ completion/cancellation
```

Later: queueing, advanced recurrence, clinical/industry-specific records, advanced messaging.

## 15.8 Professional/Lead Workflow

```text
Marketplace/Website
→ service/listing
→ enquiry
→ Lead: New
→ Contacted
→ Qualified
→ Won/Lost
```

Later: automation, advanced pipeline, proposals, attribution, campaign tooling.

## 15.9 Gym Workflow

```text
Plan/class Offering
→ enrolment
→ payment or approved offline state
→ Membership validity
→ class/session availability
→ booking
→ Business membership/class management
→ consumer visibility
```

Later: attendance systems, access hardware, training plans, loyalty, payroll.

## 15.10 Real Estate/Lead-Driven Workflow

```text
Listing/service
→ enquiry
→ Lead
→ source/context preserved
→ follow-up
→ Qualified
→ Won/Lost
```

Later: external listing feeds, complex agent assignment, proposal/deal-room depth, sales analytics.

## 15.11 Tuition/Coaching Workflow

```text
Course/class/plan
→ enrolment or Membership
→ payment
→ validity
→ scheduled class/session booking where applicable
→ Business membership/class management
→ consumer Membership/Booking visibility in My Activity
```

Later: grading, attendance ERP, course content/LMS, parent portal, examinations, certificates.

## 15.12 Repair/Home-Service Workflow

```text
Service
→ enquiry/Lead OR available slot/Booking
→ provider association where needed
→ approved online deposit/full payment at Booking where configured
→ service execution/completion
→ remaining payment through approved COD/pay-at-Business state where applicable
```

Post-service online payment links or invoices are Later with `invoicing`; First Launch must not imply that deferred flow. Later: optimized dispatch, parts/procurement, recurring maintenance contracts, route planning.

## 15.13 Rental/Resource Workflow

```text
Resource
→ date/time period
→ overlap/capacity availability
→ reservation
→ deposit/full payment
→ handover/start
→ return/completion where feasible
```

Later: inspection/damage claims, complex security deposits, fleet telemetry, dynamic pricing, contracts.

---

# 16. Dependency Architecture for Launch

## 16.1 Capability Dependency Graph

```text
Platform Identity/Auth
        │
        ▼
Business + Location + Team/Access + Entitlement
        │
        ├──────────────► Module Registry / Capability Evaluation
        │
        ▼
Business Profile + Offerings
        │
        ├──────────────► Structured Website Generation / Publishing
        │                         │
        │                         ▼
        │                 Marketplace Projection/Search
        │
        ├──► Orders ─────► Payments
        │      │              │
        │      ├──events────► Customer Relationships
        │      ├──events────► Inventory
        │      └──events────► Fulfilment
        │
        ├──► Bookings ──sync──► Workforce Availability
        │      │
        │      ├──sync───────► Payments
        │      └──events─────► Customer Relationships
        │
        ├──► Memberships ────► Payments
        │      └─────────────► Bookings (classes/sessions)
        │
        └──► Leads ──events──► Customer Relationships
```

The diagram indicates dependency order, not direct table access. Immediate results use stable public contracts; asynchronous reactions use domain events under Document 10.

## 16.2 Critical Sequencing Consequences

- Offerings must be available before Website generation can produce accurate product/service/room/plan/class sections.
- A minimum provider/resource availability slice of `workforce` must be implemented before provider-based appointment/class booking is accepted.
- Payment domain contracts may be designed early, but production online payment is not complete until merchant onboarding, durable webhooks, refunds, and reconciliation states pass readiness gates.
- Customer Relationships, Inventory, and Fulfilment consume events; their basic projections must be tested against idempotent replay.
- Marketplace must index only publication-ready, discoverable joined Businesses.
- My Activity depends on stable consumer-side events/projections from Orders, Bookings, Memberships, and Payments.

---

# 17. Dependency-Aware Implementation Sequence

The stages are release-planning structures, not isolated waterfall silos. Workstreams may proceed in parallel when contracts are stable. A stage exits only when its required vertical slices are demonstrably usable.

## 17.1 Stage 1 — Platform Foundation

### Scope

- repository/project foundation;
- local, test, staging baseline;
- Platform Identity/Auth;
- context resolution and Destination Intent;
- Business and Business lifecycle;
- Locations from day one;
- Team & Access;
- canonical permission identifier scheme;
- Entitlement and capability evaluation;
- module registry, activation, configuration, and lifecycle contracts;
- event/outbox/job foundation;
- tenant isolation, RLS/session binding, privileged-access governance;
- audit and security foundations;
- provider abstraction skeletons.

### Entry

- Document 10 Version 1.2 accepted.
- Repository, database, auth, job mechanism, and permission-ID decisions assigned.

### Exit

- identity can create and enter a Business context;
- Business/Location/team data is tenant-isolated;
- three roles and explicit grants enforce deny-by-default;
- Entitlement, module state, Location, permission, and resource gates are distinct;
- audit events and outbox/job processing work;
- no cross-module table access;
- automated tenant isolation and privilege-path tests pass.

## 17.2 Stage 2 — Business Presence

### Scope

- generation-first onboarding;
- Business Profile;
- Offerings foundation and representative typed Offerings;
- structured Website model/rendering;
- AI-assisted Website generation with deterministic fallback;
- Website editing, media, theme/navigation;
- preview and publishing;
- Business content management;
- initial Workspace shell/Home.

### Entry

- Stage 1 Business, access, Entitlement, media, and module contracts stable.

### Exit

- a new Business receives a useful draft early;
- owner can create representative Offerings before or during generation;
- draft is editable and publishable;
- Website renders without arbitrary code;
- publication requirements and failure states are enforced;
- AI failure does not block manual/deterministic completion.

## 17.3 Stage 3 — Discovery

### Scope

- Marketplace search entry;
- Business/Offering indexing;
- joined-Business-only rules;
- basic Location/type refinement;
- Marketplace Business Profile;
- Website handoff and Destination Intent;
- indexing health and Admin recovery.

### Entry

- published Business Profile, Website, Location, Offering, and visibility data available.

### Exit

- eligible Business becomes searchable;
- ineligible/unpublished Business does not leak;
- search result hands off to the correct Website/Offering/Location;
- no-result, sparse-market, stale-index, and index-recovery tests pass;
- search works on the approved First Launch engine.

## 17.4 Stage 4 — Commerce

### Scope

- cart/checkout;
- Orders;
- Payments;
- basic Inventory;
- basic Fulfilment;
- Customer Relationships order projection;
- Business and consumer order experiences;
- payment/COD/deposit/refund flows;
- durable provider webhooks.

### Entry

- Offerings and Website public actions stable.
- Payment provider and merchant onboarding sequence approved for implementation.

### Exit

- purchase-based general retail, supermarket, furniture, and food commerce flows pass end-to-end; enquiry-led furniture/retail paths complete after Stage 6 Leads;
- order and payment idempotency pass retry tests;
- stock adjustment/reversal is correct;
- pickup and Business delivery states work;
- refunds and cancellation coordination are attributable;
- payment provider failure degrades safely;
- customer funds settle through approved merchant paths.

## 17.5 Stage 5 — Reservations

### Scope

- shared reservation/availability foundation;
- minimum `workforce` provider/profile/availability slice built before dependent booking modes;
- appointment booking;
- accommodation reservation;
- table reservation;
- class/session booking;
- rental/resource reservation where included;
- payment/deposit integration;
- consumer and Business management experiences.

### Entry

- typed reservable Offerings available.
- payment contract stable.
- minimum Workforce availability contract implemented.

### Exit

- appointment, accommodation, table, and capacity-only class/session modes pass their distinct invariants;
- the rental/resource subset approved by closed `FL-DEC-018` passes; return/completion is required only if that decision includes it;
- concurrency/overbooking tests pass;
- hotel date-range availability is not stock;
- provider appointment availability is not room inventory;
- table capacity and capacity-only class/session booking work;
- cancellations, deposits, and My Activity projection work.

## 17.6 Stage 6 — Relationships, Leads, Memberships, and Workforce Completion

### Scope

- customer interaction history;
- basic lead capture/pipeline/follow-up;
- membership plan/enrolment/validity;
- recurring payment integration where approved;
- Workforce launch-depth completion;
- class/provider associations.

### Entry

- Orders/Bookings events stable enough for projections.
- Payments recurring capability decision resolved where used.

### Exit

- lead-driven, professional, gym, education, repair, and membership flows pass;
- customer records remain Business-scoped;
- membership validity and payment states reconcile;
- membership-gated and provider-linked class/session booking passes for gym and education fixtures;
- Workforce remains separate from Team & Access;
- no advanced CRM, payroll, or education ERP scope has leaked in.

## 17.7 Stage 7 — Platform Completion

### Scope

- adaptive Workspace navigation completion;
- operational Home/dashboard aggregation;
- My Activity projections and details;
- Core Notifications and transactional delivery;
- commercial account/recovery essentials;
- Super Admin launch operations;
- audit and observability;
- security hardening;
- backup/restore and failure/recovery;
- permission, Entitlement, Business/Location, provider, and resource-state testing.

### Entry

- all launch modules have stable workflows and events.

### Exit

- every in-scope operational exception has a truthful recoverable state;
- Admin can inspect and support without silent impersonation;
- dead-letter, provider, search, payment, Website, and entitlement failures are visible;
- My Activity remains separate from Workspace;
- dashboard cards link to operational actions and respect permission/Location;
- security and payment readiness gates in Sections 21.1 and 21.2 pass.

## 17.8 Stage 8 — Launch Validation

### Entry

- Stage 7 exit criteria pass.
- All applicable Section 26 Production Blockers are closed or have an explicitly approved non-production limitation.
- Production-like environments, reference fixtures, providers, support ownership, and Sections 21–22 readiness evidence are available.

### Scope

- run complete real-world journeys across all 11 reference models;
- validate guest/authenticated consumer paths;
- validate Primary Owner, Manager, Member, Location-scoped Member, and Super Admin;
- validate production-like payment/provider failure;
- validate recovery, support, and data integrity;
- perform founder/product go/no-go review.

### Exit

- every mandatory launch-readiness criterion in Sections 22.1–22.4 is met;
- unresolved Production Blockers are closed;
- accepted limitations are documented in product/support language;
- rollback, support ownership, monitoring, and incident response are ready.

---

# 18. Data, Migration, and Seed Strategy

## 18.1 Migration Principles

- Schema changes use versioned migrations.
- Platform Core schema precedes optional module schema that depends on it.
- Each module owns its tables and migrations.
- Cross-module references use stable IDs/contracts without authorizing cross-module table reads.
- RLS policies and privileged execution rules ship with the relevant schema.
- Destructive migrations require explicit data-retention and rollback plans.
- Module deactivation, downgrade, or trial expiry never silently deletes Business data.

## 18.2 Required Seed Categories

| Seed category | First Launch requirement |
|---|---|
| Module registry | All 21 optional modules registered with canonical IDs; launch classification stored in release configuration, not as duplicate modules |
| Platform Core registry | All 10 Core groups present and non-installable |
| Roles | Primary Owner, Manager, Member |
| Permission identifiers | Canonical action/resource IDs for all launch Core and module operations after `FL-DEC-013` closes; provisional IDs must not enter production seeds |
| Permission templates | Built-in minimum templates for common launch functions; explicit grants remain authoritative; custom `CORE-012` authoring remains Later |
| Business-Type Profiles | Approved initial profiles/terminology/recommendations plus “Other / Not sure”; no automatic Entitlement or activation. The 11 validation fixtures may use characteristics-only mappings before `FL-DEC-006` closes |
| Launch-depth overlay | A/B/C/D depth stored in release configuration against canonical module IDs, never as duplicate modules |
| Operating characteristics | Product/service/order/booking/delivery/membership/class/team/Location characteristics required by onboarding |
| Website section types | Core and launch-module sections with schemas and allowed variants |
| Plans/Entitlements | Development/test grants and approved production Plan/Entitlement seeds |
| Provider configuration | Payment, email/SMS/transactional delivery, AI generation, media, and search adapters for each environment |
| Reference fixtures | Synthetic Businesses for all 11 validation models; never used as fake production proof |

## 18.3 Existing Data Strategy

If launch begins with pilot Businesses or pre-launch data:

- map legacy module names to canonical IDs;
- split legacy `catalog-orders` data into `offerings-catalog` and `orders`;
- map `crm`, `staff`, `delivery`, `subscriptions`, and other aliases to canonical modules;
- validate Business/Location ownership;
- generate missing Entitlement/module-state records without auto-activating unapproved modules;
- preserve auditability of imported state;
- verify consumer identity linking only through approved verified identifiers;
- rebuild Marketplace and My Activity projections from authoritative records/events where possible.

No migration may convert Business type into a hard-coded module bundle.

---

# 19. Test and Validation Requirements

## 19.1 Test Layers

| Layer | Required coverage |
|---|---|
| Domain/unit | State machines, pricing snapshots, availability, stock, membership validity, permission/Entitlement decisions |
| Contract | Public module interfaces, event payloads/versioning, provider adapters, read models |
| Database/security | RLS, tenant predicates, privileged paths, soft deletion, Location scope, migration rollback |
| Integration | Orders↔Payments, Bookings↔Workforce/Payments, event projections, webhook receipt/processing |
| Experience | Page states, validation, recovery, accessibility, responsive behavior, adaptive terminology/navigation |
| End-to-end | Business onboarding→publish→discover→action→Workspace→My Activity for every applicable reference model |
| Operational | retry, dead-letter, backup/restore, provider outage, search lag, CDN/cache failure, audit retrieval |
| Payment | signature, idempotency, durable receipt, duplicate delivery, failure/retry, refunds, reconciliation, settlement-path verification |

## 19.2 Required Actor/Context Matrix

Test at minimum:

- unauthenticated consumer;
- authenticated consumer;
- Business Primary Owner;
- Manager;
- Member with explicit grants;
- Location-scoped Member;
- invited but not activated user;
- suspended/removed member;
- attributed Platform Super Admin;
- Business with expired/suspended Entitlement;
- Business with enabled but incomplete module configuration;
- Business with provider disconnected/restricted state.

## 19.3 Required State Matrix

Every in-scope page family must cover:

- first use;
- empty;
- quiet success;
- loading;
- validation error;
- recoverable system error;
- degraded/offline where relevant;
- no permission;
- wrong Location;
- not entitled;
- not enabled;
- configuration incomplete;
- provider unavailable/disconnected;
- Business suspended/restricted;
- access changed mid-session.

## 19.4 Reservation Validation

Separate test suites are required for:

- overlapping appointment slots;
- provider schedule/Location mismatch;
- accommodation date-range capacity and concurrent reservation;
- party-size/table capacity;
- class capacity and duplicate attendee;
- rental overlap and quantity/resource availability for the subset approved by `FL-DEC-018`; return/completion tests are mandatory only when that decision includes them.

Passing appointment tests does not prove accommodation, table, class, or rental correctness.

The accommodation fixture and test granularity become final only after `FL-DEC-017` closes.

## 19.5 Reference-Business Acceptance

Each of the 11 reference fixtures must complete:

- onboarding;
- generated Website preview;
- offering setup;
- publication;
- Marketplace search;
- primary public action;
- Business Workspace management;
- supported My Activity projection where applicable under Section 14; enquiry-primary fixtures may instead prove Website confirmation plus transactional notification and document My Activity as not applicable;
- failure/recovery scenario;
- explicit confirmation that deferred vertical functions are not falsely implied.

Repair/home-service validation includes both a lead-primary fixture and a booking-primary fixture. Public Business-Type Profile taxonomy may map multiple fixtures to one profile plus different characteristics; the fixtures do not require 11 separate architectures or profile IDs.

---

# 20. Super Admin and Operational Readiness

## 20.1 Required Super Admin Flow

```text
Admin Dashboard
→ Businesses
→ Open Business
→ Inspect overview, Primary Owner, Website, Locations, modules, Entitlements,
  provider state, issues, history
→ Perform attributed support action
→ Record reason and outcome
```

## 20.2 Required Launch Operations

- inspect Business onboarding and publication state;
- inspect and support merchant payment onboarding;
- inspect Website configuration and provide controlled structured assistance;
- inspect Location, module, Entitlement, configuration, and provider state;
- apply temporary/manual Entitlement adjustment where policy permits;
- correct platform-owned state through controlled actions;
- inspect webhook receipts, jobs, retries, dead-letter events, and search indexing;
- investigate tenant-safe logs and audit history;
- suspend/recover Business or provider capability according to approved policy;
- never silently impersonate the Primary Owner;
- never act as an ongoing Website agency or Business operator.

## 20.3 Support Readiness

Before launch:

- issue categories and escalation owners (responsible support people, not Business Primary Owners) are defined;
- provider and payment escalation paths are documented;
- support can identify the actual gate causing denial;
- recovery actions are reversible where possible;
- manual corrections are attributed;
- known limitations have customer-facing explanations;
- high-risk actions require step-up confirmation or appropriate approval.

---

# 21. Security and Payment Readiness Gates

## 21.1 Security Gates

Production launch is blocked until:

- server-side authorization evaluates identity, context, Business, applicable Location, permission, Entitlement, module/configuration state, and resource state;
- RLS is enabled and tested wherever the execution context supports it;
- privileged credentials are server-only, narrowly scoped, audited, and absent from client/AI paths;
- cross-Business isolation tests pass for every launch module;
- permission and Location leakage tests pass;
- secrets are managed and rotatable;
- audit events exist for Super Admin, permission, Entitlement, refund, provider, and sensitive configuration actions;
- rate limiting and abuse controls protect authentication, public, payment, and AI-generation endpoints;
- backup, point-in-time recovery, and tested restoration are available;
- security logging excludes tokens, secrets, and payment-sensitive credentials.

## 21.2 Payment Gates

Production payment launch is blocked until:

- merchant onboarding/KYC states are truthfully represented;
- provider signature verification is implemented;
- idempotency keys are enforced;
- webhook receipt is durable before success acknowledgement;
- asynchronous effects retry and dead-letter;
- duplicate and out-of-order events are safe;
- payment/order/booking/membership state reconciliation is defined;
- refunds are permissioned and audited;
- COD/pay-later/deposit/recurring methods are shown only when configured and policy-permitted;
- settlement destination is the approved Business merchant/linked account;
- platform billing uses a separate commercial flow;
- provider outage and recovery tests pass;
- support can inspect payment state without exposing sensitive credentials.

---

# 22. Launch Readiness Criteria

The First Launch Version is ready only when all mandatory criteria are met.

## 22.1 Product Completeness

- Business and consumer loops in Section 1 pass end-to-end.
- All 10 Platform Core groups meet Section 6.
- All five Full modules meet Section 9.
- All five Basic modules meet Section 10.
- Deferred modules are absent from claims/navigation unless represented by explicitly separate Core functionality.
- Workspace performs real operations, not only reporting.
- My Activity remains lightweight and separate.
- Marketplace and Website handoff preserves intent.

## 22.2 Reference-Model Credibility

- All 11 models pass Section 19.5.
- Hotel availability uses date-range reservation semantics.
- Gym supports Memberships and relevant class booking.
- Tuition/coaching works without claiming a full education ERP.
- Lead-driven Businesses have the basic lead pipeline.
- Supermarket stock and fulfilment work at controlled depth.
- Other/Not sure onboarding remains usable.

## 22.3 Technical and Operational Readiness

- all Stage 1–8 exit criteria pass, including all 11 reference fixtures under Section 19.5;
- security and payment gates pass;
- migrations apply cleanly to empty and representative existing datasets;
- monitoring, alerting, dead-letter, backup/restore, and incident procedures are tested;
- no Severity 1/critical unresolved defect remains;
- production configuration contains no development credentials or synthetic Plan grants;
- rollback and feature-disable procedures are documented;
- provider degraded modes preserve Core Business data access.

## 22.4 Commercial and Support Readiness

- approved production Plan/Entitlement behavior is seeded;
- free/paid launch choice is reflected consistently;
- Terms, privacy, payment/refund, and support policies required for the launch geography are approved;
- Primary Owner-facing recovery paths exist for Entitlement, provider, and payment problems;
- support ownership and escalation coverage are active.

## 22.5 Go/No-Go Authority

Final go/no-go requires:

- Product/Founder confirmation of scope and known limitations;
- Engineering confirmation of technical gates;
- security confirmation of tenant/privileged-access controls;
- payment/operations confirmation of provider and settlement readiness;
- support confirmation of incident and recovery readiness.

---

# 23. Known Risks and Mitigations

| Risk | Impact | Mitigation / scope control |
|---|---|---|
| Five Full + five Basic modules create excessive breadth | Delayed launch and shallow quality | Build vertical slices around shared primitives; stage gates; no advanced depth without scope displacement |
| Reservation modes hide materially different rules | Overbooking and incorrect UX | Shared foundation plus separate mode policies/tests; no “appointment-only” abstraction |
| Payment provider/KYC delay | Commerce and reservation launch blocked | Provider abstraction, early merchant-onboarding spike, controlled offline methods only where approved; do not fake online readiness |
| AI generation reliability/cost | Onboarding delay or poor content | Deterministic fallback, structured schemas, draft/review, provider abstraction, rate/cost controls |
| Business-type branching | Fragmented architecture | Characteristics/configuration only; canonical modules and contracts remain shared |
| Workspace becomes cluttered | Poor usability and permission leakage | Adaptive navigation, progressive complexity, role/Location-aware Home |
| Basic modules expand into full ERPs | Scope failure | Explicit depth boundaries and rejected-feature list |
| Marketplace begins with sparse density | Weak consumer experience | Search-first honest states, direct shared links, joined-only quality, controlled geography/rollout decision |
| Event projection lag/replay bugs | Wrong dashboard/My Activity/customer history | Outbox, idempotent consumers, replay tests, authoritative detail contracts |
| Membership/class dependency is implemented in the wrong stage | Gym/education flow appears complete but cannot enforce validity | Capacity-only class booking in Stage 5; membership-gated/provider-linked class acceptance in Stage 6 |
| Page-family relevance drifts from Document 09 | Missing checkout, booking, membership, lead, or Admin operations | Treat Section 4.1 as the mandatory release overlay in acceptance plans |
| Enquiry-primary model is forced into unsupported My Activity | Fake or empty consumer history | Use Website confirmation + transactional notification; mark My Activity not applicable under Section 14 |
| Public profile taxonomy is mistaken for 11 separate architectures | Business-type branching and seed sprawl | Validate 11 fixtures through profile + characteristics; close `FL-DEC-006` before production seeds |
| Tenant isolation or privileged-access defect | Critical data breach | RLS + explicit predicates + privileged-path inventory + automated cross-tenant tests |
| Webhook loss or duplicate effects | Financial inconsistency | Durable-before-ack, idempotency, reconciliation, retry/dead-letter |
| Core Notifications confused with Messaging | Accidental launch gap | Separate registry IDs, explicit transactional delivery acceptance tests |
| Basic insights confused with Analytics | Businesses operate blindly or scope expands | Core operational metrics only; deep analysis deferred |
| Founder support becomes hidden manual operations | Product is not truly usable | Attributed Admin tools, track manual intervention rate, block launch if routine cases require support |

---

# 24. Scope-Control Register

## 24.1 Rejected First Launch Expansion Categories

The following do not enter First Launch without formal scope change:

- advanced vertical compliance/data models;
- third-party module marketplace;
- social/community features;
- B2B procurement/RFQ network;
- advanced marketing automation;
- consumer review/reputation system;
- loyalty economics;
- payroll/accounting suite;
- proprietary fleet/logistics;
- arbitrary Website code;
- advanced BI/forecasting;
- AI employee autonomy;
- multiple payment providers merely for architectural completeness;
- advanced Marketplace recommendation/ranking.

## 24.2 Build-vs-Ship Rule

A capability may be implemented internally as an enabling dependency without being publicly exposed. Public launch inclusion requires:

- page/experience completion;
- permission and Entitlement behavior;
- failure/recovery states;
- support readiness;
- telemetry;
- documentation and acceptance tests.

“Code exists” does not mean “First Launch scope is complete.”

---

# 25. Decision Classification

This document distinguishes:

- **Foundation Blocker:** blocks affected foundational implementation.
- **Feature Blocker:** blocks only the affected module/workflow.
- **Production Blocker:** implementation may proceed with abstractions/defaults, but production launch or traffic is blocked.
- **Commercial Decision:** blocks only the affected commercial behavior unless it becomes a production commitment.

No unresolved decision blocks unrelated canonical foundation work.

---

# 26. Unresolved Decisions

## 26.1 Founder/Product Approval Required

| ID | Decision | Category | What it blocks | Safe work that may continue |
|---|---|---|---|---|
| `FL-DEC-001` | Initial public geography, rollout cohort, and density strategy | Production Blocker | Public launch targeting, support coverage, legal/payment configuration, Marketplace quality plan | Generic platform, reference fixtures, staging validation |
| `FL-DEC-002` | Free vs paid First Launch strategy, production Plan names/prices, and included Entitlements | Commercial Decision / Production Blocker for paid launch | Production Plan seeds, billing activation, upgrade/recovery copy | Entitlement engine, development grants, module gating |
| `FL-DEC-003` | Merchant payment provider and implementation sequence, including KYC/settlement model | Feature Blocker / Production Blocker | Real online payments, deposits, refunds, recurring collection | Provider-neutral domain/contracts, COD/pay-at-Business design |
| `FL-DEC-004` | Which payment methods are permitted by Business model and launch geography: COD, pay later, pay-at-property/Business, deposits | Product/Payment Production Blocker | Method visibility, policy, cancellation/refund behavior | Generic payment method capability model |
| `FL-DEC-005` | Recurring payment launch policy and provider-supported use cases | Feature Blocker | Automatic Membership renewal | Fixed-duration/manual-renew Memberships |
| `FL-DEC-006` | Public Business-Type Profile taxonomy and initial recommendation seeds | Feature Blocker | Final onboarding labels/default recommendations and seed data | Generic characteristics model and all 11 validation fixtures |
| `FL-DEC-007` | First Launch success thresholds and go/no-go numeric targets | Production Blocker | Objective launch decision and post-launch evaluation | Instrumentation implementation |
| `FL-DEC-008` | Refund/cancellation policy ownership and default customer-facing policy boundaries | Product/Payment Production Blocker | Final Orders/Bookings/Payments policy UX | State machines and configurable-policy framework |
| `FL-DEC-009` | Production legal/support policies for the selected geography | Production Blocker | Public traffic and real payment acceptance | Product implementation and internal testing |

## 26.2 Engineering/Product Decisions Required

| ID | Decision | Category | What it blocks |
|---|---|---|---|
| `FL-DEC-010` | Monorepo tool and CI task graph | Foundation Blocker | Formal repository bootstrap |
| `FL-DEC-011` | Managed PostgreSQL and final Auth provider | Foundation Blocker | Provider-specific provisioning, session/RLS binding, production auth |
| `FL-DEC-012` | Background job/outbox processing mechanism | Foundation Blocker | Durable worker, retry/dead-letter, webhook async effects |
| `FL-DEC-013` | Canonical permission identifier scheme and minimum built-in templates | Foundation Blocker | Permission registry and complete authorization implementation |
| `FL-DEC-014` | First Launch search engine: Postgres GIN default or immediate external engine | Feature Blocker | Search infrastructure; Postgres GIN is recommended default |
| `FL-DEC-015` | Initial AI model/provider for structured Website generation, budget and fallback policy | Feature Blocker / Production Blocker | Live AI generation; deterministic fallback can proceed |
| `FL-DEC-016` | Production cloud/region, platform domain, and CDN configuration | Production Blocker | Production infrastructure, DNS, canonical URLs, asset delivery |
| `FL-DEC-017` | Accommodation availability granularity at launch: named units, unit-type capacity, or both | Feature Blocker | Final hotel fixture/schema and booking UI; shared reservation core may proceed |
| `FL-DEC-018` | Rental/resource launch boundary: which resource classes require named-resource vs quantity capacity and whether return state is mandatory | Feature Blocker | Final rental acceptance suite; generic interval reservation may proceed |
| `FL-DEC-019` | Manager delegation ceiling plus built-in template update/merge semantics | Foundation/Feature Blocker | Permission-management behavior and safe template evolution |
| `FL-DEC-020` | Delivery Partner representation: assignment-scoped mode vs separate membership/domain representation | Feature/schema Blocker | Future Delivery Partner surface and any schema field that would lock the model prematurely |
| `FL-DEC-021` | Whether Super Admin may apply production Entitlement changes without Primary Owner acceptance, and under what policy | Product/Production Blocker | Final Admin commercial-correction workflow |
| `FL-DEC-022` | Business terminology override scope, validation, and fallback precedence | Feature Blocker | Final terminology storage and adaptive labels |
| `FL-DEC-023` | Business-Type Profile versioning and migration behavior for existing Businesses | Feature/Data Blocker | Profile update tooling and production profile migration |
| `FL-DEC-024` | Guest-to-authenticated identity linking implementation, preserving the approved verified-identifier-only rule | Product/Data Blocker | Cross-session guest history linking; guest checkout itself may proceed |
| `FL-DEC-025` | Tax, fee, delivery-charge, and price-presentation policy for the launch geography | Product/Payment Production Blocker | Final checkout totals, receipts, and customer-facing price policy |

> ### Amendment — 2026-09-12: decision status (additive, dated per Document 08 §25.3)
>
> **Status only. No scope, depth, sequencing, or gate change.** The two tables above are
> retained as the original decision register; read them as history and this block as
> current status.
>
> **§26.2 is stale — six of its ten decisions are closed.** Document 12 §0.2 resolved them
> as engineering decisions, and all six are implemented in the repository. A reader who
> stops at the table above will believe the foundation is still blocked:
>
> | ID | Status | Resolution |
> |---|---|---|
> | `FL-DEC-010` | **Closed** | Turborepo + pnpm workspaces — Document 12 §1. Implemented. |
> | `FL-DEC-011` | **Closed** | Supabase (managed PostgreSQL + Supabase Auth) — Document 12 §6. Implemented, including dual-mode JWT verification (ES256 via JWKS, legacy HS256 for pre-migration tokens). |
> | `FL-DEC-012` | **Closed** | PostgreSQL transactional outbox + a Python-native worker with safe row claiming, leases, retry/backoff, idempotency, and dead-letter handling — Document 12 §18. Implemented. |
> | `FL-DEC-013` | **Closed** | Canonical permission identifier grammar `<resource>.<action>` — Document 12 §8. Implemented. |
> | `FL-DEC-014` | **Closed** | PostgreSQL full-text search with GIN indexes — Document 12 §14. Implemented. |
> | `FL-DEC-019` | **Closed** (delegation ceiling) | Managers may grant up to but not beyond their own effective permissions — Document 12 §8. Implemented. **Built-in template update/merge semantics remain open.** |
>
> Still open in §26.2: `FL-DEC-017`, `FL-DEC-018`, `FL-DEC-020`, `FL-DEC-022`–`FL-DEC-025`,
> and the template-merge half of `FL-DEC-019`.
>
> **§26.1 — four decisions are formally open but already committed in implementation.**
> This gap is recorded so it is visible now rather than discovered at a launch gate. None
> of these is hereby closed; closing them is a founder act.
>
> | ID | Formal status | What implementation has already committed to | What still needs the founder |
> |---|---|---|---|
> | `FL-DEC-003` | **Open** | **Razorpay.** Each Business's own Key ID / Key Secret are entered by the owner, stored encrypted on `MerchantConnection`, and verified by a live provider call before the connection is marked active. The platform does not replicate Razorpay KYC. | KYC/settlement model; whether Razorpay is the launch commitment or one adapter among several; and confirmation that the platform-level `RAZORPAY_*` environment variables are for **platform billing only** and are never used for merchant collection. |
> | `FL-DEC-006` | **Open** | A working `business_type_profiles` registry with development seeds and recommendation logic. | The **public** taxonomy and the recommendation seeds that actually ship. |
> | `FL-DEC-015` | **Open** | **Gemini**, default model `gemini-3.6-flash`, exactly one structured call per Business, deterministic fallback on any failure. Proven end to end. See Document 12 §12.9. | Budget ceiling; formal fallback policy; and **rotation of the temporary founder-authorised API key before any public traffic** — treat this as a launch gate, not a cleanup task. |
> | `FL-DEC-016` | **Open** | Supabase project region **Mumbai (`ap-south-1`)**, moved from `ap-northeast-1`. | Application hosting platform, production platform domain, and CDN configuration. |
>
> **Consequence for §22 (Launch Readiness) and §21 (Gates):** none of the above changes a
> gate, but `FL-DEC-015`'s key rotation is now an explicit item under §21.1, and
> `FL-DEC-003`'s settlement model remains the binding constraint on §21.2.


## 26.3 Explicitly Resolved by This Document

The following Document 10 decisions are no longer open at the scope level:

- which optional modules ship: Sections 8–11;
- First Launch module implementation sequence: Section 17;
- First Launch reference Business models: Section 5;
- first AI employee: none is required for First Launch; governed Website generation only;
- exact classification of Core Notifications vs Messaging;
- exact classification of Core operational insights vs Analytics.

Provider, commercial, infrastructure, permission-ID, profile-seed, and production-policy decisions remain open as listed above.

### Document 10 §35 Resolution Mapping

| Document 10 decision | Document 11 status |
|---|---|
| MVP/First Launch module scope | Resolved — Sections 3 and 8–11 |
| First optional modules and implementation sequence | Resolved — Sections 16–17 |
| Repository tool | Open — `FL-DEC-010` |
| Deployment cloud/region | Open — `FL-DEC-016` |
| Managed PostgreSQL and Auth provider | Open — `FL-DEC-011` |
| Search approach | Open — `FL-DEC-014` |
| Background job mechanism | Open — `FL-DEC-012` |
| Initial AI provider/model | Open — `FL-DEC-015` |
| Payment provider sequence | Open — `FL-DEC-003` |
| Platform domain and CDN | Open — `FL-DEC-016` |
| Initial Business types/profiles | Partially resolved by reference models; public seeds open — `FL-DEC-006` |
| First AI employee | Resolved — none required; governed Website generation only |
| Canonical permission identifiers | Open — `FL-DEC-013` and `FL-DEC-019` |
| Free vs paid strategy | Open — `FL-DEC-002` |

---

# 27. Conflict and Supersession Register

| ID | Conflict/tension | Documents in tension | Governing First Launch resolution |
|---|---|---|---|
| `D11-CONFLICT-001` | Older Horizon 1 excludes Marketplace discovery | Doc 01 vs Docs 09–11 | First Launch includes the search-first Marketplace loop. Advanced discovery remains later. |
| `D11-CONFLICT-002` | Older Horizon 1 excludes customer accounts beyond checkout identity | Doc 01 vs Docs 05, 09, 11 | Shared Platform Identity and lightweight My Activity are First Launch requirements. |
| `D11-CONFLICT-003` | Older plans treat Business Profile and Website as installable modules | Docs 03–04 vs Doc 08 | Both are Platform Core and required. |
| `D11-CONFLICT-004` | Older `catalog-orders` composite | Docs 03–04 vs Doc 08 | Preserve separate `offerings-catalog` and `orders`. |
| `D11-CONFLICT-005` | Business type auto-provisions required/default modules | Docs 01, 03, 04 vs Docs 05, 07, 08 | Type/characteristics recommend; Primary Owner choice, Entitlement, activation, configuration, and permission govern. |
| `D11-CONFLICT-006` | Fixed Merchant Dashboard/sidebar vs adaptive Business Workspace | Doc 04 vs Docs 02, 05, 09 | Business Workspace is adaptive and operational; no fixed 21-module navigation. |
| `D11-CONFLICT-007` | Free-form/drag-drop Website assumptions vs structured Website | Doc 04 vs Docs 02, 09, 10 | First Launch uses AI-assisted structured sections, variants, content, and branding/navigation controls. |
| `D11-CONFLICT-008` | Document 09 classifies Bookings, Payments, and Memberships as Post-MVP | Doc 09 relevance baseline vs approved Document 11 scope | Their page families are promoted to First Launch at the controlled Full depth defined here; Document 09 page definitions remain canonical. |
| `D11-CONFLICT-009` | Document 09 classifies Leads, Inventory, Fulfilment, and Workforce as Post-MVP | Doc 09 baseline vs approved Document 11 scope | They are promoted to Basic/Controlled depth, not full future depth. |
| `D11-CONFLICT-010` | Older `analytics-basic` module vs one canonical Analytics module | Docs 03–04 vs Docs 08–11 | Core operational insights launch in `core-workspace`; full `analytics` remains later. |
| `D11-CONFLICT-011` | Older WhatsApp Notifications module vs Core Notifications/Messaging separation | Docs 03–04 vs Doc 08 | Core and transactional notifications launch; full `messaging` remains later. |
| `D11-CONFLICT-012` | Team/staff concepts overlap | Docs 03–04 vs Docs 06, 08 | `core-team-access` governs access; `workforce` Basic governs operational providers/schedules. |
| `D11-CONFLICT-013` | Events-only cross-module integration | Docs 03–04 vs Doc 10 Version 1.1 | Immediate needs use stable public contracts; asynchronous effects use domain events; no cross-module table access. |
| `D11-CONFLICT-014` | Older no-payment launch assumptions | Doc 01 vs approved Document 11 scope | `payments` is First Launch Full; real provider readiness remains blocked by Section 26 decisions and Section 21 gates. |
| `D11-CONFLICT-015` | Admin impersonation/agency-like operation | Docs 03–04 vs Docs 06, 09, 10 | First Launch uses explicit attributed Super Admin support actions, not silent impersonation or agency operations. |
| `D11-CONFLICT-016` | Document 09 treats full checkout and `WEB-009`, `WEB-010`, `WEB-012`, `WEB-014`, and `ADM-013` as Post-MVP or later | Doc 09 vs approved Document 11 scope | These page families are promoted at the controlled depth in Section 4.1 because Orders, Bookings, Payments, Memberships, Basic Leads, and payment support are First Launch requirements. |
| `D11-CONFLICT-017` | Document 09 requires only at least one coherent operational loop and marks Orders/Customer Relationships conditional | Doc 09 §18 vs approved multi-loop launch breadth | This document intentionally validates multiple horizontal loops across the 11 reference models; Orders is Full and Customer Relationships is Basic. |
| `D11-CONFLICT-018` | Document 09 treats Messaging as Conditional MVP | Doc 09 vs Sections 3.3, 8, 11 | In-platform and required transactional delivery launch through Core/shared services; the full Business-configurable `messaging` module remains Later. |
| `D11-CONFLICT-019` | Document 09 places Loyalty in Future Ecosystem while the approved direction places it Later | Doc 09 vs Section 8 | `loyalty` is classified Later, not First Launch and not a new module. Its implementation still depends on mature customer/event history. |
| `D11-CONFLICT-020` | Document 10 §35 leaves launch scope, first modules, and first AI employee deferred | Doc 10 v1.1 vs this document | Sections 8–17 and 26.3 resolve those scope-level rows. Provider, infrastructure, commercial, permission, and production decisions remain open. |

This register records genuine launch-scope supersessions. It does not amend source documents.

---

# 28. Traceability Matrix

| First Launch concern | Governing source | This document |
|---|---|---|
| Identity/context/journeys | Docs 05–06 | Sections 1, 4, 6, 7, 14, 19 |
| Business-type adaptation | Doc 07 | Sections 0.4, 5, 6.2, 7.3, 18 |
| Core/module registry | Doc 08 | Sections 6, 8–11 |
| Page experiences | Doc 09 | Sections 4, 6–7, 13–15 |
| Modular monolith/contracts | Doc 10 v1.1 | Sections 16–17, 19, 21 |
| RLS/privileged access | Doc 10 v1.1 | Sections 19, 21, 22 |
| Durable webhooks/payments | Doc 10 v1.1 | Sections 9.4, 17.4, 19, 21 |
| Implementation decisions | Doc 10 §35 | Sections 17, 25–26 |
| First Launch scope | This document | Sections 1–15 |
| Launch readiness | This document | Sections 19–23 |

---

# 29. Final Validation

| Validation requirement | Status |
|---|---|
| All 21 canonical optional modules classified exactly once | Confirmed — Section 8 |
| All 10 Platform Core groups accounted for | Confirmed — Section 6 |
| All 11 reference Business models have a credible path | Confirmed — Sections 5 and 15 |
| Business Workspace includes content editing and real operations, not only analytics | Confirmed — Section 7 |
| Core Notifications remain at First Launch while full Messaging is later | Confirmed — Sections 3.3, 6, 11 |
| Basic dashboard insights remain while full Analytics is later | Confirmed — Sections 7.2, 11, 12 |
| Accommodation reservations use date-range/capacity semantics, not ordinary appointment or stock logic | Confirmed — Sections 9.3, 15.6, 19.4 |
| Tuition/coaching is supported without claiming a full education ERP | Confirmed — Sections 5, 15.11 |
| Real-estate/lead-driven Businesses have a usable basic lead path | Confirmed — Sections 10.2, 15.10 |
| Gyms have Memberships and class/session booking support | Confirmed — Sections 5, 9.3, 9.5, 15.9 |
| Merchant payments remain separate from platform billing | Confirmed — Sections 6.3, 9.4, 21.2 |
| No all-modules-at-launch assumption is introduced | Confirmed — Sections 8–11 |
| Deferred advanced modules remain compatible with canonical architecture | Confirmed — Sections 11, 16, 24 |
| Implementation stages respect actual dependencies | Confirmed — Sections 16–17 |
| Basic Workforce is available before provider-dependent reservation completion | Confirmed — Sections 16.2, 17.5 |
| AI-assisted Website generation does not imply all AI employees | Confirmed — Sections 3, 6.2, 26.3 |
| Business type remains recommendation/configuration, not architecture or authorization | Confirmed — Sections 0, 2, 5, 27 |
| Search-first joined-Business Marketplace is included | Confirmed — Section 13 |
| My Activity and Business Workspace remain separate | Confirmed — Sections 4, 14 |
| Launch includes security, payment, support, audit, and recovery gates | Confirmed — Sections 19–23 |
| Scope remains bounded against complete vertical ERP expansion | Confirmed — Sections 2, 5, 9–11, 24 |
| Genuine unresolved major decisions are explicit, not silently invented | Confirmed — Section 26 |
| Every promoted or deferred Document 09 page family has an explicit First Launch overlay | Confirmed — Section 4.1 |
| Immediate cross-domain results use public contracts; asynchronous effects use events | Confirmed — Sections 16.1–16.2, aligned with Document 10 `ARCH-010` |
| Document 10 §35 scope decisions are traced as resolved, partial, or open | Confirmed — Section 26.3 |
| Stage exit criteria reference the correct readiness gates | Confirmed — Sections 17, 21, 22 |

---

# 30. Completion State

This document makes the First Launch module subset, page-family overlay, capability depth, reference-model validation, and implementation sequence canonical.

Implementation may begin on stable foundational work while Section 26 decisions are resolved according to their actual blocking scope. Production launch must not occur until every applicable Production Blocker, security gate, payment gate, and launch-readiness criterion is closed.

Downstream documents may now treat the 5 Full + 5 Basic + 7 Later + 4 Future classification, all-10-Core requirement, eight-stage sequence, 11-model validation set, no-First-Launch-AI-employee decision, and Core Notifications/Analytics distinctions as resolved.

They must continue to treat the Section 26 provider, infrastructure, commercial, permission, profile, guest-linking, vertical-boundary, and production-policy decisions as open. Earlier Kernel conflicts recorded by Documents 05–10 also remain amendment work; this document does not silently rewrite them.

---

**End of Document 11 — First Launch Scope & Implementation Plan**
