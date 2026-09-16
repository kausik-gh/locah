# Product Experience Bible
*The single source of truth for every designer, writer, motion designer, and product maker on this team.*

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
> | Content here | Governing position |
> |---|---|
> | "The single source of truth" for product makers | Still governing for **how the platform should feel**. The canonical *page and surface inventory* is **Document 09**; launch scope is **Document 11**. |
> | Trust Score references | `svc-statistics-trust`, a shared service — `D10-CONFLICT-006` |
>
> This document's emotional architecture, clarity, progressive-complexity, and
> access-state language principles are **current and governing**. It is the least
> superseded of Documents 01–04.

---

---

## Preface — The Governing Question

Before any design decision, animation, line of copy, or screen layout, ask:

> **Did this make the person’s purpose clearer, easier, and more trustworthy—or did it make them manage the software?**

For a Business operator, this means feeling capable, informed, and in control. For a consumer, it means discovering, deciding, ordering, or booking with confidence. For a prospective Business owner, it means understanding the platform and seeing a credible path forward. For a visitor, it means grasping how Businesses and people participate in one connected ecosystem.

The platform is not only a merchant product. It connects Businesses establishing and operating their digital presence with people discovering and interacting with those Businesses.

The interface should recede. The person’s purpose should remain.

This document governs how the platform should feel and behave. It does not permanently prescribe what every page must look like.

---

## I. Emotional Architecture

Different people encounter the platform with different intentions. Emotional goals belong to contexts and surfaces, not permanent user categories. The underlying register remains **calm, precise, professional, purposeful, and on the person’s side.**

### Business operators — capability and control

A Business operator should feel capable, informed, and less burdened by operational complexity. Relief matters when scattered work becomes coherent. Competence matters when the platform notices what needs attention, explains it clearly, and then gets out of the way.

### Consumers — trust, ease, and confidence

A person discovering a Business, product, or service should feel confident that the information is credible and the next action is clear. Ordering, booking, contacting, saving, and returning should feel easy without resembling a merchant operating dashboard.

### Prospective Business owners — understanding and confidence

A prospective owner should feel recognized: the platform understands real Business needs rather than presenting abstract software. They should see a credible path from joining to establishing a presence, selecting useful capabilities, and operating the Business.

### Platform and brand visitors — ecosystem clarity

A visitor to the main platform website should understand both sides of the system: Businesses create and operate their presence; people discover and interact with them. The experience may communicate ambition and possibility, but comprehension comes first.

Relief, trust, recognition, competence, calm, and precision remain valuable emotional outcomes. Their priority changes with the journey. No single emotion is permanently assigned to every person in a broad audience.

---

## II. Design Language

### Durable experience principles

The platform should feel minimal, neat, professional, clear, calm, purposeful, trustworthy, and highly considered. Minimal does not mean empty, generic, or static. Restraint is deliberate: whitespace clarifies relationships, hierarchy makes decisions easier, and visual emphasis is earned.

Premium quality comes primarily from typography, spacing, composition, consistency, responsiveness, performance, accessibility, thoughtful interaction, and precise execution. Gradients, 3D, glass effects, dramatic shadows, animation, and decoration are not substitutes for those fundamentals. They may be used when they serve a clear purpose and suit the surface.

Across platform-owned surfaces:

- hierarchy MUST remain clear at a glance;
- whitespace MUST be generous enough to aid comprehension, not waste space;
- typography MUST be readable and structurally consistent;
- colour MUST be deliberate, accessible, and coherent;
- responsive behavior MUST feel designed rather than merely compressed;
- interaction states MUST be understandable without relying on colour alone;
- visual density MUST match the work and the device;
- real content MUST be preferred over decorative placeholders; and
- accessibility and performance are qualities of the experience, not post-design checks.

### Platform-owned surfaces and Business-owned websites

The main platform website, Marketplace, consumer account, Business workspace, and Platform Administration are platform-owned surfaces. They should share coherent identity, interaction logic, accessibility standards, and design-system foundations while adapting density and expression to their different jobs.

