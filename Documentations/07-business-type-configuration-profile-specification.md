# Business-Type Configuration Profile Specification

**Document:** 07  
**Document Status:** Canonical foundation  
**Version:** 1.0  
**Date:** July 2026  
**Authority:** Business-type adaptation, recommendation, and configuration-profile semantics  
**Depends On:** `01-vision-document.md` · `02-product-experience-bible.md` · `03-business-kernel-specification.md` · `04-master-product-specification.md` · `05-user-context-journey-navigation-architecture-specification.md` · `06-role-permission-access-experience-matrix.md`

---

# 1. Purpose, Scope and Non-Goals

## 1.1 Purpose

This document defines how one modular platform adapts intelligently to different kinds of Businesses without creating separate products for every industry.

Its governing question is:

> Given what kind of Business this is, what should the platform recommend, call things, emphasize, configure, and adapt—while still allowing the Business to choose the capabilities it actually wants?

A **Business-Type Configuration Profile** is a versioned set of recommendations, terminology suggestions, starting defaults, guidance, and presentation hints. It helps a Business reach a relevant starting point. It is not an authority grant or an operational module bundle.

The governing model is:

```text
Shared Platform Core
+ Business-Type Profile
+ Explicit Business Choices
+ Enabled Modules and Capabilities
+ Business Configuration
+ Location Configuration
+ Commercial Entitlement
+ User Permission and Scope
+ Runtime Resource State
= Actual Business Experience
```

## 1.2 This document governs

- how Business type influences experience without creating vertical products;
- what a profile may recommend or adapt;
- what remains invariant across all Businesses;
- how profile suggestions are selected, previewed, accepted, overridden, and updated;
- how mixed and evolving Businesses are represented;
- how Business and Location configuration interact with a profile;
- how profiles influence onboarding, workspace emphasis, websites, Marketplace presentation, and AI context; and
- representative profiles that prove the framework across different Business models.

## 1.3 Non-goals

This document does not:

- create separate products or codebases per industry;
- define complete page-by-page experiences;
- define physical database tables, columns, or storage technology;
- define APIs or event payloads;
- define prices, plans, packaging, billing, or Commercial Entitlement implementation;
- duplicate the complete module and feature inventory;
- enumerate every possible Business type;
- redefine Document 05 navigation architecture;
- redefine Document 06 access evaluation;
- create a complete AI runtime or medical-record architecture; or
- introduce agency/reseller or third-party-created Business listing models.

## 1.4 Core rules

**BTYPE-001 — One platform:** Every Business uses the same Business entity, Platform Identity foundation, module system, renderer model, and access architecture.

**BTYPE-002 — Recommendation, not authority:** A Business-Type Profile recommends and pre-fills. It does not grant Commercial Entitlement, activate modules, grant permission, or bypass policy.

**BTYPE-003 — Explicit choice wins:** A Business’s explicit accepted configuration overrides profile recommendations unless a higher platform invariant, security rule, genuine dependency, Entitlement limit, or policy applies.

**BTYPE-004 — No silent reversal:** A profile selection or update MUST NOT silently re-enable, disable, reconfigure, or expose something the Business explicitly changed.

**BTYPE-005 — Dependencies are functional:** A dependency exists only when the chosen capability logically or technically requires another capability. Industry identity alone is never a dependency.

**BTYPE-006 — Configuration, not conditionals:** Product behavior SHOULD derive from capabilities, configuration, and profile data—not scattered `if business.type == ...` branches.

**BTYPE-007 — Location is not tenant:** Location variation remains inside one canonical Business unless the entities are genuinely separate Businesses.

**Traceability:** Document 03 §1.1, §1.4, §2.1–§2.3, §4; Document 05 `MOD-008`, `MOD-009`, `KIR-002`, `CONFLICT-004`.

---

# 2. Configuration Model

## 2.1 Conceptual hierarchy

```text
Platform invariants and core
→ Platform defaults
→ Selected Business-Type Profile
→ Business characteristics
→ Explicit Business capability choices
→ Enabled/configured modules
→ Business-level configuration
→ Location-level configuration
→ Commercial Entitlement and access evaluation
→ Runtime experience
```

The hierarchy is not a license for lower layers to override higher-authority controls. Profile and platform defaults fill useful blanks; explicit Business decisions replace those suggestions. Entitlement, security, access, dependencies, and resource state still constrain runtime behavior.

## 2.2 Configuration layers

| Layer | Purpose | Examples | Authority |
|---|---|---|---|
| Platform invariant | Preserve one coherent platform and safe domain rules | One Business identity, tenant boundary, access enforcement | Mandatory |
| Platform core | Provide universal Business-operating foundation | Identity/profile management, workspace foundation, settings, team/access, module management, basic notifications | Universal category; exact inventory unresolved |
| Platform default | Provide safe fallback when no profile or override applies | Generic labels, neutral onboarding prompt | Overridden by profile or explicit configuration |
| Business-Type Profile | Recommend relevant starting experience | Capability recommendations, terminology, guidance, emphasis | Advisory |
| Business characteristics | Describe actual operating model beyond one industry label | Product-led, appointment-based, delivers, multi-Location | Advisory/configurational |
| Explicit Business choice | Accept, dismiss, enable, disable, or customize | Choose Website + Reservations but not Delivery | Governs within higher constraints |
| Module/capability state | Make chosen capability operational | Enabled, setup required, active, deactivated | Operational |
| Business configuration | Define Business-wide behavior | Booking policy, default fulfilment, public terminology | Explicit Business authority |
| Location configuration | Override supported behavior per Location | Hours, menu availability, service availability | Explicit subordinate override |
| Commercial Entitlement | Define commercial ceiling | Permitted module/capability/quota | Separate authority; Document 08 |
| User access/context | Define what this person may see/do here | Permission, role, Location scope | Document 06 |
| Runtime state | Apply current resource and workflow conditions | Closed Location, unavailable item, full queue | Immediate operational truth |

