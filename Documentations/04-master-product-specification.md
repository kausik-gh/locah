# Complete Master Product Specification
## The Digital Operating System for Local Businesses

**Document Status:** Living — Frozen Foundation, Evolving Detail  
**Version:** 1.0  
**Last Updated:** July 2026  
**Authors:** Product Team  
**Based On:** Vision v3 · Product Experience Bible · Business Kernel Specification v1

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
> At 3,600 lines this is the largest document in the set and the most likely to be
> read selectively. Several of its most-quoted structures have been superseded.
>
> | Content here | Governing position |
> |---|---|
> | Six-portal surface map | Omits the **Main Platform Website**, a first-class platform-owned surface — Document 05 `GAP-001`; Document 09 §19 |
> | Accountant and Receptionist as **roles** | **Permission templates**, not roles. Invariant roles are Primary Owner, Manager, Member — `D10-CONFLICT-002` |
> | Trust Score as an installable module | `svc-statistics-trust`, a shared service — Document 08 §22; `D10-CONFLICT-006` |
> | `catalog-orders` as one module | Separate `offerings-catalog` and `orders` — `D10-CONFLICT-004` |
> | Free-form / drag-and-drop / page-builder website implications | **Structured sections**, supported layout variants, and branding/navigation controls. AI authors **content only** — Document 10 §11, Document 12 §§12.6–12.8; `D11-CONFLICT-007` |
> | Fixed Merchant Dashboard with a stable 21-module navigation tree | Business Workspace navigation is **adaptive** to type terminology, enabled modules, permission, and Location — `D11-CONFLICT-006` |
> | Owner sees all navigation permanently | Owner retains authority, but navigation is **progressive and relevant** — Document 06 `RPA-CONFLICT-002` |
> | Business type auto-provisions required/default modules | Type **recommends**; the Business explicitly selects — `D11-CONFLICT-005` |
> | Events-only cross-module wording (Event Bus glossary, Appendix C §2) | Synchronous public contracts + asynchronous events — `D10-CONFLICT-010` |
> | Marketplace discovery deferred beyond the first horizon | First Launch **includes** the search-first discovery loop — `D11-CONFLICT-001` |
> | Module uninstall may hard-delete data | Deactivation retains history — `D10-CONFLICT-005` |
> | Admin can impersonate a Business owner | Attributed Admin investigation/work mode only — `D11-CONFLICT-015` |
> | Merchant gateway and platform billing shown together | **Permanently separate** concerns — Document 08 §§17–18 |
> | Relevance labels ("MVP Essential" / "Post-MVP") | **Document 11** is the release-scope overlay; several Post-MVP families are promoted to First Launch — `D11-CONFLICT-008`, `D11-CONFLICT-009`, `D11-CONFLICT-016` |
>
> What **remains governing**: this document's answer to "if the platform were
> complete, what exactly exists?" — the system, workflow, object-state,
> notification, settings, and event inventories. Read it as the **complete-state
> inventory**, never as launch scope or current structure.

---

---

> **How to Read This Document**
>
> This is the complete blueprint of the platform — every system, module, page, workflow, state, role, permission, notification, and setting. It is organized from the broadest level (Platform) down to the most specific (individual interactions). Read Part 0 for orientation, then jump to any section as needed. Every page cross-references its module; every module cross-references its pages.
>
> **This document answers one question: if this platform were complete, what exactly exists?**
>
> It does not answer: what to build first (see Vision v3, Section 16 — Horizons), or how to build it (see Business Kernel Specification v1).

---

# TABLE OF CONTENTS