Business-owned public websites and storefronts use the platform’s quality standards but do not inherit one mandatory visual personality. Their typography, colour, composition, imagery, motion, and page structure may adapt to Business identity, industry, requirements, content, enabled capabilities, Locations, and desired style.

### Current design-system direction — provisional

Exact tokens and component choices are implementation, not eternal experience philosophy. A future Platform Design System may supersede this section as the canonical authority for fonts, colour values, spacing, radii, elevation, and component specifications.

The following remain useful current direction:

- A warm neutral “ink” scale from `#0B0C0E` to an off-white `#FAFAF9` base.
- Signal Indigo `#4A5FE0` as a restrained platform accent.
- Semantic success `#1F9D6B`, danger `#D8483C`, and warning `#B8862E`, each used with accessible contrast and non-colour cues.
- Geist as the current platform-interface typeface, with tabular numerals for aligned financial and operational data.
- A 4px spacing base, disciplined layout rhythm, modest radii, and restrained elevation.
- Dark mode as an optional surface-specific choice rather than an automatic marker of premium quality.

These choices SHOULD remain consistent while current, but they MAY evolve through deliberate design-system governance. They MUST NOT be copied as mandatory branding for every Business website.

### Typography and spacing

Typography must establish hierarchy, remain legible under real content, and support the tone of its surface. Operational interfaces prioritize scanning, numbers, and compact clarity. Consumer surfaces prioritize discovery and confident action. Business websites may use type systems appropriate to their own identities; Fraunces and Inter are an example direction, not a universal pairing.

Spacing should produce rhythm, grouping, and breathing room. Density may differ between an administration table, mobile checkout, Marketplace result, and editorial Business website. Consistency matters, but no single section-padding value or type scale is universal across all surfaces.

### Content and imagery

Real, credible content is stronger than generic polish. When the subject can be represented honestly, prefer real Business photography, names, products, services, and specific facts. A notebook, conversation, order, or storefront should feel like evidence from a real operating context rather than a stock SaaS scene.

Illustration, abstract graphics, generated imagery, and technically expressive visuals are valid when they clarify a concept or suit the brand. They should not fabricate Business facts, imitate evidence, or replace useful content with visual noise.

---

## III. Motion Philosophy

Motion is deliberate when it supports storytelling, comprehension, transition, feedback, spatial orientation, hierarchy, focus, continuity, brand expression, or earned delight. It does not need to be strictly necessary to be legitimate, but it must justify its cost in attention, accessibility, and performance.

Use a surface-appropriate motion register:

- **Marketing/platform website:** may use expressive, memorable, technically impressive motion when it strengthens the story and leaves the proposition understandable without animation.
- **Marketplace and consumer experience:** generally subtle, responsive, and non-obstructive; motion should reinforce confidence and continuity rather than delay action.
- **Business workspace:** functional, restrained, and fast; operational work takes priority over spectacle.
- **Platform Administration:** direct and predictable, with strong state feedback.
- **Business websites:** adapts to the Business identity and desired experience while meeting quality, accessibility, and performance requirements.

Minimal does not mean static. It means motion has composition, timing, and purpose rather than appearing everywhere.

The current platform design system may define standard duration and easing tokens for consistency. Those values belong to implementation governance, not permanent product philosophy.

Every motion system MUST:

- honor reduced-motion preferences;
- preserve understanding and action without animation;
- avoid blocking navigation or interaction;
- avoid layout shift and excessive resource cost;
- distinguish loading, progress, success, and failure truthfully; and
- remove meaningless repetition, ambient noise, and motion that competes with the task.

Skeletons, progress indicators, and transitions should match the actual loading model and reduce perceived instability. No one loading pattern is mandatory for every duration or content type.

---

## IV. The Main Platform Website — A Connected Ecosystem

The website is the clearest public expression of the company. It should explain that the platform connects two sides:

- **People** discover Businesses, products, and services; order, book, contact, and return.
- **Businesses** establish a digital presence, choose capabilities, operate, use assistance and automation, and reach the people they serve.

It may use narrative storytelling, product evidence, real Business context, or ecosystem visualization. Recognition, transformation, and vision remain powerful narrative ingredients, but **Chaos → Recognition → Hope → Transformation → Vision** is a creative concept, not mandatory homepage architecture.

The website should remain minimal, spacious, professional, and easy to understand. Its story may be ambitious and memorable without hiding essential meaning behind spectacle.

### Signature hero principle

One strong signature storytelling experience may create memorability while the overall website remains minimal, clear, and structured.

A central visual—potentially a phone, device, Business presence, or another strong object—may show scattered activity becoming connected, capabilities coming together, customers discovering the Business, transactions or bookings occurring, and Businesses joining a wider ecosystem.

This principle does not define a final storyboard. Exact scenes, sequence, device design, animation, scroll behavior, and interaction belong to the page-level specification.

The visitor MUST understand the platform and reach primary actions without completing, watching, or interacting with the animation. Storytelling MUST NOT block navigation, accessibility, performance, or comprehension.

### Beyond the hero

The page may later cover the ecosystem, consumer discovery, Business capabilities, websites and digital presence, AI and automation, Marketplace, modules, trust, network effects, and calls to action.

This Bible does not fix their order, copy, visual treatment, or interaction. The Public Platform & Customer Page-by-Page Experience Specification will define the detailed page architecture.

---

## V. Business Workspace

### The morning test

The workspace passes or fails on one question:

> **What matters now?**

If opening the workspace replaces checking several disconnected tools—because relevant work is coherent and intelligently ordered—the product works. If it is merely another place to check, it has failed regardless of visual quality.

### Adaptive operational emphasis

There is no universal dashboard composition. The useful first view depends on Business type, enabled modules, Commercial Entitlements, permissions, role or permission template, Active Location, current activity, and Business scale.

Examples:

- A restaurant may prioritize orders, preparation, pickup, and delivery.
- A clinic may prioritize appointments, queue state, doctors, and urgent follow-up.
- A gym may prioritize attendance, memberships, and renewals.
- A salon may prioritize appointments, staff schedules, and service availability.

An action queue, operational observation, revenue snapshot, Business Health signal, or AI suggestion may be valuable. None is a mandatory universal block. The interface should surface the most consequential permitted work and make its scope—Business-wide or Location-specific—clear.

### Progressive complexity

The workspace grows with the Business. A small operator and a multi-Location Business need different levels of depth. Surface what is relevant to the current context, with more detail available deliberately. Do not expose complexity merely because the platform supports it, and do not hide required capability behind oversimplification.

Business type informs recommendations, terminology, and starting emphasis; it does not rigidly dictate one interface. Modules shape available experiences. Entitlement, activation/configuration, Location availability, and permission determine what is actually usable.

### Navigation and interaction patterns

Navigation should be stable, permission-aware, module-aware, responsive, and progressively revealed. A desktop sidebar, mobile tab bar, contextual drawer, focused page, modal, or command palette may be the right pattern in a particular implementation. No one pattern is immutable across every Business workflow.

Preserve context during routine work where useful. Reserve interruption and full-attention treatment for actions that warrant it. Advanced shortcuts and search may improve expert efficiency without becoming prerequisites for normal operation.

The Merchant Workspace Page-by-Page Experience Specification and Platform Design System will define exact navigation, dashboard composition, mobile patterns, drawers, dialogs, and command behavior.

---

## VI. Business-Owned Websites and Storefronts

### The core challenge

A Business website should feel specific to the Business, not like a shared platform template with a different logo. A restaurant, clinic, gym, luxury salon, home-food brand, and professional service Business may require substantially different structures, tones, and interaction models.