## 2.3 Explicit choice and remembered intent

- Dismissing a recommendation records preference; it MUST NOT reappear as if never considered on every visit.
- Disabling a module is an explicit operational decision. A type change or profile update MUST NOT reactivate it.
- Accepting a recommendation begins the normal Entitlement, enablement, configuration, and access flow. It does not skip those gates.
- A recommended default becomes authoritative only after the Business accepts or saves it.
- Where no explicit choice exists, a newer profile version MAY update suggestions, but not committed Business configuration.

---

# 3. What a Business-Type Profile May Influence

## 3.1 Influence matrix

| Category | Profile contribution | Boundary |
|---|---|---|
| Recommended modules/capabilities | Rank and explain capabilities commonly useful for this Business | Business chooses; genuine dependencies only |
| Suggested starting configuration | Pre-fill sensible, reviewable defaults | Not committed until accepted |
| Terminology | Suggest understandable labels and action vocabulary | Canonical entities/routes remain stable |
| Dashboard emphasis | Suggest likely high-priority information/actions | Actual composition derives from enabled capabilities, access, Location, activity |
| Navigation emphasis | Rank relevant enabled destinations | Cannot reveal unauthorized or unavailable areas |
| Onboarding guidance | Ask relevant questions and sequence selected setup | Cannot force unrelated steps |
| Website suggestions | Suggest pages, sections, CTAs, content prompts, capabilities | No universal template; Business brand/configuration wins |
| Marketplace presentation | Suggest category, offering emphasis, public facts, action types | Published capability and truthful data govern |
| Workflow suggestions | Recommend common operating patterns | Business explicitly adopts/configures |
| AI assistance | Suggest useful AI support, prompts, or future AI employees | No authority; all normal gates apply |
| Location behavior | Suggest likely Business-wide defaults and useful per-Location overrides | One Business remains tenant; explicit Location config wins |

## 3.2 Recommended capabilities

A recommendation should state:

- why it is relevant;
- what Business goal it supports;
- whether it has a genuine dependency;
- whether current setup is compatible;
- whether it requires Commercial Entitlement review; and
- what happens if the Business declines.

Recommendation does not equal installation (`MOD-001`). Entitlement does not equal activation (`MOD-002`). Activation does not grant permission (`MOD-003`).

## 3.3 Suggested terminology

Terminology adapts comprehension, not domain identity.

Examples:

| Generic concept | Possible configured label |
|---|---|
| Offering | Product, Service, Menu Item, Class, Package |
| Scheduled service | Appointment, Session, Consultation, Reservation |
| Customer relationship | Customer, Client, Member, Patient, Guest |
| Provider/team member | Staff, Doctor, Trainer, Stylist, Professional |

Rules:

- labels MAY vary by surface and Business configuration;
- canonical object, capability, event, route, and permission semantics remain stable;
- a profile MUST NOT imply regulated data semantics merely by displaying “Patient”;
- explicit Business terminology overrides profile suggestions;
- ambiguous or misleading terminology MUST fall back to the platform term; and
- action language remains consistent through the journey, as required by Document 02.

## 3.4 Dashboard and navigation emphasis

A profile may suggest likely first priorities:

- Restaurant: current orders, preparation, reservations, fulfilment.
- Clinic: appointments, queue, providers, availability.
- Gym: attendance, memberships, sessions, renewals.
- Salon: appointments, schedules, service availability.

These are emphasis hints, not fixed widgets or hard-coded dashboards. Runtime emphasis derives from enabled modules, Entitlement, configuration, Location, permission, resource state, and actual activity.

Navigation may make relevant enabled capabilities easier to reach. It MUST still follow Document 05 `NAV-007`–`NAV-011` and Document 06 visibility/access rules.

## 3.5 Onboarding and public presentation

Profiles may:

- omit irrelevant setup questions;
- suggest questions that clarify operating characteristics;
- recommend website content and CTAs;
- suggest whether products, services, bookings, orders, or enquiries deserve stronger public emphasis;
- propose Marketplace categories and presentation hints; and
- suggest Business-appropriate AI assistance.

All outputs remain proposals until accepted or published by an authorized person.

---

# 4. What a Business-Type Profile Must Not Control

A Business-Type Profile MUST NOT:

1. grant or change a person’s role, permission, or Location scope;
2. grant Commercial Entitlement or consume quota;
3. bypass module state, dependency, security, approval, or policy gates;
4. activate operational modules solely because the Business belongs to a type;
5. expose private Business, customer, health, financial, or Location data;
6. permanently prevent unrelated compatible modules from being discovered or enabled;
7. create a separate tenant, identity system, permission engine, renderer, or codebase;
8. overwrite explicit Business or Location configuration without an approved migration;
9. delete data or silently remove enabled capabilities when type changes;
10. make a module mandatory solely because it is common in that industry;
11. replace truthful runtime availability with a profile assumption; or
12. authorize an AI action.

Platform invariants and genuine dependencies are not profile controls. They are separately governed platform rules.