- [Part 0 — Platform Overview](#part-0--platform-overview)
- [Part 1 — Information Architecture & Navigation](#part-1--information-architecture--navigation)
- [Part 2 — User Roles & Permissions](#part-2--user-roles--permissions)
- [Part 3 — Platform Systems & Modules](#part-3--platform-systems--modules)
- [Part 4 — Every Page Defined](#part-4--every-page-defined)
- [Part 5 — Every Workflow](#part-5--every-workflow)
- [Part 6 — Every Object State](#part-6--every-object-state)
- [Part 7 — Notification System](#part-7--notification-system)
- [Part 8 — Settings Architecture](#part-8--settings-architecture)
- [Part 9 — Platform Events Catalog](#part-9--platform-events-catalog)
- [Part 10 — Business Type Configurations](#part-10--business-type-configurations)

---

# PART 0 — PLATFORM OVERVIEW

## 0.1 Mission

> **Build the digital operating system and infrastructure layer for local businesses — the layer every other tool a business uses eventually plugs into or gets replaced by.**

This is an infrastructure company in the same category-defining sense that Stripe is infrastructure for payments, Shopify is infrastructure for commerce, and Salesforce is infrastructure for customer relationships.

**One business identity. Many renderings.** The merchant dashboard, public website, marketplace profile, AI assistant context, developer API, and customer-facing app are all different views into one business's data — never six separate products that share a login.

---

## 0.2 Platform Architecture Map

```
╔══════════════════════════════════════════════════════════════════════════╗
║                              THE KERNEL                                  ║
║  Identity · Auth · Multitenancy · Module Registry · Event Bus            ║
║  Rendering Engine · AI Service Layer · Billing · Audit Log               ║
╠══════════════════════════════════════════════════════════════════════════╣
║                           MODULES (Installed per Business)               ║
║  Core         │ Website · Business Profile · CRM · Notifications         ║
║  Transaction  │ Orders · Booking · Inventory · Payments · Invoicing      ║
║  Growth       │ Marketing · Reviews · Loyalty · AI Employees · Analytics ║
║  Operations   │ Staff · Delivery · Appointments · Subscriptions          ║
║  Platform     │ Business Passport · Trust Score · B2B · Developer API    ║
╠══════════════════════════════════════════════════════════════════════════╣
║                        RENDER SURFACES                                   ║
║  Merchant Dashboard · Public Storefront · Marketplace Listing            ║
║  AI Context · Customer Portal · Developer API · Admin Panel · Invoices   ║
╠══════════════════════════════════════════════════════════════════════════╣
║                          ECOSYSTEMS                                      ║
║  Merchant · Customer · Developer · AI Employees · Marketplace · B2B      ║
╚══════════════════════════════════════════════════════════════════════════╝
```

---

## 0.3 Ecosystem Map

The platform consists of six interconnected ecosystems. Each has independent value; together, they create a compounding network.

### Merchant Ecosystem
The primary ecosystem. Business owners and their teams use the Merchant Dashboard to run their daily operations — orders, bookings, customers, staff, inventory, marketing, and AI employees. Every other ecosystem exists to serve or be served by merchants.

### Customer Ecosystem
Customers interact with businesses through merchant storefronts and the marketplace. Platform-level customer accounts (Horizon 2+) give customers a unified order history, saved addresses, loyalty points, and an AI shopping assistant across all businesses they've used.

### Marketplace Ecosystem
The discovery layer. Customers find businesses by location, category, rating, and availability. Businesses gain organic reach. The marketplace is powered by the Business Trust Score and is a primary growth channel for merchants who opt in.

### AI Employee Ecosystem
Thirteen AI roles that replace specific labor functions for merchants who cannot afford or don't need a full-time hire. AI employees are kernel-level services, not isolated chatbots — they read from the same business data and emit to the same event bus as every other module.

### Developer Ecosystem (Horizon 4)
External developers publish modules to the Module Marketplace using the same internal contract shape that platform modules use. Merchants install third-party modules the way they install a Shopify app.

### B2B Ecosystem (Horizon 3+)
Businesses discover verified suppliers, service providers, and business partners. Powered by the Business Graph — relationship data accumulated from years of transactions.

---

## 0.4 Design System Reference

All visual and interaction decisions in this specification are governed by the Product Experience Bible. Key constants repeated here for specification clarity:

| Token | Value | Use |
|-------|-------|-----|
| `signal-indigo` | `#4A5FE0` | Interactive elements, primary CTAs, links |
| `success` | `#1F9D6B` | Success states, confirmations |
| `danger` | `#D8483C` | Error states, destructive actions |
| `warning` | `#B8862E` | Warning states, low-stock alerts |
| `ink-950` | `#0B0C0E` | Primary text, dark surfaces |
| `paper` | `#FAFAF9` | Light mode background |
| Platform font | Geist | Dashboard, admin, onboarding |
| Storefront display | Fraunces | Hero, section headings on public pages |
| Storefront body | Inter | Body copy on public pages |
| Base unit | 4px | All spacing |
| Animation: micro | 120ms | Button press, focus ring |
| Animation: standard | 200ms | Dropdown, tab switch |
| Animation: panel | 320ms | Modal/drawer entrance |
| Animation: page | 480ms | Route transitions |

**Motion test:** If removing an animation and showing the end state loses no user understanding, the animation is cut.

**Color rule:** Signal Indigo appears only on interactive or important elements. Never decoratively.

**Copy rule:** Active, present tense, short sentences. No banned words: "All-in-one," "Powerful," "AI-powered," "Seamless," "Supercharge," "Unlock," "Smart," "Next-gen," "Manage everything."

---

## 0.5 Terminology Glossary

| Term | Definition |
|------|------------|
| **Business** | The root entity — a merchant's business on the platform. One business, many renderings. |
| **Merchant** | The person or team that owns and operates a Business. |
| **Owner** | The specific merchant member who has ultimate control of a Business. Exactly one per business. |
| **Module** | A self-contained unit of business capability (e.g., Orders, Booking, CRM). Installed per-business. |
| **Kernel** | The platform infrastructure all modules are built on. Never changes per-business-type. |
| **BusinessType** | A named bundle of default modules for a category (e.g., "home_food," "salon," "clinic"). Data-driven, not code. |
| **Capability** | A computed ability of a business (e.g., `can_receive_orders`). Derived from installed modules + config + status. |
| **Event Bus** | The system through which all modules communicate — by emitting and subscribing to events, never by calling each other directly. |
| **Rendering Engine** | The kernel layer that takes one Business aggregate and produces any output surface. |
| **BusinessAggregate** | The fully-assembled read model: Business + installed modules' public data + computed capabilities. |
| **Trust Score** | A 0–100 composite score per business. Powers marketplace ranking and merchant health coaching. |
| **Business Passport** | A portable, verifiable identity document for a business (GST, FSSAI, certifications). Horizon 3+. |
| **Business Graph** | The relationship network of businesses, customers, suppliers, and transactions. Horizon 3+. |
| **AI Employee** | An AI agent that replaces a specific labor function for a merchant. Kernel-level service, not a chatbot module. |
| **Progressive Complexity** | The principle that merchants only see features relevant to their current size and type of business. |
| **ULID** | The ID format used for all entities — sortable, globally unique, safe to expose in URLs. |
| **RLS** | Row Level Security — the database-level enforcement of tenant isolation and permissions. |
| **Dead Letter Queue** | Where failed events go for inspection — never silently dropped. |
| **Horizon** | A stage of platform evolution. H1 (0–9mo) · H2 (9–24mo) · H3 (2–4yr) · H4 (4yr+). |

---

# PART 1 — INFORMATION ARCHITECTURE & NAVIGATION

## 1.1 Portal Overview

The platform has six distinct portals, each serving a different primary user:

| Portal | Primary User | URL Pattern | Purpose |
|--------|-------------|-------------|---------|
| **Merchant Dashboard** | Business owners & staff | `app.platform.com` | Daily business operations |
| **Public Storefront** | Customers of a specific business | `{slug}.platform.com` or custom domain | Browse, order, book |
| **Marketplace** | All customers discovering businesses | `platform.com/discover` | Cross-business discovery |
| **Customer Portal** | Registered customers | `platform.com/account` | Order history, bookings, loyalty |
| **Admin Panel** | Platform operations team | `admin.platform.com` | Platform management |
| **Developer Portal** | Third-party developers | `developers.platform.com` | Module marketplace, API docs (H4) |

---

## 1.2 Merchant Dashboard — Complete Navigation Tree

The merchant dashboard uses a **left icon sidebar on desktop** and a **bottom tab bar on mobile** (5 items max without requiring scrolling). Navigation grows progressively as modules are installed.

### Primary Navigation (Always Visible)

```
Home (Dashboard)
  - Morning Overview
  - Action Queue
  - Revenue Snapshot
  - Business Health Score
  - AI Suggestions

Operations
  - Orders                    [requires: catalog-orders module]
  - Bookings                  [requires: booking-calendar module]
  - Appointments              [requires: appointments module]
  - Delivery                  [requires: delivery module]
  - Queue Management          [requires: appointments module]

Catalog
  - Products                  [requires: catalog-orders module]
  - Services                  [requires: booking-calendar or appointments module]
  - Inventory                 [requires: inventory module]
  - Subscriptions             [requires: subscriptions module]

Customers
  - Customer List             [requires: crm module]
  - Segments                  [requires: crm module]
  - Reviews                   [requires: reviews module]
  - Loyalty Program           [requires: loyalty module]

Marketing
  - Campaigns                 [requires: marketing module]
  - Coupons & Offers          [requires: marketing module]
  - WhatsApp Broadcasts       [requires: whatsapp-notifications module]
  - AI Marketing Manager      [requires: ai-marketing-manager module]

Analytics
  - Business Overview         [always visible]
  - Sales Reports             [requires: catalog-orders module]
  - Customer Insights         [requires: crm module]
  - Marketing Performance     [requires: marketing module]
  - AI Business Analyst       [requires: ai-business-analyst module]
```

### Secondary Navigation (Contextual)

```
My Business
  - Business Profile
  - Storefront / Website
  - Marketplace Listing
  - Business Passport         [requires: business-passport module, H3]
  - Trust Score Breakdown     [H2+]

Staff & Roles
  - Staff Members             [requires: staff module]
  - Roles & Permissions
  - Payroll                   [requires: payroll module, H3]
  - Schedule                  [requires: staff module]

AI Employees
  - AI Roster                 [requires: any ai-* module]
  - AI Activity Log
  - AI Settings

Settings
  - Business Settings
  - Payments & Billing
  - Notifications
  - Integrations
  - Developer / API           [requires: developer module, H4]
  - Module Manager

Support
  - Help Center
  - Submit Ticket
  - Chat with Support
```

### Navigation Scaling by Business Stage

**New Business (Onboarding, first 30 days):**
Visible: Home, Products/Services, Orders or Bookings, My Business, Settings
Hidden: Analytics, Marketing, Staff, AI Employees, Loyalty, Subscriptions

**Growing Business (Active, 1–3 modules installed):**
Visible: Home, Operations, Catalog, Customers, My Business, Settings, Support
Emerging: Analytics (basic), Marketing (first campaign)
Hidden: AI Employees, Payroll, Business Passport

**Established Business (5+ modules, H2):**
Visible: All primary navigation
Emerging: AI Employees, Loyalty, Advanced Analytics

**Mature Business (H3+):**
Visible: Everything — Business Passport, B2B Network, Developer API

---

## 1.3 Public Storefront — Navigation Structure

### Storefront Navigation (Default)
```
[Business Logo]    Home   About   Menu/Services   Gallery   Contact   [Book Now / Order Now]
```

### Storefront Pages (Merchant-Configurable)
```
/ (Home)
/about
/menu (or /services, /products — vocabulary matches business type)
/gallery
/contact
/reviews
/faq
/[custom-page-slug]         (merchant can add custom pages)
/order                      [requires: catalog-orders module]
/book                       [requires: booking-calendar module]
/cart                       [requires: catalog-orders module]
/checkout                   [requires: payments module]
/track/{orderId}            [requires: delivery module]
```

### Storefront Header Behavior
- Transparent over hero image
- Transitions to solid `paper` background with `shadow-sm` on scroll (12px threshold)
- Maximum 5 nav items (overflow becomes dropdown)
- No mega-menu
- Mobile: collapses to hamburger — slide-in drawer from right
- Sticky bottom bar on mobile: primary CTA (Order / Book / Contact) always accessible

---

## 1.4 Marketplace — Navigation Structure

```
platform.com/discover
  /discover                   (Home: featured, nearby, categories)
  /discover/{category}        (Category page: e.g., /discover/home-food)
  /discover/search            (Full-text + filter search results)
  /discover/map               (Map view of nearby businesses)
  /b/{slug}                   (Business profile page)
  /b/{slug}/order             (Direct ordering from marketplace)
  /b/{slug}/book              (Direct booking from marketplace)
```

**Marketplace Top Navigation:**
```
[Platform Logo]  Discover  [Location]  [Search Bar]  Sign In / My Account
Categories: Home Food  Salons  Clinics  Coaching  Restaurants  Retail  [More]
```

---

## 1.5 Customer Portal — Navigation Structure

```
platform.com/account
  /account                    (Dashboard: recent activity, upcoming bookings)
  /account/orders             (Order history across all businesses)
  /account/bookings           (Booking history and upcoming bookings)
  /account/favourites         (Saved/followed businesses)
  /account/loyalty            (Loyalty points and rewards)
  /account/reviews            (Reviews written by the customer)
  /account/addresses          (Saved delivery addresses)
  /account/payments           (Saved payment methods)
  /account/settings           (Profile, notifications, privacy)
```

---

## 1.6 Admin Panel — Navigation Structure

```
admin.platform.com
  Overview                    (Platform KPIs dashboard)
  Businesses
    All Businesses
    Pending Verification
    Under Review
    Suspended / Flagged
  Customers                   (Platform-level customer accounts)
  Marketplace
    Category Management
    Featured Businesses
    Review Moderation
    Search Analytics
  Financials
    Platform Revenue
    Subscription Billing
    Payout Reconciliation
  AI Monitoring               (AI employee output quality)
  Trust & Safety
    Trust Score Engine
    Fraud Detection
    Anomaly Alerts
  Support
    All Tickets
    Escalations
    Known Issues
  Platform Settings
    Module Registry
    Business Types
    Feature Flags
    System Health
  Audit Log                   (Every admin action, timestamped)
```

---

## 1.7 Developer Portal — Navigation Structure (Horizon 4)

```
developers.platform.com
  Documentation
    Getting Started
    Core Concepts
    Module SDK Reference
    Event Catalog
    REST API Reference
    Webhook Guide
  My Apps                     (Developer's published modules)
  Module Marketplace          (Browse / install modules)
  Sandbox                     (Test environment)
  Analytics                   (Install counts, revenue, usage)
  Support                     (Developer-specific support)
  Account                     (API keys, profile, billing)
```

---

## 1.8 Progressive Complexity — Design Rules

Progressive complexity is a **product principle**, not a UI feature. It is enforced through four mechanisms:

### 1. Module-gated Navigation
Navigation items appear only when the required module is installed and active. If a merchant navigates to an uninstalled module's URL, they see that module's discovery card (value proposition + install CTA), not an empty state or error.

### 2. Capability-gated Actions
Actions that require a missing capability show a contextual upgrade prompt. "Add a shipping zone" is only shown if the Delivery module is installed.

### 3. Dashboard Widget Priority
The dashboard shows only widgets from installed, active modules. Widget density scales with number of installed modules.

### 4. Onboarding Guided Paths
New businesses complete guided setup steps before the full navigation is visible. After completion, the full navigation is revealed.

---

## 1.9 Module Discovery Architecture

Merchants discover new capabilities through four surfaces:

### Surface 1: Module Manager (Settings → Module Manager)
Installed modules with status and configure/uninstall actions. Recommended modules (AI-driven). All available modules browsable by category.

### Surface 2: Contextual Discovery Cards
When a merchant navigates to a section requiring an uninstalled module, a discovery card appears with the module's value proposition and a "Try Free for 14 days" or "Add to Plan — ₹X/mo" CTA.

### Surface 3: AI Recommendations (Home Dashboard)
The AI Business Analyst surfaces module recommendations as suggestions in the dashboard's AI card. Dismissible. Frequency-capped at max 1 new module suggestion per week.

### Surface 4: Module Marketplace Page
Full App Store-style browsing. Featured modules, new modules, category filters, business-type-specific recommendations. Sort by: Installs, Rating, New, Price.

---

# PART 2 — USER ROLES & PERMISSIONS

## 2.1 Role Overview

**Business Roles** (govern actions within a specific business):
`owner` · `manager` · `staff` · `delivery_partner` · `accountant` · `receptionist`

**Platform Roles** (govern actions at the platform level):
`customer` · `platform_admin` · `platform_support` · `developer`

A user can hold both a business role (for one or more businesses) and a platform role.

---

## 2.2 Business Role: Owner

**Who They Are:** The founding member. Exactly one per business. Billing and accountability are tied to this role.

**Responsibilities:** Strategy and configuration, staff management, billing, platform trust decisions, admin escalation point of contact.

**Permissions:**
- Full access to all installed modules — read, write, manage, configure
- Billing: sole ability to upgrade/downgrade subscription, change payment method
- Staff: add/remove all roles including manager
- Module installation: install/uninstall any module
- Business settings: all settings including business type, domain, branding
- Danger zone: business closure, data export, ownership transfer

**Visible Navigation:** All navigation, no restrictions.

**Dashboard:** Full dashboard with all widgets. Business Health Score prominently featured. AI suggestions from all installed AI employees.

**Restricted Actions:** None.

---

## 2.3 Business Role: Manager

**Who They Are:** A trusted senior team member running day-to-day operations.

**Responsibilities:** Operations management, staff oversight, customer relationships, marketing, inventory.

**Permissions:**
- Default: read + write on all installed modules
- Explicitly denied: billing, subscription management, module installation, business closure, ownership transfer, full financial audit trail
- Staff management: can add/remove staff members and delivery partners; cannot modify manager permissions or add new managers

**Visible Navigation:** All navigation except billing settings, module install/uninstall actions, Danger Zone.

**Restricted Actions:** Cannot install/uninstall modules, change billing or subscription, transfer ownership, close business.

---

## 2.4 Business Role: Staff

**Who They Are:** Operational team members — cashiers, cooks, stylists, etc.

**Responsibilities:** Defined entirely by explicit permission grants from owner/manager.

**Permissions:**
- Default: no access to any module
- Granted individually by owner or manager per module: none / read / read+write
- Cannot be granted: billing, module installation, staff management, all business settings

**Visible Navigation:** Only navigation items for modules with granted access.

**Dashboard:** Simplified operational view showing only their active task queue.

**Allowed Actions:** Only what is explicitly granted. Financial data always restricted.

---

## 2.5 Business Role: Delivery Partner

**Who They Are:** Contracted or employed delivery agents.

**Permissions:**
- Read: assigned orders only (their own assignments)
- Write: order status updates on their assigned orders only
- No access: any other module, financial data, customer PII beyond name and delivery address

**Visible Interface:** Purpose-built Delivery Partner App:
- My Assigned Orders
- Order Pickup Confirmation
- Navigation (deep-link to Google Maps / OLA Maps)
- Delivery Confirmation
- Earnings Summary

---

## 2.6 Business Role: Accountant

**Who They Are:** Internal or external accountant needing financial visibility without operational control.

**Permissions:**
- Read: invoices, payments, financial reports, payout records
- Read: orders (amounts only — not customer contact details)
- No write access to any module

**Visible Navigation:** Analytics (Financial only), Invoices (read), Reports (financial only), Settings (view-only).

---

## 2.7 Business Role: Receptionist

**Who They Are:** Front-desk staff at clinics, salons, coaching centers.

**Responsibilities:** Queue management, check-in, walk-in bookings, desk-side payment collection.

**Permissions:**
- Read + Write: appointments, bookings, queue management
- Read: customer profile (name, phone, appointment history for this business)
- Write: payment collection (if payments module installed)
- No access: financial reports, inventory, marketing, staff management

---

## 2.8 Specialized Staff Role Templates

These are display labels applied to the Staff role with a specific permission bundle:

| Role Label | Granted Modules | Write Access |
|------------|-----------------|--------------|
| Doctor | Appointments, CRM | Appointment notes, patient status |
| Trainer | Bookings, CRM | Session notes, attendance |
| Teacher | Bookings, CRM | Class attendance, student progress |
| Chef / Cook | Orders | Order status updates |
| Stylist | Bookings, Appointments | Appointment status, service notes |

---

## 2.9 Platform Role: Customer

**Who They Are:** End consumers interacting with businesses through storefronts and marketplace.

**Permissions:**
- Read: their own orders, bookings, reviews
- Read: public business data (subject to business's visibility setting)
- Write: their own profile, addresses, payment methods, reviews
- No access: any business's internal data, other customers' data

---

## 2.10 Platform Role: Platform Admin

**Who They Are:** Internal operations team. Full read access across all businesses; write access only for moderation, verification, and support actions — every write action audit-logged.

**Permissions:**
- Read: all business data across all tenants (elevated RLS role)
- Write: business verification status, suspension/reinstatement, review removal (with reason), trust score override (with reason + approval chain)
- No unlogged writes — every write creates an immutable audit log entry

---

## 2.11 Platform Role: Platform Support

**Who They Are:** Frontline support agents.

**Permissions:**
- Read: business profile, order/booking summaries, module status, billing status — only for the business they're actively supporting, and only while a ticket is open
- Write: support ticket notes, ticket resolution
- No write: business data, suspension, verification, trust score
- Access is time-scoped to the ticket duration

---

## 2.12 Platform Role: Developer (Horizon 4)

**Who They Are:** Third-party developers who publish modules on the Module Marketplace.

**Permissions:**
- Read: aggregate/API data for businesses that have installed their module AND granted data access
- No read: businesses that haven't installed their module
- No write: any business data directly — all writes go through Event Bus or approved API actions

---

## 2.13 Permission Matrix Summary

| Action | Owner | Manager | Staff (granted) | Delivery | Accountant | Receptionist | Admin |
|--------|-------|---------|-----------------|----------|------------|--------------|-------|
| View Dashboard | Yes | Yes | Limited | No | No | Yes (limited) | Yes |
| Process Orders | Yes | Yes | Yes | No | No | No | Read only |
| Manage Products | Yes | Yes | If granted | No | No | No | Read only |
| Manage Bookings | Yes | Yes | If granted | No | No | Yes | Read only |
| View Customers | Yes | Yes | If granted | No PII | No PII | Limited | Yes |
| Manage Staff | Yes | Staff only | No | No | No | No | Yes |
| View Financials | Yes | Operational | No | Earnings only | Yes | No | Yes |
| Billing & Plans | Yes | No | No | No | No | No | Yes |
| Install Modules | Yes | No | No | No | No | No | Yes |
| Business Settings | Yes | Partial | No | No | No | No | Yes |
| Export Data | Yes | No | No | No | Financial | No | Yes |
| Verify Business | No | No | No | No | No | No | Yes |
| Suspend Business | No | No | No | No | No | No | Yes |

---

# PART 3 — PLATFORM SYSTEMS & MODULES

## 3.0 Module Catalog Overview

| # | Module ID | Category | Horizon | Dependencies |
|---|-----------|----------|---------|-------------|
| 01 | `business-profile` | Core | H1 | None (kernel) |
| 02 | `website` | Core | H1 | `business-profile` |
| 03 | `catalog-orders` | Transactional | H1 | `business-profile` |
| 04 | `crm` | Core | H1 | `business-profile` |
| 05 | `whatsapp-notifications` | Core | H1 | `business-profile` |
| 06 | `inventory` | Transactional | H1 | `catalog-orders` |
| 07 | `booking-calendar` | Transactional | H1 | `business-profile` |
| 08 | `appointments` | Transactional | H1 | `business-profile` |
| 09 | `payments` | Transactional | H1 | `catalog-orders` or `booking-calendar` |
| 10 | `invoicing` | Transactional | H1/H2 | `payments` |
| 11 | `delivery` | Transactional | H2 | `catalog-orders` |
| 12 | `reviews` | Growth | H1/H2 | `catalog-orders` or `booking-calendar` |
| 13 | `marketing` | Growth | H2 | `crm` |
| 14 | `loyalty` | Growth | H2 | `crm`, `payments` |
| 15 | `subscriptions` | Transactional | H2 | `catalog-orders`, `payments` |
| 16 | `staff` | Operations | H1/H2 | `business-profile` |
| 17 | `payroll` | Operations | H3 | `staff`, `payments` |
| 18 | `analytics-basic` | Analytics | H1 | `business-profile` |
| 19 | `analytics-advanced` | Analytics | H2 | `analytics-basic` |
| 20 | `ai-whatsapp-manager` | AI | H2 | `whatsapp-notifications`, `catalog-orders` |
| 21 | `ai-content-creator` | AI | H2 | `business-profile`, `website` |
| 22 | `ai-marketing-manager` | AI | H3 | `marketing`, `ai-content-creator` |
| 23 | `ai-business-analyst` | AI | H3 | `analytics-advanced` |
| 24 | `ai-inventory-manager` | AI | H3 | `inventory` |
| 25 | `ai-sales-executive` | AI | H3 | `crm`, `catalog-orders` |
| 26 | `ai-appointment-manager` | AI | H3 | `appointments` or `booking-calendar` |
| 27 | `ai-follow-up-manager` | AI | H3 | `crm`, `reviews` |
| 28 | `ai-customer-support` | AI | H3 | `crm`, `catalog-orders` |
| 29 | `ai-finance-assistant` | AI | H3 | `invoicing`, `payments` |
| 30 | `ai-delivery-coordinator` | AI | H3 | `delivery` |
| 31 | `ai-receptionist` | AI | H4 | `appointments`, `whatsapp-notifications` |
| 32 | `ai-seo-manager` | AI | H3 | `website`, `ai-content-creator` |
| 33 | `trust-score` | Platform | H2/H3 | `business-profile`, `reviews` |
| 34 | `business-passport` | Platform | H3 | `business-profile`, `trust-score` |
| 35 | `business-community` | Platform | H3 | `trust-score` |
| 36 | `b2b-network` | Platform | H3 | `business-passport`, `trust-score` |
| 37 | `developer-platform` | Platform | H4 | Multiple |
| 38 | `module-marketplace` | Platform | H4 | `developer-platform` |

---

## 3.1 Module: Business Profile (`business-profile`)

**Purpose:** The foundational module. Defines the business's public identity, operational configuration, and metadata that every other module reads from.

**Features:**
- Business identity management (name, category, description, contact)
- Logo and cover image upload and management
- Location management (one or more locations with addresses, geo-coordinates, service radius)
- Business hours (per-day, per-location, holiday overrides)
- Category and sub-category selection
- Brand color and font preferences
- Contact information (phone, email, WhatsApp, social links)
- Legal information (GST, FSSAI — optional at start)
- Business verification request
- Custom metadata per business type

**Pages (Merchant Dashboard):**
- Profile Overview
- Edit Business Info
- Manage Locations
- Business Hours Editor
- Media Library
- Verification Status & Documents
- Brand Settings

**Dependencies:** None — root module.

**Events Emitted:** `business.profile.updated`, `business.location.added`, `business.hours.updated`, `business.verification.requested`, `business.media.uploaded`

**Events Subscribed:** `business.verified` → updates verification badge

**Permissions:**
- Owner, Manager: full read/write
- Staff (granted): read only
- Admin: read + verification write

**Object States (Profile Completeness):** `incomplete` → `basic` → `complete` → `verified`

**Future Extensions:** Multi-language descriptions, video introduction, Google Business Profile sync, AI-suggested sub-categories.

---

## 3.2 Module: Website (`website`)

**Purpose:** Generates and manages the merchant's public storefront website. Every business gets a `{slug}.platform.com` subdomain on signup. Custom domains can be connected. Auto-generated from business profile data; customizable through a visual editor — no code required.

**Features:**
- Auto-generated website from business profile on signup
- Visual page editor (section-by-section, drag-and-drop ordering)
- Page management (add/edit/delete custom pages)
- Navigation management (up to 5 items)
- Section library (Hero, About, Catalog, Services, Testimonials, Gallery, FAQ, Contact, Custom)
- Theme system (3–5 platform-designed themes)
- Color and font overrides within theme constraints
- SEO settings per page (title, meta description, OG image)
- Custom domain connection (with DNS guidance)
- SSL automatic provisioning
- Analytics integration
- WhatsApp floating button
- Announcement bar (dismissible, time-limited)
- Cookie consent banner

**Pages (Merchant-Facing — Dashboard):**
- Website Overview (preview + performance summary)
- Page Editor (per-page visual editing)
- Page List (all pages, publish/unpublish control)
- Section Library (browse available sections)
- Theme Picker
- Domain Settings
- SEO Dashboard
- Website Analytics

**Pages (Customer-Facing — Storefront):**
- Home (/), About (/about), Menu or Services (/menu, /services), Gallery (/gallery), Contact (/contact), FAQ (/faq), Order (/order), Book (/book), Cart (/cart), Checkout (/checkout), Order Tracking (/track/:orderId), Custom pages (/{slug})

**Dependencies:** `business-profile`

**Events Emitted:** `website.published`, `website.page.created`, `website.page.updated`, `website.domain.connected`, `website.theme.changed`

**Events Subscribed:** `business.profile.updated` → auto-updates contact section; `catalog.product.published` → updates product section; `review.published` → updates reviews section; `business.hours.updated` → updates hours display

**Permissions:**
- Owner, Manager: full read/write
- Staff: no access
- Public (unauthenticated): read-only access to published pages

**Page States:** `draft` → `published` → `archived`

**Rendering:** Uses PublicSiteRenderer — server-rendered (SSR/ISR) for SEO and performance. Pages revalidated on content change events.

**Future Extensions:** Multi-language support, A/B testing for sections, advanced SEO tools, Blog module, Landing page builder, PWA capability.

---

## 3.3 Module: Catalog & Orders (`catalog-orders`)

**Purpose:** Manages the product/service catalog and the complete order lifecycle. The primary transactional module that converts customer intent into merchant revenue.

**Features — Catalog Management:**
- Product creation with name, description, price, category, images, variants
- Variant system (up to 3 variant axes per product: size, color, spice level, etc.)
- Modifier groups (add-ons and extras with prices)
- Category/collection management
- Product visibility: published, hidden, draft, out-of-stock
- Batch price update, product duplication, bulk import/export (CSV)
- Multiple images per product, product tags
- Minimum order quantity, product-level tax configuration
- Dietary tags (Veg/Non-veg, Jain, Gluten-free — BusinessType-specific)
- Pre-order support (available from/until dates)

**Features — Order Management:**
- Incoming order notification (real-time via event bus)
- Accept/Reject order (with reason for rejection)
- Preparation time setting per order
- Order status updates (Accepted → Preparing → Ready → Out for Delivery → Delivered)
- Order items view with modifier details, special instructions
- Order-level discount application, internal notes
- Print receipt / kitchen ticket (PDF)
- Batch order view, order history with search and filter
- Refund initiation, order cancellation (with reason)
- Repeat order from history, order export (CSV)
- WhatsApp confirmation auto-send

**Features — Cart & Checkout (Customer-Facing):**
- Add to cart from product page or catalog
- Cart review page, delivery vs. pickup selection
- Coupon/offer code application
- Order scheduling (ASAP or specific time slot)
- Special instructions field, address selection (saved or new)
- Payment method selection
- Order confirmation page with tracking link

**Pages (Merchant Dashboard):** Products List, Product Detail/Edit, Add New Product, Categories Management, Orders Dashboard (primary operational view), Order Detail, Order History, Refunds & Cancellations, Catalog Analytics.

**Pages (Customer-Facing):** Menu/Products listing, Product detail, Cart, Checkout, Order Confirmation, Order Tracking.

**Dependencies:** `business-profile`

**Events Emitted:** `order.created`, `order.accepted`, `order.rejected`, `order.preparing`, `order.ready`, `order.cancelled`, `order.completed`, `order.refunded`, `catalog.product.created`, `catalog.product.updated`, `catalog.product.published`, `catalog.product.out_of_stock`

**Events Subscribed:** `inventory.stock.low` → flags low stock; `inventory.stock.zero` → auto-marks out of stock; `payment.completed` → confirms order; `delivery.assigned` → updates order with partner details; `coupon.applied` → applies discount

**Future Extensions:** Table ordering for dine-in restaurants (QR code per table), Kitchen display system, Combo/bundle products, Digital products, AI-suggested catalog improvements.

---

## 3.4 Module: CRM (`crm`)

**Purpose:** Maintains a unified record of every customer who has interacted with the business. Powers personalization, follow-up, and segmentation.

**Features:**
- Customer profile (name, phone, email, tags, notes, preferences)
- Interaction timeline (all orders, bookings, reviews, messages — chronological)
- Customer tags (manual and auto-generated from segments)
- Segments (rule-based: "Customers who haven't ordered in 30 days")
- Customer search and filter, manual note-taking
- Birthday/anniversary tracking, customer value metrics
- Import/export customers (CSV)
- Customer merge (same phone, different email)
- Customer opt-out management, blocked customers
- Customer acquisition source tracking

**Pages (Merchant Dashboard):** Customer List, Customer Detail/Profile, Segments List, Create/Edit Segment, Import Customers, CRM Analytics.

**Dependencies:** `business-profile`

**Events Emitted:** `customer.created`, `customer.updated`, `customer.tagged`, `customer.segment.entered`, `customer.segment.exited`, `customer.blocked`

**Events Subscribed:** `order.created` → creates/updates customer record; `booking.confirmed` → updates booking history; `review.submitted` → links review to customer; `payment.completed` → updates customer lifetime value

**Future Extensions:** AI-powered customer health scores (churn risk), smart segments, customer journey visualization, external CRM integrations.

---

## 3.5 Module: Booking & Calendar (`booking-calendar`)

**Purpose:** Manages time-slot-based advance bookings for service businesses. Distinct from Appointments (which handles walk-in/queue flows).

**Features:**
- Service definition (name, duration, price, capacity per slot)
- Availability management (per-day schedule, blocked dates, custom slots)
- Staff-level availability (services bookable with specific staff members)
- Online booking page (customer-facing form)
- Booking requests (customer requests → merchant accepts/confirms) or Instant booking (auto-confirm)
- Buffer time between bookings, advance booking window, minimum notice period
- Group bookings (multiple people per slot)
- Deposit/full payment at booking (if payments installed)
- Booking reminders (automated WhatsApp/SMS)
- Reschedule and cancellation (by merchant and customer, with configurable policy)
- No-show tracking, customer booking history, booking export

**Pages (Merchant Dashboard):** Bookings Calendar (primary operational page), Bookings List, Booking Detail, Services Management, Availability Settings, Booking Policies, Booking Analytics.

**Pages (Customer-Facing):** Booking Landing Page, Date/Time Selection, Customer Details Entry, Payment (if deposit required), Booking Confirmation, Booking Management (reschedule/cancel via link).

**Dependencies:** `business-profile`

**Events Emitted:** `booking.created`, `booking.confirmed`, `booking.cancelled`, `booking.rescheduled`, `booking.completed`, `booking.no_show`, `booking.reminder.sent`

**Events Subscribed:** `payment.completed` → confirms booking if deposit required; `staff.schedule.updated` → recalculates availability

**Future Extensions:** Group class management, subscription-based session packages, Google Calendar/Apple Calendar integration for staff, AI-optimized scheduling, waitlist management.

---

## 3.6 Module: Appointments & Queue (`appointments`)

**Purpose:** Manages walk-in and same-day appointment flows — primarily for clinics, salons, and queue-based environments. Handles who's next, who's being served, who's done.

**Features:**
- Queue management (add walk-in, position tracking, wait time estimation)
- Token system (numbered tokens issued)
- Digital check-in (QR code at location)
- Pre-registration (customer joins queue via WhatsApp link before arriving)
- Queue display board (large-screen view for waiting area)
- Appointment slots (fixed slots with capacity)
- Multi-doctor/multi-chair routing
- Priority queue (urgent/priority cases)
- Average service time tracking (for accurate wait predictions)
- No-show management, appointment notes
- "Your turn is coming" notification (triggers notifications module)
- Daily appointment summary report

**Pages (Merchant Dashboard):** Queue Dashboard (real-time, primary operational page), Appointments List, Appointment Detail, Slot Configuration, Queue Display (fullscreen mode for waiting area TV), Appointment Analytics.

**Pages (Customer-Facing):** Join Queue Page (via WhatsApp link or QR code), Queue Status Page (live position and wait time).

**Dependencies:** `business-profile`

**Events Emitted:** `appointment.queued`, `appointment.called`, `appointment.checked_in`, `appointment.completed`, `appointment.cancelled`, `appointment.no_show`

---

## 3.7 Module: Inventory (`inventory`)

**Purpose:** Tracks stock levels for physical products. Prevents overselling, enables reorder alerts, connects with AI Inventory Manager for predictive restocking.

**Features:**
- Stock level tracking per product and per variant
- Initial stock entry, stock adjustment (manual +/- with reason)
- Low stock threshold per product (configurable)
- Out-of-stock automation (auto-hide product when stock reaches zero — configurable)
- Stock history (every adjustment logged with timestamp and reason)
- Inventory value report (total stock value at cost price)
- Cost price per product (for margin calculation)
- Supplier tracking, batch/expiry tracking (for food businesses — optional)
- Stock audit view, CSV import for bulk stock entry
- Multiple location inventory

**Pages (Merchant Dashboard):** Inventory Overview, Product Stock Detail, Stock Adjustments Log, Low Stock Alerts, Inventory Value Report, Supplier List.

**Dependencies:** `catalog-orders`

**Events Emitted:** `inventory.stock.updated`, `inventory.stock.low`, `inventory.stock.zero`, `inventory.stock.replenished`

**Events Subscribed:** `order.completed` → deducts stock; `order.cancelled` → restores stock (configurable)

**Future Extensions:** Barcode scanning, purchase order management, supplier integration via B2B module, AI Inventory Manager integration.

---

## 3.8 Module: Payments (`payments`)

**Purpose:** Processes monetary transactions. Connects with payment gateways (Razorpay primary). Manages the complete payment lifecycle from initiation to settlement.

**Features:**
- Payment gateway connection (OAuth-based Razorpay integration)
- Multiple payment methods: UPI, credit/debit cards, net banking, wallets, cash
- Payment collection at checkout (online orders)
- Payment collection at booking (deposit or full amount)
- Point-of-sale payment (in-person via payment link or QR)
- Payment link generation (shareable link for any amount)
- Manual payment marking (cash received)
- Refund processing (full and partial) with reason tracking
- Payment history, settlement tracking, payout schedule configuration
- Payment failure handling and retry
- Split payment (partial now, rest on delivery)
- Transaction-level tax calculation
- Payment receipt generation and delivery (email/WhatsApp)

**Pages (Merchant Dashboard):** Payments Overview, Transaction List, Transaction Detail, Refunds List, Payouts & Settlement, Payment Links, Payment Settings.

**Dependencies:** `catalog-orders` or `booking-calendar` (at least one transactional module)

**Events Emitted:** `payment.initiated`, `payment.completed`, `payment.failed`, `payment.refunded`, `payment.settlement.received`, `payment.link.created`, `payment.link.paid`

**Events Subscribed:** `order.accepted` → initiates payment request; `booking.confirmed` → processes deposit; `invoice.sent` → tracks payment against invoice

**PCI Compliance:** Payment card data is never stored on platform servers. All sensitive card data is handled by the gateway. Platform stores only tokens and transaction references.

**Future Extensions:** Multi-currency, EMI/installment support, international gateways, escrow/milestone payments, subscription billing automation.

---

## 3.9 Module: Invoicing (`invoicing`)

**Purpose:** Generates, sends, and tracks professional GST-compliant invoices for both B2C and B2B transactions.

**Features:**
- Invoice generation from order (auto-fill from completed order)
- Invoice generation manual (custom line items)
- Invoice numbering (sequential, configurable prefix)
- Invoice templates (3–5 designs, brand-colored)
- GST computation (CGST/SGST intra-state, IGST inter-state)
- Multiple tax rates per line item, business and customer GSTIN fields
- Place of supply tracking, PDF generation and download
- Email and WhatsApp delivery with PDF
- Invoice status tracking, payment recording against invoice
- Partial payment tracking, credit note generation
- Invoice archive with search, bulk invoice export
- Recurring invoice templates

**Pages (Merchant Dashboard):** Invoices List, Invoice Detail, Create Invoice, Invoice Templates, Invoice Settings, GST Report.

**Dependencies:** `payments`

**Events Emitted:** `invoice.created`, `invoice.sent`, `invoice.paid`, `invoice.overdue`, `invoice.cancelled`, `credit_note.created`

**Object States:** `draft` → `sent` → `paid` | `overdue` | `cancelled`

---

## 3.10 Module: Delivery (`delivery`)

**Purpose:** Manages last-mile delivery workflow — assigning delivery partners, tracking real-time GPS, keeping customers informed. Software only; does not manage its own fleet.

**Features:**
- Delivery zone configuration (radius or polygon)
- Delivery fee tiers (by distance, by order value, or flat rate)
- Free delivery threshold
- Delivery partner management (add/remove agents by phone)
- Manual and auto-assignment (round-robin or nearest-available)
- Real-time order status updates
- GPS tracking link (sent to customer — live map view)
- Delivery proof (photo confirmation on delivery — optional)
- Delivery failure handling, delivery time estimate display at checkout
- Delivery history and performance metrics
- Delivery partner earnings summary

**Pages (Merchant Dashboard):** Delivery Dashboard (live map view of active deliveries), Active Orders, Delivery Partners List, Delivery Zones Configuration, Delivery Fee Settings, Delivery Analytics.

**Pages (Customer-Facing):** Order Tracking Page (live GPS map + status timeline).

**Pages (Delivery Partner Interface — purpose-built):** My Assigned Orders, Order Pickup Confirmation, Navigation (deep-link to Google Maps), Delivery Confirmation.

**Dependencies:** `catalog-orders`

**Events Emitted:** `delivery.assigned`, `delivery.picked_up`, `delivery.out_for_delivery`, `delivery.delivered`, `delivery.failed`, `delivery.returned`

**Events Subscribed:** `order.ready` → triggers delivery assignment notification; `order.cancelled` → cancels active delivery if assigned

---

## 3.11 Module: Reviews & Ratings (`reviews`)

**Purpose:** Captures authentic customer reviews post-transaction. Powers the Business Trust Score. Surfaces social proof on the storefront and marketplace.

**Features:**
- Post-transaction review request (auto-triggered after order delivered or appointment completed)
- Star rating (1–5), written review (optional), photo review (up to 3 photos)
- Review response by merchant (displayed publicly)
- Review moderation (merchant can flag inappropriate reviews)
- Review display on storefront and marketplace profile
- Review metrics: average rating, distribution, total count
- Review filtering, export, verified purchase badge
- Review reminder sequence (request → 2-day reminder → no further)
- Review editing window (customer can edit within 7 days)

**Pages (Merchant Dashboard):** Reviews List, Review Detail (with response composer), Review Analytics.

**Pages (Customer-Facing):** Review submission form, Reviews section on storefront, Reviews section on marketplace profile.

**Dependencies:** `catalog-orders` or `booking-calendar`

**Events Emitted:** `review.requested`, `review.submitted`, `review.published`, `review.responded`, `review.flagged`

**Events Subscribed:** `order.delivered` → triggers review request after 2-hour delay; `booking.completed` → triggers review request after 1-hour delay

**Object States:** `pending` → `submitted` → `published` | `flagged` → `removed` | `restored`

---

## 3.12 Module: Marketing (`marketing`)

**Purpose:** Enables merchants to run campaigns — promotional messages, seasonal offers, targeted outreach. Channels: WhatsApp broadcast, email (H2), push notification (H2).

**Features:**
- Campaign creation wizard (channel → audience → content → schedule → send)
- Audience targeting (all customers, specific CRM segments, custom filter)
- WhatsApp broadcast campaigns, email campaigns (H2), push notification campaigns (H2)
- Campaign scheduling (send now or schedule)
- Campaign templates (festival offers, new product launch, loyalty rewards)
- AI-assisted campaign creation (AI Marketing Manager — H3)
- Campaign performance tracking (sent, delivered, opened, clicked, converted)
- Coupon and offer management (discount codes, percentage or fixed, expiry, usage limit)
- Offer linking to campaigns
- A/B testing for campaign content (H3)
- Campaign history and archive, compliance management (opt-out exclusion, DND checks)

**Pages (Merchant Dashboard):** Campaigns Dashboard, Create Campaign (wizard), Campaign Detail, Coupons & Offers List, Create/Edit Coupon, Coupon Performance, Marketing Analytics, Marketing Templates Library.

**Dependencies:** `crm` (for audience segments), `whatsapp-notifications`

**Events Emitted:** `campaign.created`, `campaign.launched`, `campaign.completed`, `campaign.message.sent`, `coupon.created`, `coupon.applied`, `coupon.exhausted`

**Events Subscribed:** `customer.segment.entered` → may trigger automated campaign; `inventory.stock.low` → triggers AI suggestion for clearance campaign

**Object States (Campaign):** `draft` → `scheduled` → `sending` → `completed` | `paused` | `cancelled`

**Object States (Coupon):** `draft` → `active` → `paused` → `expired` | `exhausted` | `archived`

---

## 3.13 Module: Loyalty Program (`loyalty`)

**Purpose:** Retains customers by rewarding repeat business. Points-based system with rewards redemption.

**Features:**
- Points earning rules (points per ₹ spent, configurable)
- Points on specific products, first order, birthdays, referrals
- Points expiry (configurable — e.g., expire after 6 months of inactivity)
- Tier system (Bronze/Silver/Gold based on total points — optional)
- Rewards catalog (discounts, free items, services)
- Redemption at checkout
- Loyalty card (digital — customer sees balance and tier)
- Points history (customer-facing and merchant-facing)
- Loyalty program settings (name, logo, colors — separately brandable)
- Loyalty analytics (points issued, redeemed, outstanding liability, top customers)
- Merchant-initiated points, bulk points import

**Pages (Merchant Dashboard):** Loyalty Overview, Loyalty Members List, Points Activity Log, Rewards Catalog Management, Loyalty Settings, Loyalty Analytics.

**Pages (Customer-Facing):** Loyalty Card (in Customer Portal and storefront), Points History, Rewards Catalog.

**Dependencies:** `crm`, `payments`

**Events Emitted:** `loyalty.points.earned`, `loyalty.points.redeemed`, `loyalty.points.expired`, `loyalty.tier.upgraded`, `loyalty.tier.downgraded`

**Events Subscribed:** `order.completed` → triggers points earning; `payment.completed` → confirms points award; `customer.birthday` → triggers birthday bonus points

---

## 3.14 Module: Subscriptions (`subscriptions`)

**Purpose:** Manages recurring subscription offerings — weekly meal plans, monthly packages, class memberships. Distinct from the merchant's own platform subscription.

**Features:**
- Subscription plan creation (name, price, frequency, included items/services)
- Subscription enrollment (customer subscribes via storefront)
- Billing automation (recurring charge via payments module)
- Customer subscription management (pause, cancel, change plan)
- Merchant subscription management (cancel, adjust, apply discount)
- Delivery schedule (for physical subscriptions)
- Service schedule (for service subscriptions)
- Usage tracking (sessions used vs. included)
- Renewal notifications, failed payment handling (retry + grace period + cancellation)
- Subscription analytics (MRR, churn rate, active subscribers)
- Pause and resume, plan migration

**Pages (Merchant Dashboard):** Subscriptions Overview (MRR, active subscribers, churn), Subscribers List, Subscriber Detail, Subscription Plans Management, Failed Payments Queue, Subscription Analytics.

**Pages (Customer-Facing):** Subscribe (plan selection + checkout), My Subscription (status, billing date, manage).

**Dependencies:** `catalog-orders`, `payments`

**Events Emitted:** `subscription.created`, `subscription.renewed`, `subscription.paused`, `subscription.resumed`, `subscription.cancelled`, `subscription.payment.failed`, `subscription.payment.succeeded`

---

## 3.15 Module: Staff Management (`staff`)

**Purpose:** Manages team members — profiles, roles, schedules, and performance. Integrates with Booking and Appointments for availability-based scheduling.

**Features:**
- Staff member profiles (name, role, photo, contact, specializations)
- Staff invitation via phone or email (OTP-based)
- Role assignment and permission grants
- Staff schedule management (working hours per day, off days)
- Service-to-staff assignment (for booking module)
- Staff performance metrics (orders processed, bookings completed, customer ratings)
- Staff attendance tracking (optional — clock-in/out)
- Staff notes (internal, owner/manager only)
- Salary/pay rate tracking, staff deactivation

**Pages (Merchant Dashboard):** Staff List, Staff Detail/Profile, Invite Staff, Staff Schedule, Staff Performance Report, Role & Permission Templates.

**Dependencies:** `business-profile`

**Events Emitted:** `staff.invited`, `staff.joined`, `staff.removed`, `staff.schedule.updated`, `staff.role.changed`

**Events Subscribed:** `booking.confirmed` → assigns to staff member's calendar; `appointment.queued` → may route to specific staff member

---

## 3.16 Module: Payroll (`payroll`) — Horizon 3

**Purpose:** Calculates and tracks staff compensation — salary, per-order commissions, attendance-based pay.

**Features:** Pay structure configuration, pay period configuration, attendance-based deductions, advance payment tracking, payroll report generation, payment marking, salary history, tax deduction tracking (TDS — simplified).

**Dependencies:** `staff`, `payments`

**Events Emitted:** `payroll.run.completed`, `payroll.payment.recorded`

---

## 3.17 Module: Analytics — Basic (`analytics-basic`)

**Purpose:** Foundational business intelligence for every merchant. Always included. Feeds the Business Overview dashboard widget.

**Features:**
- Revenue dashboard (today, this week, this month, this year with trend vs. prior period)
- Order count and average order value
- Top-selling products (top 5 by revenue and by volume)
- Busiest times heatmap (day of week × hour of day)
- Customer acquisition summary (new vs. returning)
- Website traffic summary (if website module)
- Geographic breakdown of customers
- Downloadable reports (CSV, date range)

**Pages (Merchant Dashboard):** Business Overview, Revenue Report, Product Performance Report, Customer Summary.

**Dependencies:** `business-profile`

**Events Subscribed:** All transaction completion events → aggregate into daily stats rollup

---

## 3.18 Module: Analytics — Advanced (`analytics-advanced`) — Horizon 2

**Purpose:** Deeper analytics for growing businesses. Cohort analysis, campaign attribution, customer lifetime value, predictive insights.

**Features (beyond analytics-basic):**
- Customer cohort analysis (retention curves)
- Customer LTV calculation and trends
- Campaign attribution (which campaign drove which orders)
- Funnel analysis (visitors → cart → checkout → order)
- Inventory turn rate analysis
- Staff performance analytics
- Custom date range comparisons
- Competitor benchmarking (anonymized category-level — H3)
- Scheduled email reports (weekly/monthly digest)
- Custom dashboard (owner configures which widgets to see)

**Dependencies:** `analytics-basic`, `crm`, `marketing` (for campaign attribution)

---

## 3.19 AI Module: WhatsApp Manager (`ai-whatsapp-manager`) — Horizon 2

**Purpose:** Replaces a human front-desk person managing WhatsApp inquiries. Handles order-taking, booking requests, FAQs, and lead capture automatically in natural language.

**Reads From:** Business profile (name, hours, location), product catalog (prices, availability), booking calendar (slots), FAQ data, CRM (returning customer recognition).

**Writes To/Triggers:** Orders module (creates orders), Booking module (creates bookings), CRM (logs leads), WhatsApp-notifications (sends responses).

**Features:**
- Natural language understanding in English, Hindi, Tamil, and other Indian languages
- Product inquiry response, order placement via WhatsApp conversation
- Booking request via WhatsApp, FAQ response (configurable Q&A pairs)
- Escalation handling (confidence threshold → "Let me check and get back to you" + merchant alert)
- Conversation handoff to human (owner takes over any conversation)
- Working hours enforcement (after-hours auto-reply)
- AI response quality review (merchant rates/corrects responses)
- Conversation history linked to CRM, test mode before going live

**Pages (Merchant Dashboard):** AI WhatsApp Manager Overview, Live Conversations, Escalations Queue, FAQ Configuration, AI Settings, AI Activity Log.

**Dependencies:** `whatsapp-notifications`, `catalog-orders`

---

## 3.20 AI Module: Content Creator (`ai-content-creator`) — Horizon 2

**Purpose:** Replaces need for a content/marketing hire. Generates product descriptions, social media captions, website copy, and promotional material in the merchant's brand voice.

**Reads From:** Business profile (name, category, tone), product catalog (products, prices, existing descriptions), reviews (real customer language), marketing calendar.

**Writes To/Triggers:** Website module (page copy suggestions), Marketing module (campaign content drafts).

**Features:**
- Product description generator, caption generator for social media
- WhatsApp broadcast message drafts, promotional poster copy
- Festival/occasion message templates (Diwali, Onam, Eid, New Year, etc.)
- Website section copy suggestions (About, FAQ, tagline)
- Brand voice configuration (merchant describes tone: warm/professional/traditional)
- Content calendar suggestions
- Multi-language output (Tamil/Hindi/English or mixed)
- Review and edit interface (AI draft + merchant edits before publishing)

**Pages (Merchant Dashboard):** Content Creator Home, Content Draft (edit/approve/publish), Content Calendar, Brand Voice Settings, Content History.

**Dependencies:** `business-profile`, `website`

---

## 3.21 AI Modules: Remaining Roster — Horizon 3

Each AI module follows the same architectural pattern: reads from kernel, writes via events, never calls other modules directly.

| AI Module | Replaces | Key Capability |
|-----------|----------|----------------|
| `ai-marketing-manager` | Marketing hire | Proactively surfaces opportunities ("Stock is high on mango chutney — good week for a clearance offer") |
| `ai-business-analyst` | In-house analyst | "Your Tuesday sales dropped 30% vs. last month — here's a breakdown" |
| `ai-inventory-manager` | Stock manager | Predicts stockouts 3–5 days in advance based on consumption rate |
| `ai-sales-executive` | Junior salesperson | "Priya bought pickle last month — suggest the sambar powder combo this week" |
| `ai-appointment-manager` | Scheduling staff | Optimizes schedule to reduce gaps between bookings |
| `ai-follow-up-manager` | CRM/retention staff | "Meena hasn't ordered in 45 days — send a personalized win-back message" |
| `ai-customer-support` | Support staff | Handles "where is my order" and "I want a refund" autonomously |
| `ai-finance-assistant` | Bookkeeper | "Your GST filing is due in 3 days — here's your GSTR-1 summary" |
| `ai-delivery-coordinator` | Dispatcher | Suggests optimal delivery partner for each order based on proximity |
| `ai-seo-manager` | SEO consultant | "Your 'home-made thokku Chennai' page is at position 8 — here's what to do next" |
| `ai-receptionist` (H4) | Voice receptionist | Answers incoming calls and books appointments without human intervention |

---

## 3.22 Module: Trust Score (`trust-score`) — Horizon 2/3

**Purpose:** Computes and maintains a continuous, composite trust metric per business. Powers marketplace ranking, merchant health coaching, and admin early-warning signals.

**Trust Score Signals:**

| Signal | Weight | Description |
|--------|--------|-------------|
| Review Rating | 20% | Weighted average of all verified reviews |
| Review Volume | 10% | Total verified reviews (diminishing returns above 50) |
| Response Time | 20% | Median WhatsApp/chat response time |
| Fulfillment Rate | 15% | % of orders delivered vs. cancelled/failed |
| Appointment Reliability | 10% | % of appointments that occurred vs. no-show/cancellation |
| Repeat Customer Rate | 10% | % of customers returning within 90 days |
| Verification Status | 5% | GST/FSSAI/ID verified |
| Business Tenure | 5% | Time on platform + consistency bonus |
| AI Quality Signal | 5% | Quality of AI employee outputs (when applicable) |

**Score Computation:** Computed asynchronously by a background worker. Never computed synchronously in a request path. Recomputed after any relevant event — debounced to at most once per hour. Cached on the Business row for fast reads.

**Trust Score Public Face (Customer-Visible):** Raw score is never shown to customers. Translated to human-readable facts: "Usually responds in 10 minutes," "98% of orders delivered on time," "4.8 stars from 120 verified customers," "Verified since 2024."

**Merchant-Facing Display:** Score (0–100) with breakdown showing strong signals (green) and coaching tips for improvement.

**Dependencies:** `reviews`, `catalog-orders` or `booking-calendar`, `business-profile`

---

## 3.23 Module: Business Passport (`business-passport`) — Horizon 3

**Purpose:** A portable, verifiable identity document combining platform-verified data with uploaded compliance documents. Shareable outside the platform via QR code.

**Features:**
- GST verification (enter GSTIN → verified against government data)
- FSSAI license upload and verification, industry-specific license upload
- Certification upload (ISO, quality certifications), award documentation, insurance verification
- Verification status per document (pending/verified/expired/rejected)
- Passport QR code (links to public passport page — usable on packaging, signage)
- Passport sharing (direct link, embeddable badge)
- Verification badge on marketplace profile (unlocks when key documents are verified)
- Verification level tiers (Basic → Standard → Premium)
- Admin verification workflow, document expiry tracking and renewal reminders

**Pages (Merchant Dashboard):** Business Passport Overview, Document Management, Passport Preview, Verification History.

**Pages (Public):** Business Passport Public Page (`platform.com/passport/{businessId}`) — publicly accessible.

**Dependencies:** `business-profile`, `trust-score`

**Events Emitted:** `passport.document.submitted`, `passport.document.verified`, `passport.document.rejected`, `passport.level.upgraded`

---

## 3.24 Module: Business Community (`business-community`) — Horizon 3

**Purpose:** A professional social layer for businesses that have opted into marketplace discovery. Requires critical mass to launch (50+ active businesses in a city/category).

**Features:**
- Business posts (text, image, video — up to 60 seconds)
- Post types: update, product launch, offer, event, job opening, milestone
- Follow/unfollow businesses (by customers and other businesses)
- Business-to-business messaging (DMs between businesses)
- Feed (posts from followed businesses + recommended posts)
- Commenting, liking/reacting to posts
- Business events (create with date, location, RSVP)
- Job listings, offer announcements
- Content moderation (admin panel), content reporting, notifications for interactions

**Pages (Merchant Dashboard):** Community Feed, My Posts, Create Post, Followers/Following, Messages.

**Pages (Marketplace/Public):** Community Feed tab on marketplace, Business profile's posts tab, Event pages.

**Dependencies:** `business-profile`, `trust-score` (only businesses with active trust score can post)

---

## 3.25 Module: B2B Network (`b2b-network`) — Horizon 3

**Purpose:** Enables businesses to discover verified suppliers, service providers, and business partners. Powered by the Business Graph.

**Features:**
- Supplier discovery (search by category, location, product type)
- Supplier profiles (integrated with Business Passport for verification)
- Request for Quotation (RFQ) workflow, quotation comparison
- Supplier bookmarking and ratings
- Service provider discovery (designers, photographers, accountants, agencies)
- Business connection requests, B2B order placement (different pricing, credit terms)
- Bulk order management, B2B invoice and payment management
- AI-powered supplier recommendations (based on Business Graph)

**Pages (Merchant Dashboard):** B2B Marketplace (discover suppliers), My Connections, RFQ Management, B2B Orders.

**Dependencies:** `business-passport`, `trust-score`, `invoicing`, `payments`

---

## 3.26 Module: Developer Platform (`developer-platform`) — Horizon 4

**Purpose:** Opens the platform's module contract to external developers. Third-party modules built against the same Module SDK used internally.

**Features:**
- Developer account and organization management
- Module submission workflow (submit manifest → review → approved → listed)
- Module versioning and update management
- Revenue share framework (platform takes % of module subscription fees)
- Sandbox environment for development and testing
- Developer documentation portal
- Module API key management per installed merchant
- Module analytics (install count, active users, revenue)
- Module review and ratings by merchants
- Module support ticket routing

**Module Marketplace (merchant-facing):**
- Browse by category (Marketing, Finance, Industry, AI, Integrations)
- Module detail page (description, screenshots, reviews, pricing)
- Install/uninstall workflow (same as internal modules)
- Installed modules management

---

## 3.27 Admin Platform (Internal System)

**Purpose:** Platform's own operations surface. Not a module — a separate application with elevated access to all business data.

**Systems Within Admin Platform:**

**Business Management:** All businesses list, business detail view, verification workflow, suspension/reinstatement, trust score override (with logged justification).

**Marketplace Management:** Category management, featured business curation, marketplace search analytics, review moderation.

**Financial Management:** Platform-level revenue, subscription billing records, failed payment recovery, payout reconciliation.

**Trust & Safety:** Trust Score engine monitoring, fraud detection alerts, anomaly investigation workflow, banned patterns registry.

**Support:** All support tickets, ticket assignment, escalation to admin, known issues tracker, support SLA monitoring.

**AI Quality Monitoring:** AI employee output samples for review, escalation rate by module, model performance metrics, configuration overrides.

**Platform Configuration:** Module registry, business type configuration, feature flags, platform settings (maintenance mode, messaging).

**Audit Log:** Every admin action, timestamped, with actor, target, and change. Append-only. Cannot be modified or deleted. Searchable and exportable.

---

# PART 4 — EVERY PAGE DEFINED

Each page is defined with: Purpose, Primary User, Primary Actions, Secondary Actions, Navigation Position, Required Permissions, Entry Points, Exit Points, Data Displayed, Key Components, States, Error States, Mobile Behavior, Dependencies, Related Pages.

---

## 4.0 Authentication Pages

### Sign In
**URL:** `app.platform.com/sign-in`
**Purpose:** Authenticate existing users to the merchant dashboard.
**Primary User:** Business owners, managers, staff returning to the platform.
**Primary Actions:** Enter phone number → Receive OTP → Enter OTP → Access dashboard.
**Secondary Actions:** Sign up (new user), Forgot/change number.
**Navigation Position:** Outside app navigation (standalone auth page).
**Required Permissions:** None (pre-auth).
**Entry Points:** Direct URL, email magic link, bookmark, expired session redirect.
**Exit Points:** Dashboard Home (on success), Sign Up (new user CTA).
**Data Displayed:** Platform logo, phone input, OTP input (step 2), trust signal.
**Components:** Phone number input with country code (default +91), OTP 6-digit input with timer and resend, Submit button (Signal Indigo), Error message on wrong OTP.
**States:** `entering-phone` → `otp-sent` → `entering-otp` → `verifying` → `success` | `error`
**Error States:** Invalid phone format, Wrong OTP ("Incorrect code — 2 attempts remaining"), OTP expired ("Code expired — tap Resend"), Network error.
**Mobile Behavior:** Full-screen centered layout. Number pad auto-focuses. OTP auto-submits when 6 digits entered.
**Desktop Behavior:** Centered card, max 400px width.

---

### Sign Up — Create Your Business
**URL:** `app.platform.com/sign-up`
**Purpose:** Onboard a new merchant and create their first business.
**Primary User:** New business owners.
**Primary Actions:** Phone → OTP → Business name → Category → Done.
**Secondary Actions:** Already have an account? Sign in.
**Navigation Position:** Outside app navigation.
**Required Permissions:** None.
**Entry Points:** Website CTA, marketplace "list your business" CTA, referral link.
**Exit Points:** Onboarding flow → Dashboard.
**Steps:**
- Step 1: Phone + OTP
- Step 2: Business name, Business category (searchable dropdown with icons)
- Step 3: Confirmation + "Start Setting Up" button
**States:** `step-1-phone` → `step-1-otp` → `step-2-business-info` → `step-3-confirm` → `creating` → `done`
**Error States:** Phone already registered ("You already have an account — sign in here"), Business name too short, Category not found.
**Mobile Behavior:** One step per screen, full-screen. Progress dots at top.

---

## 4.1 Dashboard Home

### Dashboard Home (Morning Overview)
**URL:** `app.platform.com/` or `app.platform.com/dashboard`
**Purpose:** The merchant's starting point every day. Answers "what happened, what needs attention, what should I do" without needing to navigate anywhere.
**Primary User:** Business owners, managers.
**Primary Actions:** Review pending orders, review pending bookings, tap into a specific action item.
**Secondary Actions:** Dismiss AI suggestions, navigate to full reports, check business health.
**Navigation Position:** First item in sidebar (home icon).
**Required Permissions:** `business-profile` installed; any role except delivery partner.
**Entry Points:** App load, browser back to home, sidebar home icon.
**Exit Points:** Orders, Bookings, Analytics, any module from action queue.
**Data Displayed:**
- Greeting with operational summary ("Good morning — 4 new orders since midnight")
- Action Queue: pending orders, pending bookings, unread messages, escalations
- Revenue Snapshot: today / this week / this month + trend arrow vs. prior period
- Business Health Score: 0–100 + one coaching tip
- AI Suggestions Card: 1–3 dismissible suggestions from AI employees
- Quick Stats: active customers this week, top product today
**Components:**
- Greeting banner (personalized, time-aware)
- Action Queue list (cards with quick action buttons: Accept / View)
- Revenue metric cards with trend indicators
- Business Health Score ring chart (0–40 danger, 41–70 warning, 71–100 success)
- AI suggestions card (dismissible, max 3 items)
- Module-contributed widgets (each installed module can contribute one widget)
**States:** `loading` (skeleton), `loaded-with-actions`, `loaded-no-actions` (quiet day — positive), `new-business` (onboarding steps instead of data)
**Error States:** Cannot load data ("Having trouble loading your dashboard — refresh to try again")
**Mobile Behavior:** Vertical stack. Action Queue topmost. Revenue second. Bottom tab bar with Home as first item. Real-time updates via WebSocket.
**Desktop Behavior:** Two-column layout. Action Queue on left (2/3 width), stats on right (1/3 width). AI suggestions below.
**Dependencies:** All installed modules (widgets are module-contributed). Event bus (real-time updates).

---

## 4.2 Onboarding Flow

### Onboarding — Welcome & Setup
**URL:** `app.platform.com/onboarding`
**Purpose:** Guide a new merchant through 5–7 key steps to have a functioning business. Shown once per business until all steps completed or dismissed.
**Primary User:** New business owners within first 30 days.
**Primary Actions:** Complete each onboarding step in sequence.
**Secondary Actions:** Skip step, return later, get help.
**Navigation Position:** Overlaid on dashboard during initial setup.
**Required Permissions:** Owner.
**Entry Points:** Auto-redirect after sign-up, dashboard banner for incomplete onboarding.
**Exit Points:** Dashboard Home when all steps complete or dismissed.
**Components:**
- Progress bar / step list (numbered, checked on completion)
- Active step form (inline, no navigation away)
- "Save and continue" button
- "Do this later" link
- Completion celebration (first site goes live — earned delight)
**Steps (example: home_food):**
1. Add business logo and cover photo
2. Add first products (at least 3)
3. Set business hours
4. Add WhatsApp number for orders
5. Preview your storefront
6. Share your link
7. (Optional) Connect Razorpay
**States:** `not-started` → `in-progress` → `completed` | `dismissed`

---

## 4.3 Products & Catalog Pages

### Products List
**URL:** `app.platform.com/products`
**Purpose:** View and manage all products in the catalog.
**Primary User:** Business owners, managers.
**Primary Actions:** Add product, search products, edit product, change product status.
**Secondary Actions:** Filter by category/status, bulk actions, import CSV, reorder products.
**Navigation Position:** Catalog section → Products.
**Required Permissions:** `catalog-orders` module; owner, manager, or staff with write grant.
**Data Displayed:**
- Product list: photo thumbnail, name, category, price, status, stock level (if inventory installed)
- Status filter tabs: All / Published / Draft / Hidden / Out of Stock
- Search bar, category filter dropdown
**Components:**
- Product list row/card (switchable view)
- Status badge (Published/Draft/Hidden/Out of Stock)
- Quick edit: status toggle, price inline edit
- Bulk selection + bulk actions (change status, delete, change category)
- Add Product button (Signal Indigo, persistent)
- Empty state ("No products yet — add your first product" with CTA)
**States:** `loading`, `loaded-with-products`, `empty`, `filtered-empty`
**Mobile Behavior:** Card list. Swipe left on product → quick actions (Edit, Hide, Delete). Floating "+" button for add.

---

### Add / Edit Product
**URL:** `app.platform.com/products/new` and `app.platform.com/products/{id}/edit`
**Purpose:** Create a new product or edit an existing one.
**Primary User:** Business owners, managers.
**Primary Actions:** Save product, publish product.
**Secondary Actions:** Preview on storefront, duplicate product, archive product.
**Required Permissions:** `catalog-orders` module; write access.
**Data Displayed/Editable:**
- Product name (required), category (required), description (rich text — bold/italic/bullets only)
- Price (required), variant groups (optional), modifier groups (optional)
- Product images (up to 6, drag to reorder, first = thumbnail)
- Stock quantity (if inventory module installed), tax rate override
- Dietary tags (BusinessType-specific), minimum order quantity
- Availability: Published / Draft / Hidden / Pre-order (with date)
**Components:**
- Two-column form (desktop): main fields left, image upload + pricing preview right
- Image upload zone (drag-and-drop + click, max 5MB per image)
- Variant builder (add axis → name → options with prices)
- Modifier group builder, auto-save indicator
- Publish / Save Draft button
**States:** `new-empty`, `editing-existing`, `saving`, `saved`, `error` (validation)
**Validation Errors:** Name required, price required (must be > 0), variant option missing price.
**Mobile Behavior:** Single column. Image upload first. Keyboard-aware form.

---

## 4.4 Orders Pages

### Orders Dashboard
**URL:** `app.platform.com/orders`
**Purpose:** The primary operational page for order-based businesses. Merchants open this every morning and after every notification.
**Primary User:** Business owners, managers, staff with order access.
**Primary Actions:** Accept order, reject order, view order details, update order status.
**Secondary Actions:** Filter orders, search by ID or customer name, export orders.
**Navigation Position:** Operations section → Orders.
**Required Permissions:** `catalog-orders` module; read access.
**Data Displayed:**
- Status column tabs: Pending (requires action) / Active / Completed / Cancelled
- Order cards: order number, customer name, items summary, total amount, time received, status
- Real-time updates (new order appears with sound + visual pulse)
**Components:**
- Kanban-style columns (Pending | Preparing | Ready | Out for Delivery) for active orders
- List view for Completed and Cancelled with search and date filter
- Accept/Reject quick actions in Pending column
- Preparation timer (starts on acceptance)
- "Mark Ready" button when preparation complete
- Assign Delivery button (if delivery module)
- Print kitchen ticket action
**States:** `loading`, `no-pending-orders` ("All caught up — no pending orders"), `live-with-orders`, `filtered-empty`
**Real-time:** New orders appear in Pending column without page refresh. Chime + banner notification. On mobile, push notification.
**Mobile Behavior:** Defaults to Pending tab. Card swipe: right = Accept, left = Reject (with confirmation). Floating new order alert banner.

---

### Order Detail
**URL:** `app.platform.com/orders/{orderId}`
**Purpose:** Full details of a single order — items, customer, payment, history, and all available actions.
**Primary User:** Business owners, managers, staff.
**Primary Actions:** Accept/Reject, update status, add note, print receipt, initiate refund.
**Secondary Actions:** View customer profile, contact customer via WhatsApp.
**Data Displayed:**
- Order number and timestamp, customer name and phone (with WhatsApp link)
- Order items with quantities, variants, modifiers, prices
- Special instructions, subtotal, discounts, delivery fee, taxes, total
- Payment status (paid/pending/COD)
- Order status history (timeline of all status changes with timestamps)
- Delivery information (if applicable), internal notes
**Components:**
- Order status timeline (horizontal desktop, vertical mobile)
- Action buttons appropriate to current status
- Print receipt button (generates PDF)
- Customer contact row (phone + WhatsApp icon)
- Note input (internal, saves inline)
- Refund drawer (opens when "Issue Refund" clicked)
**Mobile Behavior:** Full-screen detail. Status update buttons sticky at bottom.

---

## 4.5 Bookings Pages

### Bookings Calendar
**URL:** `app.platform.com/bookings`
**Purpose:** Visual calendar showing all bookings. Primary operational surface for service businesses.
**Primary User:** Business owners, managers, receptionists.
**Primary Actions:** View day/week/month, click booking to view detail, create manual booking.
**Secondary Actions:** Filter by service/staff, switch to list view, export bookings.
**Required Permissions:** `booking-calendar` module.
**Data Displayed:** Calendar grid (day/week/month switchable), booking blocks (color-coded by service or staff), booking detail tooltip on hover.
**Components:**
- Calendar header with view switcher (Day / Week / Month)
- "Today" jump button, staff filter dropdown (if staff module)
- Booking block component (click → opens booking detail drawer)
- "New Booking" button (opens booking creation form as drawer)
- Availability slots (visual empty slots)
**States:** `loading`, `loaded-with-bookings`, `empty-day`
**Mobile Behavior:** Day view by default. Horizontal date picker at top. Bookings as vertical timeline.

---

## 4.6 Customer Pages

### Customer List
**URL:** `app.platform.com/customers`
**Purpose:** Browse and manage all customers.
**Primary User:** Business owners, managers.
**Primary Actions:** Search for a customer, view customer profile, add manual customer.
**Secondary Actions:** Filter by segment, sort by value/recency, export customers, create segment.
**Required Permissions:** `crm` module; read access.
**Data Displayed:** Customer table: name, phone, last order/booking, total spent, order count, tags.
**States:** `loading`, `loaded`, `empty` ("No customers yet — they'll appear here after their first order"), `search-empty`

---

### Customer Detail
**URL:** `app.platform.com/customers/{customerId}`
**Purpose:** Full profile of a single customer. The merchant's memory of this relationship.
**Primary User:** Business owners, managers.
**Primary Actions:** Add note, send message, view order/booking history.
**Secondary Actions:** Edit contact details, add/remove tags, block customer.
**Data Displayed:**
- Customer profile header: name, phone, email, avatar, customer since date
- Lifetime metrics: total spent, order count, booking count, average order value, last interaction
- Tags (manual and auto), interaction timeline (all orders, bookings, messages, reviews)
- Notes section (internal notes with timestamp and author)
- Loyalty balance (if loyalty module)

---

## 4.7 Analytics Pages

### Business Overview (Analytics)
**URL:** `app.platform.com/analytics`
**Purpose:** High-level performance summary — a health check, not a detailed report.
**Primary User:** Business owners, managers.
**Primary Actions:** Change date range, drill into a specific metric.
**Data Displayed:**
- Revenue (today, this week, this month, this year + trends)
- Orders/Bookings count and trend, new vs. returning customers
- Top products by revenue, busiest times heatmap
- Website traffic summary (if website module), rating summary (if reviews module)
**Components:** Date range picker, metric cards with trend arrows, bar charts, heatmap, line chart.

---

## 4.8 Marketing Pages

### Campaigns Dashboard
**URL:** `app.platform.com/marketing/campaigns`
**Purpose:** Overview of all marketing campaigns — active, scheduled, and past.
**Primary User:** Business owners, managers.
**Primary Actions:** Create campaign, view performance, resume/pause campaign.
**Data Displayed:** Active campaigns (with live send progress), scheduled campaigns (with countdown), past campaigns (with summary metrics: sent, opened, converted, revenue attributed).

---

### Create Campaign (Wizard)
**URL:** `app.platform.com/marketing/campaigns/new`
**Purpose:** Step-by-step campaign creation.
**Steps:**
1. Choose channel (WhatsApp / Email / Push — shown based on installed modules)
2. Select audience (All customers / Segment / Custom filter — count shown live)
3. Create content (text + optional image; AI draft button if ai-content-creator installed)
4. Schedule (Send now / Schedule for specific date-time)
5. Review and confirm (audience count, estimated cost if applicable)
6. Launch

---

## 4.9 Staff Pages

### Staff List
**URL:** `app.platform.com/staff`
**Purpose:** Manage all team members — view roles, status, and quick actions.
**Primary User:** Business owners, managers.
**Primary Actions:** Invite staff member, view staff profile, edit role/permissions.
**Data Displayed:** Staff list: name, role, status (active/invited/removed), last login, modules accessible.

---

### Invite Staff
**URL:** `app.platform.com/staff/invite`
**Purpose:** Add a new team member by phone or email. Assign role and permissions during invitation.
**Primary User:** Business owners (managers can invite Staff/Delivery Partner only).
**Primary Actions:** Enter contact, select role, select module permissions, send invitation.
**Components:**
- Phone/email input, role selector (dropdown with role descriptions)
- Module permission checklist (per module: no access / read / read+write)
- Permission template selector ("Cashier," "Cook," "Stylist," "Receptionist")
- Send Invitation button

---

## 4.10 Settings Pages

### Settings — Business Info
**URL:** `app.platform.com/settings/business`
**Purpose:** Edit core business information.
**Primary User:** Owner, Manager.
**States:** `viewing`, `editing` (inline), `saving`, `saved`

### Settings — Payments
**URL:** `app.platform.com/settings/payments`
**Purpose:** Configure payment gateway and payment options.
**Primary User:** Owner only.
**Components:** Razorpay connection (OAuth flow), payment method toggles, split payment configuration, payout schedule.

### Settings — Notifications
**URL:** `app.platform.com/settings/notifications`
**Purpose:** Control which notifications are sent, to whom, and on which channels.
**Primary User:** Owner, Manager.
**Organized By:** Notification type × Channel matrix.

### Settings — Module Manager
**URL:** `app.platform.com/settings/modules`
**Purpose:** View installed modules, install new modules, configure or uninstall existing ones.
**Primary User:** Owner only.
**Primary Actions:** Install module, configure module, uninstall module.
**Uninstall Warning:** "Uninstalling [Module] will remove its features from your dashboard. Your data will be retained for 30 days. This cannot be undone after 30 days."

### Settings — Domain
**URL:** `app.platform.com/settings/domain`
**Purpose:** Connect a custom domain to the business's public storefront.
**Primary User:** Owner only.
**Components:** Custom domain input, DNS instructions (specific CNAME records), verification status, SSL status, current subdomain display.

### Settings — Security
**URL:** `app.platform.com/settings/security`
**Purpose:** Manage account security settings.
**Primary User:** Owner.
**Components:** Phone number change (OTP verified), active sessions list (with revoke), account activity log, 2FA toggle, session timeout.

### Settings — Billing & Subscription
**URL:** `app.platform.com/settings/billing`
**Purpose:** Manage the merchant's subscription to the platform.
**Primary User:** Owner only.
**Data Displayed:** Current plan, plan features, add-on modules, payment method on file, invoice history.
**Primary Actions:** Upgrade plan, downgrade plan, cancel subscription, update payment method.
**States:** `active`, `past-due` (with payment resolution CTA), `cancelled` (with reactivation option)

---

## 4.11 My Business Pages

### Business Profile (Merchant View)
**URL:** `app.platform.com/my-business/profile`
**Purpose:** View and edit how the business appears publicly. Shows a live preview of the business profile card as it would appear on the marketplace.
**Primary User:** Owner, Manager.
**Components:** Profile completeness indicator, live marketplace card preview, verification badge status.

### Website Editor
**URL:** `app.platform.com/my-business/website`
**Purpose:** Visual editor for the merchant's public storefront.
**Primary User:** Owner, Manager.
**Components:**
- Page list (left panel), canvas with current page sections (center), section library (right panel)
- Properties panel (edits selected section's content)
- Mobile/Desktop preview toggle
- Publish button ("Changes not published" indicator when unsaved changes exist)
- "View Live Site" button

### Media Library
**URL:** `app.platform.com/my-business/media`
**Purpose:** Central repository for all uploaded images and files.
**Primary User:** Owner, Manager.
**Components:** Upload zone, asset grid, filter by purpose (logo/cover/product/gallery), asset detail panel (shows where asset is used).

### Marketplace Listing Preview
**URL:** `app.platform.com/my-business/marketplace`
**Purpose:** Shows the merchant how their business appears on the marketplace. Non-editable — content comes from profile and modules. Explains how to improve.
**Data Displayed:** Live preview of marketplace business card and full profile page, Trust Score breakdown, suggestions for improving the listing.

---

## 4.12 AI Employee Pages

### AI Roster
**URL:** `app.platform.com/ai-employees`
**Purpose:** Overview of all installed AI employees, their current activity, and health.
**Primary User:** Owner, Manager.
**Data Displayed:** Installed AI employees (name, role, status, actions handled today), Available AI employees (with install CTA).

### AI Employee Detail
**URL:** `app.platform.com/ai-employees/{aiModuleId}`
**Purpose:** Operational view for a specific AI employee — live activity, configuration, and performance.
**Data Displayed (example: AI WhatsApp Manager):** Status toggle, today's metrics, live conversation feed, escalation queue, configuration, activity log.
**Primary Actions:** Toggle on/off, resolve escalations, add FAQ entries, review and correct AI output.

---

## 4.13 Support Pages

### Help Center
**URL:** `app.platform.com/support`
**Purpose:** Self-serve support — answers, how-to guides, video tutorials.
**Primary User:** All merchant roles.
**States:** `search-results`, `category-view`, `article-view`

### Submit Support Ticket
**URL:** `app.platform.com/support/new`
**Purpose:** Create a support request when self-serve doesn't solve the issue.
**Components:** Issue category selector, issue description, screenshot upload (optional), priority selector, Submit button. After submission: ticket number shown with estimated response time.

---

## 4.14 Marketplace Pages (Customer-Facing)

### Marketplace Home
**URL:** `platform.com/discover`
**Purpose:** Entry point for customers discovering businesses. Goal: feel curated and alive, not a generic directory.
**Primary User:** Customers (logged in or not).
**Primary Actions:** Search for a business or product, browse by category, tap into a business.
**Data Displayed:** Search bar with location (primary CTA), nearby businesses (if location granted), featured businesses (admin-curated), category quick links, recently visited businesses (if logged in), community posts (H3).
**Mobile Behavior:** Location prompt on first visit. Bottom navigation: Home / Search / Favourites / Account.

### Marketplace Search Results
**URL:** `platform.com/discover/search?q=...`
**Purpose:** Show relevant businesses matching search criteria.
**Primary User:** Customers.
**Components:**
- Business result cards (photo, name, category, trust signals, CTA)
- Filter panel (collapsible): rating minimum, distance radius, open now, category
- Sort controls: Relevance / Distance / Rating / New
- Map view toggle
- No results state

### Business Profile (Marketplace)
**URL:** `platform.com/b/{slug}` or `{slug}.platform.com`
**Purpose:** The public-facing profile of a business. Customers make purchase/booking decisions here.
**Primary User:** Customers.
**Primary Actions:** Order, Book, Contact via WhatsApp, Follow business, Write review.
**Data Displayed:** Cover image + logo, business name + category + trust badges, trust signals (human-readable facts), About, Products/Services, Reviews (with merchant responses), Gallery, Location map + hours, Follow button (H2+).
**Components:**
- Sticky header (after cover scrolls past): business name + CTA buttons
- Trust signal row, product catalog with add-to-cart
- Reviews section with rating distribution chart, response time badge
- Operating hours display
**Mobile Behavior:** Sticky bottom bar: Order / Book / WhatsApp / Call. Prominent while scrolling.

---

## 4.15 Customer Portal Pages

### Customer Dashboard
**URL:** `platform.com/account`
**Purpose:** Customer's personal hub across all businesses on the platform.
**Primary User:** Registered customers (Horizon 2+).
**Data Displayed:** Upcoming bookings (next 3), recent orders (last 3 from any business), favourite businesses, loyalty points summary, recommended businesses.

### Customer Order History
**URL:** `platform.com/account/orders`
**Purpose:** All orders placed across all businesses.
**Data Displayed:** Order list with business name, date, items summary, amount, status.
**Actions:** View order detail, reorder, write review (if eligible), track live order.

### Customer Booking History
**URL:** `platform.com/account/bookings`
**Data Displayed:** Booking list with business name, service, date/time, status.
**Actions:** View booking detail, cancel/reschedule (within policy), add to calendar.

---

## 4.16 Admin Panel Pages

### Admin — Businesses
**URL:** `admin.platform.com/businesses`
**Purpose:** Full list of all businesses on the platform. Operational hub for admin team.
**Required Permissions:** Platform Admin.
**Primary Actions:** Search business, view business detail, verify business, suspend business.
**Data Displayed:** Business table: name, type, city, status, trust score, subscription tier, created date, last active.
**Filters:** Status, Type, City, Subscription tier, Verification status.

### Admin — Business Detail
**URL:** `admin.platform.com/businesses/{businessId}`
**Purpose:** Complete view of one business — all data the admin team can see.
**Data Displayed:** Business profile summary, all installed modules and status, recent events (last 50), trust score breakdown, subscription and billing status, support ticket history, audit log.
**Admin Actions:** Verify, Suspend, Reinstate, Override Trust Score (with required justification), Reset module, Impersonate (for debugging — audit logged).

### Admin — Pending Verification Queue
**URL:** `admin.platform.com/businesses/pending-verification`
**Purpose:** Process business verification requests.
**Actions per item:** View documents, approve with badge, reject with reason, request more documents.
**States per item:** `submitted`, `under-review`, `approved`, `rejected`, `needs-more-info`
**Admin SLA:** 48 hours (tracked in admin dashboard).

### Admin — Review Moderation
**URL:** `admin.platform.com/marketplace/reviews`
**Purpose:** Moderate reviews flagged by merchants as inappropriate.
**Actions:** Remove review (with reason), Keep review (dismiss flag), Escalate to legal.

### Admin — Audit Log
**URL:** `admin.platform.com/audit`
**Purpose:** The immutable log of all admin actions.
**Data Displayed:** Action timeline: timestamp, admin user, action type, target, before/after values.
**Immutability:** Append-only. No admin can edit or delete audit log entries.

---

# PART 5 — EVERY WORKFLOW

## 5.1 Business & Onboarding Workflows

### Workflow: Create New Business
**Actor:** New user / existing user (adding a second business).
**Steps:**
1. User visits sign-up page or clicks "Add business" from dashboard.
2. Enters phone number → receives OTP → enters OTP.
3. Enters business display name.
4. Selects business category (determines default module bundle).
5. System provisions: Business entity, default modules, subdomain slug.
6. User directed to Onboarding Flow.
7. Onboarding guides through: logo upload, first products, business hours, WhatsApp number.
8. User previews storefront → publishes.

**Events Emitted:** `business.created`, `business.onboarding.started`, `website.published`
**Failure Paths:** Phone already registered → direct to sign-in; subdomain conflict → auto-suggest alternative slug.
**Target Completion Time:** Under 15 minutes for a functional storefront.

---

### Workflow: Business Verification
**Actor:** Business owner (initiates); Platform Admin (reviews).
**Steps:**
1. Owner navigates to Business Passport or verification prompt on profile.
2. Uploads required documents (GST certificate, FSSAI if applicable, ID proof).
3. System creates verification request → emits `business.verification.requested`.
4. Admin notified in admin panel verification queue.
5. Admin reviews documents → approves (with tier) or rejects (with reason) or requests more info.
6. Owner notified via WhatsApp + in-app notification.
7. If approved: verification badge appears on marketplace profile + Trust Score updated.

**Failure Paths:** Document image too low quality → rejection with guidance; expired license → rejection with specific note.
**Admin SLA:** 48 hours.

---

### Workflow: Invite Staff Member
**Actor:** Business owner or manager.
**Steps:**
1. Staff → Invite Staff.
2. Enters phone or email of staff member.
3. Selects role (Manager / Staff / Delivery Partner / Accountant / Receptionist).
4. If Staff: selects permission template or custom module grants.
5. Clicks Send Invitation.
6. System creates invitation record + sends OTP link to staff member's phone.
7. Staff member opens link → enters OTP → creates account (or signs in to existing account).
8. Staff member sees restricted dashboard based on their permissions.

**Events Emitted:** `staff.invited`, `staff.joined`
**Expiry:** Invitation link expires after 48 hours. Can be resent.
**Existing Account:** Link is added to existing account — no duplicate account created.

---

### Workflow: Transfer Business Ownership
**Actor:** Current owner.
**Steps:**
1. Settings → Business → Danger Zone → Transfer Ownership.
2. Enters new owner's phone number (must be an existing staff/manager).
3. Confirmation dialog ("This is irreversible without the new owner's consent").
4. OTP confirmation to current owner's phone.
5. New owner receives notification + confirmation prompt.
6. New owner confirms.
7. Roles swapped: new owner gets `owner`; previous owner demoted to `manager` or removed.

**Failure Paths:** New owner phone not found → error; new owner doesn't confirm within 24 hours → request expires.

---

## 5.2 Product & Catalog Workflows

### Workflow: Add First Product
**Actor:** Business owner or manager.
**Steps:**
1. From onboarding step 2 or Products List → Add Product.
2. Enter product name, category (creates if new).
3. Enter description (AI can draft if ai-content-creator installed).
4. Set price.
5. Add variants if applicable.
6. Upload product image.
7. Set stock quantity (if inventory module installed).
8. Select dietary tags (if food business).
9. Publish or Save Draft.

**Events Emitted:** `catalog.product.created`, optionally `catalog.product.published`
**Target Completion Time:** Under 3 minutes for a simple product with one photo.

---

### Workflow: Bulk Import Products via CSV
**Actor:** Business owner or manager.
**Steps:**
1. Products List → Import → Download CSV template.
2. Fill template with product data.
3. Upload completed CSV.
4. System validates: checks required fields, flags errors row by row.
5. Validation summary shown ("45 products valid, 3 errors — fix before importing").
6. Merchant fixes errors or proceeds with valid rows only.
7. Import runs → products created in Draft status.
8. Merchant reviews and publishes products.

---

## 5.3 Order Workflows

### Workflow: Customer Places Order (Online)
**Actor:** Customer.
**Steps:**
1. Customer browses menu on storefront or marketplace.
2. Adds products to cart.
3. Selects delivery or pickup.
4. Applies coupon code (optional).
5. Enters delivery address (or selects saved address).
6. Selects payment method.
7. Reviews order and total.
8. Confirms order → payment is processed.
9. Order created → `order.created` emitted.
10. Customer sees order confirmation with order ID.
11. Merchant receives real-time notification (sound + banner + push).

**Events Chain:** `order.created` → `payment.completed` → `whatsapp-notification.order_confirmation` → `crm.customer.updated` → `analytics.daily_stats.updated`

---

### Workflow: Merchant Accepts Order
**Actor:** Business owner, manager, staff with order access.
**Steps:**
1. Merchant sees pending order in Orders Dashboard (real-time).
2. Opens order card → reviews items, special instructions, delivery address.
3. Clicks Accept → enters preparation time estimate (in minutes).
4. Order moves to Preparing state.
5. Customer receives WhatsApp confirmation with order details and estimated time.
6. When ready: clicks Mark Ready.
7. If delivery: assigns delivery partner (manual or auto).
8. Delivery partner picks up → clicks Picked Up.
9. Delivery partner delivers → clicks Delivered.
10. Order completes → `order.completed` emitted → review request triggered after 2-hour delay.

---

### Workflow: Order Rejection
**Actor:** Business owner, manager.
**Steps:**
1. Merchant sees pending order.
2. Clicks Reject → required to select reason (Out of stock / Closed / Delivery area issue / Custom reason).
3. Order moves to Rejected/Cancelled state.
4. Customer receives WhatsApp notification with rejection reason.
5. Refund automatically initiated if online payment was collected.

**Events Emitted:** `order.rejected`, `payment.refunded` (if applicable)

---

### Workflow: Order Refund
**Actor:** Business owner, manager.
**Steps:**
1. Merchant finds order in history.
2. Clicks "Issue Refund."
3. Selects refund type: Full or Partial (enter amount).
4. Enters refund reason.
5. Confirms → refund processed via payment gateway.
6. Customer notified via WhatsApp ("Your refund of ₹X has been initiated — 3–5 business days").
7. Order marked as Refunded.

**Failure Paths:** Refund amount > original payment → error; refund window expired → requires admin approval.

---

## 5.4 Booking Workflows

### Workflow: Customer Books a Service Online
**Actor:** Customer.
**Steps:**
1. Customer visits storefront or marketplace profile.
2. Clicks Book Now.
3. Selects service (if multiple available).
4. Selects staff member (if applicable).
5. Selects available date and time slot.
6. Enters name, phone, any notes.
7. Selects payment (if deposit required).
8. Confirms booking.
9. Booking created → confirmation sent via WhatsApp with date/time/cancellation link.
10. Merchant notified.

---

### Workflow: Merchant Manages Booking
**Actor:** Business owner, manager, receptionist.
**Options:** Confirm (if approval required), Reschedule (pick new slot → customer notified), Cancel (with reason → customer notified), Mark No-Show, Mark Complete.
**On completion:** Review request triggered after 1-hour delay.

---

## 5.5 Payment & Financial Workflows

### Workflow: Connect Payment Gateway (Razorpay)
**Actor:** Business owner.
**Steps:**
1. Settings → Payments → Connect Razorpay.
2. Merchant redirected to Razorpay OAuth page.
3. Merchant logs in or creates Razorpay account.
4. Authorizes the platform.
5. Razorpay account is linked → payment module becomes active.
6. Owner selects accepted payment methods and payout schedule.

**KYC Note:** Razorpay requires KYC. If not completed, payments are placed in escrow until KYC is approved. Platform shows clear guidance and tracks KYC status.

---

### Workflow: Generate and Send Invoice
**Actor:** Business owner, manager, accountant.
**Steps:**
1. Invoicing section → Create Invoice (or auto-generated from completed order if configured).
2. Select customer (from CRM) or enter manually.
3. Add line items (product/service name, quantity, unit price, tax rate).
4. Review GST calculation (CGST/SGST auto-computed based on state).
5. Set invoice date and due date.
6. Click Send → choose channel (Email / WhatsApp).
7. Customer receives invoice with payment link (if payments module installed).
8. Invoice status changes to Sent.
9. When customer pays: `payment.completed` emitted → invoice marked Paid.

---

## 5.6 Marketing & Campaign Workflows

### Workflow: Create and Launch a Campaign
**Actor:** Business owner, manager.
**Steps:**
1. Marketing → Campaigns → Create Campaign.
2. Step 1: Select channel.
3. Step 2: Select audience — All Customers or choose segment (count shown live).
4. Step 3: Write message (or use AI draft if ai-content-creator installed).
5. Step 4: Attach offer code (optional — from coupons).
6. Step 5: Schedule (now or future date/time).
7. Step 6: Review (audience count, compliance warnings).
8. Click Launch → campaign scheduled or immediately enqueued.
9. Campaign runs → sent/failed counts update in real time.
10. Performance report available within 24 hours.

---

### Workflow: Create a Coupon
**Actor:** Business owner, manager.
**Steps:**
1. Marketing → Coupons → Create Coupon.
2. Enter: code (or generate), discount type (% or fixed), discount value, applicable products (all or specific), minimum order value, usage limit (total + per customer), expiry date.
3. Publish coupon (active immediately or from a future date).

---

## 5.7 AI Employee Workflows

### Workflow: Install and Activate AI WhatsApp Manager
**Actor:** Business owner.
**Steps:**
1. Module Manager → AI WhatsApp Manager → Install.
2. Review what the module does (permissions it needs).
3. Confirm installation.
4. Configuration screen: connect WhatsApp Business number, enter FAQ entries, set escalation threshold, set working hours.
5. Test mode: enter test questions, see AI responses before going live.
6. Activate — AI is now responding to incoming WhatsApp messages.

---

### Workflow: Handle AI Escalation
**Actor:** Business owner or manager.
**Steps:**
1. Merchant receives escalation notification (in-app + push) — "AI couldn't confidently answer this message from Meena."
2. Views escalation queue (AI Employees → AI WhatsApp Manager → Escalations).
3. Sees: customer's original message, AI's attempted response (not sent), AI's reason for escalating.
4. Merchant types their own response → sends directly to customer via WhatsApp.
5. Merchant optionally adds the Q&A to the FAQ.
6. Escalation marked resolved.

---

## 5.8 Website Workflows

### Workflow: Customize and Publish Storefront
**Actor:** Business owner, manager.
**Steps:**
1. My Business → Website → opens Website Editor.
2. Editor shows auto-generated website (pre-populated from profile).
3. Merchant edits Hero section (headline, description, CTA button text).
4. Reorders sections (drag handles).
5. Adds new section from Section Library.
6. Edits About content.
7. Selects products to feature in catalog section.
8. Previews on mobile.
9. Clicks Publish.
10. On first publish: celebration moment — "Your business is live. Share your link!" (earned delight).
11. Shareable link appears with copy button and WhatsApp share option.

---

### Workflow: Connect Custom Domain
**Actor:** Business owner.
**Steps:**
1. Settings → Domain → Enter custom domain.
2. System provides DNS records to add (CNAME pointing to platform's hosting).
3. Merchant logs in to their domain registrar, adds the DNS records.
4. Clicks Verify in platform.
5. System checks DNS propagation (may take up to 24 hours).
6. On verification: SSL certificate auto-provisioned.
7. Custom domain becomes primary; old subdomain remains as redirect.

**Failure Path:** DNS not found after 24 hours → check guide + support ticket.

---

## 5.9 Marketplace Workflows

### Workflow: Opt Into Marketplace Discovery
**Actor:** Business owner.
**Steps:**
1. My Business → Marketplace Listing → Enable marketplace visibility.
2. Review what it means: "Your business becomes discoverable by all customers, and the platform saves customer data from marketplace transactions."
3. Confirm opt-in (explicit, not default).
4. Business visibility changes from `unlisted` to `discoverable`.
5. Listing appears in marketplace within 15 minutes (after search index update).

---

### Workflow: Upgrade Subscription Plan
**Actor:** Business owner.
**Steps:**
1. Settings → Billing or prompted via paywall when accessing a premium module.
2. View current plan vs. available plans (feature comparison).
3. Select new plan.
4. Review prorated pricing for current billing cycle.
5. Confirm payment method (use existing or add new card/UPI).
6. Upgrade confirmed → new modules/features immediately available.
7. Billing cycle resets or prorated charge applied.

---

# PART 6 — EVERY OBJECT STATE

## 6.1 Business States

### Business Lifecycle State
```
onboarding → active → dormant → closed
```
- `onboarding`: Business created but onboarding not complete
- `active`: Business is operational and regularly using the platform
- `dormant`: No login or transaction for 90+ days — triggers AI follow-up
- `closed`: Owner manually closed the business — data retained for 2 years

### Business Platform Status
```
in_good_standing → under_review → suspended
```
- `in_good_standing`: No issues
- `under_review`: Admin investigating; business may still operate but is flagged
- `suspended`: Cannot receive orders or appear in marketplace; owner notified with reason and appeal process

### Business Visibility
```
private → unlisted → discoverable
```
- `private`: Only accessible to authenticated staff; no public URL
- `unlisted`: Has public URL, accessible via direct link, not in marketplace search
- `discoverable`: Fully visible in marketplace search and discovery

A business can be `active` + `in_good_standing` + `unlisted` (fully operational, opted out of marketplace discovery) — a common and valid combination.

### Business Verification Status
```
unverified → pending → verified → expired
(per document; badge levels: Basic / Standard / Premium)
```

---

## 6.2 Product / Service States

```
draft → published → hidden → archived
               |
         out_of_stock (sub-state of published or hidden)
```
- `draft`: Being created, not visible to customers
- `published`: Visible on storefront and marketplace; orderable
- `hidden`: Saved but temporarily not shown; link-only access
- `out_of_stock`: Sub-state; shown with "Out of stock" label; cannot be added to cart
- `archived`: Soft-deleted; removed from storefront; data retained; can be restored

**Transitions:**
- `draft` → `published`: On click "Publish" (requires name and price)
- `published` → `hidden`: Manual toggle or scheduled unpublish
- `published` → `out_of_stock`: Auto (inventory hits 0) or manual
- `out_of_stock` → `published`: Auto (inventory replenished) or manual
- `[any]` → `archived`: Manual; confirmation required
- `archived` → `draft`: Restore action

---

## 6.3 Order States

```
pending → accepted → preparing → ready → out_for_delivery → delivered
    |          |
rejected   cancelled (can cancel before preparing starts)
                |
            refunded (triggered post-cancellation or post-delivery complaint)
                |
            expired (no action within timeout window; auto-cancelled)
```

**State Descriptions:**
- `pending`: Order received, awaiting merchant acceptance
- `accepted`: Merchant accepted; preparation time set; customer notified
- `rejected`: Merchant rejected; customer notified with reason; refund auto-initiated if payment collected
- `preparing`: Merchant is preparing the order
- `ready`: Order ready for pickup or delivery assignment
- `out_for_delivery`: Delivery partner has picked up
- `delivered`: Customer received order; `order.completed` emitted; review request queued
- `cancelled`: Cancelled by customer (before acceptance) or merchant; refund initiated if applicable
- `refunded`: Full or partial refund processed
- `expired`: Not accepted within configured timeout (e.g., 30 minutes); auto-cancelled; refund initiated

**Allowed Transitions:**
- Customer can cancel: `pending` only (before acceptance)
- Merchant can cancel: `pending`, `accepted`, `preparing` (with reason)
- System auto-cancels: `pending` → `expired` after timeout

---

## 6.4 Booking States

```
pending → confirmed → checked_in → completed
    |          |
rejected   cancelled (by merchant or customer, within policy)
    |          |
(customer) rescheduled → confirmed (new slot)
                |
            no_show (merchant marks if customer doesn't arrive)
```

- `pending`: Customer submitted booking request; awaiting confirmation
- `confirmed`: Merchant confirmed or auto-confirmed (instant booking)
- `checked_in`: Customer arrived and been marked as present
- `completed`: Service delivered; review request triggered
- `rejected`: Merchant declined; customer notified
- `cancelled`: Cancelled by either party within policy; refund if deposit paid
- `rescheduled`: New time proposed; moves back to confirmed with new slot
- `no_show`: Customer didn't arrive; affects Trust Score

---

## 6.5 Appointment / Queue States

```
queued → called → checked_in → completed
    |        |
cancelled  skipped (didn't respond when called → moved to end or cancelled)
                |
            no_show
```

---

## 6.6 Delivery States

```
pending_assignment → assigned → picked_up → out_for_delivery → delivered
                                    |
                                returned (delivery failed; back at merchant)
                                    |
                                failed (customer unreachable, wrong address, etc.)
```

---

## 6.7 Invoice States

```
draft → sent → paid
           |
        overdue (payment not received by due date)
           |
        cancelled (if disputed or replaced by credit note)
```

Substates: `partially_paid` (payment received but less than total), `written_off` (admin marks as uncollectable — H3).

---

## 6.8 Campaign States

```
draft → scheduled → sending → completed
    |                   |
archived             paused → resumed → completed
                         |
                     cancelled
```

---

## 6.9 Coupon States

```
draft → active → paused → archived
            |
         expired (past expiry date)
            |
         exhausted (usage limit reached)
```

---

## 6.10 Staff Member States

```
invited → active → removed
    |
expired (invitation not accepted in 48 hours)
```

---

## 6.11 Module States (per business installation)

```
installable → installed(pending_config) → active → suspended → uninstalled
```

- `installable`: Available but not yet installed
- `installed(pending_config)`: Installed but requires configuration before active (e.g., Payments installed but Razorpay not connected)
- `active`: Fully configured and contributing features
- `suspended`: Temporarily deactivated; data preserved
- `uninstalled`: Deactivated; data enters 30-day grace period before hard delete

---

## 6.12 Review States

```
pending → submitted → published
                          |
                       flagged → removed
                          |
                       restored
```

---

## 6.13 Customer States (within a business)

```
lead → active → lapsed → blocked
```

- `lead`: Has contacted but hasn't completed a transaction
- `active`: Has completed at least one transaction in the last 90 days
- `lapsed`: No transaction in 90+ days; target for win-back campaigns
- `blocked`: Merchant has blocked this customer from ordering/booking

---

## 6.14 Subscription States (Business-to-Customer)

```
active → paused → cancelled → expired
    |
past_due (payment failed; grace period) → cancelled (after grace period)
```

---

## 6.15 AI Employee States

```
inactive → configuring → active → paused → error
```

- `inactive`: Module installed but not yet configured/activated
- `configuring`: Setup in progress (API connections, FAQ entries, test mode)
- `active`: Running and handling interactions
- `paused`: Temporarily deactivated by merchant; still installed
- `error`: Integration failure (e.g., WhatsApp API disconnected); merchant notified

---

# PART 7 — NOTIFICATION SYSTEM

## 7.1 Notification Channels

| Channel | Description | Use Cases |
|---------|-------------|-----------|
| **In-App** | Notification bell in merchant dashboard; toast notifications | All operational events; real-time |
| **Push Notification** | Mobile push (via platform's mobile app) | Urgent events: new order, new booking |
| **WhatsApp** | Via WhatsApp Business API | Customer-facing confirmations; merchant alerts for urgent items |
| **SMS** | Fallback when WhatsApp unavailable | Order/booking confirmations to customers |
| **Email** | For longer communications, invoices, reports | Invoices, weekly reports, critical account alerts |

### Channel Priority by Event Type

| Event Type | In-App | Push | WhatsApp | SMS | Email |
|------------|--------|------|----------|-----|-------|
| New Order | Yes | Yes | Optional | — | — |
| Order Status Update | Yes | Yes | Yes (customer) | Fallback | — |
| New Booking | Yes | Yes | Optional | — | — |
| Booking Reminder | Yes | Yes | Yes (customer) | Fallback | — |
| Invoice Sent | Yes | — | Yes | — | Yes |
| Payment Received | Yes | — | Yes (customer) | — | — |
| Campaign Launched | Yes | — | — | — | — |
| Review Received | Yes | — | — | — | — |
| Low Stock Alert | Yes | Yes | — | — | — |
| AI Escalation | Yes | Yes | — | — | — |
| Business Health Alert | Yes | — | — | — | Weekly email |
| Staff Invitation | — | — | Yes | Yes | — |
| Security Alert | Yes | Yes | — | — | Yes |
| Subscription Renewal | Yes | — | — | — | Yes (7 days before) |
| Trust Score Change | Yes | — | — | — | — |

---

## 7.2 Merchant Notifications — Complete Trigger List

**Order Notifications:**
- New order received — immediate, all channels
- Order payment confirmed — immediate, in-app + push
- Order cancelled by customer — immediate, in-app + push
- Order approaching timeout (10 min before auto-cancel) — push + in-app
- Refund processed — in-app

**Booking Notifications:**
- New booking request — immediate, push + in-app
- Booking reminder: 1 hour before — push + in-app
- Booking cancellation by customer — immediate, push + in-app
- Booking reschedule request — immediate, push + in-app
- No-show marked — in-app (confirmation to merchant after marking)

**Inventory Notifications:**
- Product low stock (crosses threshold) — push + in-app
- Product out of stock (reaches zero) — push + in-app
- Product auto-hidden (when out of stock auto-hide enabled) — in-app

**Review Notifications:**
- New review received — in-app + email digest
- Review flagged (now in moderation) — in-app

**Marketing Notifications:**
- Campaign sending completed — in-app
- Coupon approaching expiry (3 days before) — in-app
- Coupon exhausted (usage limit reached) — in-app

**Financial Notifications:**
- Payment received (from customer) — in-app
- Settlement processed (payout from Razorpay) — in-app + email
- Payment failed (for subscription or recurring) — push + email
- Invoice overdue (customer hasn't paid) — in-app + email
- Invoice paid — in-app

**Staff Notifications:**
- Staff invitation accepted — in-app
- Staff removed from another device — in-app

**AI Employee Notifications:**
- AI escalation (AI couldn't handle a message) — push + in-app
- AI report available (daily summary) — in-app
- AI error (integration broken) — push + in-app + email

**Platform / Account Notifications:**
- Subscription renewal upcoming (7 days before) — email + in-app
- Subscription payment failed — push + email
- Business verification update (approved/rejected) — push + email
- Trust Score significant change (±10 points) — in-app
- New staff login from new device — in-app + email
- Suspicious activity detected — push + email

**AI Business Analyst Notifications (H3):**
- Weekly performance digest — email + in-app card
- Anomaly detected ("Your Tuesday revenue is 40% below your average") — push + in-app

---

## 7.3 Customer Notifications — Complete Trigger List

**Order Notifications (to Customer):**
- Order placed confirmation — WhatsApp + SMS fallback
- Order accepted by merchant — WhatsApp (includes estimated time)
- Order out for delivery — WhatsApp (includes tracking link)
- Order delivered — WhatsApp
- Order cancelled — WhatsApp (includes reason + refund info if applicable)
- Order rejected — WhatsApp (includes reason)
- Refund initiated — WhatsApp ("Your refund of ₹X has been initiated")

**Booking Notifications (to Customer):**
- Booking confirmed — WhatsApp (includes date, time, cancellation link)
- Booking reminder: 24 hours before — WhatsApp
- Booking reminder: 2 hours before — WhatsApp
- Booking rescheduled — WhatsApp (includes new time, old time, reason)
- Booking cancelled by merchant — WhatsApp (includes reason, refund info if applicable)

**Queue/Appointment Notifications (to Customer):**
- Queue position confirmation (join queue) — WhatsApp
- "Your turn is approaching" (2–3 people ahead) — WhatsApp
- "You are next" — WhatsApp
- Appointment complete — WhatsApp (triggers review request)

**Review Notifications (to Customer):**
- Review request (2 hours post-order/booking) — WhatsApp
- Review reminder (2 days after request if not submitted) — WhatsApp

**Loyalty Notifications (to Customer):**
- Points earned (after qualifying transaction) — WhatsApp
- Tier upgrade — WhatsApp + in-app (if customer account exists)
- Points expiring soon (30 days before expiry) — WhatsApp

**Marketing Notifications (to Customer):**
- Campaign message received — WhatsApp / Email (per campaign channel)
- Explicitly opt-in; opt-out respected via unsubscribe mechanism on every message

---

## 7.4 Admin Notifications

- New business pending verification — in-app (admin) + email
- Business verification overdue (>48h in queue) — in-app (admin)
- Business flagged for fraud/anomaly — push (admin) + email
- Review flagged for moderation — in-app (admin)
- Support ticket escalated — push (admin) + email
- Failed events in dead letter queue — in-app (platform health)
- Platform error rate threshold crossed — push + email
- AI quality alert (error rate above threshold) — in-app (admin)

---

## 7.5 Notification Behavior Rules

1. **Opt-out respected:** Every customer-facing notification includes an easy opt-out mechanism. Opted-out customers are not messaged even for order confirmations (except WhatsApp reply-based orders where the customer initiated contact).

2. **DND compliance:** WhatsApp broadcast campaigns respect TRAI DND registry automatically. Transactional messages (order confirmations, OTPs) are DND-exempt.

3. **Frequency capping:** Marketing notifications to customers: max 2 per week per business. AI module recommendations to merchant: max 1 per week.

4. **Notification preference inheritance:** If a merchant disables "push" for "new order," that applies to all users on their business. Individual staff can further restrict their personal notification preferences.

5. **Deduplication:** If a merchant takes action on an order within 30 seconds of receiving the notification, the notification is marked as resolved and doesn't generate a follow-up.

6. **Message templates:** All WhatsApp messages use pre-approved Meta message templates for customer-facing notifications. Merchants cannot send freeform WhatsApp messages to opted-out customers.

7. **Language:** Default notification language follows the merchant's configured language preference. Customer-facing notifications can be in Tamil, Hindi, or English based on the customer's phone region or explicit preference.

---

# PART 8 — SETTINGS ARCHITECTURE

## 8.1 Settings Hierarchy

Settings are organized in three tiers:
- **Tier 1 — Business Settings** (per-business, owner/manager)
- **Tier 2 — Platform Settings** (global, admin-only)
- **Tier 3 — User Settings** (per-user, any role)

---

## 8.2 Tier 1: Business Settings (Complete)

### Group: Business Info
| Setting | Type | Who Can Change | Description |
|---------|------|----------------|-------------|
| Business Display Name | Text | Owner, Manager | Publicly shown name |
| Business Legal Name | Text | Owner | For invoices and verification |
| Business Category | Select | Owner | Changes default module suggestions |
| Business Sub-category | Select | Owner, Manager | Secondary category |
| Business Description | Rich text (limited) | Owner, Manager | Shown on storefront and marketplace |
| Primary Phone | Phone | Owner | Contact number |
| Secondary Phone | Phone | Owner, Manager | Backup contact |
| Business Email | Email | Owner | Contact email |
| Social links | Text fields | Owner, Manager | Instagram, Facebook, Twitter, YouTube |
| Business Logo | Image upload | Owner, Manager | PNG/JPG, min 200×200px |
| Business Cover Image | Image upload | Owner, Manager | Min 1200×400px |

### Group: Locations
| Setting | Type | Who Can Change | Description |
|---------|------|----------------|-------------|
| Location Name | Text | Owner, Manager | e.g., "Main Branch" |
| Address | Text (structured) | Owner, Manager | Street, area, city, pincode |
| Geo Coordinates | Auto-detect or manual | Owner, Manager | For map display and delivery radius |
| Service Radius | Km (1–50) | Owner, Manager | Max delivery distance |
| Location Phone | Phone | Owner, Manager | Per-location contact |
| Is Primary | Toggle | Owner | Which location is shown by default |
| Add New Location | Action | Owner | Adds a location (multi-branch) |

### Group: Business Hours
| Setting | Type | Who Can Change | Description |
|---------|------|----------------|-------------|
| Daily Hours | Time range per day | Owner, Manager | Open/close times per day of week |
| Day Off | Toggle per day | Owner, Manager | Mark entire day as closed |
| Holiday Closures | Date picker + label | Owner, Manager | Specific dates the business is closed |
| Break Times | Time range | Owner, Manager | Mid-day break periods |
| Same hours for all days | Quick toggle | Owner, Manager | Copy Monday hours to all days |

### Group: Branding
| Setting | Type | Who Can Change | Description |
|---------|------|----------------|-------------|
| Brand Color | Color picker | Owner, Manager | Primary brand color (applied to storefront) |
| Font Theme | Select (3 options) | Owner, Manager | Modern / Warm / Bold |
| Storefront Theme | Select (3–5 themes) | Owner, Manager | Full visual theme for the storefront |

### Group: Payments
| Setting | Type | Who Can Change | Description |
|---------|------|----------------|-------------|
| Connected Gateway | Display + disconnect | Owner | Razorpay account linked |
| Accepted Methods | Toggles | Owner | UPI, Cards, Wallets, Net Banking |
| Cash Accepted | Toggle | Owner | Whether cash on delivery is an option |
| Default Payment Mode | Select | Owner | Online payment required / COD default / Both |
| Payout Schedule | Select (daily/weekly) | Owner | When Razorpay pays out to bank account |

### Group: Taxes
| Setting | Type | Who Can Change | Description |
|---------|------|----------------|-------------|
| Default Tax Rate | % input | Owner | Applied to all products unless overridden |
| Tax Inclusive Pricing | Toggle | Owner | Whether displayed prices include or exclude tax |
| Business GSTIN | Text | Owner | GST registration number |
| State (for GST computation) | Select | Owner | Determines CGST/SGST vs. IGST |
| Tax-exempt categories | Multi-select | Owner | Product categories exempt from tax |

### Group: Delivery (if delivery module installed)
| Setting | Type | Who Can Change | Description |
|---------|------|----------------|-------------|
| Delivery Enabled | Toggle | Owner, Manager | Turn delivery on/off |
| Delivery Zones | Zone editor | Owner, Manager | Geographic zones with per-zone fees |
| Delivery Fee | ₹ input | Owner, Manager | Flat fee or distance-based |
| Free Delivery Threshold | ₹ input | Owner, Manager | Order value above which delivery is free |
| Estimated Delivery Time | Text | Owner, Manager | Shown at checkout ("30–45 min") |
| Max Delivery Distance | Km | Owner, Manager | Hard limit for delivery |
| Self-pickup Enabled | Toggle | Owner, Manager | Whether customers can pick up in person |

### Group: Orders
| Setting | Type | Who Can Change | Description |
|---------|------|----------------|-------------|
| Auto-accept Orders | Toggle | Owner, Manager | Skip the "accept" step and auto-confirm |
| Order Acceptance Timeout | Minutes (5–60) | Owner, Manager | Auto-cancel if not accepted within this time |
| Minimum Order Value | ₹ input | Owner, Manager | Reject orders below this value |
| Special Instructions | Toggle | Owner, Manager | Allow/disallow customer instruction field |
| Order Scheduling | Toggle | Owner, Manager | Allow customers to schedule future orders |
| Max Advance Order Days | Days (1–30) | Owner, Manager | How far ahead customers can schedule |

### Group: Booking Policies (if booking module installed)
| Setting | Type | Who Can Change | Description |
|---------|------|----------------|-------------|
| Instant Booking | Toggle | Owner, Manager | Auto-confirm vs. require merchant approval |
| Cancellation Policy | Select | Owner, Manager | Free cancel (X hours), partial refund, no refund |
| Reschedule Policy | Select | Owner, Manager | Allow/restrict and X-hour window |
| Advance Booking Window | Days | Owner, Manager | How far ahead bookings can be made |
| Minimum Notice Period | Hours | Owner, Manager | Shortest notice required for a booking |
| Buffer Time | Minutes | Owner, Manager | Gap between consecutive bookings |
| Deposit Required | Toggle + % | Owner, Manager | Require upfront payment at booking |

### Group: Website & Storefront (if website module installed)
| Setting | Type | Who Can Change | Description |
|---------|------|----------------|-------------|
| Subdomain | Text (current: {slug}) | Owner | Platform subdomain |
| Custom Domain | Text + verify | Owner | Connect owned domain |
| Page Ordering | Drag list | Owner, Manager | Order of pages in nav |
| WhatsApp Button | Toggle | Owner, Manager | Show/hide WhatsApp floating button |
| Cookie Banner | Toggle | Owner | Show/hide cookie consent notice |
| Google Analytics ID | Text | Owner, Manager | For third-party analytics tracking |

### Group: Marketplace
| Setting | Type | Who Can Change | Description |
|---------|------|----------------|-------------|
| Marketplace Visibility | Toggle | Owner | Opt in/out of marketplace discovery |
| Featured Products | Multi-select | Owner, Manager | Products highlighted on marketplace listing |
| Marketplace Category Tags | Multi-select | Owner, Manager | Tags that improve discoverability |

### Group: AI Employees (if any AI module installed)
| Setting | Type | Who Can Change | Description |
|---------|------|----------------|-------------|
| AI Active Hours | Time range | Owner, Manager | When AI employees operate |
| Default Escalation Behavior | Select | Owner, Manager | Escalate immediately vs. try to respond then escalate |
| AI Response Language | Select | Owner, Manager | Tamil/Hindi/English/Auto |
| AI Tone | Select | Owner, Manager | Formal / Friendly / Traditional |

### Group: Notifications
| Setting | Type | Who Can Change | Description |
|---------|------|----------------|-------------|
| New Order Sound | Toggle | Owner, Manager | Chime when new order arrives |
| Channel per Event | Matrix toggles | Owner, Manager | Per event type × channel on/off |
| Customer Notification Templates | Text editor | Owner, Manager | Customize message templates |
| Review Request Delay | Hours (1–24) | Owner, Manager | How long after transaction to send review request |
| Marketing Frequency Cap | Checkbox | Owner | Enforce platform-recommended weekly limits |

### Group: Staff & Roles
| Setting | Type | Who Can Change | Description |
|---------|------|----------------|-------------|
| Permission Templates | Editor | Owner | Create/edit named permission bundles |
| Require approval to join | Toggle | Owner | Staff invitation requires additional confirmation |

### Group: Integrations
| Setting | Type | Who Can Change | Description |
|---------|------|----------------|-------------|
| WhatsApp Business API | Connect | Owner | For AI WhatsApp Manager module |
| Google Business Profile | Connect | Owner | Sync hours, updates |
| Meta (Facebook/Instagram) | Connect | Owner | For social campaign publishing |
| Webhooks | URL + events | Owner, Manager | Push platform events to external systems |
| API Keys | Generate + manage | Owner | For Developer API access (H4) |

### Group: Security
| Setting | Type | Who Can Change | Description |
|---------|------|----------------|-------------|
| Primary Phone | Update (OTP verified) | Owner | Owner's login phone number |
| Active Sessions | List + revoke | Owner | All devices with active sessions |
| Two-Factor Authentication | Toggle | Owner | Additional OTP on sign-in from new device |
| Session Timeout | Select | Owner | Auto-logout after X hours of inactivity |

### Group: Billing (Platform Subscription)
| Setting | Type | Who Can Change | Description |
|---------|------|----------------|-------------|
| Current Plan | Display | Owner | Name, price, features, renewal date |
| Change Plan | Action | Owner | Upgrade/downgrade |
| Add-on Modules | List + remove | Owner | Active add-ons with individual prices |
| Payment Method | Card/UPI on file | Owner | Update method for subscription billing |
| Invoice History | List | Owner | Past invoices downloadable as PDF |
| Cancel Subscription | Danger action | Owner | Cancels at end of current billing period |

### Group: Danger Zone
| Setting | Type | Who Can Change | Description |
|---------|------|----------------|-------------|
| Export All Data | Action (email delivery) | Owner | Full data export (JSON/CSV) |
| Delete All Customer Data | Action (GDPR) | Owner | Anonymizes customer records |
| Transfer Ownership | Action | Owner | Transfer to another member |
| Close Business | Action | Owner | Archives business; all staff lose access; data retained 2 years |

---

## 8.3 Tier 2: Platform Settings (Admin Only)

| Setting Group | Settings Include |
|---------------|------------------|
| Module Registry | Add module, enable/disable globally, set module version |
| Business Types | Add business type, edit default module bundle, edit onboarding schema |
| Feature Flags | Per-business, per-city, per-plan, or global feature enables |
| Trust Score Engine | Weight configuration per signal, recomputation frequency, anomaly thresholds |
| Marketplace Config | Featured section rules, category management, search ranking weights |
| Platform Pricing | Subscription plan configurations, add-on module pricing, promo codes |
| AI Configuration | Default confidence thresholds, language model version per module |
| Support Config | SLA targets, auto-assignment rules, escalation paths |
| Notification Templates | Platform-level default templates for each notification type |
| Maintenance Mode | Enable/disable with custom message for merchant dashboard |

---

## 8.4 Tier 3: User Settings (Per User)

| Setting | Description |
|---------|-------------|
| Display Name | How name appears on internal notes and audit log |
| Profile Photo | Avatar shown in dashboard (initials-based if not uploaded) |
| Notification Preferences | Which in-app and push notifications to receive personally |
| Dashboard Language | UI language preference (English / Tamil / Hindi) |
| Dashboard Theme | Light / Dark (personal preference, not business-level) |
| Default View | Whether to open on Dashboard or Operations page on login |
| Timezone | Display timezone (defaults to business location) |

---

# PART 9 — PLATFORM EVENTS CATALOG

## 9.1 Event Naming Convention

Format: `{domain}.{entity}.{verb}` (past tense)

Examples: `order.created`, `booking.confirmed`, `ai.whatsapp.escalation.created`

All events follow the `BusinessEvent` shape from the Business Kernel Specification with fields: `id` (ULID), `businessId`, `type` (event name), `payload`, `emittedByModule`, `occurredAt`, `causationId`, `correlationId`.

---

## 9.2 Complete Event Catalog

### Business Domain
| Event | Emitted By | Key Payload Fields |
|-------|------------|-------------------|
| `business.created` | kernel | businessId, businessType, ownerId |
| `business.profile.updated` | business-profile | businessId, changedFields |
| `business.hours.updated` | business-profile | businessId, locationId, newHours |
| `business.location.added` | business-profile | businessId, locationId |
| `business.location.updated` | business-profile | businessId, locationId |
| `business.verification.requested` | business-passport | businessId, documentType |
| `business.verification.approved` | kernel (admin action) | businessId, verificationLevel |
| `business.verification.rejected` | kernel (admin action) | businessId, reason |
| `business.status.changed` | kernel (admin action) | businessId, from, to, reason, adminId |
| `business.visibility.changed` | kernel | businessId, from, to |
| `business.trust_score.updated` | trust-score | businessId, newScore, previousScore, breakdown |
| `business.media.uploaded` | business-profile | businessId, assetId, purpose |
| `business.closed` | kernel | businessId, ownerId, reason |

### Catalog Domain
| Event | Emitted By | Key Payload Fields |
|-------|------------|-------------------|
| `catalog.product.created` | catalog-orders | businessId, productId, name, price |
| `catalog.product.updated` | catalog-orders | businessId, productId, changedFields |
| `catalog.product.published` | catalog-orders | businessId, productId |
| `catalog.product.hidden` | catalog-orders | businessId, productId |
| `catalog.product.out_of_stock` | catalog-orders or inventory | businessId, productId |
| `catalog.product.restocked` | inventory | businessId, productId, newStock |
| `catalog.product.archived` | catalog-orders | businessId, productId |
| `catalog.category.created` | catalog-orders | businessId, categoryId, name |

### Order Domain
| Event | Emitted By | Key Payload Fields |
|-------|------------|-------------------|
| `order.created` | catalog-orders | businessId, orderId, customerId, items, totalAmount, paymentMethod |
| `order.accepted` | catalog-orders | businessId, orderId, preparationMinutes |
| `order.rejected` | catalog-orders | businessId, orderId, reason |
| `order.preparing` | catalog-orders | businessId, orderId |
| `order.ready` | catalog-orders | businessId, orderId |
| `order.out_for_delivery` | delivery | businessId, orderId, deliveryPartnerId |
| `order.delivered` | delivery or catalog-orders | businessId, orderId, completedAt |
| `order.cancelled` | catalog-orders | businessId, orderId, cancelledBy, reason |
| `order.expired` | kernel (timeout worker) | businessId, orderId |
| `order.refunded` | payments | businessId, orderId, refundAmount, refundType |

### Booking Domain
| Event | Emitted By | Key Payload Fields |
|-------|------------|-------------------|
| `booking.created` | booking-calendar | businessId, bookingId, customerId, serviceId, startTime, endTime |
| `booking.confirmed` | booking-calendar | businessId, bookingId |
| `booking.rejected` | booking-calendar | businessId, bookingId, reason |
| `booking.rescheduled` | booking-calendar | businessId, bookingId, oldTime, newTime |
| `booking.cancelled` | booking-calendar | businessId, bookingId, cancelledBy, reason |
| `booking.checked_in` | booking-calendar | businessId, bookingId |
| `booking.completed` | booking-calendar | businessId, bookingId |
| `booking.no_show` | booking-calendar | businessId, bookingId |
| `booking.reminder.sent` | whatsapp-notifications | businessId, bookingId, channel |

### Appointment Domain
| Event | Emitted By | Key Payload Fields |
|-------|------------|-------------------|
| `appointment.queued` | appointments | businessId, appointmentId, customerId, queuePosition |
| `appointment.called` | appointments | businessId, appointmentId |
| `appointment.checked_in` | appointments | businessId, appointmentId |
| `appointment.completed` | appointments | businessId, appointmentId |
| `appointment.cancelled` | appointments | businessId, appointmentId, reason |
| `appointment.no_show` | appointments | businessId, appointmentId |

### Payment Domain
| Event | Emitted By | Key Payload Fields |
|-------|------------|-------------------|
| `payment.initiated` | payments | businessId, paymentId, amount, customerId, source |
| `payment.completed` | payments | businessId, paymentId, amount, method, gatewayRef |
| `payment.failed` | payments | businessId, paymentId, reason, failureCode |
| `payment.refunded` | payments | businessId, paymentId, refundAmount, refundId |
| `payment.settlement.received` | payments | businessId, settlementId, amount, periodFrom, periodTo |
| `payment.link.created` | payments | businessId, linkId, amount, expiresAt |
| `payment.link.paid` | payments | businessId, linkId, paymentId |
| `subscription.payment.succeeded` | subscriptions | businessId, subscriptionId, amount |
| `subscription.payment.failed` | subscriptions | businessId, subscriptionId, reason |

### Invoice Domain
| Event | Emitted By | Key Payload Fields |
|-------|------------|-------------------|
| `invoice.created` | invoicing | businessId, invoiceId, customerId, amount, dueDate |
| `invoice.sent` | invoicing | businessId, invoiceId, channel |
| `invoice.paid` | invoicing | businessId, invoiceId, paymentId |
| `invoice.overdue` | kernel (scheduler) | businessId, invoiceId, dueSince |
| `invoice.cancelled` | invoicing | businessId, invoiceId |
| `credit_note.created` | invoicing | businessId, creditNoteId, originalInvoiceId |

### Customer Domain
| Event | Emitted By | Key Payload Fields |
|-------|------------|-------------------|
| `customer.created` | crm | businessId, customerId, phone |
| `customer.updated` | crm | businessId, customerId, changedFields |
| `customer.tagged` | crm | businessId, customerId, tags |
| `customer.segment.entered` | crm | businessId, customerId, segmentId |
| `customer.segment.exited` | crm | businessId, customerId, segmentId |
| `customer.blocked` | crm | businessId, customerId |
| `customer.birthday` | crm | businessId, customerId (triggered annually) |

### Review Domain
| Event | Emitted By | Key Payload Fields |
|-------|------------|-------------------|
| `review.requested` | reviews | businessId, reviewRequestId, customerId, orderId |
| `review.submitted` | reviews | businessId, reviewId, customerId, rating, hasText, hasPhoto |
| `review.published` | reviews | businessId, reviewId |
| `review.responded` | reviews | businessId, reviewId, responseLength |
| `review.flagged` | reviews | businessId, reviewId, flagReason |
| `review.removed` | kernel (admin action) | businessId, reviewId, adminId, reason |

### Inventory Domain
| Event | Emitted By | Key Payload Fields |
|-------|------------|-------------------|
| `inventory.stock.updated` | inventory | businessId, productId, variantId, delta, reason, newLevel |
| `inventory.stock.low` | inventory | businessId, productId, currentLevel, threshold |
| `inventory.stock.zero` | inventory | businessId, productId |
| `inventory.stock.replenished` | inventory | businessId, productId, addedQuantity, newLevel |

### Marketing Domain
| Event | Emitted By | Key Payload Fields |
|-------|------------|-------------------|
| `campaign.created` | marketing | businessId, campaignId, channel, audienceSize |
| `campaign.launched` | marketing | businessId, campaignId, scheduledAt |
| `campaign.message.sent` | marketing | businessId, campaignId, customerId, channel |
| `campaign.message.delivered` | marketing | businessId, campaignId, customerId |
| `campaign.message.opened` | marketing | businessId, campaignId, customerId |
| `campaign.completed` | marketing | businessId, campaignId, stats |
| `coupon.created` | marketing | businessId, couponId, code, discountType |
| `coupon.applied` | catalog-orders | businessId, couponId, orderId, discountAmount |
| `coupon.exhausted` | marketing | businessId, couponId |

### Loyalty Domain
| Event | Emitted By | Key Payload Fields |
|-------|------------|-------------------|
| `loyalty.points.earned` | loyalty | businessId, customerId, points, reason, balance |
| `loyalty.points.redeemed` | loyalty | businessId, customerId, points, orderId, balance |
| `loyalty.points.expired` | loyalty | businessId, customerId, points |
| `loyalty.tier.upgraded` | loyalty | businessId, customerId, from, to |

### Staff Domain
| Event | Emitted By | Key Payload Fields |
|-------|------------|-------------------|
| `staff.invited` | staff | businessId, memberId, phone, role |
| `staff.joined` | staff | businessId, memberId, userId |
| `staff.role.changed` | staff | businessId, memberId, fromRole, toRole |
| `staff.permissions.updated` | staff | businessId, memberId, changedGrants |
| `staff.removed` | staff | businessId, memberId, removedBy |
| `staff.schedule.updated` | staff | businessId, memberId, newSchedule |

### Delivery Domain
| Event | Emitted By | Key Payload Fields |
|-------|------------|-------------------|
| `delivery.assigned` | delivery | businessId, orderId, deliveryPartnerId |
| `delivery.picked_up` | delivery | businessId, orderId, pickedUpAt, partnerId |
| `delivery.out_for_delivery` | delivery | businessId, orderId |
| `delivery.delivered` | delivery | businessId, orderId, deliveredAt, proofAssetId |
| `delivery.failed` | delivery | businessId, orderId, reason |
| `delivery.returned` | delivery | businessId, orderId |

### AI Domain
| Event | Emitted By | Key Payload Fields |
|-------|------------|-------------------|
| `ai.whatsapp.conversation.started` | ai-whatsapp-manager | businessId, conversationId, customerId |
| `ai.whatsapp.order.created` | ai-whatsapp-manager | businessId, orderId, conversationId |
| `ai.whatsapp.escalation.created` | ai-whatsapp-manager | businessId, conversationId, reason, confidence |
| `ai.whatsapp.conversation.handoff` | ai-whatsapp-manager | businessId, conversationId, staffId |
| `ai.content.created` | ai-content-creator | businessId, contentId, contentType |
| `ai.escalation.resolved` | any-ai-module | businessId, escalationId, resolvedBy |
| `ai.quality.feedback` | any-ai-module | businessId, aiAction, merchantRating |

### Module Domain
| Event | Emitted By | Key Payload Fields |
|-------|------------|-------------------|
| `module.installed` | kernel | businessId, moduleId, version |
| `module.activated` | kernel | businessId, moduleId |
| `module.deactivated` | kernel | businessId, moduleId, reason |
| `module.configuration.updated` | kernel | businessId, moduleId, changedKeys |
| `module.uninstalled` | kernel | businessId, moduleId |

### Website Domain
| Event | Emitted By | Key Payload Fields |
|-------|------------|-------------------|
| `website.published` | website | businessId, isFirstPublish |
| `website.page.created` | website | businessId, pageId, slug |
| `website.page.updated` | website | businessId, pageId |
| `website.domain.connected` | website | businessId, domain |
| `website.theme.changed` | website | businessId, newTheme |

### Platform-Level Events (Kernel)
| Event | Emitted By | Key Payload Fields |
|-------|------------|-------------------|
| `platform.business.created` | kernel | businessId, businessType |
| `platform.subscription.created` | kernel (billing) | businessId, planId |
| `platform.subscription.upgraded` | kernel (billing) | businessId, fromPlan, toPlan |
| `platform.subscription.cancelled` | kernel (billing) | businessId, planId, effectiveDate |
| `platform.admin.action` | kernel (admin audit) | adminId, actionType, targetId, before, after |
| `platform.fraud.flagged` | trust-score / admin | businessId, flagType, severity |
| `platform.error.dead_letter` | event-processor | eventId, eventType, failureCount, lastError |

---

# PART 10 — BUSINESS TYPE CONFIGURATIONS

## 10.1 What Is a Business Type?

A BusinessType is a named bundle of default modules provisioned when a business of that type signs up. It is **data**, not code. Adding a new business type means adding a row to the `business_types` table — not writing a new code path.

Each BusinessType defines:
- `defaultModules`: modules installed and activated at signup
- `requiredModules`: subset that cannot be uninstalled
- `onboardingSchema`: the sequence of setup steps for this type
- `defaultPageSections`: initial website section order
- `customMetadataKeys`: type-specific fields exposed in settings

**The engineering rule:** No module ever checks `if business.type === 'salon'`. All behavior differences live in the BusinessType configuration and module capability checks.

---

## 10.2 Business Type: Home Food / Tiffin Service

**ID:** `home_food` | **Label:** Home Food & Tiffin

### Default Module Bundle
| Module | Required | Reason |
|--------|----------|--------|
| `business-profile` | Yes | Identity |
| `website` | Yes | Public presence |
| `catalog-orders` | Yes | Core selling mechanism |
| `crm` | Yes | Customer records |
| `whatsapp-notifications` | Yes | Primary communication |
| `analytics-basic` | Yes | Basic performance |
| `inventory` | No | Optional stock tracking |
| `delivery` | No | For delivery-enabled sellers |
| `payments` | No | For online payment |

### Onboarding Steps
1. Upload logo and cover photo ("Your food photo is your storefront")
2. Add your first 5 products (meals, tiffin boxes, special items)
3. Set business hours and delivery window
4. Add WhatsApp number (the first order channel)
5. Set your delivery area and fee (if delivery enabled)
6. Preview your storefront
7. Share your link

### Default Page Sections (Storefront)
Hero → Featured Menu → How to Order → About the Chef → Reviews → Contact

### Custom Metadata Keys
- `cuisineType` (Tamil, South Indian, North Indian, Multi-cuisine)
- `dietarySpeciality` (Pure Veg, Non-Veg, Jain-friendly)
- `homeKitchenCertification` (FSSAI license)
- `orderAdvanceHours` (how early to order for next-day)

### Recommended First Add-on Modules
- `payments` (online UPI collection)
- `subscriptions` (monthly tiffin plans)
- `loyalty` (repeat customer retention)
- `ai-whatsapp-manager` (handle WhatsApp order overflow)

---

## 10.3 Business Type: Salon & Beauty

**ID:** `salon` | **Label:** Salon & Spa

### Default Module Bundle
| Module | Required | Reason |
|--------|----------|--------|
| `business-profile` | Yes | Identity |
| `website` | Yes | Public presence |
| `booking-calendar` | Yes | Core service mechanism |
| `crm` | Yes | Client records |
| `staff` | Yes | Multi-stylist management |
| `whatsapp-notifications` | Yes | Booking confirmations |
| `analytics-basic` | Yes | Performance |
| `reviews` | No | Social proof |
| `payments` | No | Online booking deposit |

### Onboarding Steps
1. Add services (haircut, facial, manicure — with prices and durations)
2. Add staff members and their specializations
3. Set working hours and slot duration
4. Set booking policy (instant vs. approval, cancellation window)
5. Configure WhatsApp number for confirmations
6. Preview booking page

### Default Page Sections (Storefront)
Hero → Services & Prices → Meet Our Team → Gallery → Reviews → Book Now CTA → Contact

### Custom Metadata Keys
- `styleSpeciality` (Bridal, Hair Color, Skincare, Nail Art)
- `genderServed` (Ladies, Gents, Unisex)
- `bookingApprovalRequired` (true/false)

### Recommended First Add-on Modules
- `loyalty` (client retention — birthday rewards)
- `subscriptions` (monthly membership plans)
- `ai-appointment-manager` (reduce no-shows)
- `inventory` (product sales tracking)

---

## 10.4 Business Type: Clinic & Healthcare

**ID:** `clinic` | **Label:** Clinic & Healthcare

### Default Module Bundle
| Module | Required | Reason |
|--------|----------|--------|
| `business-profile` | Yes | Identity |
| `website` | Yes | Public presence |
| `appointments` | Yes | Queue management |
| `booking-calendar` | Yes | Advance appointment booking |
| `crm` | Yes | Patient records |
| `staff` | Yes | Doctor/staff management |
| `whatsapp-notifications` | Yes | Appointment confirmations |
| `analytics-basic` | Yes | Performance |
| `payments` | No | Consultation fee collection |
| `invoicing` | No | Receipt generation |

### Onboarding Steps
1. Add consultation types and fees (General, Specialist, Follow-up)
2. Add doctors/staff and their specializations
3. Set consulting hours and slot capacity
4. Set booking policy (advance appointments and walk-in ratio)
5. Add clinic contact and location

### Default Page Sections (Storefront)
Hero → Services & Fees → Meet Our Doctors → Facilities → Reviews → Appointment Booking → Contact

### Custom Metadata Keys
- `specialties` (array: Cardiology, Dermatology, Pediatrics, etc.)
- `languagesSpoken` (array)
- `emergencyServices` (boolean)
- `insuranceAccepted` (array)
- `medicalRegistrationNumber`

### Regulatory Note
Clinics have additional verification requirements for the Business Passport module: Medical Registration Certificate is a required verified document before full marketplace listing.

### Recommended First Add-on Modules
- `business-passport` (medical registration verification)
- `ai-appointment-manager` (optimize queue)
- `ai-receptionist` (H4 — phone appointment booking)

---

## 10.5 Business Type: Coaching & Education

**ID:** `coaching` | **Label:** Coaching & Education

### Default Module Bundle
| Module | Required | Reason |
|--------|----------|--------|
| `business-profile` | Yes | Identity |
| `website` | Yes | Public presence |
| `booking-calendar` | Yes | Class/session booking |
| `crm` | Yes | Student records |
| `whatsapp-notifications` | Yes | Session confirmations |
| `analytics-basic` | Yes | Performance |
| `payments` | No | Fee collection |
| `subscriptions` | No | Course/membership enrollment |

### Onboarding Steps
1. Add courses/subjects (name, description, fee, duration)
2. Set class schedule (recurring slots)
3. Configure batch capacity
4. Set payment and enrollment policy
5. Add instructor profiles (if multiple)

### Custom Metadata Keys
- `subjectsOffered` (array)
- `ageGroups` (Kids, Teens, Adults, Senior)
- `teachingMode` (Offline, Online, Hybrid)
- `certificationsOffered` (boolean + description)
- `boardAffiliation` (CBSE, ICSE, State Board, etc.)

### Recommended Add-ons
- `subscriptions` (course enrollment)
- `loyalty` (sibling discounts, referrals)
- `ai-content-creator` (course descriptions, social content)

---

## 10.6 Business Type: Restaurant / Cafe

**ID:** `restaurant` | **Label:** Restaurant & Cafe

### Default Module Bundle
| Module | Required | Reason |
|--------|----------|--------|
| `business-profile` | Yes | Identity |
| `website` | Yes | Menu and online presence |
| `catalog-orders` | Yes | Online ordering |
| `crm` | Yes | Customer records |
| `whatsapp-notifications` | Yes | Order updates |
| `analytics-basic` | Yes | Performance |
| `delivery` | No | Delivery management |
| `payments` | No | Online payment |
| `inventory` | No | Ingredient tracking |
| `booking-calendar` | No | Table reservations |

### Custom Metadata Keys
- `cuisineType` (array)
- `diningOptions` (Dine-in, Takeaway, Delivery)
- `seatingCapacity`
- `averageCostForTwo` (₹ range)
- `fssaiLicense` (required for verification)
- `alcoholServed` (boolean — affects marketplace category)

### Recommended Add-ons
- `loyalty` (repeat diner rewards)
- `subscriptions` (weekly meal subscriptions)
- `ai-whatsapp-manager` (WhatsApp order management)

---

## 10.7 Business Type: Retail Store / Boutique

**ID:** `retail` | **Label:** Retail & Boutique

### Default Module Bundle
| Module | Required |
|--------|----------|
| `business-profile` | Yes |
| `website` | Yes |
| `catalog-orders` | Yes |
| `inventory` | Yes |
| `crm` | Yes |
| `whatsapp-notifications` | Yes |
| `analytics-basic` | Yes |
| `payments` | No |
| `delivery` | No |

### Custom Metadata Keys
- `productCategories` (Clothing, Electronics, Home Goods, etc.)
- `priceRange` (budget / mid-range / premium)
- `returnsPolicy` (text)
- `warrantyOffered` (boolean)

---

## 10.8 Business Type: Fitness & Wellness

**ID:** `fitness` | **Label:** Gym, Yoga & Fitness

### Default Module Bundle
| Module | Required |
|--------|----------|
| `business-profile` | Yes |
| `website` | Yes |
| `booking-calendar` | Yes |
| `subscriptions` | Yes |
| `crm` | Yes |
| `staff` | Yes |
| `whatsapp-notifications` | Yes |
| `analytics-basic` | Yes |
| `payments` | No |

### Custom Metadata Keys
- `fitnessTypes` (Yoga, CrossFit, Zumba, Swimming, etc.)
- `genderPolicy` (Ladies only, Gents only, Mixed)
- `trainerCertifications` (array)
- `facilityFeatures` (AC, Parking, Locker, Steam, etc.)

---

## 10.9 Business Type: Photography & Creative Services

**ID:** `photography` | **Label:** Photography & Creative

### Default Module Bundle
| Module | Required |
|--------|----------|
| `business-profile` | Yes |
| `website` | Yes |
| `booking-calendar` | Yes |
| `inquiry-leads` | Yes |
| `crm` | Yes |
| `whatsapp-notifications` | Yes |
| `payments` | No |
| `invoicing` | No |

### Custom Metadata Keys
- `photographyTypes` (Wedding, Corporate, Portrait, Product, etc.)
- `equipmentBrands`
- `deliveryTimeline` (edited photos delivered in X days)
- `packageNames` (array)

---

## 10.10 Business Type: Home Services

**ID:** `home_services` | **Label:** Home Services (Plumber, Electrician, Carpenter)

### Default Module Bundle
| Module | Required |
|--------|----------|
| `business-profile` | Yes |
| `website` | Yes |
| `inquiry-leads` | Yes |
| `crm` | Yes |
| `whatsapp-notifications` | Yes |
| `booking-calendar` | No |
| `invoicing` | No |
| `payments` | No |

### Custom Metadata Keys
- `serviceTypes` (Plumbing, Electrical, Carpentry, Painting, etc.)
- `serviceArea` (array of areas/localities served)
- `warrantyOffered` (boolean + description)
- `emergencyAvailable` (24/7 boolean)

---

## 10.11 Business Type: Events & Catering

**ID:** `events_catering` | **Label:** Events & Catering

### Default Module Bundle
| Module | Required |
|--------|----------|
| `business-profile` | Yes |
| `website` | Yes |
| `inquiry-leads` | Yes |
| `crm` | Yes |
| `invoicing` | Yes |
| `whatsapp-notifications` | Yes |
| `booking-calendar` | No |
| `payments` | No |

### Custom Metadata Keys
- `eventTypes` (Wedding, Corporate, Birthday, etc.)
- `cateringCapacity` (minimum/maximum guests)
- `cuisineOffered` (array)
- `venuePartners` (whether they also provide venues)
- `fssaiLicense`

---

## 10.12 Adding New Business Types

New business types require:
1. A new row in the `business_types` table
2. `defaultModules` array (from existing modules)
3. `onboardingSchema` JSON (step sequence)
4. `defaultPageSections` array (section order for website)
5. `customMetadataKeys` (new JSONB keys for this type)

**No new code required.** No new modules required (unless the type needs a genuinely new capability). This is what makes "unlimited industries" an honest architectural claim.

---

# APPENDICES

## Appendix A: Platform Subscription Plans (Reference)

| Plan | Price | Target Business | Included Modules |
|------|-------|-----------------|------------------|
| **Starter** | Rs. 499/mo | New businesses, 0–50 orders/month | business-profile, website, catalog-orders, crm, whatsapp-notifications, analytics-basic |
| **Growth** | Rs. 1,499/mo | Active businesses, 50–500 orders/month | All Starter + payments, delivery, reviews, marketing, inventory |
| **Pro** | Rs. 3,999/mo | Established businesses, 500+ orders | All Growth + staff, subscriptions, loyalty, analytics-advanced + 2 AI modules |
| **Scale** | Custom | Multi-location, high-volume | All modules, custom AI configuration, dedicated support |

**Add-on Modules:** Any module not included in the base plan can be added for Rs. 199–Rs. 999/month depending on the module.

**Note:** Plan structure is governed by platform configuration. The above is illustrative.

---

## Appendix B: Data Privacy & Customer Ownership

### Horizon 1 & 2 (Merchant-Owned Customers)
- Customer data (name, phone, order history) is owned by the merchant's business
- Platform does not share customer data between businesses
- Customer can request deletion from any business; merchant processes the request
- Platform retains only anonymized transaction records for aggregate analytics

### Horizon 3+ (Marketplace-Opted-In Businesses)
- Customers who transact through the marketplace explicitly consent to platform-level account storage
- Cross-merchant order history, loyalty points, and recommendations are activated for these customers
- Merchant is clearly informed of this trade-off at the point of marketplace opt-in
- Customer can revoke consent; their cross-merchant data is anonymized
- Merchant's own customer relationship data remains merchant-owned even after marketplace opt-in

---

## Appendix C: Key Technical Constraints for Product Decisions

These constraints from the Business Kernel Specification directly affect product decisions:

**1. Renderers format; they never compute business rules.**
Product implication: If a UI element needs to show/hide based on a business rule, that rule must be expressed as a `capability` (computed by the kernel), not as logic in the UI component.

**2. Modules never call each other directly — only the event bus.**
Product implication: When designing a feature spanning two modules (e.g., "when a product goes out of stock, pause its associated subscriptions"), the implementation is: inventory emits `inventory.stock.zero`; subscriptions module subscribes and pauses relevant subscriptions. Never a direct function call.

**3. No business-type-specific code in modules.**
Product implication: If a feature behaves differently for a clinic vs. a salon, that difference must be expressed through module configuration or capability checks — not through an `if business.type === 'clinic'` branch inside the module's code.

**4. Customer data ownership boundary is enforced at the schema level.**
Product implication: UI cannot simply "show all customer data from all businesses" before a merchant has opted into marketplace. This is not a display toggle — it's a fundamental data access boundary enforced by RLS policies.

**5. Trust Score is never computed synchronously.**
Product implication: Trust Score always shows a cached value with a `lastComputedAt` timestamp. UI should show this timestamp to communicate that the score is a snapshot, not a live calculation.

**6. Business capabilities are derived, not stored.**
Product implication: "Can this business receive orders?" is never stored as a field. It is computed from `(installedModules, configuration, status)` every time. Product features that gate on this capability must call the capability check function.

---

## Appendix D: Design & Interaction Constants

**The Morning Test:** The dashboard must answer "what happened, what needs attention" without the merchant navigating anywhere.

**The Disappearance Test:** Every screen should result in the merchant thinking about their business, not the software.

**The Motion Test:** If removing an animation and showing the end state loses no user understanding, the animation is cut.

**The Copy Test:** Every label, error message, empty state, button text, and confirmation is written from the merchant's side. "Save changes" not "Submit." "Order placed" not "Your order has been successfully submitted." "No products yet — add your first" not "No data available."

**The Specificity Test:** One true, checkable, specific claim is worth more than five adjectives. "Usually responds in 10 minutes" rather than "lightning-fast responses."

**The Delight Budget:** Exactly two moments in the entire product are allowed genuine expressive warmth — the first time a storefront goes live, and the first order ever received. Everything else is calm and precise.

**Color Discipline:** Signal Indigo (#4A5FE0) appears only on interactive or important elements. Its appearance on a non-interactive element is a product defect, not a style choice.

**Progressive Complexity Discipline:** No merchant ever sees a feature they don't yet need. The interface grows as the business grows. When in doubt: hide it until it's needed, never show it "just in case."

---

*End of Complete Master Product Specification v1.0*

---

**Document Control**

| Version | Date | Changes |
|---------|------|---------|
| 1.0 | July 2026 | Initial complete specification |

**This document is the living single source of truth for the platform. No product feature exists outside this document. No feature may be built without first being defined here. When this document is updated, the change is logged in the Version History above with the specific change noted.**