Websites may be AI-generated, Business-configured, manually customized, or customized by the Platform Super Admin during the early stage. They may adapt to Business identity, industry, requirements, brand, content, enabled capabilities/modules, Locations, and desired style.

### Universal quality requirements

Every Business website should provide:

- clear and appropriate navigation;
- strong hierarchy and readable content;
- prominent actions appropriate to the Business;
- truthful Business, offering, Location, availability, and trust information;
- responsive and accessible interaction;
- strong performance;
- visual and verbal consistency within that Business’s identity; and
- safe transaction and contact paths where supported.

No universal hero, font pairing, section sequence, navigation style, maximum item count, or sticky action pattern is mandated here. About, catalog, services, trust signals, reviews, gallery, FAQ, Locations, contact, ordering, and booking are possible content families, not a required order.

Action vocabulary should remain consistent through a journey. If the action is “Book,” the confirmation should clearly report that booking outcome; if it is “Order,” the result should use the same language.

Individual Business website specifications, templates, and generation systems define concrete structures within these quality requirements.

---

## VII. Marketplace and Business Profiles

### The marketplace is not a directory

A directory shows rows. The Marketplace helps people discover and interact with real Businesses, products, and services. It is a consumer destination for local discovery, commerce, booking, contact, favourites, and return activity—including managing relevant orders and bookings—not a merchant dashboard and not merely a list of profiles.

The experience may support:

`Discover → Search → Browse → Compare → Understand trust → View Business → Explore products/services → Order / Book / Contact / Visit → Return and manage activity`

### Discovery and trust

Search, categories, location, filters, recommendations, comparison, and direct actions should emerge according to user intent rather than front-loading complexity. The experience should help people understand what a Business offers, where and when it is available, why its information is credible, and what action is possible now.

### The Trust Score's public face

The composite Trust Score never appears as a raw number to customers. It appears as earned, specific facts: "Usually responds in 10 minutes." "98% of orders delivered on time." These come from the same underlying score but land as credible observations rather than an abstract rating. Customers see its evidence, not its formula.

### Business profiles

Business profiles should reveal identity, offerings, Locations, useful trust evidence, and available actions. Products and services are first-class discovery objects, not details hidden behind a generic listing.

The exact Marketplace homepage, recommendation model, result card, filter layout, profile layout, and navigation are deferred to the Public Platform & Customer Page-by-Page Experience Specification.

---

## VIII. Copywriting Philosophy

Writing is a design material. Every word should help someone understand, decide, navigate, or act. Marketing may persuade, but it should do so through clarity and credible value rather than empty intensity.

**Write from the person’s purpose, not the system’s implementation.** “Get notified when an order arrives” is usually clearer than “real-time order notification subsystem.” “Track your booking” is clearer than exposing an internal workflow state.

**Specificity beats intensity.** "Selvi, Ambattur — 340 orders since March" is worth more than "Trusted by thousands of businesses across India." The former is checkable and specific. The latter is what every competitor also says.

**Active, present tense, short sentences.** "Save changes," not "Submit." "Order placed," not "Your order has been successfully submitted." "No products yet — add your first," not "No data available." Errors explain what happened and how to fix it: "Enter a phone number to continue," never "Oops! Something went wrong."

**Match the action's name in the confirmation.** Whatever the button says, the confirmation echoes it. Publish → Published. Book → Booked. This is how a person learns the interface vocabulary without stopping to interpret it.

Terms such as “powerful,” “AI-powered,” “smart,” or “seamless” are not automatically forbidden. They are weak when used as unsupported substitutes for meaning. Use them only when accurate, necessary, contextually useful, and supported by what the product actually does.

Voice adapts by surface:

- **Marketing:** concise, clear, credible, and compelling.
- **Marketplace/consumer:** familiar, easy to scan, and action-oriented.
- **Business workspace:** operational, direct, and precise.
- **Business websites:** may follow the Business’s own brand voice while preserving clarity.
- **Platform Administration:** direct, unambiguous, and explicit about consequences.

---