**Traceability:** Document 05 `CTX-009`, `MOD-001`–`MOD-009`; Document 06 `ACCESS-001`–`ACCESS-006`, §2.

---

# 5. Business Type Selection and Evolution

## 5.1 Initial selection

During setup, Business type is a recommendation seed:

1. collect minimum Business identity;
2. ask for a primary type or “Other/Not sure”;
3. ask a small number of operating-characteristic questions;
4. preview terminology, capability recommendations, and setup guidance;
5. let the Business accept recommendations selectively;
6. configure only chosen capabilities; and
7. enter the adaptive workspace.

This section contributes profile behavior only. Document 05 remains authoritative for the complete onboarding journey.

## 5.2 Uncertain, custom, and mixed selection

- **Not sure:** use characteristics and generic platform defaults; do not block Business creation.
- **Other/custom:** capture a human-readable category and characteristics without generating a new code path.
- **Mixed Business:** choose a primary type for starting recommendations, then add characteristics and explicit capabilities.
- **Secondary classification:** MAY improve discovery or recommendations, but does not automatically apply a second full profile until combination semantics are canonical.

## 5.3 Changing Business type

Changing type is a recommendation/configuration event, not Business replacement.

The experience MUST:

1. preview changed recommendations and terminology;
2. preserve Business identity, ownership, membership, Locations, data, enabled capabilities, and explicit settings;
3. identify incompatible or newly irrelevant configuration without deleting it;
4. leave deliberately deactivated capabilities deactivated;
5. require explicit confirmation before changing saved terminology or defaults;
6. preserve historical operational records; and
7. allow cancellation before applying changes.

The change recalculates suggestions. It does not silently reinstall, activate, deactivate, or delete modules.

## 5.4 Businesses that evolve

A Business may add services, products, appointments, delivery, memberships, or new Locations without changing its primary type. Capabilities and characteristics should represent actual operation more accurately than repeated category switching.

---

# 6. Mixed and Hybrid Businesses

## 6.1 Composition model

Hybrid operation is modeled through:

```text
Primary Business-Type Profile
+ Operating characteristics
+ Explicitly chosen capabilities/modules
+ Business and Location configuration
```

It is not modeled by creating a new hard-coded type for every combination.

## 6.2 Representative hybrids

| Business | Primary profile may be | Characteristics/capabilities added |
|---|---|---|
| Bakery + café | Restaurant/Food Service | Product sales, dine-in, takeaway, pre-orders |
| Clinic + pharmacy | Clinic | Appointments plus retail products/inventory; sensitive domains remain separated by permission/policy |
| Gym + personal training | Gym/Fitness | Memberships, classes, one-to-one appointments |
| Salon + retail products | Salon | Services/bookings plus products/inventory |
| Restaurant + catering | Restaurant | Orders plus enquiry/quote workflow |
| Home-food + packaged products | Home-Food | Menu/order flow plus durable product catalogue |
| Professional service + appointments | Professional Services | Leads/enquiries plus booking |

## 6.3 Complexity controls

- Prefer reusable characteristics over subtype creation.
- Prefer chosen capabilities over type-specific feature forks.
- Use one primary profile unless multiple-profile semantics are deliberately approved.
- Ask only characteristic questions that materially change recommendations or setup.
- Do not combine profile defaults blindly; produce one previewable recommendation set.

---

# 7. Business-Wide and Location-Specific Variation

## 7.1 One Business, many Locations

A multi-Location operator normally has:

- one canonical Business identity;
- one Business tenant and membership system;
- one overall public identity and website where appropriate;
- Business-wide defaults; and
- Location-specific operational configuration where supported.

Locations are not separate Businesses merely because they have different hours, staff, offerings, or availability.

## 7.2 Variation matrix

| Dimension | Business-wide default | Possible Location override |
|---|---|---|
| Public identity | Business name, brand, core description | Location contact/directions/local details |
| Hours | Default operating pattern | Location hours and temporary closure |
| Offerings | Master products/services/menu | Availability, price, or assortment where supported |
| Appointments | Shared policy defaults | Providers, services, slots, queue |
| Team | Business membership | Assignment and operating Location |
| Fulfilment | Shared methods/policies | Pickup, delivery area, fees, service radius |
| Module behavior | Business-level activation | Location availability/configuration only when module supports it |
| Website | One Business website | Location selection and Location-specific content/action state |
| Marketplace | One Business profile/identity | Location-specific discoverability and availability views |

## 7.3 Public experience examples

A restaurant may use one website where a customer chooses a Location and sees the relevant menu, availability, pickup, and delivery options.

A clinic may use one website where services, providers, appointments, and availability vary by Location.

This document does not define the exact selector, URL, or page layout. Document 05 governs Location context and route architecture; later page specifications govern UI.

## 7.4 Profile behavior with Locations

- The profile may suggest which settings commonly vary by Location.
- Business configuration supplies defaults; explicit Location configuration overrides only supported fields.
- A profile update MUST NOT overwrite Location overrides.
- Location-specific module availability cannot exceed Business Entitlement or Business-level capability.
- User access to Location configuration remains governed by Document 06.

**Traceability:** Document 05 Part 11, `LOC-001`–`LOC-011`, `KIR-004`; Document 06 `SCOPE-001`–`SCOPE-006`.

---

# 8. Profile Lifecycle

## 8.1 States and transitions

| State | Meaning | Allowed experience |
|---|---|---|
| Profile suggested | Platform proposes likely type based on supplied information | Review, choose another, skip |
| Profile selected | Business chooses a starting profile | Preview recommendations/defaults |
| Defaults previewed | Proposed terminology, capabilities, and guidance are visible | Accept selectively, edit, dismiss |
| Recommendations accepted selectively | Business chooses individual recommendations | Continue through normal Entitlement/setup gates |
| Business customized | Explicit choices/configuration diverge from profile | Preserve and label as Business configuration |
| Profile changed | Business chooses another primary profile | Preview differences; preserve data and explicit decisions |
| Profile version updated | Maintainer publishes improved recommendations | Apply to future suggestions; do not overwrite committed configuration |

## 8.2 Recommendation update versus migration

| Change type | Behavior |
|---|---|
| Recommendation update | Changes what is suggested next; safe to apply without mutating Business state |
| Default update for unset field | May be offered for review; not silently committed |
| Terminology suggestion update | Preview and request acceptance if Business has saved terminology |
| Business configuration migration | Explicit, versioned, impact-reviewed change with recovery/rollback expectations defined elsewhere |
| Module compatibility migration | Governed by module lifecycle/technical specification, not profile update |

**PROFILE-001:** Profile version updates MUST preserve explicit Business decisions.

**PROFILE-002:** A migration is never disguised as a recommendation refresh.

**PROFILE-003:** The experience SHOULD identify when the Business differs from current profile defaults without framing customization as an error.

---

# 9. Recommendation Behavior

## 9.1 Inputs

Recommendations may consider:

- selected Business type;
- operating characteristics;
- enabled and deactivated capabilities;
- current Business configuration;
- Business maturity and setup completion;
- single- or multi-Location structure;
- actual usage and observed needs where appropriate;
- current compatibility and genuine dependencies; and
- available Commercial Entitlement options without designing pricing here.

## 9.2 Explanation standard

Recommendations should be understandable:

- “Restaurants commonly enable Reservations when they accept table bookings.”
- “This capability works with your current Website and booking setup.”
- “This Location has delivery enabled, but no delivery area is configured.”

Avoid:

- “Recommended for you” with no reason;
- urgency or scarcity unsupported by reality;
- repeated upsell after explicit dismissal;
- implying a common pattern is mandatory;
- hiding dependencies until after commitment; or
- recommending a capability the Business cannot meaningfully use.

## 9.3 Recommendation outcomes

| Outcome | Effect |
|---|---|
| Accept | Begin Entitlement/enablement/setup flow |
| Dismiss | Record preference; retain discoverability without repeated pressure |
| Remind later | Defer for a clear period or milestone |
| Not applicable | Suppress until relevant characteristics/configuration change |
| Already configured externally/differently | Preserve explicit Business approach; do not force platform workflow |

This document does not define a machine-learning recommendation engine. Deterministic, explainable rules are sufficient.

---

# 10. Reference Business-Type Profiles

## 10.1 How to read these profiles

These profiles prove the framework. They are examples, not mandatory bundles. “Recommended” means commonly useful, not automatically installed, entitled, enabled, or visible.

Canonical module names from Document 04 are included where available. Module inventory remains owned by Document 04 and future module specifications.

## 10.2 Restaurant / Food Service

| Dimension | Reference profile |
|---|---|
| Business characteristics | Product/menu-led; may support dine-in, takeaway, delivery, reservations, catering; often Location-sensitive |
| Likely goals | Publish menu, receive orders/reservations, coordinate preparation and fulfilment, retain customers |
| Recommended capabilities | Website, `catalog-orders`, payments where needed, `delivery`, `booking-calendar` for reservations, `crm`, future/relevant AI Receptionist |
| Suggested terminology | Menu Items, Orders, Reservations, Guests, Pickup, Delivery |
| Dashboard emphasis | Current orders, preparation status, reservations, availability, fulfilment exceptions |
| Website/Marketplace suggestions | Menu and Location prominence; Order/Reserve/Contact CTAs based on enabled capabilities |
| Location considerations | Menu/price/availability, hours, seating, pickup/delivery area may vary |
| Optional extensions | Inventory, loyalty, subscriptions, catering enquiries, AI WhatsApp assistance |

## 10.3 Clinic / Healthcare Service

| Dimension | Reference profile |
|---|---|
| Business characteristics | Service/provider-led; scheduled appointments; may use queue; often multi-Location |
| Likely goals | Explain services, show providers/availability, manage appointments and follow-up |
| Recommended capabilities | Website, Services, `appointments` or `booking-calendar`, provider/staff capability, availability, queue where applicable, billing/payments, customer relationship capability |
| Suggested terminology | Services, Appointments, Doctors/Providers, Patients where appropriate, Locations |
| Dashboard emphasis | Upcoming appointments, queue, provider availability, urgent operational follow-up |
| Website/Marketplace suggestions | Services, providers, Locations, availability, Book/Contact CTAs, verified factual credentials where canonical |
| Location considerations | Providers, services, schedules, queue, contact information differ by Location |
| Optional extensions | Invoicing, reminders, AI appointment assistance; no medical-record or regulatory-compliance claim is created here |

## 10.4 Gym / Fitness