## IX. Brand Identity

The product should earn **quiet competence**: the feeling of being in the hands of a platform that has thought carefully about the person’s purpose and executes reliably.

A Business operator should associate the platform with understanding and control. A consumer should associate it with credible Businesses and confident action. A prospective owner should see a serious path to establishing and operating a Business. A visitor should understand the scale and value of the connected ecosystem.

These associations are earned through the product doing what it says, repeatedly and without drama. Visual language and copy reinforce that identity; they cannot manufacture it.

Product experience remains calm, clear, precise, and dependable. Brand and marketing expression may also communicate ambition, innovation, scale, vision, and memorability when appropriate. Expressiveness is strongest when concentrated in purposeful moments and supported by disciplined surrounding composition.

Exact identity assets and usage rules belong to future brand and design-system governance.

---

## X. Product Principles

These are not aspirations. They are gates. No design, copy, or interaction ships that violates them.

**Minimal, neat, and professional is the baseline.** Quality comes from hierarchy, typography, spacing, composition, consistency, responsiveness, performance, accessibility, and execution—not decorative excess.

**Different surfaces have different jobs.** Marketing, Marketplace, consumer account, Business workspace, Administration, and Business websites should not be forced into one emotional register, density, or interaction model.

**Clarity comes before complexity.** A person should understand where they are, what matters, and what can happen next.

**Progressive complexity is mandatory.** Reveal depth as the person, Business, and work require it; do not confuse simplicity with withholding necessary capability.

**Business experiences are adaptive.** Business type informs terminology and recommendations but does not rigidly dictate the experience. Modules shape what exists; entitlement, configuration, Location, permission, and activity shape what is available now.

**Consumers discover and interact.** The consumer experience is oriented around Businesses, products, services, commerce, booking, contact, trust, and return activity—not merchant operation.

**Businesses operate through context.** The workspace answers “What matters now?” using the Active Business, Location, role, permission template, modules, entitlement, and current activity.

**Business websites remain brand-flexible.** They share universal quality requirements, not one font pairing, hero, section sequence, template, or personality.

**The Marketplace is more than listings.** It enables discovery, understanding, trust, and interaction with real Businesses, products, and services.

**Motion is purposeful and surface-appropriate.** It may explain, orient, connect, express, or delight, but it must respect attention, accessibility, and performance.

**Storytelling is a tool, not a template.** The main website may use a flexible narrative. No fixed act structure is mandatory for every homepage or section.

**One signature experience can create memorability.** A strong hero or equivalent moment may carry expressive storytelling while the surrounding experience remains clear and restrained.

**Accessibility and performance are experience requirements.** A visually impressive idea that excludes people, blocks action, or degrades delivery is unfinished.

**Copy is interface.** Labels, errors, empty states, buttons, and marketing language should be concise, specific, consistent, and appropriate to their surface.

**Trust comes from evidence and execution.** Credible information, real content, truthful status, consistent behavior, and reliable operation matter more than claims of trust.

**Every feature and screen must justify its cognitive cost.** Information, controls, and effects should help a person understand or act—not merely prove the platform can display them.

**Implementation is not philosophy.** Current tokens, layouts, components, navigation patterns, and templates are governed implementation choices, not eternal product principles.

**Timelessness comes from disciplined judgment.** Use trends only when they serve the product and can be executed with integrity; novelty alone is not a design rationale.

---

## XI. Document Boundary and Future Authority

This Product Experience Bible is the canonical answer to:

> **What principles should govern how the platform feels and behaves?**

It does not fully answer:

> **What exactly does every page look like?**

Detailed authority belongs to:

- the Public Platform & Customer Page-by-Page Experience Specification;
- the Merchant Workspace Page-by-Page Experience Specification;
- the Admin Operations Experience Specification;
- the future Platform Design System; and
- individual Business website specifications, templates, and generation systems.

Examples in this Bible explain principles. Unless explicitly marked as a durable requirement, they are not universal page contracts.