| Dimension | Reference profile |
|---|---|
| Business characteristics | Membership-led; attendance, trainers, classes, sessions, renewals |
| Likely goals | Acquire members, manage plans/classes, track attendance, support renewals |
| Recommended capabilities | Website, memberships/subscriptions, attendance, trainers/staff, classes, booking/sessions, payments, `crm` |
| Suggested terminology | Members, Memberships, Classes, Sessions, Trainers, Attendance |
| Dashboard emphasis | Today’s classes, attendance, expiring memberships, renewals, trainer availability |
| Website/Marketplace suggestions | Membership options, classes, trainers, facilities, Join/Book/Visit CTAs |
| Location considerations | Classes, trainers, facilities, schedules, membership availability may vary |
| Optional extensions | Loyalty, events, personal-training appointments, communications, AI content assistance |

## 10.5 Salon / Personal Care

| Dimension | Reference profile |
|---|---|
| Business characteristics | Service and appointment-led; staff/provider schedules; may sell products/packages |
| Likely goals | Present services, fill schedules, manage staff availability, retain customers |
| Recommended capabilities | Website, Services, `booking-calendar`, staff, `crm`, payments where needed |
| Suggested terminology | Services, Appointments, Stylists/Professionals, Clients, Packages |
| Dashboard emphasis | Today’s appointments, staff schedule, availability gaps, customer follow-up |
| Website/Marketplace suggestions | Services/prices, team, availability, Book/Contact CTAs, brand-flexible visual presentation |
| Location considerations | Services, staff, hours, prices, and availability may differ |
| Optional extensions | Memberships/packages, loyalty, inventory/retail products, AI appointment assistance |

## 10.6 Home-Food / Small Food Business

| Dimension | Reference profile |
|---|---|
| Business characteristics | Small product/menu-led operation; home-based, online-only, pickup, or delivery; variable availability |
| Likely goals | Establish credible presence, publish current offering, receive manageable orders, communicate fulfilment |
| Recommended capabilities | Website, product catalogue/menu, `catalog-orders`, payments where useful, `delivery`, customer communication/`crm` |
| Suggested terminology | Menu, Items, Orders, Availability, Pickup, Delivery |
| Dashboard emphasis | New orders, preparation/fulfilment, cutoff times, current availability |
| Website/Marketplace suggestions | Current menu, order timing, service area, trust facts, Order/Contact CTA |
| Location considerations | Do not force a public branch; use service area, pickup point, or online-only behavior |
| Optional extensions | Subscriptions, loyalty, inventory, AI WhatsApp assistance, packaged-product catalogue |

## 10.7 Retail / Commerce

| Dimension | Reference profile |
|---|---|
| Business characteristics | Product-led; inventory may matter; online, physical, or hybrid fulfilment |
| Likely goals | Publish products, manage stock/orders, collect payment, fulfil and retain customers |
| Recommended capabilities | Website/storefront, Products/`catalog-orders`, `inventory`, payments, shipping/`delivery`, `crm` |
| Suggested terminology | Products, Categories, Stock, Orders, Shipping, Pickup |
| Dashboard emphasis | Orders, low stock, fulfilment, returns/exceptions, sales activity |
| Website/Marketplace suggestions | Product/category discovery, availability, fulfilment choices, Buy/Order/Visit CTAs |
| Location considerations | Stock, assortment, pickup, prices where supported, and hours may vary |
| Optional extensions | Loyalty, marketing, subscriptions, supplier/invoicing capabilities |

## 10.8 Professional Services

No canonical `professional_services` type identifier currently exists in Document 04. This reference describes the configuration family; it does not invent a production identifier.

| Dimension | Reference profile |
|---|---|
| Business characteristics | Expertise/service-led; enquiry, proposal, appointment, project, or invoice-oriented; B2C, B2B, or both |
| Likely goals | Establish credibility, explain services, capture qualified enquiries, schedule discussions, invoice where supported |
| Recommended capabilities | Website, Services, enquiries/leads, appointments where relevant, `crm`, payments/invoicing where supported |
| Suggested terminology | Services, Enquiries, Consultations, Clients, Projects |
| Dashboard emphasis | New enquiries, follow-ups, appointments, outstanding proposals/invoices where enabled |
| Website/Marketplace suggestions | Expertise, services, evidence, service area, Enquire/Book/Contact CTA |
| Location considerations | May be office-based, service-area, remote, or multi-office; no physical Location should be forced |
| Optional extensions | Booking, invoicing, document exchange, customer communication, AI content assistance |

---

# 11. Configuration Dimensions Beyond Business Type

## 11.1 Operating characteristics

Business type alone is insufficient. A compact characteristic set may include:

| Characteristic | Question it answers |
|---|---|
| Sells products | Are catalogue, inventory, order, and fulfilment recommendations relevant? |
| Provides services | Are service presentation and provider concepts relevant? |
| Accepts appointments | Are availability and scheduled booking relevant? |
| Accepts orders | Are cart/order/fulfilment workflows relevant? |
| Has physical Locations | Are hours, directions, Location selection, and local availability relevant? |
| Delivers/serves an area | Are address eligibility, service radius, shipping, or delivery relevant? |
| Has a team | Are assignment, schedules, permission templates, and access setup relevant? |
| Has memberships | Are plans, renewals, attendance, and recurring relationships relevant? |
| Runs classes/events | Are capacity, schedule, attendance, and recurring sessions relevant? |
| Operates online-only | Should physical-branch setup be omitted? |
| Serves consumers, Businesses, or both | Which discovery, relationship, and transaction suggestions are relevant? |

## 11.2 Taxonomy restraint

- Add a characteristic only when it changes recommendations, setup, terminology, or runtime configuration.
- Prefer booleans or small controlled options over an industry ontology.
- Characteristics are not permissions or Entitlements.
- Avoid duplicating data already known from enabled modules or Business configuration.
- Let actual capability choice supersede a stale characteristic.

---

# 12. Onboarding Implications

## 12.1 Profile contribution

The profile contributes to this bounded sequence:

```text
Business basics
→ Type and operating characteristics
→ Relevant capability recommendations
→ Business selects capabilities
→ Selected capabilities enter Entitlement/enablement/setup
→ Workspace adapts
```

## 12.2 Onboarding rules

**ONBOARD-TYPE-001:** Type selection MUST be skippable through “Other/Not sure” without preventing Business creation.

**ONBOARD-TYPE-002:** Recommended modules MUST be individually understandable and selectively accepted.

**ONBOARD-TYPE-003:** Setup questions appear only when they affect the Business minimum, a chosen capability, publication, transaction readiness, or accepted enrichment.

**ONBOARD-TYPE-004:** The onboarding summary distinguishes Platform Core, recommendations, selected modules, dependencies, and commercially gated choices.

**ONBOARD-TYPE-005:** AI-generated configuration remains an editable proposal and MUST NOT silently publish, purchase, activate, or invent regulated facts.

**Traceability:** Document 05 §8.2–§8.6, `JRN-BIZ-001`, `JRN-BIZ-002`.

---

# 13. Workspace Implications

The runtime workspace is not generated from Business type alone.

```text
Workspace =
Platform-core shell
+ enabled/configured module contributions
+ Business/Location configuration
+ Entitlement
+ permission and Location scope
+ current activity/resource state
+ progressive-complexity policy
```

A profile may influence:

- initial dashboard emphasis before meaningful usage exists;
- terminology and task framing;
- suggested setup actions;
- contextual empty-state guidance;
- module recommendations; and
- ordering of equally authorized/relevant destinations.

A profile MUST NOT:

- show an unauthorized feature because it is “recommended”;
- replace access-denied states with type-based assumptions;
- keep a deactivated module in routine operational navigation;
- override runtime urgency with a static vertical dashboard; or
- bypass Document 06 visibility and route-guard rules.

As actual activity accumulates, runtime relevance may supersede the initial type-based emphasis.

**Traceability:** Document 02 §V; Document 05 §9.1–§9.5; Document 06 §6–§7.

---

# 14. Public Website and Marketplace Implications

## 14.1 Website suggestions

A profile may suggest:

- useful content families;
- primary action vocabulary;
- offering emphasis;
- Location information;
- trust and verification prompts;
- content questions for AI/manual generation; and
- capabilities needed for Order, Book, Enquire, Contact, or Visit journeys.

It MUST NOT prescribe one universal hero, font, section order, visual personality, or template. Business identity, requirements, content, selected capabilities, and explicit customization govern the final website.

## 14.2 Marketplace suggestions

A profile may suggest:

- Marketplace category and secondary tags;
- whether products, services, appointments, or Locations deserve prominence;
- relevant filters and factual trust evidence;
- appropriate action types; and
- characteristic-specific public information.

Published Business data, module capability, Location availability, and visibility rules govern what actually appears. A profile hint cannot publish data.

## 14.3 One Business, distinct renderings

The website and Marketplace profile remain distinct renderings of one Business. Profile hints may inform both without forcing them to share identical page structure.

Detailed page architecture belongs to later Public Platform, Customer, and Business website specifications.

**Traceability:** Document 02 §VI–§VII; Document 03 §4; Document 05 `SUR-003`, `CONFLICT-009`.

---

# 15. AI Implications

## 15.1 AI context inputs

AI assistance may use:

- Business-Type Profile;
- operating characteristics;
- enabled capabilities and configuration;
- active Business and Location;
- configured terminology;
- actual Business data the user may access;
- current resource/workflow state; and
- profile recommendations and their explanation.

## 15.2 Authority boundary

Business type alone never authorizes an AI action.

AI remains constrained by:

1. Platform Identity and active context;
2. Business membership;
3. Location scope;
4. Commercial Entitlement;
5. module enabled/configured state;
6. user permission;
7. resource/workflow policy; and
8. future AI-specific safety and approval rules.

AI may propose website content, configuration, workflow, or capability recommendations. It MUST NOT silently:

- purchase Entitlement;
- enable or re-enable a module;
- publish a website or Marketplace change;
- alter access;
- act in a disallowed Location;
- fabricate Business facts, credentials, or compliance; or
- execute a consequential workflow without required authority.

This document does not define model selection, prompts, tool contracts, memory, or AI runtime implementation.

---

# 16. Configuration Profile Schema — Conceptual Only

## 16.1 Conceptual fields

| Field | Purpose |
|---|---|
| Profile identifier | Stable reference to the profile |
| Name and description | Human-readable meaning and intended Business characteristics |
| Category/family | Broad classification for organization and discovery |
| Version/status | Track maintained profile evolution |
| Characteristics | Signals commonly associated with the profile |
| Recommended capabilities | Ranked suggestions with reason and compatibility/dependency hints |
| Suggested terminology | Labels and action vocabulary |
| Suggested defaults | Reviewable starting values, not committed Business state |
| Dashboard emphasis | Likely initial priorities, not fixed layout |
| Navigation emphasis | Relative relevance hints for enabled/authorized destinations |
| Onboarding guidance | Questions, sequencing hints, and skip conditions |
| Website suggestions | Content, CTA, capability, and generation hints |
| Marketplace hints | Categories, offering emphasis, filters, public facts |
| Workflow suggestions | Common operational patterns |
| Location considerations | Likely Business-wide defaults and supported variations |
| AI context hints | Relevant assistance categories and vocabulary |
| Provenance/maintainer | Who maintains the profile and why a recommendation exists |

## 16.2 Explicitly separate records/concepts

The conceptual profile MUST remain separate from:

- the Business’s accepted module choices;
- Installed/Enabled Module state;
- Commercial Entitlement;
- Business configuration;
- Location configuration;
- membership, role, permission template, and Location scope;
- runtime resources and transactions; and
- pricing/plan definitions.

This section is not a database schema. It defines conceptual ownership only.

---

# 17. Precedence and Override Matrix

## 17.1 Matrix

| Source | What it may determine | Can profile override it? | When sources differ |
|---|---|---|---|
| Platform invariant | Identity, tenant, security, core domain rules | No | Invariant wins |
| Security/access rule | What this person may know/do in context | No | Document 06 evaluation wins |
| Commercial Entitlement | Commercial maximum and quota | No | Entitlement limits runtime availability |
| Genuine capability dependency | Required supporting capability | No | Dependency must be satisfied or chosen capability cannot activate |
| Explicit Business module choice | Enable, decline, deactivate, re-enable | No | Explicit choice wins over recommendation |
| Explicit Business configuration | Business-wide saved behavior | No | Saved Business value wins over profile/default |
| Explicit Location configuration | Supported Local override | No | Location value wins in that Location, within Business/Entitlement limits |
| Business-Type recommendation | Suggested capability/default/terminology/emphasis | N/A | Applies only where no explicit decision exists |
| Platform default | Generic fallback | Yes | Profile suggestion may replace it until Business explicitly saves |
| User permission and Location scope | Person-specific visibility/action | No | May further restrict; never grants capability |
| Runtime resource/workflow state | Current truth and actionability | No | Current state governs immediate behavior |

## 17.2 Resolution examples

- Profile recommends Delivery; Business declines → Delivery remains disabled.
- Profile update adds Reservations; Business sees a new recommendation → nothing activates automatically.
- Business enables Website but lacks current Entitlement → show the correct commercial state; profile cannot bypass it.
- Business config says “Services,” profile suggests “Treatments” → saved Business terminology wins.
- Business default menu includes an item; Location marks it unavailable → Location runtime/configuration governs there.
- Profile emphasizes Bookings; Member lacks permission → Bookings remain hidden/restricted according to Document 06.

---

# 18. Anti-Patterns

## 18.1 Separate product per type

**Reject:** RestaurantOS, ClinicOS, and GymOS as isolated applications or codebases.

**Use:** one Business/kernel/module/renderer foundation with profile data and chosen capabilities.

## 18.2 Forced bundles

**Reject:** “You are a restaurant; therefore Delivery is mandatory.”

**Use:** recommend Delivery with a reason; allow the Business to decline unless an explicitly chosen capability genuinely depends on it.

## 18.3 Template equals product

**Reject:** defining a Business type as one fixed website template.

**Use:** brand-flexible website suggestions and capabilities.

## 18.4 Industry label controls everything

**Reject:** deriving dashboard, routes, permissions, and workflows only from a type string.

**Use:** type + characteristics + chosen modules + configuration + context.

## 18.5 Endless subtype explosion

**Reject:** BakeryCaféWithDelivery, ClinicWithPharmacy, SalonWithRetail as hard-coded types.

**Use:** primary profile plus characteristics and capabilities.

## 18.6 Profile overrides explicit choice

**Reject:** profile updates that reactivate, rewrite, or remove Business configuration.

**Use:** recommendation refresh plus explicit migration when truly necessary.

## 18.7 Location equals Business

**Reject:** separate tenant/website/account solely for each branch.

**Use:** one Business with Location-specific configuration and public context.

## 18.8 False dependency

**Reject:** requiring Website for every Payments use case or Orders for every restaurant.

**Use:** capability/use-case dependencies. Website checkout, invoice payment, payment link, and in-person collection may require different supporting capabilities.

---

# 19. Traceability

## 19.1 Canonical references

| Topic | Source |
|---|---|
| One Business, modular platform | Document 01 §1–§3; Document 03 §1.1, §2, §4 |
| Current legacy `BusinessType` manifest | Document 03 §1.4 |
| Configuration/settings separation | Document 03 §1.5 |
| Module manifests and dependencies | Document 03 §2.1–§2.3; Document 04 §3.0 |
| Current Business-type inventory | Document 04 Part 10 |
| Product module inventory | Document 04 §3.0 |
| Business-type recommendation decision | Document 05 `MOD-008`, `KIR-002`, `CONFLICT-004` |
| Use-case dependency rule | Document 05 `MOD-009` |
| Adaptive onboarding | Document 05 §8.2–§8.6 |
| Adaptive workspace/navigation | Document 05 §9.1–§9.5, `NAV-007`–`NAV-011` |
| Location behavior | Document 05 Part 11, `LOC-001`–`LOC-011`, `KIR-004` |
| Entitlement/module separation | Document 05 §12, `MOD-001`–`MOD-006`, `KIR-005` |
| Access evaluation | Document 06 `ACCESS-001`–`ACCESS-006`, §2, Matrix D |
| Location-scoped access | Document 06 `SCOPE-001`–`SCOPE-006` |
| Website/Marketplace experience | Document 02 §VI–§VII; Document 05 `SUR-003` |

## 19.2 Source assumptions superseded here

The following earlier assumptions are not preserved:

- Document 01 §3 describes types as module bundles that enable operational modules.
- Document 03 §1.4 uses `defaultModules` and `requiredModules`.
- Document 03 §2.3 describes Business type as a module bundle.
- Document 04 §0.5 and Part 10 describe default/required modules.
- Document 04 onboarding automatically provisions a type bundle.
- Document 04 type-specific page-section sequences can read as fixed templates.

The governing resolution is Document 05 `KIR-002`: Platform Core is universal; Business type recommends operational modules; the Business chooses; genuine capability dependencies remain enforceable.

## 19.3 Traceability limitations

- The exact Platform Core inventory is not canonical.
- Some module names differ between Documents 03 and 04.
- `inquiry-leads` appears in Business-type configurations but is absent from Document 04’s main module catalogue.
- A canonical Professional Services profile identifier does not exist.
- Profile, characteristic, terminology, and dependency concepts lack stable source IDs beyond Document 05 rules.

---

# 20. Gap and Decision Register

## 20.1 Genuine conflicts

| ID | Conflict | Governing resolution | Classification |
|---|---|---|---|
| `BTP-CONFLICT-001` | Documents 01, 03, and 04 treat type as an auto-provisioned/default/required module bundle | Type is a recommendation profile; only Platform Core is universal | Blocking before technical/data design |
| `BTP-CONFLICT-002` | Document 04 onboarding auto-provisions the category bundle | Recommendations require selective Business acceptance | Blocking before onboarding implementation |
| `BTP-CONFLICT-003` | Document 04 fixed dashboard blocks and type-specific page sequences conflict with adaptive workspace and brand-flexible websites | Treat them as examples/suggestions, not immutable structures | Important, non-blocking |
| `BTP-CONFLICT-004` | Document 03/04 use inconsistent module identifiers such as `orders` versus `catalog-orders` | Normalize against the future canonical module registry | Blocking before technical contracts |
| `BTP-CONFLICT-005` | Document 04 dependency examples can imply one static Payments dependency path | Dependencies must be capability/use-case specific under `MOD-009` | Blocking before Document 08/technical design |

## 20.2 Gaps and decisions

| ID | Question/Gap | Recommended direction | Classification |
|---|---|---|---|
| `BTP-DEC-001` | Which capabilities are true Platform Core? | Canonically enumerate only identity/profile foundation, workspace/home foundation, settings, team/access, module management, basic notifications, and essential infrastructure after validating module ownership | Blocking before Document 08 |
| `BTP-DEC-002` | May one Business apply multiple full profiles? | Use one primary profile plus characteristics initially; add multi-profile composition only with demonstrated need | Important, non-blocking |
| `BTP-DEC-003` | How do terminology overrides scope and fall back? | Business explicit label → profile suggestion → platform default; keep canonical object semantics stable | Blocking only before technical/data design |
| `BTP-DEC-004` | How do profile versions affect existing Businesses? | Update recommendations automatically; require explicit review for saved configuration or terminology migrations | Blocking only before technical/data design |
| `BTP-DEC-005` | Are recommendations globally maintained or Business-customizable? | Platform maintains profile recommendations; Businesses customize resulting choices/configuration, not the global profile | Important, non-blocking |
| `BTP-DEC-006` | How are genuine module dependencies represented? | Canonical capability/dependency registry with alternatives and use-case conditions | Blocking before Document 08 and technical design |
| `BTP-DEC-007` | What is the minimal canonical characteristic vocabulary? | Start with the dimensions in §11; add only behavior-changing characteristics | Important, non-blocking |
| `BTP-GAP-001` | Commercial Entitlement contract is not yet canonical | Resolve under Document 05 `KIR-005`; Document 08 owns commercial model | Blocking before Document 08 finalization |
| `BTP-GAP-002` | Location-level module override contract is not in the Kernel | Resolve under `KIR-004` | Blocking only before technical/data design |
| `BTP-GAP-003` | `professional_services` has no canonical profile ID | Decide whether to add a broad family or retain narrower profiles plus characteristics | Important, non-blocking |
| `BTP-GAP-004` | `inquiry-leads` is referenced but absent from the primary module catalogue | Normalize module inventory before using it as a dependency or Entitlement item | Blocking before Document 08 |

## 20.3 Blocking summary

No unresolved decision blocks page-by-page experience design if profiles are treated as recommendations and examples.

Before Document 08 can be finalized, resolve:

1. the exact Platform Core inventory;
2. canonical module/capability identifiers;
3. genuine dependency representation, including alternative/use-case dependencies;
4. the Commercial Entitlement contract boundary; and
5. whether missing modules such as `inquiry-leads` are canonical.

Before physical data/API design, additionally resolve:

- profile version/migration semantics;
- terminology override storage/scope;
- Location-level module override contracts; and
- stable characteristic/profile identifiers.

---

# Document Completion Criteria

This document is complete when future product and coding work can determine:

1. what Business type may influence;
2. what remains shared across every Business;
3. why recommendations cannot force operational modules;
4. how explicit Business and Location configuration override suggestions;
5. how hybrid Businesses avoid subtype explosion;
6. how reference profiles guide without becoming bundles;
7. how access, Entitlement, and runtime state constrain the result; and
8. which unresolved concepts belong to Documents 08 or later technical specifications.

---

**End of Document 07 — Business-Type Configuration Profile Specification**
