# LOCAH — Business Capability Universe

Sep 24, 2026 · @Kausik GH

## 1. Purpose, authority and how to use this doc

This doc is the single canonical map from every selectable business category to the modules, role workspaces, AI employees and integrations LOCAH provides. It exists so that "gyms also need this" is decided once, here, and never re-litigated inside a build prompt.

**Authority.** Proposed as **Doc 13**. For First Launch scope, Docs 12 → 11 → 10 → 09 and the Build Spec still win. This doc governs everything after First Launch. Where a module key here already exists in the Doc 11 module registry (live or deferred), the registry key wins and this doc is corrected.

**ChitBridge.** Chit & Bridge stays a separately deployed product, as Build Spec §9 requires. LOCAH connects to it as a connector actor for business-to-business obligations (§16). LOCAH never copies its rail into the LOCAH database.

**How Claude Code uses it.** Every build packet in §26 cites the sections it implements. No module, role, AI employee or integration is built unless it is listed here first. Category-to-module logic is deterministic code tested by fixtures (§27), not AI.

| Tag | Meaning |
| --- | --- |
| **EXISTS** | Built and verified in First Launch (Completion Report §5) |
| **EXTEND** | Exists; this doc adds depth to it |
| **NEW** | New module, table or surface |
| **FUTURE** | Designed here, not scheduled in §26 |
| **Core** | Switched on by default for the category |
| **Recommended** | Pre-ticked in onboarding step 4; owner can untick |
| **Optional** | Offered, not pre-ticked |
| **P1–P6** | Build phase from §26. P0 = First Launch (done) |

## 2. Non-negotiable design principles

Thirteen rules govern every module in this doc; a feature that breaks one is redesigned, not shipped.

1. **One Business OS, many views.** A vertical is never a separate app. It is category → traits → packs → configured modules, website template and role surfaces, all on one backend.
2. **Category is guidance, not an allowlist.** Any business may enable any module that exists. Categories only decide what is pre-ticked and what the AI suggests.
3. **Traits decide, names don't.** A home baker (made-to-order, WhatsApp orders) and a bakery chain (POS, four outlets) share a category but not a module set. Operating traits (§4.3) drive the mapping.
4. **Deterministic first, AI second.** Module mapping, tax, stock maths, BOM explosion, renewal schedules and prices are code. AI handles language: free-text understanding, drafting and conversation.
5. **AI employees are staff.** They use the same permission engine and audit log as humans, as actor type `ai_employee`. Money movement, refunds, ad spend, deletions and supplier orders above a limit always need owner approval.
6. **One source of truth per data family.** Every connector (Tally, ChitBridge, Meta, Google) declares which system owns which data. No two-way free-for-all.
7. **Build Spec §9 honesty rules apply everywhere.** No fabricated data, no fake features, deferred modules invisible, AI output labelled as a draft until a human accepts it.
8. **Tenant isolation is unchanged.** LOCAH rows stay `business_id = current_business_id()`. Records shared between two businesses live on ChitBridge as per-party copies, never as shared LOCAH rows.
9. **Built for real devices.** POS, the crew app and attendance must work on entry-level Android phones over patchy 4G, with an offline queue.
10. **India-first defaults.** INR, GST, UPI, WhatsApp-first messaging, English + Tamil + Hindi (code-mixed input accepted), DPDP Act consent records.
11. **Every automation is idempotent and visible.** It runs through the existing outbox/jobs kernel, has an idempotency key, shows in the owner's activity log and has an off switch.
12. **The owner never sees JSON.** Build Spec §7 applies to every module's settings, not only the website editor.
13. **Every metered cost is metered.** WhatsApp messages, voice minutes, Maps calls and LLM tokens each get a per-business meter, a cap and honest pass-through pricing.

## 3. Layer model: one Business OS

Every surface — website, WhatsApp, phone, Workspace, crew app, AI employee — calls the same module services. Nothing has its own private copy of orders, bookings or stock.

```mermaid
flowchart TD
  CS[Customer surfaces<br/>Website · Marketplace · WhatsApp · Phone]
  RS[Role surfaces<br/>Workspace · Crew app · POS · KDS]
  AE[AI employees<br/>actor_type ai_employee]
  MS[Module services<br/>orders · bookings · memberships · stock ...]
  CORE[LOCAH Core<br/>business · locations · team · customers]
  AUTO[Automation kernel<br/>outbox · jobs · notifications]
  HUB[Connector hub<br/>WhatsApp · Razorpay · Maps · Tally · Meta]
  CB[ChitBridge rail<br/>supplier network]
  CS --> MS
  RS --> MS
  AE --> MS
  MS --> CORE
  MS --> AUTO
  AUTO --> HUB
  HUB --> CB
```

Humans, AI employees and connectors enter through the same service layer, so permissions, RLS and audit apply identically to all three.

| Layer | Holds | Status | Section |
| --- | --- | --- | --- |
| LOCAH Core | Business, locations, team, customers, website, Marketplace, entitlements | EXISTS | Build Spec |
| Module services | 10 First Launch modules + the NEW modules in §6 | EXTEND | §6 |
| Automation kernel | Outbox, jobs, notification kernel, rules for reminders and renewals | EXISTS, EXTEND | §24 |
| Role surfaces | Workspace (desktop), crew app (mobile PWA), POS, kitchen display, customer portals | EXTEND | §7 |
| AI employees | Tool-using agents with a role, limits and an audit trail | NEW | §8 |
| Connector hub | Adapters with a source-of-truth contract per data family | NEW | §9 |
| Network | Supplier and buyer links over ChitBridge | NEW | §16 |

## 4. Classification: category, subcategory, traits

Every business is described by four fields: a selectable **category** (32 + Other), a **subcategory** (every example from the research list is one), a set of **operating traits**, and an **org shape**. Traits, not names, drive module recommendations.

### 4.1 Picker UX (replaces Build Spec §4 step 1 after First Launch)

- **Search first.** One box: "What kind of business? e.g. meat shop, dental clinic, tiffin service". Matches \~500 subcategory labels plus synonyms (kirana, mess, tiffin, mandapam, PG, kadai, tuition), spelling-tolerant, fully deterministic.
- **Grid second.** 12 most-chosen categories as tiles, then "See all 32".
- **No match.** "Describe it in a sentence" → one AI call proposes category, subcategory and traits → owner confirms. Never auto-saved.
- The First Launch 14-type grid keeps working until the P1 migration; `business_type` stays as the website template key.

### 4.2 Selectable categories

| Key | Category | Subcategories (each selectable) | Default packs (§5) | Website template now → target |
| --- | --- | --- | --- | --- |
| `fresh_grocery` | Fresh food & grocery | Meat shop, butcher, chicken shop, seafood, fish market, fruit shop, vegetable shop, organic produce, grocery / kirana, supermarket, provision store, dry fruits, spices, rice store, dairy / milk, eggs | Commerce, Delivery, Memberships (daily milk) | `retail` → `fresh_store` |
| `home_food` | Home food & packaged food | Home kitchen, pickles & podi, snacks, sweets, home bakery, tiffin / meal subscription, cloud kitchen, homemade chocolates, jams & sauces, millet foods, healthy meals | Commerce (made-to-order), Memberships, Delivery | `home_food` |
| `food_service` | Restaurants, cafés & catering | Restaurant, café, tea shop, juice bar, bakery, pizzeria, fast food, fine dining, food truck, catering, canteen, pub / bar, ice cream, desserts, biryani shop, mess | Food service, Commerce, Delivery, Trade | `restaurant` / `cafe` |
| `retail` | Retail stores | Clothing, footwear, jewellery, cosmetics, stationery, gifts, toys, electronics, mobile store, furniture, home decor, kitchenware, hardware, sports goods, books, optical, pet supplies | Commerce, POS, Delivery | `retail` |
| `fashion_custom` | Fashion, tailoring & handmade | Boutique, tailor, bridal wear, designer label, uniform supplier, embroidery, custom T-shirts, leather goods, bags, handmade crafts | Commerce (made-to-order), Appointments (fittings), Sales & quotes | `retail` → `boutique` |
| `beauty` | Beauty & personal care | Salon, barber, spa, nail studio, makeup artist, bridal makeup, skincare clinic, beauty academy, massage centre, tattoo studio, piercing studio | Appointments, Memberships (packages), POS | `salon` / `spa` |
| `fitness` | Fitness & wellness | Gym, yoga, Pilates, CrossFit, powerlifting, martial arts, dance fitness, personal trainer, nutrition coach, meditation centre, wellness studio | Memberships, Appointments (classes, PT) | `gym` / `studio` |
| `healthcare` | Healthcare & clinics | Hospital, clinic, polyclinic, dental, physiotherapy, diagnostic centre, pharmacy, eye clinic, ENT, dermatology, paediatrics, fertility clinic, home nursing, ambulance service | Health front desk, Commerce (pharmacy), Delivery (sample pickup) | `professional_service` → `clinic` |
| `therapy` | Therapy & counselling | Psychologist, counsellor, therapist, speech therapy, occupational therapy, rehabilitation centre | Appointments (private mode), Memberships (session packages) | `professional_service` → `practice` |
| `education` | Education & tutoring | School, preschool, tuition centre, coaching (NEET / JEE), language school, music school, dance school, coding academy, vocational institute, driving school; tutors: maths, science, German, IELTS, music, art, online educator | Learning, Memberships (fees), Appointments | `education` |
| `professional` | Professional & consulting services | CA, accountant, lawyer, company secretary, tax consultant, management / HR / business consultant, recruitment agency; process, engineering, quality / ISO, environmental, supply-chain consultancy | Sales & quotes, Appointments, Documents | `professional_service` |
| `finance_insurance` | Finance & insurance | Financial adviser, insurance agent, loan consultant, mortgage broker, investment adviser, wealth manager, bookkeeping service | Sales & quotes, Appointments, Documents, Renewal reminders | `professional_service` |
| `real_estate` | Real estate & property | Agency, broker, developer, builder, plots, apartment projects, property management, rental agency, commercial real estate, co-living | Sales & quotes, Projects & listings, Stays (co-living rent) | `real_estate` |
| `design_build` | Architecture, interiors & construction | Architect, interior designer, landscape architect, modular kitchens, renovation, furniture designer; civil, electrical, plumbing, painting, roofing, flooring, fabrication, waterproofing, HVAC contractors | Sales & quotes, Projects, Field service, Procurement | `professional_service` → `portfolio_projects` |
| `home_services` | Home, repair & IT services | Cleaning, pest control, plumber, electrician, appliance repair, AC service, water purifier service, laundry, dry cleaning, housekeeping, gardening; watch / shoe / jewellery / furniture / electronics / machinery repair; computer repair, CCTV installer, networking, printer service, mobile repair | Field service, Appointments, Memberships (AMC), Delivery (laundry) | `professional_service` → `service_business` |
| `automotive` | Automotive | Car dealer, used cars, bike dealer, garage, mechanic, car wash, detailing, tyres, batteries, spare parts, car rental, driver service | Field service (job cards), Commerce (parts), Sales & quotes, Rentals | `retail` → `automotive` |
| `logistics` | Transport, logistics & storage | Courier, packers & movers, trucking, fleet operator, last-mile delivery, warehousing, cold storage, freight forwarding, taxi service, bus operator | Sales & quotes, Delivery & dispatch, Trade | `professional_service` → `logistics` |
| `travel_stay` | Travel, stays & tourism | Hotel, resort, homestay, hostel, villa rental, travel agency, tour operator, adventure tourism, guide, pilgrimage tours | Stays, Sales & quotes (packages) | `hotel` / `homestay` |
| `events` | Events & weddings | Event planner, wedding planner, decorator, mandapam / banquet hall, florist, caterer, DJ, sound & light rental, invitation business | Sales & quotes, Projects (event timeline), Rentals (hall dates) | `professional_service` → `events` |
| `creative` | Photography, media & creative | Wedding / studio / product photographer, videographer, filmmaker, editor, drone; ad agency, digital marketing, SEO, social media, branding, PR, content studio, influencer management; graphic designer, illustrator, artist, animator, UX designer, fashion designer, writer, musician | Sales & quotes, Projects, Appointments, Portfolio | `professional_service` → `portfolio` |
| `creators` | Creators & personal brands | YouTuber, influencer, coach, speaker, author, podcaster, newsletter creator, online educator | Commerce (digital products), Memberships (community), Appointments (1:1) | `professional_service` → `personal_brand` |
| `technology` | Technology & IT services | Software company, SaaS, IT services, web / app development, cybersecurity, cloud consultancy, data & AI consultancy | Sales & quotes, Projects, Memberships (retainers) | `professional_service` |
| `industrial` | Manufacturing & industrial supply | Pumps, valves, motors, bearings, instrumentation, chemicals, lab equipment, safety equipment, panels, automation, machine tools; food / textile / garment / plastics / chemical / pharma / auto-component / machinery / furniture / packaging manufacturer, metal fabrication; process equipment, boilers, compressors, water treatment, conveyors; corrugated boxes, labels, bottles, flexible packaging; printing press, digital printing, signage, flex, engraving, laser cutting | Trade & supply, Sales & quotes, Commerce (B2B catalogue), Recipes / BOM | `retail` → `b2b_catalogue` |
| `trade` | Wholesale, distribution & import/export | FMCG, pharma, food, electrical, building-material and industrial distributors; export house, garment / food / handicraft exporter, machinery importer, trading company | Trade & supply, Delivery & dispatch | `retail` → `b2b_catalogue` |
| `agriculture` | Agriculture & agri services | Farm, organic farm, nursery, dairy farm, poultry farm, fish farm, mushroom farm, hydroponics, agri inputs; tractor rental, irrigation services, farm consultancy, seed supplier, fertiliser dealer, agri-equipment dealer | Commerce, Memberships (produce box), Trade, Rentals | `retail` → `farm` |
| `energy_env` | Energy & environment | Solar installer / EPC, EV charging, battery storage, generator rental, renewable consultancy, waste management, recycling, water treatment, composting, environmental consultancy | Sales & quotes, Projects, Field service (AMC) | `professional_service` |
| `pets` | Pets | Pet shop, grooming, boarding, veterinary clinic, pet training, dog walking, pet food, pet photography | Commerce, Appointments, Stays (boarding), Health front desk (vet) | `retail` / `salon` → `pets` |
| `care` | Child, family & senior care | Daycare, babysitting, activity centre, play school, kids sports, maternity services; elder care, assisted living, caregiver agency | Memberships (fees), Learning, Field service (caregivers) | `education` |
| `rentals_spaces` | Rentals & spaces | Car, bike, camera, tool, construction-equipment, party-equipment, furniture, costume and dress rental; co-working, office rental, meeting rooms, incubator; self-storage, document storage | Rentals, Memberships (desks), Stays | `retail` / `hotel` → `rentals` |
| `security_staffing` | Security, facilities & staffing | Security agency, guards, alarm systems, fire safety; commercial cleaning, maintenance contracts, manpower supply, building management; recruitment, temp staffing, domestic-help agency | Sales & quotes, Memberships (service contracts), Workforce (deployment, attendance) | `professional_service` |
| `labs` | Testing, research & labs | Testing lab, calibration lab, R&D firm, contract research, inspection; material / water / food / environmental testing | Sales & quotes, Field service (sample → report), Documents | `professional_service` |
| `community` | Clubs, communities & nonprofits | Sports / hobby clubs, associations, chambers, member networks; temple service organisations, cultural centres, trusts, community halls; NGO, animal rescue, education NGO, social enterprise, charity | Community & giving, Memberships, Rentals (hall) | `none` → `organisation` |
| `other` | Something else / not sure | Free text → AI proposes, owner confirms | Storefront only until traits are set | `none` |

Franchises, multi-location chains, B2B-only / B2C-only / hybrid, solo / team / enterprise and the "-led" models are not categories. They are traits and org shapes (§22).

### 4.3 Operating traits

Traits start from the subcategory default, are confirmed by at most two onboarding questions (Build Spec §4 rule holds), and are editable later in Settings.

| Trait group | Traits | Switches on (§6 keys) |
| --- | --- | --- |
| Buyer | `b2c`, `b2b` (both = hybrid) | `b2b` → `quotes`, `invoicing` (B2B GST), `ledger`, `trade-network` |
| Offer | `sells_products`, `sells_services`, `sells_access` | products → `offerings-catalog`, `orders`; access → `memberships` |
| How they transact | `order_led`, `booking_led`, `quote_led`, `enquiry_led`, `subscription_led`, `project_led`, `donation_led` | `orders` · `bookings` · `quotes` · `leads` · `memberships` · `projects` · `donations` |
| Booking kind | `appointment`, `table`, `stay`, `class`, `rental`, `site_visit`, `event_date` | `bookings` mode; `stay` → `tasks` (housekeeping); `rental` → handover checklists |
| Fulfilment | `walk_in`, `pickup`, `local_delivery`, `shipping`, `on_site_service`, `digital` | walk-in products → `pos`; walk-in services → `queue`; delivery → `fulfilment` + `dispatch`; on-site → `jobs` |
| Stock | `stock_tracked`, `perishable`, `weight_based`, `variant_based`, `serialised`, `made_to_order`, `ingredient_based` | `inventory` (+ batches, weights, serials); ingredient / made-to-order → `recipes` → `procurement` |
| People | `provider_based`, `field_team`, `shift_staff` | `workforce`, `dispatch`, `attendance` |
| Regulated | `gst_registered`, `composition_scheme`, `food_licensed`, `health_regulated`, `finance_regulated`, `minors_involved` | Invoice mode; `compliance`; AI guardrails; guardian contacts, no marketing to minors |
| Presentation | `portfolio_led`, `digital_only`, `nonprofit` | Portfolio sections; no address on site; `donations` |

**Org shape** (one value): `solo`, `team`, `multi_location`, `franchise_brand`, `franchise_outlet`, `enterprise`. It decides role templates and plan tier, not modules.

### 4.4 Storage and code

- `businesses` gains `category_key`, `subcategory_key`, `org_shape`. New table `business_traits (business_id, trait_key, source: default | owner | ai_suggested_confirmed)`. Existing `business_type` stays as `website_template_key`.
- One versioned registry file owns the taxonomy, synonyms, trait defaults and trait → module rules: `python/core/platform_core/catalog/taxonomy.py`. Frontend reads it through one API endpoint; nothing is hard-coded twice.
- Every subcategory has a fixture asserting its Core / Recommended / Optional module set (§27).

## 5. Capability packs

Fifteen packs group modules by operating model so onboarding, pricing and sales can talk in outcomes ("take orders and payments"), while entitlements stay per module key. A business usually holds 2–4 packs; Storefront is always on.

| Pack | Outcome for the owner | Modules (§6 keys) | Role surfaces | AI employees | Key integrations |
| --- | --- | --- | --- | --- | --- |
| **Storefront** (all) | "I'm online, findable and reachable" | website, marketplace listing, customer-relationships, reviews, messaging, insights, compliance | Owner, manager | Website editor assist, Review Responder | WhatsApp, Google Business Profile |
| **Commerce** | "People can buy from me online and at the counter" | offerings-catalog, orders, payments, inventory, fulfilment, invoicing, pos, ledger, loyalty | Cashier, store keeper | WhatsApp Manager, Inventory Manager | Razorpay, Tally, barcode scanners, thermal printers, shipping aggregator |
| **Food service** | "Orders reach the kitchen and stock follows sales" | Commerce + table bookings, kitchen display, recipes, dine-in QR ordering, procurement | Kitchen, waiter, cashier | WhatsApp Manager, Procurement Planner | Kitchen printer, ChitBridge |
| **Appointments** | "My calendar fills itself and no-shows drop" | offerings-catalog (services), bookings, workforce, queue, memberships (packages) | Front desk, provider | Appointment Manager, Receptionist | Telephony, Google Calendar |
| **Stays & rentals** | "Rooms and assets are booked, paid and turned around" | bookings (date range), payments (deposits), tasks, documents, handover checklists | Front desk, housekeeping | Receptionist | Channel manager (FUTURE) |
| **Memberships** | "Renewals collect themselves" | memberships, attendance, payments, bookings (classes) | Front desk, trainer | Collections Assistant | Razorpay Subscriptions / payment links, access control (FUTURE) |
| **Learning** | "Batches, attendance and fees in one place" | academics, attendance, memberships (fee plans), documents | Teacher, office, guardian & student portal | Receptionist (admissions), Collections Assistant | Meet / Zoom links |
| **Sales & quotes** | "No lead or quote goes cold" | leads, quotes, projects, documents, invoicing, ledger | Sales executive, project lead | Sales Executive | Meta lead ads, e-sign (FUTURE) |
| **Field service** | "Technicians get jobs, customers get updates" | jobs, dispatch, inventory (van stock), memberships (AMC), quotes | Technician, dispatcher | Appointment Manager, Delivery Coordinator | Maps |
| **Delivery & dispatch** | "I can see every delivery live" | fulfilment, dispatch | Delivery partner, dispatcher | Delivery Coordinator | Maps URLs, Routes API, hyperlocal / courier partners |
| **Trade & supply** | "Buying and selling to businesses without phone chaos" | quotes (RFQ), price lists, invoicing (B2B, e-invoice, e-way bill), ledger, procurement, recipes, trade-network | Sales, accountant, store keeper, supplier view | Procurement Planner, Bookkeeper, Sales Executive | ChitBridge, Tally, GST IRP / e-way bill |
| **Health front desk** | "Patients book and queue without calling five times" | bookings (provider / department), queue, workforce, documents (non-clinical forms), payments | Reception, provider | Receptionist (medical guardrails) | Telephony |
| **Growth** | "I spend on ads that bring orders" | marketing, loyalty | Owner, marketer | Marketing Manager | Meta Marketing API + Conversions API, Google Business Profile |
| **Community & giving** | "Members, dues and donations tracked" | memberships (dues), donations, bookings (hall), workforce (volunteers) | Secretary, treasurer | Collections Assistant | Razorpay |
| **Back office** | "My books, cash and licences are under control" | expenses, ledger, compliance, documents, connectors, payroll (FUTURE) | Accountant | Bookkeeper | Tally, Zoho Books, CSV |

Packs are presentation and packaging only. The entitlement engine (First Launch, `test_business_entitlements.py`) keeps enforcing per module key.

## 6. Module catalogue

LOCAH needs 10 extended First Launch modules plus 26 new ones to cover every category in §4; 3 more are FUTURE. Each is one entitlement key, one service package, one Workspace route group and one fixture set.

**Reconcile first:** Doc 11 lists 21 module keys; only the 10 below are confirmed from the Build Spec. Before P1, map every NEW key here against the other 11 registry keys and reuse any that match.

### 6.1 First Launch modules — what gets extended

| Key | Status | Extension (phase) |
| --- | --- | --- |
| `offerings-catalog` | EXTEND | Offering kinds (§6.3), GTIN / HSN / SAC codes, units and conversions, variants, B2B price lists (P1; price lists P4) |
| `orders` | EXTEND | Channel field (web, WhatsApp, POS, phone, ChitBridge), dine-in / table orders, pre-orders with a date, returns and exchanges (P1–P2) |
| `payments` | EXTEND | Payment links, UPI dynamic QR, deposits, split tender, cash / card records, COD, refunds, Razorpay Subscriptions (P1–P2) |
| `inventory` | EXTEND | Batches and expiry (FEFO), weights, serials, stock counts, wastage, reorder points, location transfers, van stock (P1–P4) |
| `fulfilment` | EXTEND | Pickup, local delivery, shipping; hands local delivery to `dispatch` (P2) |
| `bookings` | EXTEND | Modes: appointment, table, stay, class, rental, site visit, event date; waitlist; recurring; reschedule policy (P2) |
| `memberships` | EXTEND | Plan kinds (§10): access, session pack, recurring delivery, service contract (AMC), fee plan, member dues; freeze, grace, autopay (P2) |
| `workforce` | EXTEND | Provider schedules, shifts, skills, assignment rules, commission rules (FUTURE) (P2) |
| `customer-relationships` | EXTEND | Unified timeline, tags, segments, consent flags, guardians, customer assets (vehicle, pet, AC unit, property) (P1–P5) |
| `leads` | EXTEND | Configurable stages, sources (web, WhatsApp, call, Meta lead ads), assignment, follow-up SLA (P2–P3) |

### 6.2 New modules

| Key | Module | Does | Core entities | Phase |
| --- | --- | --- | --- | --- |
| `invoicing` | Invoices & GST | Tax invoice, bill of supply, credit / debit notes, FY number series per location, place-of-supply tax split, e-invoice IRN when required | invoice, invoice\_line, number\_series, credit\_note | P1 |
| `pos` | Counter billing | Scan or search, cart, hold bill, split tender, returns, cash drawer shifts, offline queue | pos\_register, pos\_shift, pos\_bill | P1 |
| `ledger` | Khata / credit book | Running balance per customer and supplier, credit limits, ageing, reminders, settlements | ledger\_account, ledger\_entry | P1 |
| `messaging` | WhatsApp & messages | Business inbox, templates, opt-ins, routing to human or AI, SMS / email fallback | channel, conversation, message, template, consent | P1 |
| `reviews` | Reviews | Verified reviews, replies, reports, moderation, Google sync | review, review\_reply, review\_report | P1 |
| `compliance` | Licences & deadlines | Licence and filing calendar, expiry reminders, document vault link | compliance\_item | P1 |
| `quotes` | Quotes & proposals | Versioned quotes, RFQ replies, validity, online accept, PDF, convert to order / project / invoice | quote, quote\_version, quote\_line | P2 |
| `dispatch` | Live delivery | Delivery and field jobs, crew assignment, live location, ETA, proof of delivery, COD settlement | dispatch\_job, crew\_shift, location\_ping, pod, cod\_settlement | P2 |
| `queue` | Walk-in queue | Tokens, live queue board, "your turn soon" WhatsApp | queue, queue\_token | P2 |
| `tasks` | Tasks & checklists | Housekeeping, maintenance, prep, opening / closing checklists | task, checklist\_template | P2 |
| `attendance` | Check-ins | Member, student and staff check-in by QR or manual; hardware adapters later | attendance\_event | P2 |
| `kitchen` | Kitchen display | Kitchen order tickets by station, bump screen, prep timers, printer fallback | kot, kot\_item, station | P2 |
| `marketing` | Campaigns & ads | Audiences, WhatsApp broadcasts, Meta ads, coupons, attribution | audience, campaign, coupon, attribution\_event | P3 |
| `loyalty` | Loyalty & referrals | Points or stamps, rewards, referral codes | loyalty\_account, loyalty\_txn, referral | P3 |
| `ai-employees` | AI staff | One entitlement per AI employee, limits, approvals, meters | ai\_employee, ai\_action, ai\_approval | P3 |
| `connectors` | Integration hub | Adapters, credentials, source-of-truth settings, sync logs | connector, sync\_run, sync\_mapping | P4 |
| `expenses` | Expenses & cash book | Expenses, petty cash, daily cash closing | expense, cash\_book\_day | P4 |
| `procurement` | Buying | Suppliers, price agreements, requisitions, POs, goods receipt, supplier bills, payables | supplier, requisition, purchase\_order, grn, supplier\_bill | P4 |
| `recipes` | Recipes & BOM | Components per offering, yield, wastage, unit conversions, production batches, consumption on sale | recipe, recipe\_line, production\_batch | P4 |
| `trade-network` | ChitBridge link | Entity binding, buyer / supplier relations, chit sync | cb\_binding, trade\_relation, chit\_ref | P4 |
| `projects` | Projects | Stages, milestones, payment schedule, client approvals, file room; property projects and units | project, milestone, unit, payment\_schedule | P5 |
| `jobs` | Job cards | Request → inspect → estimate → approve → work → parts → QC → invoice, linked to a customer asset | job\_card, job\_part, job\_check | P5 |
| `academics` | Courses & batches | Courses, batches, timetable, enrolment, assessments, homework, certificates | course, batch, session, enrolment, assessment | P5 |
| `documents` | Forms & files | Templates, intake and consent forms, uploads, typed / drawn signatures | document\_template, document, signature | P5 |
| `donations` | Donations | Causes, one-off and recurring gifts, 80G receipts, donor timeline | cause, donation, receipt | P5 |
| `insights` | Insights | Dashboards computed from real data only (Build Spec §9) | metric views | P1 → P5 |
| `payroll` | Payroll | Salary runs from attendance and commissions | — | FUTURE |
| `channel-manager` | OTA sync | Room availability sync with travel sites | — | FUTURE |
| `ticketing` | Event tickets | Tickets for events (excluded now per Build Spec §3) | — | FUTURE |

### 6.3 Offering kinds

One catalogue, many kinds; the kind decides which fields, website section and transaction flow apply.

| Kind | Transacted by | Used by |
| --- | --- | --- |
| `product` (variants optional) | Cart → order / POS | Retail, fashion, pharmacy |
| `weighed_product` (per kg, cut, pack size) | Cart → order / POS weighed label | Meat, fish, produce, sweets |
| `menu_item` (modifiers, add-ons) | Cart → order / table / KOT | Restaurants, cafés, home food |
| `service` (duration, provider) | Booking | Salon, clinic, repair, consultant |
| `class` / `course` | Booking or enrolment | Gym, studio, education |
| `room_type` / `rental_resource` | Date-range booking + deposit | Hotel, homestay, rentals, halls |
| `plan` | Membership | Gym, tiffin, AMC, fees, dues |
| `package` (bundle of sessions or items) | Order, then redeemed | Salon packages, PT packs |
| `property_project` / `unit` | Enquiry → site visit → quote | Real estate |
| `vehicle` | Enquiry → test drive → quote | Dealers |
| `portfolio_item` | Showcase → enquiry | Photographers, architects, agencies |
| `digital_product` | Order → download link | Creators, course sellers |
| `cause` | Donation | NGOs, trusts |

## 7. Role workspaces

There is one backend and one permission engine; each role gets its own home screen and only the records its scope allows. A delivery partner never opens the owner's Workspace — they open the crew app and see their jobs.

### 7.1 Surfaces

| Surface | Device | Who | Status |
| --- | --- | --- | --- |
| Workspace | Desktop / tablet web | Owner, manager, office roles | EXISTS |
| Crew app (`/crew`) | Phone PWA, then native wrapper for background location | Delivery, technician, housekeeping, provider on the move | NEW P2 |
| POS | Tablet or desktop, full screen | Cashier | NEW P1 |
| Kitchen display | Kitchen tablet | Kitchen stations | NEW P2 |
| My Activity | Customer phone / web | Customers | EXISTS |
| Guardian & student portal | Phone web | Parents, students | NEW P5 |
| Supplier view | ChitBridge mailbox, or a magic-link PO page for off-network suppliers | Suppliers | NEW P4 |
| Brand HQ | Desktop | Franchise brand owners | FUTURE |

### 7.2 Role templates

Scope values: **business** (all records), **location** (records at assigned locations), **assignment** (only records assigned to me), **self** (my own profile and time).

| Role | Sees and does | Scope | Surface | Home screen answers |
| --- | --- | --- | --- | --- |
| Owner | Everything, approvals, billing, AI limits | Business | Workspace | Needs you now · Today · Your business (Build Spec §8) |
| Manager | Operations, approvals up to a limit, staff rota | Location | Workspace | What is late or stuck at my location? |
| Front desk | Bookings, queue, check-ins, customers, collect payments | Location | Workspace | Who is here, who is next, who owes? |
| Provider (doctor, stylist, trainer) | Own schedule, own appointments, booking notes | Assignment | Workspace or crew app | My next appointment and my day |
| Cashier | POS, orders, payments, returns under a limit, cash shift | Location | POS | Open shift, bills, drawer balance |
| Kitchen | Tickets for their station; no prices or phone numbers | Location | Kitchen display | What to cook next |
| Store keeper | Stock, goods receipt, counts, transfers, draft requisitions | Location | Workspace | What is low, what arrived |
| Dispatcher | Dispatch board, assign crew, reassign failed jobs | Location | Workspace | Unassigned and late deliveries |
| Delivery partner | Assigned deliveries: name, address, amount, COD; phone only while the job is active | Assignment | Crew app | My next drop |
| Technician | Assigned job cards, parts used, photos, that asset's service history | Assignment | Crew app | My next job |
| Housekeeping | Assigned room and area tasks | Assignment | Crew app | Rooms to turn around |
| Sales executive | Assigned leads, quotes, site visits | Assignment | Workspace or crew app | Follow-ups due today |
| Teacher | Own batches: attendance, assessments, announcements | Assignment | Workspace or crew app | Today's classes |
| Accountant | Invoices, ledger, expenses, exports, connectors; no customer messaging | Business | Workspace | Unpaid, unsynced, due |
| Marketer | Campaigns and audiences as counts; no phone-number export | Business | Workspace | What is running and what it earned |

### 7.3 Build rules

- A role is a permission set + scope + default surface. Owners clone a template to make custom roles; they cannot exceed their own permissions.
- **Assignment scope is the new security primitive.** Add an RLS arm `assigned_member_id = current_member_id()` on dispatch jobs, job cards, tasks, bookings and leads. Extend `test_actor_matrix.py` with one row per role × record type before any crew surface ships.
- One person can hold roles in several businesses; the existing context switching handles it.
- AI employees receive a role from this table (§8). They never get Owner.

## 8. AI employees

LOCAH ships 12 AI employees, each a tool-using agent with a role from §7, a tool allowlist, autonomy tiers, a monthly budget and a complete audit trail. They call the same services humans call; limits are enforced by the services, never by the prompt.

### 8.1 The roster

| AI employee | Works in | Acts on its own | Always asks the owner | Phase |
| --- | --- | --- | --- | --- |
| **WhatsApp Manager** | `messaging`, `orders`, `bookings`, `leads` | Answers FAQs, builds carts from the catalogue, books free slots, sends payment links at list price, gives order status | Discounts, custom prices, refunds, off-catalogue items | P1 structured, P3 AI |
| **Receptionist** (voice) | Phone, WhatsApp calls | Answers, books, reschedules, takes messages, sends confirmations | Anything medical, complaints, refunds; hands the call to a human | P3 |
| **Appointment Manager** | `bookings`, `queue` | Fills cancellations from the waitlist, reminders, no-show follow-ups | Overbooking, fee waivers | P3 |
| **Collections Assistant** | `memberships`, `ledger`, `donations` | Renewal and dues reminders on the owner's schedule, payment links | Waivers, extensions, credit-limit changes | P2 rules, P3 AI |
| **Delivery Coordinator** | `dispatch` | Suggests or auto-assigns within rules, sends ETA updates, reschedules failed drops | Paid third-party courier booking | P3 |
| **Inventory Manager** | `inventory` | Low-stock alerts, wastage anomaly flags, reorder suggestions | Every stock adjustment | P3 |
| **Procurement Planner** | `recipes`, `procurement`, `trade-network` | Drafts requisitions from demand and BOM | Sending any PO (auto-send only under an owner limit to an approved supplier) | P4 |
| **Bookkeeper** | `expenses`, `procurement`, `connectors` | Reads bill photos into drafts, matches payments, flags sync errors | Posting anything to books or Tally | P4 |
| **Sales Executive** | `leads`, `quotes`, `bookings` | Qualifies leads, schedules site visits, follow-up nudges, quote drafts | Sending a quote, any price change | P3 |
| **Marketing Manager** | `marketing` | Audience and campaign drafts, creative drafts, weekly results summary | Any spend, any broadcast | P3 |
| **Review Responder** | `reviews` | Reply drafts; auto-posts 4–5 star replies if the owner turns it on | Replies to 1–3 star reviews, reports | P3 |
| **Website Editor** | `website` | Rewrites a section's content fields (Build Spec §7) | Publishing | EXISTS |

### 8.2 Autonomy tiers

| Tier | Meaning | Examples |
| --- | --- | --- |
| T0 Read | Look up, never change | Order status, slot availability |
| T1 Draft | Prepare; a human sends | Quotes, POs, bill entries, campaigns |
| T2 Act within limits | Do it, inside owner-set limits, logged | Book a free slot, send a list-price payment link, send a scheduled reminder |
| T3 Approval always | Owner taps Approve in "Needs you now" | Spend, refunds, discounts above limit, deletions, POs above limit |

### 8.3 Contract every AI employee follows

- **Identity.** Every call carries `actor_type = ai_employee`, the employee id and `business_id`. RLS and the authorization engine apply unchanged.
- **Audit.** Each action writes an `ai_action` row: tool, inputs, result, reason, conversation link, tokens and cost. Owners see it as a readable feed.
- **Limits live in services.** Max discount, max PO value, allowed hours and channels are service-side checks. A prompt cannot raise them.
- **Injection-safe.** Customer text is data. No tool can change prices, permissions, payouts or AI limits.
- **Kill switch.** One toggle per employee, plus a global pause. Paused means the flow falls back to buttons and human handoff.
- **Discloses itself.** Voice calls open with "You're speaking with the assistant at \<business>". Chat says so when asked.
- **Language.** Replies in the customer's language: English, Tamil, Hindi and code-mixed text first.

### 8.4 Cost ladder

Cheapest path first, every time:

1. Buttons, lists and WhatsApp Flows — no model call.
2. Deterministic intent (keywords, synonyms, cached answers) — no model call.
3. Small model for extraction ("2 kg chicken curry cut" → cart lines).
4. Larger model only for generation (campaign copy, quote wording, voice turns).

Each business has a monthly AI credit meter with a hard cap. At the cap, flows drop to step 1–2 and the owner is told. The model interface stays provider-agnostic, reusing the First Launch deterministic-fallback pattern.

## 9. Integrations and connectors

Every external system plugs into one connector hub with a written source-of-truth contract; LOCAH never runs an ungoverned two-way sync. WhatsApp and Razorpay come first because nearly every category needs them.

### 9.1 Connector table

| Integration | Used for | How | Source of truth | Phase | Constraint to design around |
| --- | --- | --- | --- | --- | --- |
| **WhatsApp Business Platform** (Cloud API) | Notifications, inbox, ordering, bookings, payment links, Flows, catalogue | LOCAH as Meta Tech Provider; Embedded Signup per business; coexistence so owners keep the Business app on the same number | LOCAH owns orders / bookings; Meta owns delivery status | P1 | Per-message pricing; templates are the only thing sendable outside the 24 h window ([Meta pricing](https://developers.facebook.com/documentation/business-messaging/whatsapp/pricing)). General-purpose AI chatbots are banned since 15 Jan 2026; business-task bots are allowed ([explainer](https://respond.io/blog/whatsapp-general-purpose-chatbots-ban)) |
| **WhatsApp Business Calling API** | AI Receptionist on WhatsApp calls | Graph API + webhooks or SIP; media over WebRTC | LOCAH owns call log and outcome | P3 | Number must run on Cloud API, not the Business app; needs a daily messaging limit of 2,000+ unique recipients; routes to WebRTC / SIP ([Meta calling docs](https://developers.facebook.com/documentation/business-messaging/whatsapp/calling)) |
| **Telephony (normal phone calls)** | AI Receptionist on the business's existing number | Owner forwards busy / no-answer calls to a LOCAH virtual number with media streaming | LOCAH owns call log | P3 | Provider choice open (§28): India inbound numbers need KYC; streaming audio support must be confirmed |
| **Razorpay** | Checkout, payment links, UPI QR, deposits, refunds, subscriptions / autopay, payouts FUTURE | Existing merchant integration (`test_merchant_razorpay.py`) + webhooks | Razorpay owns money movement; LOCAH owns what it was for | EXISTS → P1–P2 | RBI e-mandate rules for recurring debits (verify limits at build) |
| **Google Maps Platform** | Driver navigation, ETA, address entry | Maps URLs for "open in Google Maps" (no key); Routes API for ETA; Places Autocomplete | LOCAH owns jobs and pings | P2 | Routes and Places are metered: recompute ETA on movement, not on a timer |
| **Shipping + hyperlocal partners** | Courier shipping, overflow delivery | Aggregator API (e.g. Shiprocket); hyperlocal partner APIs | Partner owns tracking; LOCAH mirrors status | P2–P4 | Confirm which partners give API access to small merchants |
| **TallyPrime** | Stock, masters, vouchers sync | LOCAH Connector Agent on the Tally PC calls Tally's local HTTP server; JSONEx from TallyPrime 7.0, XML for older ([Tally JSON](https://help.tallysolutions.com/tally-prime-integration-using-json-1/), [prerequisites](https://help.tallysolutions.com/pre-requisites-for-integrations/)) | Declared per family (§15) | P4 | Tally runs on a local machine with a company loaded; cloud cannot call it directly |
| **Other accounting / billing** | Zoho Books, Vyapar, Busy, Marg | CSV / Excel import-export first; APIs where offered | Declared per family | P4 | Verify each vendor's API before promising sync |
| **GST IRP (e-invoice) + e-way bill** | IRN + QR on B2B invoices | Through a GST Suvidha Provider API | IRP owns IRN | P4 | Mandatory for B2B when AATO > ₹5 crore; 30-day reporting cap at ≥ ₹10 crore; B2C excluded ([Tally guide, Aug 2026](https://tallysolutions.com/business-guides/e-invoicing-compliance-rules-in-2026/)) |
| **Meta Marketing API + Conversions API + Lead Ads** | Ads, audiences, lead import, purchase events | Business Login; server-side events from LOCAH | Meta owns spend and delivery; LOCAH owns attribution to orders | P3 | Needs Meta app review for ads permissions |
| **Google Business Profile** | Reviews, replies, hours, posts | GBP APIs | GBP owns its reviews; LOCAH mirrors | P3 | API access requires Google approval (verify) |
| **Google Calendar** | Provider availability sync | OAuth per provider | LOCAH owns bookings | P3 | Two-way only for busy / free blocks |
| **Email + SMS** | Receipts, OTP, fallback alerts | Transactional email provider; SMS provider | LOCAH | P1 | Indian SMS needs DLT-registered templates |
| **ChitBridge** | Business-to-business obligations | REST + HMAC webhooks + `Idempotency-Key`; LOCAH acts as a connector actor | ChitBridge owns the co-held chit; each LOCAH tenant owns its own copy | P4 | ChitBridge's own two-way loop is "built, unverified" per its Reality tab (§16) |
| **Hardware** | Scanners, receipt / kitchen printers, cash drawers, label scales | Scanner as keyboard input or phone camera; ESC/POS printers; drawer kick via printer | LOCAH | P1–P2 | Must work without drivers on Android tablets |
| **Access control, card terminals** | Gym turnstiles, biometric attendance, card-present payments | Vendor SDKs | Device owns events; LOCAH ingests | FUTURE | Vendor-specific; pilot one device first |
| **ONDC, OTA channel managers, food aggregators** | Network selling, room distribution | Partner programmes | Partner | FUTURE | No open self-serve API assumed; do not promise |

### 9.2 Connector contract (every adapter)

- Declares its **data families**, their **owner** and **direction** (pull, push, or both with owner-wins).
- Stores credentials in the secrets store, never in plain tables. Every run writes a `sync_run` with counts and errors.
- Every write is idempotent on an external id mapping (`sync_mapping`). Retries never duplicate.
- Failure shows in "Needs you now" in plain words: "Tally is closed on the shop PC, 14 bills waiting."

### 9.3 WhatsApp pricing watch

Meta's pricing page, read on 24 Sep 2026, still lists non-template messages and utility templates inside the service window as free ([Meta pricing](https://developers.facebook.com/documentation/business-messaging/whatsapp/pricing)). Some partners report both become billable from 1 Oct 2026 ([Omnichat](https://blog.omnichat.ai/whatsapp-business-api-service-messages-pricing/)). The meter in §8.4 must count every message, so either outcome is absorbed without a redesign.

## 10. Deep dive: memberships and subscriptions

A membership is a plan plus a customer subscription with a start date, an end date and a state. Renewals collect themselves: a reminder ladder sends WhatsApp intimations with a payment link (or charges an autopay mandate), and a paid link extends the period automatically. Phase P2; AI wording P3.

### 10.1 One module, six plan kinds

| Plan kind | Examples | "Active" means | Renews by |
| --- | --- | --- | --- |
| `access` | Gym, yoga studio, co-working desk, club | Can check in until the end date | Month / quarter / year |
| `session_pack` | 10 PT sessions, salon package, therapy pack | Sessions left > 0 and before expiry | Buying a new pack |
| `recurring_delivery` | Milk, tiffin, flowers, produce box | Deliveries are generated on schedule | Prepaid period or month-end bill |
| `service_contract` | AC / RO / pest-control AMC, IT retainer | Covered visits within the period | Contract year |
| `fee_plan` | Coaching term fees, school instalments | Enrolment stays active while instalments are paid | Instalment due dates |
| `member_dues` | Associations, clubs, trusts | Member in good standing | Annual dues |

### 10.2 States

```mermaid
stateDiagram-v2
  [*] --> PENDING_PAYMENT
  PENDING_PAYMENT --> ACTIVE: paid
  ACTIVE --> PAUSED: freeze
  PAUSED --> ACTIVE: resume, end date + paused days
  ACTIVE --> GRACE: end date passed, unpaid
  GRACE --> ACTIVE: paid
  GRACE --> EXPIRED: grace over
  EXPIRED --> ACTIVE: renewed
  ACTIVE --> CANCELLED
  EXPIRED --> [*]
```

"Expiring soon" is a derived view (end date within 7 days), not a stored state. Early renewal queues the next period; it never shortens the current one.

### 10.3 Entities

- `plan`: price, duration, joining fee, grace days, freeze allowance, allowed channels, reminder ladder.
- `member_subscription`: customer, plan, status, current period, next renewal date, autopay mandate id.
- `subscription_period`: from, to, invoice, payment. One row per paid period, so history is never overwritten.
- `subscription_freeze`: from, to, reason. `attendance_event`: check-ins.

### 10.4 Renewal ladder (defaults, owner-editable)

| When | What the member receives | System action |
| --- | --- | --- |
| T−7 days | WhatsApp: "Your plan ends on 30 Sep. Renew now" + pay button | Create payment link for the next period |
| T−2 days | Same, with the amount and plan name | Link reused, not recreated |
| T0 | "Your plan ends today" | Autopay: attempt charge; failure falls back to the link |
| T+1 | "You're in your grace period until \<date>" | Status → GRACE |
| End of grace | "Your membership has expired" | Status → EXPIRED; owner sees it in "Expired this week" |
| T+15 | Win-back offer | Only with marketing opt-in, sent as a marketing template |

- Payment webhook → extend period, issue invoice, send receipt, cancel pending ladder steps. One transaction.
- Idempotency key = subscription + period number + ladder step. A replayed webhook never extends twice.
- Quiet hours (default 9 pm–8 am) and the Asia/Kolkata date boundary apply to every step.
- Template categories are assigned by Meta; renewal reminders are drafted as utility, offers as marketing.

### 10.5 Surfaces

- **Members board (Workspace):** tabs Active · Expiring in 7 days · In grace · Expired · Paused · Payment pending. Row actions: send link, record cash, freeze, renew.
- **Renewal calendar:** month grid showing renewals due per day and their amounts; tap a day to see the members.
- **Member profile:** a from → to bar per period, freezes shaded, check-ins as dots, payments beneath.
- **Front desk check-in:** scan the member's QR. Green = active; amber = grace (allowed if the owner permits); red = expired with a "Collect renewal" action.
- **My Activity (customer):** membership card with the date bar, days left, check-in QR, Renew and Request freeze.

### 10.6 Kind-specific rules

- **Recurring delivery:** at a cutoff (default 9 pm) tomorrow's orders and delivery jobs are generated. Customers skip or pause days with WhatsApp buttons. Postpaid customers accrue to the `ledger` and get a month-end bill — the milkman model.
- **Service contract:** schedules preventive visits as `jobs`; parts are covered or chargeable per contract.
- **Fee plan:** instalments with due dates, late-fee rule, guardian as payer.

### 10.7 Acceptance tests

- A replayed payment webhook does not double-extend.
- A 10-day freeze moves the end date by exactly 10 days.
- No reminder is sent after renewal, or inside quiet hours.
- An expired member cannot book a class unless the owner allows it.
- Every ladder step appears in the owner's activity log with its delivery status.

## 11. Deep dive: AI Receptionist (voice)

The AI Receptionist answers the calls a busy front desk misses, books into the real LOCAH calendar, confirms on WhatsApp, and hands anything medical, angry or unusual to a human. Phase P3, sold as a metered add-on.

### 11.1 Two ways in

| Route | For whom | Setup |
| --- | --- | --- |
| **Forwarded phone calls** (primary) | Every business with an ordinary number | Owner sets carrier forwarding on busy / no answer / after hours to a LOCAH virtual number |
| **WhatsApp calls** | Businesses whose number runs on Cloud API and meets Meta's calling prerequisites | Enable calling on the number; calls arrive over WebRTC / SIP (§9.1) |

### 11.2 Call flow

```mermaid
sequenceDiagram
  participant C as Caller
  participant T as Telephony / WhatsApp
  participant V as Voice gateway
  participant A as Receptionist agent
  participant S as LOCAH services
  C->>T: calls the business
  T->>V: streams audio
  V->>A: speech → text turns
  A->>S: check_availability(service, date)
  S-->>A: free slots
  A->>V: "10:30 or 12:00 tomorrow?"
  C->>V: "10:30"
  A->>S: create_booking + send_whatsapp
  V-->>C: confirms and ends the call
```

The agent's tools: `business_info`, `list_services`, `check_availability`, `hold_slot`, `create_booking`, `reschedule`, `cancel`, `order_status`, `capture_lead`, `take_message`, `transfer_to_human`, `send_whatsapp`. Nothing else.

### 11.3 What it does per business type

| Business | Caller usually wants | Receptionist does | Hands to a human when |
| --- | --- | --- | --- |
| Clinic / hospital / dental | Appointment with a doctor or department, timings, directions, queue status | Books the provider slot, sends time + token + map on WhatsApp, reminder 2 h before | Symptoms, emergencies, reports, prescriptions, billing disputes |
| Hotel / homestay / resort | Room for dates, rate, check-in time | Checks date-range availability, quotes, holds the room, sends a deposit link; confirms on payment | Groups above the owner's room limit, complaints |
| Salon / spa | Service with a stylist | Books the provider slot, offers the next free alternative | Bridal packages (captured as a lead), pricing disputes |
| Restaurant / café | Table booking, opening hours, order status | Books the table; for phone orders sends a WhatsApp order link instead of taking a long order by voice | Catering and large parties (lead) |
| Real estate | Project details, site visit | Captures the lead, books a site visit with the assigned sales executive, sends brochure + map | Price negotiation |
| Education | Admissions, batch timings, fees | Answers from the course catalogue, books a demo class or counselling | Fee concessions |
| Home services / garage | Technician visit, job status | Creates the job request with address and slot | Complaints, warranty claims |
| Gym / studio | Timings, plans, trial | Books a trial, sends the plan link | Refunds, freezes beyond policy |

### 11.4 Guardrails

- **Healthcare:** never gives medical advice or triage. Emergency phrases trigger: "Please call 108 or 112, or go to the nearest emergency room", then an immediate transfer attempt.
- **Disclosure:** opens with "You're speaking with the assistant at \<business>". When recording is on, the recording announcement plays first.
- **No payment details by voice.** Money only moves through a payment link sent on WhatsApp.
- **Holds expire.** A slot held for a deposit auto-releases after the owner's hold time (default 15 min).
- **Languages:** English, Tamil, Hindi, switching mid-call when the caller does.
- **Fallback:** if the AI or provider is down, callers get voicemail, a "we'll call you back" WhatsApp, and the owner gets a callback task.

### 11.5 Workspace

- **Calls page:** every call with outcome (booked, lead, message, transferred, missed), a 2-line summary, transcript and a Call back button.
- **Setup:** hours, forwarding steps for the owner's carrier, transfer number, which actions the AI may take (T2 limits), voice and languages.
- **Knowledge:** assembled from the website, offerings, policies and an FAQ list the owner edits. No free-form training uploads in P3.
- Transcripts keep for a default 90 days, owner-configurable, card-like numbers redacted.

### 11.6 Cost and acceptance

Every minute costs telephony + speech-to-text + model + text-to-speech. Minutes are metered per business with a monthly cap; at the cap, calls go to voicemail mode.

- A booking is only created in a slot that is free at commit time (slot lock); two parallel calls cannot take the same slot.
- A medical question never receives advice in any test transcript (red-team fixture set).
- Every booking made by the AI shows `actor_type = ai_employee` and links to its call.

## 12. Deep dive: WhatsApp commerce

Customers order, book, enquire, pay, track, reorder and renew without leaving WhatsApp. Buttons, lists and WhatsApp Flows carry P1 with zero model calls; the AI WhatsApp Manager adds free-text understanding in P3. Every path ends in the same LOCAH order, booking or lead the website would create.

### 12.1 Routing

```mermaid
flowchart LR
  IN[Inbound message] --> R{Router}
  R -->|button / list reply| F[Deterministic flow step]
  R -->|menu word or number| F
  R -->|free text| AI[AI WhatsApp Manager]
  R -->|human asked / low confidence| H[Workspace inbox]
  F --> SVC[Module services]
  AI --> SVC
  SVC --> OUT[Reply or template]
```

The router always tries the cheapest branch first (§8.4). A human reply in a thread pauses the AI in that thread for 12 hours by default.

### 12.2 Entry points

Counter and packaging QR ("Scan to order on WhatsApp"), website "Order on WhatsApp" button, Marketplace profile, Google Business Profile, and Click-to-WhatsApp ads — which open Meta's 72-hour free entry point window when answered within 24 hours ([Meta pricing](https://developers.facebook.com/documentation/business-messaging/whatsapp/pricing)).

### 12.3 Journeys

| Customer intent | P1 structured path | P3 free-text path | Ends in |
| --- | --- | --- | --- |
| **Order** (restaurant, meat, grocery, bakery) | Menu → category → item → quantity / cut / weight Flow → cart summary → delivery or pickup → address pin → pay link or COD | "2 kg chicken curry cut and 1 kg mutton, deliver" → cart lines, asks only the missing choice (cut, weight) | `orders` + stock reservation + `dispatch` job |
| **Book** (salon, clinic, gym trial, table) | Service → date → slots → confirm | "Haircut tomorrow evening with Priya" | `bookings` |
| **Enquire** (real estate, B2B, education, services) | Lead-form Flow | Short qualifying questions, then a site visit or callback offer | `leads` + assignment |
| **Pay / renew / dues** | Template button → payment link | "How much do I owe?" → ledger balance + link | `payments`, `memberships`, `ledger` |
| **Track** | "Where's my order" → status + live tracking link | Same, from free text | Tracking page (§13) |
| **Reorder** | "Repeat last order" | "Same as last week" | `orders` |
| **Change / cancel** | Within the owner's policy only | Same | `orders` / `bookings` |
| **Talk to a person** | Button always visible | Detected from text | Workspace inbox |

### 12.4 Rules

- **The customer confirms every cart or booking with a button.** Nothing is placed silently.
- **Prices and stock come only from LOCAH.** The AI cannot quote a price that is not in the catalogue; stock and slots are re-checked at confirm time, with alternatives offered.
- **Addresses:** WhatsApp location pin → geocoded and saved to the customer; the last address is offered first.
- **Payment:** Razorpay link (UPI intent) or COD where the owner allows it, with a first-order COD cap.
- **Templates:** order confirmed, out for delivery, delivered, booking reminder, renewal and payment due — pre-approved in English, Tamil and Hindi.
- **Consent:** transactional messages follow the customer's own action. Marketing needs explicit opt-in, stored in `consent` with timestamp and source.
- **Policy boundary:** the bot only handles this business's tasks. Off-topic questions get a polite redirect, which keeps LOCAH inside Meta's business-bot rules (§9.1).
- **Catalogue sync (optional):** LOCAH offerings can be pushed to a Meta commerce catalogue for native product messages. LOCAH stays the source of truth for price and stock.

### 12.5 Workspace inbox

- One list of conversations with status chips: AI handling, needs a person, order, booking, lead.
- Side panel shows the customer's orders, bookings, balance and membership, with one-tap actions.
- Assign to staff, quick replies, and a wait timer. Chats waiting more than 10 minutes appear in "Needs you now".
- Coexistence lets the owner keep replying from the WhatsApp Business app; those replies still mark the thread as human-handled.

### 12.6 Acceptance tests

- A cart can never be created with a price different from the catalogue price at that moment.
- Duplicate webhook deliveries create one order.
- A thread with a human reply in the last 12 hours receives no AI message.
- A customer without marketing consent never receives a marketing template.

## 13. Deep dive: delivery and dispatch

Every local delivery becomes a dispatch job with an assigned crew member, live location while on duty, an ETA, proof of delivery and a cash settlement. The owner watches a live board, the customer watches a tracking page, and the delivery partner sees only their own jobs. Phase P2; the same machinery serves field technicians (§21).

### 13.1 Job states

```mermaid
stateDiagram-v2
  [*] --> CREATED
  CREATED --> READY: packed
  READY --> ASSIGNED
  ASSIGNED --> PICKED_UP
  PICKED_UP --> EN_ROUTE
  EN_ROUTE --> DELIVERED: OTP / photo
  EN_ROUTE --> FAILED: reason
  FAILED --> ASSIGNED: rescheduled
  FAILED --> RETURNED
  DELIVERED --> [*]
```

The customer sees five friendly steps: Placed · Preparing · Picked up · On the way · Delivered.

### 13.2 Entities

- `dispatch_job`: order or job card, pickup location, drop address + coordinates, promised window, COD amount, assignee, status, sequence.
- `crew_shift`: member, on-duty start / end, vehicle, cash in hand.
- `location_ping`: member, shift, lat, lng, accuracy, time. Written only while on duty.
- `proof_of_delivery`: OTP verified, photo, signature, recipient name.
- `cod_settlement`: shift, expected, declared cash, UPI collected, difference, verified by.

### 13.3 Crew app (delivery partner)

1. **Go on duty** — one toggle; location permission; a banner says location is shared only while on duty.
2. **My jobs** — cards in suggested order: customer first name, area, amount, COD badge, time window.
3. **Job** — Navigate (opens Google Maps directions through a Maps URL, no API key), Call customer (active job only), Picked up, Arrived, Delivered (OTP or photo), Failed (reason list).
4. **Collect COD** — cash, or a UPI QR shown on the partner's phone for the customer to scan.
5. **End shift** — settlement screen: expected vs collected; hand cash to the manager, who confirms.

Status taps and pings queue offline and sync when the network returns.

### 13.4 Location tracking — what is actually possible

- A browser app reliably reads GPS only while it is open in the foreground; background tracking, especially on iPhones, needs a native wrapper.
- **P2a:** PWA with screen wake-lock and "keep LOCAH open while delivering".
- **P2b:** native wrapper (Flutter or Capacitor) with background location and battery-aware intervals.
- Ping cadence: about every 15 s when moving, 60 s when stopped; nothing off duty.
- Retention: raw pings deleted after 7 days (owner can choose up to 30); job summaries (distance, times) stay. Consent is recorded at crew onboarding.

### 13.5 Owner dispatch board

- Columns: Unassigned · Assigned · Picked up · On the way · Delivered today · Failed.
- Map view: crew dots showing how old their last ping is, job pins by status.
- Assign by drag, or auto-assign: nearest on-duty partner with capacity, then round-robin. Group jobs in the same area into one run.
- Alerts in "Needs you now": job late against its window, partner's ping older than 5 minutes while on the way, COD not settled at shift end.

### 13.6 Customer tracking page (extends `/[slug]/track/[orderId]`)

- The stepper from 13.1. During "On the way": live map with the partner's dot (realtime channel, about every 15 s), "about 18 min" ETA and the partner's first name.
- The call button dials the **business**, not the partner's personal number.
- The partner's position is visible only between pickup and delivery. The signed link expires 24 hours after delivery.
- After delivery: map disappears, "Rate your delivery" opens a verified review (§17).
- Courier-shipped orders use the same page with milestones and no live map.

### 13.7 ETA and cost

ETA is computed with the Routes API at pickup and again only when the partner drifts from the route or 5 minutes pass. Map rendering choice (Google Maps JS vs an open-source renderer with a commercial tile provider) is decided in §28.

### 13.8 Overflow

With no partner free, the Delivery Coordinator suggests a third-party courier. The owner approves the paid booking, and the partner's tracking link is stored on the job.

### 13.9 Acceptance tests

- A delivery partner's session can read only jobs assigned to them (RLS, §7.3).
- No ping is stored when the partner is off duty.
- The tracking page shows no location before pickup or after delivery.
- Shift COD expected = sum of delivered COD jobs; any difference raises an alert.

## 14. Deep dive: billing, POS, GST and scanning

One billing engine produces every bill — counter, website, WhatsApp, B2B — as a correctly numbered document with a PDF, a WhatsApp copy and a stock movement. Tax rates are data the owner or their CA sets; LOCAH computes, it does not advise. Phase P1 (e-invoice P4).

### 14.1 Counter flow (POS)

```mermaid
flowchart LR
  A[Open shift<br/>opening cash] --> B[Scan or search]
  B --> C[Cart + optional customer]
  C --> D[Tender<br/>cash · UPI QR · card · split · khata]
  D --> E[Receipt print<br/>+ WhatsApp bill]
  E --> F[Stock moved<br/>ledger posted]
  F --> B
  F --> G[Close shift<br/>counted vs expected]
```

- Hold and recall bills for queues of customers. Returns and exchanges create a credit note and put stock back.
- UPI: a dynamic QR with the exact amount, confirmed by the payment webhook. Card: recorded against an external terminal until card-present integration (FUTURE).
- Role limits: discount cap per role; voids and returns past the window need a manager PIN.
- Restaurants: POS sends kitchen tickets by station, supports table bills, split and merge (§21 food service).

### 14.2 Offline mode

- The POS keeps working without internet: catalogue and prices cached with a version stamp; bills queue in the device.
- Each register reserves a block of invoice numbers (default 50) while online, so offline bills keep legal sequential numbering.
- UPI cannot be verified offline; the cashier takes cash or marks the bill "UPI to verify", reconciled on sync.

### 14.3 Scanning and labels

| Situation | How |
| --- | --- |
| Packaged goods with barcodes | USB or Bluetooth scanner acting as a keyboard (cheapest, fastest), or the tablet camera |
| Loose goods without barcodes | LOCAH generates an in-store code and prints labels on a sheet or label printer |
| Weighed goods (meat, sweets, produce) | Label-printing scales print a barcode carrying item code + weight or price; POS decodes it using a per-business format set during pilot |
| Packaged product master | GTIN stored on the offering, matching ChitBridge's GS1 field so B2B lines match |
| Supplier bills | Photo → AI Bookkeeper draft (§15) |

### 14.4 GST document rules

| Seller situation | Document | Must carry |
| --- | --- | --- |
| GST-registered, regular scheme, consumer sale | Tax invoice | GSTIN, FY number series, HSN / SAC, taxable value, CGST + SGST (same state) or IGST (other state), place of supply |
| GST-registered, sale to a business | Tax invoice with buyer GSTIN | As above; IRN + QR when e-invoicing applies (§9.1) |
| Composition scheme | Bill of supply | Composition declaration; no tax charged |
| Not registered | Bill / receipt | No GST fields |
| Return or price reduction | Credit note | Reference to the original invoice |

- **Rates are data:** stored per offering or HSN with effective dates, because the GST Council revises them. Never hard-coded.
- **Numbering:** one gapless series per GSTIN × financial year (April–March) × register, e.g. `CHN1/26-27/000123`. Cancelled invoices stay, marked cancelled.
- **Outputs:** A4 PDF and 58 / 80 mm thermal; WhatsApp "Your bill from \<business>" with the PDF; email.
- **For the CA:** sales register, HSN summary, tax-by-rate summary, GSTR-1-ready export (format verified at build), Tally export (§15).
- Anything touching tax treatment (advances, restaurant rate choice, reverse charge) shows "Confirm with your CA" and a setting, never an assumption.

### 14.5 Khata and daily cash

- **Khata (credit book):** a credit sale posts to the customer's ledger. They get a WhatsApp statement with a UPI link; the owner sees ageing and sets credit limits. At a limit, POS blocks credit unless a manager overrides.
- **Cash closing:** opening + cash sales − cash refunds − petty expenses = expected. Counted cash and variance are logged per shift.

### 14.6 Acceptance tests

- Offline bills from two registers sync with no duplicate or missing numbers.
- Same-state sale splits CGST / SGST; other-state sale uses IGST, from place of supply.
- A composition-scheme business never prints a tax line.
- Round-off is shown as its own line and never changes the tax.

## 15. Deep dive: inventory and Tally sync

LOCAH inventory handles units, weights, yields, batches, expiry, serials, locations and wastage. TallyPrime sync runs through a small agent on the shop PC, and the owner picks which system owns each data family, so the two never fight over stock. Inventory depth P1–P2; Tally P4.

### 15.1 Inventory capabilities

| Capability | Who needs it | Behaviour |
| --- | --- | --- |
| Units and conversions | Everyone buying and selling differently | Buy by crate or kg, sell per 500 g or piece; conversions per item |
| Yield | Meat, fish, sweets, bakeries, kitchens | Owner-entered yield, e.g. 1 kg whole chicken → 0.8 kg curry cut; used in selling and in procurement maths (§16) |
| Variants | Fashion, footwear, electronics | Size × colour matrix, stock per SKU |
| Batches and expiry | Pharmacy, dairy, packaged food | First-expiry-first-out picking, expiry alerts |
| Serials and warranty | Electronics, appliances, vehicles | Serial captured at sale; warranty lookup by serial |
| Multi-location | Chains, franchises, warehouses | Stock per location, transfers with in-transit state |
| Reservations | All online sellers | Existing kernel reserves on order, releases on cancel |
| Stock counts | Everyone | Cycle counts by category; variances need approval |
| Wastage | Food, fresh, florists | Reasons (expired, damaged, trim loss); feeds yield accuracy |
| Reorder points | Everyone | Min / max per location → low-stock alert → requisition draft |
| Van stock | Technicians, route sales | A vehicle is a location |
| Valuation | Everyone | Weighted average cost from goods receipts |

### 15.2 Tally sync architecture

```mermaid
flowchart LR
  CLOUD[LOCAH cloud<br/>sync queue] <-->|outbound HTTPS only| AGENT[LOCAH Connector Agent<br/>Windows service on Tally PC]
  AGENT <-->|localhost HTTP| TALLY[TallyPrime<br/>company loaded]
```

- The agent opens every connection outward, so shops need no static IP or open ports. It pairs with a one-time code from Workspace.
- TallyPrime 7.0+ uses JSONEx; older versions use XML ([Tally JSON reference](https://help.tallysolutions.com/tally-prime-integration-using-json-1/)).
- Every request names the company explicitly (`svCurrentCompany`); Tally's docs warn data otherwise lands in the active company.
- Heartbeat: when the PC is off or Tally is closed, Workspace says so in plain words and queues changes.
- Idempotency: each LOCAH record's id is written into the Tally voucher reference and `sync_mapping`, so a retry never duplicates.

### 15.3 Who owns what (owner picks a preset at setup)

| Data family | Preset A — "LOCAH runs the shop, Tally keeps the books" (default) | Preset B — "Tally is master, LOCAH sells online" |
| --- | --- | --- |
| Stock items (masters) | LOCAH → Tally | Tally → LOCAH |
| Selling prices | LOCAH | Tally price levels → LOCAH |
| Stock quantities | LOCAH, pushed as stock journals | Tally → LOCAH on a schedule; LOCAH reserves locally between pulls |
| Sales vouchers | LOCAH → Tally | LOCAH → Tally |
| Purchases | LOCAH goods receipt → Tally | Tally → LOCAH |
| Customer / supplier ledgers | LOCAH creates → Tally | Both create; Tally owns edits |
| Receipts and payments | LOCAH → Tally | LOCAH → Tally |
| GST returns, P&L, balance sheet | Tally | Tally |

Conflicts resolve owner-wins per family; an overwritten edit is logged as "overridden" with both values.

### 15.4 Setup wizard

1. Install agent, pair, choose company.
2. Choose Preset A or B.
3. Map tax rates to Tally ledgers (e.g. Output CGST), payment modes to cash / bank ledgers.
4. Match stock items by name, part number or GTIN on a review screen.
5. Choose posting: per invoice (default, required for B2B buyers' ITC) or daily summary per tax rate (high-volume counters).

### 15.5 Other billing software

Zoho Books via its cloud API. Vyapar, Busy and Marg start with CSV / Excel import-export templates; direct sync only after each vendor's API is verified.

### 15.6 Supplier bill capture

Photo of a supplier bill → the AI Bookkeeper extracts supplier, lines, quantities and GST → matches lines to stock items → shows a draft purchase. A human confirms before any goods receipt, payable or Tally voucher exists.

### 15.7 Acceptance tests

- Running the same sync twice creates no duplicate vouchers.
- An agent offline for 3 days catches up in original order.
- A request without an explicit company is rejected by the agent.
- In Preset B, stock quantities match after a full round-trip.

## 16. Deep dive: ChitBridge supply network

LOCAH turns demand into supplier orders: orders, bookings, subscriptions and a forecast are multiplied through recipes, stock is subtracted, and what is left becomes a requisition. The owner approves it and LOCAH sends it to connected suppliers over ChitBridge. A supplier that is also on LOCAH receives it as an incoming order and repeats the same maths upstream — that chain of businesses is the network. Phase P4.

### 16.1 Worked example: a 100 kg biryani catering order

The owner's recipe (illustrative values — every business enters its own) per 1 kg of chicken biryani: chicken curry cut 0.45 kg, basmati 0.30 kg, onion 0.20 kg, oil 0.05 L, curd 0.08 kg. Tomorrow also has 15 kg of normal biryani forecast from the last four same-weekdays.

| Ingredient | Needed (catering + forecast) | On hand | On order | Safety stock | Net to buy | Rounded to supplier pack |
| --- | --- | --- | --- | --- | --- | --- |
| Chicken curry cut (kg) | 45 + 15 = 60 | 12 | 0 | 5 | 53 | 53 kg (sold per kg) |
| Basmati rice (kg) | 30 + 10 = 40 | 50 | 0 | 10 | 0 | — |
| Onion (kg) | 20 + 6 = 26 | 8 | 0 | 5 | 23 | 1 × 25 kg bag |
| Oil (L) | 5 + 2 = 7 | 3 | 0 | 2 | 6 | 1 × 15 L tin |
| Curd (kg) | 8 + 2 = 10 | 2 | 0 | 1 | 9 | 9 kg |

The requisition goes to three suppliers: the meat wholesaler (53 kg chicken), the vegetable supplier (onion) and the dairy (curd, oil).

```latex
\text{net}_i = \max\Big(0,\ \sum_{d} q_d \cdot \frac{r_{d,i}}{y_i} + s_i - h_i - o_i\Big)\ \text{rounded up to pack size and MOQ}
```

Here q is demand per offering, r the recipe quantity, y the yield (1.0 when the supplier sells it ready to use), s safety stock, h on hand, o already on order.

### 16.2 The chain

```mermaid
flowchart LR
  CUST[Customers<br/>orders, catering] --> REST[Restaurant<br/>LOCAH]
  REST -->|chit: 53 kg chicken| MEAT[Meat wholesaler<br/>LOCAH]
  MEAT -->|chit: live birds| FARM[Poultry farm<br/>LOCAH or ChitBridge]
  REST -->|chit: onion| VEG[Vegetable supplier]
  REST -->|chit: curd, oil| DAIRY[Dairy distributor]
  DAIRY -->|chit: milk| DFARM[Dairy farm]
```

Every arrow is a sealed chit with one copy per party; each node runs its own LOCAH tenant and sees only its own copy.

### 16.3 Demand sources

- Confirmed future orders and pre-orders (catering, cake orders).
- Bookings that consume stock (event covers, hotel breakfasts from guest counts).
- Subscriptions: tomorrow's milk and tiffin runs, generated at the cutoff (§10.6).
- Forecast: deterministic first — average of the last four same-weekdays × an owner-set festival multiplier. ML only after 6 months of data (FUTURE).
- Par levels for items without recipes.

### 16.4 Purchase order lifecycle

```mermaid
stateDiagram-v2
  [*] --> DRAFT: Procurement Planner
  DRAFT --> APPROVED: owner, or auto under limit
  APPROVED --> SENT: chit or WhatsApp link
  SENT --> COUNTERED: supplier changes qty / price / slot
  COUNTERED --> APPROVED: owner accepts
  SENT --> ACKNOWLEDGED
  ACKNOWLEDGED --> DISPATCHED
  DISPATCHED --> RECEIVED: goods receipt, actual weights
  RECEIVED --> DISPUTED: short weight / quality
  RECEIVED --> BILLED
  BILLED --> PAID
  PAID --> [*]
```

### 16.5 How LOCAH uses ChitBridge

| Need | ChitBridge primitive (from its report) | LOCAH side |
| --- | --- | --- |
| Send a PO | Chit on the buyer's Order track, delivered per-copy in one transaction | `purchase_order` keeps the chit id |
| Supplier receives it | Chit lands on the supplier's Task track | If the supplier is on LOCAH, `trade-network` creates a sales order in the supplier's own tenant |
| Status updates | Append-only `state_log`, HMAC webhooks | Updates LOCAH's own copy; never a shared row |
| Agreed price | Catalogue adopted by reference; the chit pins the version seen | Price on the PO line = pinned version |
| Short weight, spoilage | Dispute as a private siding | LOCAH shows "Disputed" and the outcome only |
| Money and codes | Stamped `{amount, currency}`, GTIN, HS, ISO 4217 | Same fields on offerings and invoices |

- **Why not build it inside LOCAH:** LOCAH RLS stays single-tenant. ChitBridge already owns per-copy delivery, dispute confidentiality and the standards set.
- **Off-network suppliers:** the PO goes as a WhatsApp template with a magic-link page to accept, change quantity or pick a delivery slot. The supplier can later claim a free entity and join.
- **Dependency gate:** ChitBridge's Reality tab lists governed peer two-way as "built, unverified". LOCAH's chit path starts only after one live A↔B loop passes. The WhatsApp magic-link path ships first, so owners are not blocked.

### 16.6 What the network unlocks

- **Forward demand for suppliers:** a wholesaler sees confirmed POs from its buyers (and forecasts, only where a buyer opts in) and plans its own buying.
- **Standing orders:** daily milk to a café as a recurring chit.
- **Supplier scorecard (private to the buyer):** on-time rate, fill rate, short-weight rate, price history with jump alerts.
- **Credit terms across the chain** through `ledger`, with reminders both ways.
- **Supplier discovery:** opt-in B2B listings in the Marketplace (P6).
- **Group buying:** FUTURE, only after legal review of competition rules.

### 16.7 Privacy rules

- Suppliers never see the buyer's customers — only PO lines, quantities, dates and delivery location.
- Forecast sharing is opt-in per supplier and can be withdrawn.

### 16.8 Acceptance tests

- The biryani fixture above reproduces the exact net quantities and pack rounding.
- A replayed ChitBridge webhook never advances a PO twice.
- A supplier-side LOCAH tenant cannot query the buyer's tenant under any role.
- A counter-offer never changes the PO until the buyer accepts.

## 17. Deep dive: reviews and moderation

Reviews come only from real transactions. The business can reply, report and choose which reviews to feature on its own website, but only a LOCAH moderator can remove a Marketplace review, and only for a listed violation with a reason code. That keeps the rating trustworthy for customers and fair to owners. Phase P1; AI replies P3.

### 17.1 Who can review

- One review per completed interaction: delivered order, completed booking, a membership period with at least one check-in, or a closed job card.
- Window: 30 days after completion. Rating 1–5, text, up to 3 photos, and a "Verified" badge.
- Invitation: a WhatsApp message after completion (template category decided by Meta at approval) and a prompt in My Activity.

### 17.2 Controls

| Action | Business owner | LOCAH moderator |
| --- | --- | --- |
| Reply publicly | Yes | — |
| Report a review | Yes, with a reason | Works the report queue |
| Feature on own website | Chooses which reviews appear in the featured strip | — |
| Remove from Marketplace | No | Only for a violation below; reason logged; reviewer told; one appeal |
| Edit review text | Never | Never — may only redact personal data |
| Rating average | Always computed from every published review | Same rule |

The website's featured strip always shows the true average and a "See all reviews" link, so featuring cannot fake the score.

**Violation reasons:** no genuine experience (spam or fake), abuse or hate, personal data, off-topic, conflict of interest (staff, owner, competitor), illegal content.

### 17.3 Recovery, not deletion

A 1–2 star review creates a "Needs you now" item with the customer's contact. The owner can reach out and put things right; only the reviewer can then update their review.

### 17.4 AI and Google

- The Review Responder drafts replies; it auto-posts only 4–5 star replies, and only if the owner turns that on.
- Google Business Profile reviews are mirrored read-only with reply support (P3). They never enter LOCAH's verified average.

### 17.5 Acceptance tests

- No business-side role or API can delete or edit a review.
- A review without an eligible, completed interaction is rejected.
- The displayed average equals the mean of all published reviews, featured or not.

## 18. Deep dive: marketing, Meta Ads and local presence

Marketing runs on the business's own data: audiences come from the CRM, offers become coupons, campaigns go out on WhatsApp or Meta ads, and spend is traced to orders and bookings. The AI Marketing Manager drafts; the owner approves every broadcast and every rupee. Phase P3.

### 18.1 Campaign flow

```mermaid
flowchart LR
  G[Goal] --> AU[Audience<br/>from CRM]
  AU --> OF[Offer<br/>coupon / plan]
  OF --> CR[Creative<br/>own photos + drafted text]
  CR --> CH[Channel + budget]
  CH --> AP{Owner approves}
  AP --> LIVE[Live]
  LIVE --> RES[Results<br/>spend → orders → revenue]
```

### 18.2 Building blocks

| Block | What it does | Rules |
| --- | --- | --- |
| **Audiences** | Rule-built segments: "ordered biryani 2+ times in 60 days", "membership expired 15–60 days ago", "lapsed 90 days", "within 5 km", "birthday this month" | Shows counts; only consented contacts for WhatsApp; marketer role cannot export phone numbers |
| **Offers** | Coupon codes, auto-applied offers, first-order and win-back offers | Usage limits, expiry, per-customer caps |
| **WhatsApp broadcasts** | Marketing templates to opted-in customers | Per-message cost shown before send |
| **Meta ads** | Facebook / Instagram ads including Click-to-WhatsApp, via the owner's own ad account | Spend billed by Meta to the owner; monthly cap enforced before any API call |
| **Conversions** | Server-side Purchase and Lead events sent to Meta with consent | Improves ad delivery; no raw personal data leaves unhashed |
| **Google Business Profile** | Hours, holiday hours, posts, photos, review replies, links to LOCAH order / book pages | Listing stays the owner's |
| **Loyalty and referrals** | Points per ₹, stamp cards ("10th coffee free"), referral codes rewarded on the friend's first order | Points ledger with expiry |
| **Attribution** | UTM links, Click-to-WhatsApp ad ids, coupon use → leads, orders, bookings, revenue, cost per order | Labelled "approximate, last touch" |

### 18.3 AI Marketing Manager behaviour

- Suggests from the business's own history only: "Last Diwali you sold 140 cakes in 5 days; run a 7-day, 5 km campaign at ₹300 / day?". With no history, it says so and offers a small test.
- Uses an owner-selectable, region-aware calendar: Pongal, Diwali, Onam, Eid, Christmas, wedding season, school reopening, exam results.
- Drafts creative from the owner's photos and brand colours; copy in English, Tamil or Hindi.
- Never promises results. Weekly summary: what ran, what it cost, what it brought.
- Regulated categories (real estate, finance, recruitment, health) carry Meta's ad restrictions; the manager checks the category before drafting targeting (§28).

### 18.4 Acceptance tests

- No marketing template reaches a customer without stored marketing consent.
- A campaign whose budget would exceed the monthly cap is blocked before the Meta call.
- Every result figure is computed from LOCAH orders or Meta's reported numbers — never estimated.

## 19. Deep dive: real estate projects and quotations

A developer or broker lists projects by status — upcoming, live, sold out, completed — with galleries, floor plans, unit inventory and brochures. Every enquiry becomes a lead that moves through site visit → quote → negotiation → token → payment schedule. Listings and quotes P2; payment schedules and progress updates P5. The same `quotes` module serves interiors, B2B machinery, events and travel packages with different line templates.

### 19.1 Entities

- `project`: name, status (`upcoming`, `launching`, `live`, `sold_out`, `completed`, `on_hold`), location + map pin, RERA registration number field, possession date, amenities, gallery, video, brochure, floor plans.
- `unit_type`: e.g. 2 BHK, carpet area, starting price.
- `unit`: tower / floor / number, facing, area, base price, status (`available`, `held`, `booked`, `sold`, `blocked`).
- `price_component`: base, floor rise, preferential location charge, parking, club, GST, owner-entered estimates such as stamp duty.
- `payment_schedule`: milestones (booking, agreement, slab stages, possession) with amounts and due rules.

### 19.2 Owner upload flow

1. Create project, pick status.
2. Bulk-upload images (auto-compressed, drag to reorder, captions), video link, brochure, floor plans.
3. Add unit inventory by grid or CSV.
4. Publish. The website gets a Projects section with tabs Upcoming · Live · Completed, and each project page shows gallery, map, amenities, unit types, a live availability chart built from real unit statuses, "Download brochure" (phone + consent → lead) and "Book site visit".

### 19.3 Sales pipeline

New → Contacted → Site visit booked → Visited → Quote sent → Negotiation → Token paid → Agreement → Won / Lost. Each lead carries its source: website, WhatsApp, Meta lead ad, walk-in or channel partner.

### 19.4 Quote builder

```mermaid
flowchart LR
  U[Pick unit] --> P[Price components<br/>auto-filled]
  P --> D[Discount<br/>role-limited]
  D --> PS[Payment plan]
  PS --> V[Validity<br/>default 7 days]
  V --> S[PDF + link<br/>sent on WhatsApp]
  S --> A[Customer accepts<br/>name + OTP]
  A --> T[Token payment link]
  T --> B[Unit HELD → BOOKED]
```

- Versions: v1, v2… during negotiation; the owner sees when the customer opened each version.
- A valid quote soft-holds the unit only if the owner enables holds; otherwise first token wins.
- Discounts above the executive's limit go to the owner for approval.
- The accepted version locks every price component.

### 19.5 After booking

- Payment schedule reminders through the Collections Assistant (§8).
- Document checklist (KYC, agreement drafts) in `documents`.
- Construction progress: photos per milestone posted to the buyer's portal, which reduces "what's the status?" calls.
- Channel partners get an assignment-scoped view of their own leads; commission tracking is FUTURE.

### 19.6 Acceptance tests

- Two customers cannot both reach BOOKED on one unit.
- The availability chart equals the count of units by status — never typed in.
- An accepted quote's total never changes after acceptance.

## 20. Deep dive: education

Coaching centres, academies and tutors run admissions, batches, timetables, attendance, fee instalments, marks and announcements in LOCAH, with a guardian and student portal and WhatsApp updates. The first target is coaching, tuition and academies; a full school ERP (transport, exams board, HR) is FUTURE. Phase P5, with fee plans arriving earlier through memberships (P2).

### 20.1 Entities

`course` → `batch` (teacher, schedule, capacity, room or online link, start / end) → `session` (each class occurrence) → `enrolment` (student, guardian, batch, fee plan) → `attendance_event`, `assessment` (test, marks, maximum), `assignment`, `announcement`, `certificate`.

### 20.2 Journeys

| Journey | Flow | Modules |
| --- | --- | --- |
| **Admissions** | Enquiry (website, WhatsApp, AI Receptionist) → demo class booking → counselling → enrolment form with documents → fee plan → payment → batch allocation → welcome message to guardian and student | leads, bookings, documents, memberships, academics |
| **Daily attendance** | Teacher opens today's sessions → one tap per student (default present) → optional absence note to the guardian: "Arun was absent from today's Physics batch" | academics, attendance, messaging |
| **Fees** | Fee plan (full or instalments) → reminder ladder (§10.4) → receipts; late-fee rule; concessions and sibling discounts need approval | memberships (`fee_plan`), payments, invoicing |
| **Tests and marks** | Enter marks per test → report card PDF → shared with guardian → progress chart from real marks only | academics |
| **Homework** | Post an assignment with a file; submissions by upload later (P5b) | academics, documents |
| **Announcements** | To a batch or everyone, over WhatsApp and the portal | messaging |
| **Timetable** | Teacher and room clash detection when creating batches | academics |
| **Online classes** | Meeting link per session; attendance marked manually | academics |
| **Certificates** | PDF with a verification link on course completion | academics, documents |

### 20.3 Portals

- **Guardian:** each child's classes today, attendance %, fees due with a Pay button, marks, homework, announcements. One guardian, many children.
- **Student:** same view without payments.
- **Teacher (crew app or Workspace):** today's sessions, attendance, marks entry, announcements to own batches only.

### 20.4 Safeguarding (trait `minors_involved`)

- The guardian is the contact of record for anyone under 18; messages go to the guardian by default.
- No marketing templates to minors. Teachers cannot export student contacts.
- Photos of students need a guardian consent flag before they appear anywhere public.
- DPDP Act rules on children's data (verifiable guardian consent) are checked at build (§28).

### 20.5 Variants

- **Preschool / daycare:** authorised pick-up list, daily activity note to guardians.
- **Driving school:** instructor + vehicle slot bookings, learner-licence date tracking.
- **Music / dance / art:** session packs, recital or exhibition dates, grade-exam tracking.

### 20.6 Acceptance tests

- A guardian can see only their own children's records.
- An absence note is sent once per missed session, never for a cancelled session.
- Overdue instalments change enrolment status only by the owner's written rule.

## 21. Sector playbooks: what every business family needs

All 54 sector families from the research list are covered below, grouped into 11 playbooks. Each row configures modules that are built once in §6; no row creates a module of its own. "Core" modules are on by default; "Rec" are pre-ticked in onboarding step 4. The 23 operating-model rows (franchise, B2B-only, walk-in and so on) are traits, handled in §22.

### 21.1 Food and fresh commerce

The deepest commerce pack: ordering by weight and cut, WhatsApp ordering, daily subscriptions, kitchen tickets, recipes driving stock, and suppliers ordered through the network (§16).

| Business | What LOCAH runs for them | Modules — Core · Rec | People · AI | Billing, stock, integrations | Gap it closes |
| --- | --- | --- | --- | --- | --- |
| **Meat, chicken, fish shops** | Orders by weight and cut on WhatsApp and website; live stock of cuts; delivery with tracking; next-morning supplier order | Core: offerings (weighed), orders, payments, inventory (yield), pos, fulfilment, dispatch · Rec: messaging, ledger, procurement, trade-network | Cashier, cutting counter screen, delivery partner · WhatsApp Manager, Procurement Planner | Scale-label barcodes; per-item GST rate set by the CA; FSSAI licence reminder | Orders lost in chats; yield and wastage invisible; supplier ordering by phone at 5 am |
| **Grocery, kirana, supermarket** | Barcode counter billing, khata, "send your list" WhatsApp orders picked and delivered, repeat baskets | Core: pos, invoicing, inventory (batches, expiry), ledger, orders, payments · Rec: fulfilment, dispatch, loyalty, procurement, connectors | Cashier, picker, delivery · WhatsApp Manager (turns a typed or photographed list into a cart to confirm), Inventory Manager | Scanners, thermal printer, Tally sync, distributor POs over ChitBridge | Credit in a notebook; expiry losses; distributor orders by phone |
| **Fruit, vegetable, dairy, egg sellers** | Daily subscriptions (e.g. 500 ml milk daily), morning route runs, skip / pause by WhatsApp, month-end bill | Core: memberships (`recurring_delivery`), orders, dispatch, ledger, payments · Rec: pos, inventory (perishable), procurement | Route delivery partner · Collections Assistant | Month-end WhatsApp bill with UPI link | Month-end bills written by hand; disputes over skipped days |
| **Home kitchens, pickles, podi, snacks, sweets, home bakers, chocolates** | Catalogue with pre-order dates, batch cooking list, city delivery and pan-India shipping for shelf-stable items | Core: offerings, orders, payments, fulfilment · Rec: recipes, inventory (batches), invoicing, marketing, reviews | Often solo owner, delivery · WhatsApp Manager, Marketing Manager | Shipping aggregator; batch and expiry on labels; FSSAI registration reminder | Orders buried in DMs; no records; cannot ship beyond the city |
| **Tiffin services, meal subscriptions, cloud kitchens** | Weekly menu calendar, veg / non-veg choice, daily count = subscribers − skips, delivery runs; one kitchen, several brand menus | Core: memberships (`recurring_delivery`), orders, kitchen, dispatch, recipes · Rec: procurement, inventory, reviews | Kitchen, delivery · Procurement Planner (tomorrow's ingredient list), Collections Assistant | Own ordering channel first; aggregator links FUTURE | Daily count by phone calls; aggregator commissions |
| **Restaurants, cafés, QSR, pubs** | QR dine-in ordering, table bookings, kitchen tickets by station, POS with split bills, takeaway and delivery, recipe-based stock, supplier POs | Core: offerings (menu + modifiers), orders, pos, kitchen, payments, invoicing, bookings (table) · Rec: recipes, inventory, procurement, trade-network, dispatch, loyalty, reviews, marketing | Cashier, waiter (crew app), kitchen, manager, delivery · WhatsApp Manager, Receptionist, Procurement Planner, Review Responder | Kitchen printers, Tally, ChitBridge, Google Business Profile; bar licence reminders | Sales never linked to ingredient stock; missed table-booking calls |
| **Bakeries, sweet shops** | Counter POS plus custom cake pre-orders (flavour, weight, message, photo, date), festival pre-order windows, daily production list | Core: pos, orders (dated pre-orders), offerings (weighed + custom), payments (advance) · Rec: recipes, kitchen, dispatch, marketing, loyalty | Cashier, baker, delivery · WhatsApp Manager, Marketing Manager | Advance payments; weighed-sweet labels | Custom orders on paper; festival rush chaos |
| **Catering, canteens** | Enquiry → per-plate menu quote → event booking with guest count → advance → BOM-driven purchase (§16.1) → staff roster; canteens get corporate monthly billing | Core: leads, quotes, bookings (event date), payments (milestones), recipes, procurement · Rec: trade-network, workforce, invoicing (B2B), ledger | Sales, kitchen head, event staff · Sales Executive, Procurement Planner | Supplier chits on ChitBridge; B2B GST invoices | Quantities guessed; advances tracked on WhatsApp |

### 21.2 Retail and custom products

One stock count for the shop and the website, variants and serials handled properly, and made-to-order work tracked by stage instead of by phone calls.

| Business | What LOCAH runs for them | Modules — Core · Rec | People · AI | Billing, stock, integrations | Gap it closes |
| --- | --- | --- | --- | --- | --- |
| **Clothing, footwear, fashion retail** | Size × colour variants, barcode POS, online catalogue with size guide, exchanges within a window, India-wide shipping | Core: offerings (variants), pos, inventory, orders, payments, fulfilment, invoicing · Rec: loyalty, marketing, reviews, connectors | Cashier, store keeper · WhatsApp Manager, Marketing Manager | SKU labels; shipping aggregator; returns → credit notes | Shop and online stock disagree; exchanges untracked |
| **Electronics, mobile stores** | Serial / IMEI captured at sale, warranty lookup, installation and repair bookings linked to the sale | Core: offerings (serialised), pos, inventory (serials), invoicing, payments · Rec: jobs, bookings, leads | Cashier, technician · Receptionist | Serial capture by scan; HSN on invoices; EMI via payment partner (verify) | Lost warranty proof; repair-status calls |
| **Jewellery** | Price = today's metal rate × weight + making charge + GST from a daily rate board; custom orders with advance; hallmark (HUID) per piece | Core: offerings (formula-priced), pos, invoicing, inventory (per piece), orders · Rec: leads, bookings (consultation) | Sales staff, owner · Sales Executive | Daily rate entry; per-piece records; gold savings schemes only after legal review | Daily re-pricing by hand; custom-order tracking |
| **Furniture, home decor, kitchenware** | Dimensions and finishes, made-to-order lead times, showroom visits, delivery + installation slots, bulk quotes | Core: offerings, orders, quotes, payments (advance), fulfilment, dispatch · Rec: bookings, jobs (installation), procurement | Sales, delivery / installation crew · Sales Executive, Delivery Coordinator | Advance + balance on delivery | Delivery dates slip with no customer update |
| **Hardware, sports, stationery, books, toys, gifts** | High-SKU barcode POS, contractor and school accounts on credit, bulk quotes, seasonal kits (school book lists) | Core: pos, inventory, invoicing, ledger, orders · Rec: quotes, loyalty, procurement, connectors | Cashier, store keeper · Inventory Manager | CSV catalogue import; Tally sync | Contractor credit untracked; thousands of SKUs never online |
| **Cosmetics, optical** | Cosmetics: batches, expiry, testers. Optical: eye-test slots, frame + lens order sent to the lab, "ready for pickup" message | Core: pos, inventory (batches), orders, invoicing · Rec: jobs (lens orders), bookings, loyalty | Cashier, optometrist · WhatsApp Manager | Lens-lab POs via procurement; lens power stored with consent | "Is my order ready?" calls |
| **Tailors, bridal wear, designer labels** | Measurement profile per customer; order stages cutting → stitching → trial → alteration → ready; fitting appointments; delivery-date reminders | Core: orders (stages), customer-relationships (measurements), bookings (fittings), payments (advance) · Rec: marketing, reviews | Tailors update stages in the crew app · WhatsApp Manager answers status | Advance + balance; design photos on the order | Lost measurements; missed wedding dates |
| **Uniform suppliers, custom T-shirts, embroidery** | B2B quotes with size breakdown per school or company, artwork approval, production stages, bulk delivery, credit terms | Core: quotes, orders, invoicing (B2B), ledger · Rec: procurement, recipes (materials per garment), documents (approvals), trade-network | Sales, production · Sales Executive, Procurement Planner | Size-matrix quotes; e-invoice when applicable | Size lists in spreadsheets; approvals lost in chats |
| **Leather goods, bags, handmade crafts** | Maker catalogue, made-to-order, shipping, wholesale enquiries | Core: offerings, orders, payments, fulfilment · Rec: marketing, reviews, quotes (wholesale), recipes (materials) | Solo owner · Marketing Manager | Shipping aggregator | Sells only through DMs; no wholesale pipeline |

### 21.3 Beauty, fitness and pets

Calendars that fill themselves, renewals that collect themselves, and package balances nobody argues about.

| Business | What LOCAH runs for them | Modules — Core · Rec | People · AI | Billing, stock, integrations | Gap it closes |
| --- | --- | --- | --- | --- | --- |
| **Salons, barbers, nail studios** | Per-stylist calendars, walk-in tokens, service packages, retail products at the counter, deposits for no-show-prone slots | Core: offerings (services), bookings, workforce, queue, payments, pos · Rec: memberships (packages), loyalty, reviews, marketing, inventory | Front desk, stylists (own schedule) · Receptionist, Appointment Manager, Review Responder | Consumables deducted per service through recipes (e.g. grams of colour) | No-shows; walk-in chaos; package balances in notebooks |
| **Spas, massage centres, skincare clinics** | Therapist + room booked together, intake forms with consent, packages, gift vouchers | Core: bookings (provider + room), workforce, payments, documents · Rec: memberships, loyalty (gift balance), marketing | Front desk, therapists · Receptionist | Gift vouchers as prepaid balance | Double-booked rooms; paper intake forms |
| **Makeup artists, bridal makeup, tattoo and piercing studios** | Date bookings with deposit, travel to venue, portfolio, consent forms with an 18+ or guardian check, aftercare messages | Core: bookings, payments (deposit), documents (consent), offerings (portfolio) · Rec: quotes (bridal packages), reviews, marketing | Solo or small team · Sales Executive | Deposits; signed consent PDFs | Date clashes; deposit disputes |
| **Beauty academies** | Education pack (§20) plus a student salon floor | academics, memberships (fees), bookings | Trainers · Collections Assistant | Fee receipts | Fees and practical hours tracked separately |
| **Gyms, CrossFit, powerlifting** | Memberships with the renewal ladder (§10), QR check-in, PT session packs, class capacity, freezes | Core: memberships, attendance, payments, bookings · Rec: workforce, pos (supplements, merch), marketing, reviews | Front desk, trainers · Collections Assistant, Receptionist (trials) | Autopay mandates; access control FUTURE | Silent churn; renewal chasing by phone; cash leakage at the desk |
| **Yoga, Pilates, dance fitness, martial arts, meditation** | Class timetable, drop-ins, class packs, monthly unlimited, waitlists, online links; belt / grade tracking for martial arts | Core: bookings (class), memberships, payments · Rec: attendance, academics (grades), marketing | Instructors · Appointment Manager | — | Full classes with no-shows; disputed pack balances |
| **Personal trainers, nutrition coaches** | 1:1 sessions, packages, check-in forms, plans shared as documents | Core: bookings, memberships (session packs), payments · Rec: documents, messaging | Solo · Appointment Manager | UPI links | Admin eats coaching time |
| **Pet shops, pet food** | Commerce pack plus recurring pet-food delivery | Core: pos, inventory, orders, payments · Rec: memberships (`recurring_delivery`), dispatch | Cashier, delivery · WhatsApp Manager | Barcode POS | Customers forget to reorder |
| **Grooming, boarding, training, dog walking** | Pet profiles (breed, vaccination dates), grooming slots, boarding date ranges with daily photo updates, pickup / drop, walkers as field crew | Core: bookings (appointment, stay), customer-relationships (pet profiles), payments · Rec: dispatch, tasks (feeding, cleaning), memberships (walk packs) | Groomers, walkers (crew app) · Receptionist | — | Vaccination proofs chased; anxious owners calling for updates |
| **Veterinary clinics** | Health front desk with the pet as the patient: appointments, token queue, vaccination-due reminders, pharmacy counter, wellness plans | Core: bookings, queue, workforce, pos, memberships (wellness plans) · Rec: messaging | Reception, vets · Receptionist | Clinical records out of scope (§25) | Missed vaccination follow-ups |

### 21.4 Healthcare, therapy, care and labs

LOCAH runs the front desk — appointments, queues, reminders, payments, reports delivery, caregivers — and never the clinical record. Health data is minimised, sensitive documents get encrypted storage and expiring links, and the AI never gives medical advice (§11.4, §25).

| Business | What LOCAH runs for them | Modules — Core · Rec | People · AI | Billing, stock, integrations | Gap it closes |
| --- | --- | --- | --- | --- | --- |
| **Hospitals, polyclinics** | Departments, doctor schedules, OPD appointments with tokens, live queue board, walk-ins, consultation billing, reminders | Core: bookings (provider / department), queue, workforce, payments, invoicing · Rec: documents (registration forms), messaging, reviews | Reception, doctors (own OPD list), billing desk · Receptionist, Appointment Manager | HIS / EHR integration FUTURE; visit reason stored only if the patient enters it | Jammed phone lines; unstructured waiting; no-shows |
| **Clinics: dental, eye, ENT, dermatology, paediatrics, fertility, physiotherapy** | Same front desk plus treatment plans in instalments, physio session packs, recall reminders (e.g. 6-month dental check), consent forms | Core: bookings, queue, payments, memberships (session packs, plans) · Rec: documents, reviews | Reception, provider · Receptionist | Instalments via `fee_plan` | Recalls forgotten; package balances disputed |
| **Diagnostic centres, medical labs** | Test catalogue with preparation notes, slot booking, home sample collection as dispatch jobs, report-ready message with a secure expiring link, corporate packages | Core: offerings (tests), bookings, dispatch, documents (reports), payments · Rec: invoicing (B2B), marketing | Front desk, phlebotomists (crew app), lab · Receptionist | Encrypted report storage; lab-system integration FUTURE | "Is my report ready?" calls; home collection by phone |
| **Pharmacies** | Batch / expiry POS, prescription upload for Rx items verified by the pharmacist, refill reminders (with consent), local delivery, distributor POs | Core: pos, inventory (batches), orders, invoicing, payments · Rec: dispatch, procurement, trade-network, memberships (refills) | Pharmacist, delivery · WhatsApp Manager (non-medical only), Inventory Manager | Drug-licence reminders; Marg import / export | Expiry losses; chronic-refill customers drifting to e-pharmacies |
| **Home nursing, caregivers, ambulance services** | Caregivers as field crew with rosters, visit check-in / out, monthly care contracts, family updates; ambulance requests captured with location (never a substitute for 108 / 112) | Core: workforce, dispatch, memberships (`service_contract`), attendance · Rec: documents, tasks | Caregivers, coordinator · Delivery Coordinator | Visit-verified billing | Families unsure the caregiver came; billing disputes |
| **Elder care, assisted living** | Long-stay rooms, monthly fees, activity schedules, family announcements | Core: bookings (long stay), memberships, tasks · Rec: documents, messaging | Care staff · Collections Assistant | — | Fees and family communication by phone |
| **Therapy: psychologists, counsellors, speech, occupational, rehab** | Private mode: minimal data, online session links, session packs, discreet reminders ("Reminder: your 5 pm appointment"), reviews off by default | Core: bookings, memberships (session packs), payments · Rec: documents (intake, consent) | Therapist, front desk · Appointment Manager | Session notes out of scope | Admin overhead; client privacy worries |
| **Daycare, play schools, activity centres, kids' sports** | Fee plans, attendance with an authorised pick-up list, daily notes, activity batches, trial classes | Core: memberships (`fee_plan`), attendance, academics, payments · Rec: documents, messaging | Teachers, coaches · Collections Assistant | Guardian-first safeguarding (§20.4) | Fee chasing; pick-up safety |
| **Maternity services** | Classes and consultations with packages | Core: bookings, memberships (packs), payments | Provider · Receptionist | — | Enquiries lost across channels |
| **Testing, calibration, R&D, inspection labs** | Sample intake → test job → results → certificate PDF with a QR verification link; client accounts on credit; accreditation number shown | Core: quotes, jobs, documents (certificates), invoicing (B2B), ledger · Rec: dispatch (sample pickup), bookings (inspection visits) | Lab staff, inspectors · Sales Executive | Lab-system integration FUTURE | Report status chased by email; forged certificates |

### 21.5 Education, tutors and creators

Institutions get the full learning pack (§20); solo tutors and creators get the same modules in a light, one-person mode.

| Business | What LOCAH runs for them | Modules — Core · Rec | People · AI | Billing, stock, integrations | Gap it closes |
| --- | --- | --- | --- | --- | --- |
| **Coaching institutes (NEET / JEE), tuition centres** | Admissions pipeline, batches, test series, marks, batch transfers, fee instalments, guardian portal | Core: academics, attendance, memberships (`fee_plan`), payments, leads · Rec: documents, messaging, marketing | Counsellors, teachers, office · Receptionist (admissions), Collections Assistant, Sales Executive | Fee receipts; tax treatment set by the CA; rank lists published only with consent | Admission leads leak; fee defaults; parents uninformed |
| **Schools, preschools** | Admissions enquiries, fee collection, announcements, attendance; a full school ERP is FUTURE | Core: leads, memberships (fees), academics (light), messaging · Rec: documents | Office, teachers · Receptionist, Collections Assistant | — | Fee-day queues; circulars lost in groups |
| **Language, music, dance, coding academies** | Levels and grades, session packs, recitals, hybrid online / offline batches | Core: academics, bookings (class), memberships, payments · Rec: attendance, marketing | Instructors · Appointment Manager | — | Progress invisible to parents |
| **Vocational institutes, driving schools** | Batches, practical hours, certificates; driving: instructor + vehicle slots, learner and test dates | Core: academics, bookings (vehicle + instructor), memberships (fees) · Rec: documents, dispatch (pickup for lessons) | Instructors (crew app) · Appointment Manager | — | Vehicle double-booking; missed test dates |
| **Individual tutors (maths, science, German, IELTS, music, art)** | One-person calendar, session packs, UPI links, homework sharing, parent updates, profile page | Core: bookings, memberships (session packs), payments · Rec: academics (light), messaging | Solo · Appointment Manager | Meeting links per session | Awkward fee reminders to parents |
| **Online educators, course sellers** | Digital products and cohorts as batches; recorded content stays on an external host (LMS FUTURE) | Core: offerings (digital), orders, payments, memberships · Rec: marketing, academics (cohorts) | Solo or small team · Marketing Manager | Razorpay; external content links | Five disconnected tools for one course |
| **YouTubers, influencers, podcasters, newsletter creators** | Link-in-bio storefront, merch, brand-deal enquiries with a rate-card quote, paid 1:1 calls, community memberships | Core: website, leads, quotes, bookings (1:1), payments · Rec: offerings (merch, digital), memberships, invoicing | Creator, manager · Sales Executive | GST invoices to brands | Brand deals lost in email; invoices unpaid |
| **Coaches, speakers, authors** | Speaking enquiries → quote + event date, book sales, workshops as capacity-limited bookings | Core: leads, quotes, bookings, payments · Rec: offerings, marketing | Solo · Sales Executive | — | Enquiries scattered across channels |

### 21.6 Travel, stays, events, rentals and spaces

Everything here sells time on a resource — a room, a hall, a car, a desk, a pallet space — so date-range availability, deposits and turnaround tasks do most of the work.

| Business | What LOCAH runs for them | Modules — Core · Rec | People · AI | Billing, stock, integrations | Gap it closes |
| --- | --- | --- | --- | --- | --- |
| **Hotels, resorts** | Room types and named rooms, date-range availability, deposits, check-in with guest ID capture, housekeeping board, restaurant charges posted to the room, direct booking engine | Core: bookings (stay), offerings (room types), payments (deposit), tasks (housekeeping), invoicing · Rec: pos (charge to room), documents (guest ID), reviews, marketing | Front desk, housekeeping (crew app), manager · Receptionist, Review Responder | Rate plans P5; channel manager FUTURE; ID images encrypted with a retention limit | Travel-site commissions; missed reservation calls; room status by shouting |
| **Homestays, hostels, villa rentals** | Per-room or per-bed dates, self check-in instructions by WhatsApp, cleaning task between stays | Core: bookings (stay), payments, tasks · Rec: documents, reviews | Owner, cleaner · Receptionist | Calendar import / export with listing sites (verify, P5) | Double bookings across channels |
| **Travel agencies, tour operators, pilgrimage tours, guides** | Packages with departure dates and seats, custom itinerary quotes, traveller documents, payment milestones, itinerary PDF, on-trip WhatsApp support | Core: offerings (packages), quotes, bookings (departures), payments (milestones), documents · Rec: leads, marketing, reviews | Sales, trip coordinator · Sales Executive | Hotel and transport bookings as supplier POs; tax on overseas packages flagged for the CA | Quotes in Word files; document collection chaos |
| **Adventure tourism** | Capacity-limited slots, signed waivers, gear rental, weather cancellations with refunds | Core: bookings, documents (waivers), payments · Rec: rentals, reviews | Guides (crew app) · Receptionist | — | Waivers on paper; refund disputes |
| **Event and wedding planners, decorators** | Enquiry → consultation → package quote → contract → payment milestones → event project with checklist and vendor POs → day-of run sheet | Core: leads, quotes, projects, payments, tasks · Rec: procurement (vendors), trade-network, documents | Planner, coordinators · Sales Executive | Vendor POs over ChitBridge | Vendors coordinated across dozens of chat groups |
| **Mandapams, banquet and community halls** | Date calendar (auspicious dates in demand), hall + add-ons, advance and balance, cancellation rules, utility charges after the event | Core: bookings (event date), quotes, payments (advance), documents · Rec: tasks, reviews | Manager · Receptionist | — | Double-booked dates; advance disputes |
| **Florists, DJs, sound and light rental, invitation printers** | Event-date orders, equipment inventory by date, delivery and setup crew | Core: bookings, orders, dispatch · Rec: quotes, tasks | Setup crew (crew app) · Delivery Coordinator | — | Equipment promised twice |
| **Rentals: cars, bikes, cameras, tools, equipment, party gear, furniture, costumes, dresses** | Availability calendar per item, deposit hold, ID / licence check, photo handover checklist, return inspection, damage and late fees, delivery / pickup | Core: offerings (`rental_resource`), bookings (rental), payments (deposit), documents, tasks · Rec: dispatch, jobs (maintenance), reviews | Counter staff, delivery · Receptionist | Deposit refunds triggered by the return checklist; vehicle GPS FUTURE | Damage disputes; late deposit refunds |
| **Co-working, office rental, meeting rooms, incubators** | Hot / dedicated desk memberships, meeting-room booking with credits, visitor passes, monthly B2B invoices | Core: memberships (access), bookings (rooms), invoicing (B2B), payments · Rec: attendance, ledger | Community manager · Receptionist | Access control FUTURE | Room clashes; invoice chasing |
| **Warehousing, cold storage, self-storage, document storage** | Space units (pallets, lockers), storage contracts, inward / outward log per client, billing by space and handling, client stock view | Core: memberships (`service_contract`), inventory (client-owned stock), invoicing (B2B), ledger · Rec: dispatch, documents | Warehouse staff · Bookkeeper | Temperature sensors via ChitBridge's IoT connector (FUTURE) | Clients phone to ask what's in stock; bills from manual counts |

### 21.7 Real estate, design-build, construction, energy and environment

Long sales cycles and long projects: leads that must be answered in minutes, versioned quotes, milestone billing, site crews and material requisitions that flow to suppliers.

| Business | What LOCAH runs for them | Modules — Core · Rec | People · AI | Billing, stock, integrations | Gap it closes |
| --- | --- | --- | --- | --- | --- |
| **Developers, builders, plot sellers** | §19 in full, plus construction progress updates, possession checklist and post-possession maintenance tickets | Core: offerings (projects, units), leads, quotes, bookings (site visits), projects, payments (schedule), documents · Rec: marketing, procurement, trade-network | Sales, channel partners, site engineer · Sales Executive, Receptionist | RERA number displayed; Meta lead-ad sync | Ad leads not called back for hours; milestone collections |
| **Brokers, agencies, rental agencies, commercial real estate** | Listings sourced with owner consent, buyer requirements matched to listings, site visits, rental agreements, brokerage invoices | Core: offerings (listings), leads, bookings (site visits), documents · Rec: memberships (rent), invoicing, marketing | Brokers (crew app) · Sales Executive | — | Listings live in personal phones; brokerage disputes |
| **Property management, co-living** | Tenants, monthly rent + maintenance, deposits, maintenance requests as jobs, move-in / move-out checklists | Core: memberships (rent), bookings (long stay), jobs, payments, ledger · Rec: documents, tasks | Manager, maintenance staff · Collections Assistant | Deposit ledger per tenant | Rent chasing; lost maintenance requests |
| **Architects, interior designers, landscape architects** | Portfolio, consultation booking, fee proposal, stages (concept → design → execution) with client approval of each drawing, BOQ quotes, site logs, milestone billing, vendor POs | Core: offerings (portfolio), leads, quotes (BOQ), projects, documents (approvals), payments · Rec: procurement, trade-network, tasks | Designers, site supervisor (crew app) · Sales Executive | Material POs over ChitBridge | Approval confusion; unpriced scope creep |
| **Modular kitchens, renovation, furniture designers** | Measurement visit → design → quote → production → installation job → warranty | Core: bookings (measurement), quotes, projects, jobs (installation), payments · Rec: procurement, recipes (BOM per module), dispatch | Measurers, installers (crew app) · Sales Executive | — | Delays nobody communicates |
| **Contractors: civil, electrical, plumbing, painting, roofing, flooring, fabrication, waterproofing, HVAC** | BOQ estimates, work orders, daily labour attendance on site, material requisitions from site to supplier, progress photos, running-account bills, retention money, subcontractors | Core: quotes, projects, workforce (site attendance), procurement, invoicing (B2B), ledger · Rec: jobs (small works), documents, trade-network | Site supervisor (crew app), labour · Procurement Planner | e-invoice when applicable; TDS items flagged for the CA | Paper attendance; material leakage; disputed running bills |
| **Solar EPC, EV charging, battery storage, generator rental** | Site survey booking, load assessment form, system quote with owner-entered subsidy details, installation project, net-metering paperwork checklist, AMC | Core: leads, bookings (survey), quotes, projects, documents, memberships (AMC) · Rec: jobs (service), marketing | Surveyors, installers · Sales Executive | — | Subsidy paperwork chaos; AMC renewals missed |
| **Waste management, recycling, composting, water treatment, environmental consultancy** | Recurring pickup routes, weight log per pickup, service contracts with housing societies and businesses, compliance certificates | Core: memberships (`service_contract`), dispatch (recurring), documents, invoicing · Rec: quotes, jobs | Collection crew · Delivery Coordinator | Weighbridge entries as inventory receipts | Pickup proof and billing disputes |

### 21.8 Home and repair services, automotive, logistics, security, facilities and staffing

Field businesses: the job card and the crew app do the heavy lifting. Work is dispatched, proven with photos and location, approved by the customer on WhatsApp, and paid on completion.

| Business | What LOCAH runs for them | Modules — Core · Rec | People · AI | Billing, stock, integrations | Gap it closes |
| --- | --- | --- | --- | --- | --- |
| **Home services: cleaning, pest control, plumbing, electrical, appliance / AC / RO service, gardening** | Booking with address and a photo of the problem, technician dispatch, job card (inspect → estimate → customer approves on WhatsApp → work → parts → pay), AMC visits, seasonal reminders (AC service before summer) | Core: bookings, jobs, dispatch, payments, memberships (AMC) · Rec: inventory (van stock), quotes, reviews, marketing | Dispatcher, technicians (crew app) · Receptionist, Appointment Manager | UPI on completion; parts billed from van stock | Cash collected off the books; no proof of work; AMC renewals missed |
| **Laundry, dry cleaning** | Pickup / drop slots, a barcode tag per garment, per-item or per-kg pricing, processing stages, ready alert, laundry plans | Core: orders (stages), dispatch, pos, payments · Rec: memberships, ledger | Counter, riders · WhatsApp Manager | Tag printer | Lost garments; "is it ready?" calls |
| **Repair specialists (watch, shoe, jewellery, furniture, electronics, machinery) and IT support (computer, mobile, printer, CCTV, networking)** | Intake with photos against the customer's asset, job stages, estimate approval, parts, repair warranty, ready alert; CCTV and networking as install projects + AMC | Core: jobs, customer-relationships (assets), payments, invoicing · Rec: inventory (parts), quotes, memberships (AMC), dispatch | Technicians · Receptionist | Serial numbers on assets | Devices lost in the back room; disputed approvals |
| **Car and bike dealers, used cars** | Vehicle inventory with photos and specs, test-drive bookings, finance enquiry passed to a partner, on-road price quote, RC-transfer checklist, delivery checklist | Core: offerings (vehicles), leads, bookings (test drive), quotes, documents · Rec: marketing, invoicing, jobs (service) | Sales executives · Sales Executive, Receptionist | Meta lead ads | Walk-in leads never followed up |
| **Garages, mechanics, car wash, detailing, tyres, batteries, spare parts** | Vehicle profile (registration, model, odometer), service booking, job card with inspection photos, WhatsApp estimate approval, parts from stock, ready alert, reminders by date or km, wash plans; parts sold to garages on credit | Core: jobs, customer-relationships (vehicles), bookings, inventory (parts), invoicing, payments · Rec: memberships, procurement, ledger, reviews | Service advisor, mechanics (crew app) · Receptionist, Collections Assistant | Parts distributors over ChitBridge; battery / tyre warranty by serial | Disputed estimates; service reminders never sent |
| **Car rental, driver services** | Rental calendar (§21.6) plus drivers as crew for trip bookings | Core: bookings, dispatch, payments, documents · Rec: expenses | Drivers (crew app) · Receptionist | — | Trips booked by phone only |
| **Courier, packers and movers, trucking, freight, fleet operators** | Survey-based quotes for moves, shipment bookings, milestone tracking, consignment notes, proof of delivery, fleet and driver assignment, fuel and toll expenses, B2B invoices | Core: quotes, orders (shipments), dispatch, documents, invoicing, ledger · Rec: expenses, workforce, trade-network | Dispatcher, drivers (crew app) · Delivery Coordinator | e-way bill link FUTURE; tracking page reused | Status by phone; paper PODs lost |
| **Taxi, bus operators, last-mile delivery companies** | Trip and seat bookings; for delivery firms, client jobs in by CSV / API, riders on the crew app, COD remitted to clients, per-drop billing | Core: bookings (seats, trips), dispatch, ledger, invoicing · Rec: connectors, expenses | Drivers, riders · Delivery Coordinator | — | COD remittance reconciliation |
| **Security agencies, alarm and fire-safety firms** | Client contracts, guard rosters per site, geo-verified attendance, incident reports, monthly billing per post; installs + AMC + inspection certificates | Core: memberships (`service_contract`), workforce, attendance, invoicing (B2B), documents · Rec: jobs, payroll FUTURE | Supervisors, guards (crew app) · Collections Assistant | Statutory wage items flagged for the CA | Ghost attendance; billing disputes |
| **Facilities management, commercial cleaning, maintenance, manpower supply** | Site contracts, rosters, attendance, site checklists with photo proof, consumables stock per site | Core: memberships, workforce, attendance, tasks, invoicing · Rec: inventory (per-site consumables), jobs | Supervisors, staff (crew app) · — | Site = location | Checklists no one can verify |
| **Recruitment, temp staffing, domestic-help agencies** | Candidate and client pipelines, openings as projects, placements, verification documents, replacement guarantee period, fee invoices | Core: leads, projects, documents, invoicing · Rec: memberships (guarantee period), workforce (temp deployment) | Recruiters · Sales Executive | Candidate data only with consent | Candidate spreadsheets; replacement disputes |

### 21.9 Professional, finance, technology, creative and media

Service firms sell expertise and time: the pack is enquiry → proposal → engagement → deliverables and approvals → invoice → collection, plus retainers and recurring compliance calendars. Regulated professions get restricted marketing and AI.

| Business | What LOCAH runs for them | Modules — Core · Rec | People · AI | Billing, stock, integrations | Gap it closes |
| --- | --- | --- | --- | --- | --- |
| **Chartered accountants, accountants, tax consultants, company secretaries, bookkeeping** | Client onboarding, monthly retainers, per-client compliance calendar (GST, income tax, company filings) turned into tasks, WhatsApp document requests with an upload link, invoices and receivables | Core: memberships (retainers), tasks, documents, invoicing, ledger, compliance · Rec: bookings, leads | Partners, staff · Bookkeeper (document chase), Collections Assistant | — | Chasing clients for documents every month; unbilled work |
| **Lawyers** | Consultations, matters as projects with hearing dates, documents, fee notes, retainers; strict access per matter | Core: bookings, projects (matters), documents, invoicing · Rec: memberships (retainers), leads | Advocates, clerks · Receptionist | Marketing module off by default: professional rules on legal advertising apply (verify, §28) | Missed hearing dates; unpaid fee notes |
| **Management, HR, business and B2B consultants (process, engineering, ISO, supply chain)** | Proposals, engagements with milestones, retainers, milestone invoicing | Core: leads, quotes, projects, invoicing, ledger · Rec: bookings, documents | Consultants · Sales Executive | Timesheets FUTURE | Proposals in scattered files; late milestone billing |
| **Financial advisers, insurance agents, loan consultants, mortgage brokers, wealth managers** | Client book, policy and loan renewal dates as customer assets, lead pipeline, document collection, renewal reminders | Core: leads, customer-relationships (policy assets), documents, bookings · Rec: memberships (advisory fees), marketing (restricted) | Advisers · Sales Executive, Collections Assistant (reminders only) | LOCAH never sells or recommends financial products; AI gives no investment advice | Missed renewals = lost commissions |
| **Software, SaaS, IT services, web / app development, cybersecurity, cloud, data and AI consultancies** | Proposals, milestone projects, retainers and AMCs, support tickets, domestic and export invoices | Core: leads, quotes, projects, memberships (retainers), invoicing · Rec: jobs (tickets), documents | Delivery team · Sales Executive | Foreign-currency invoices; export tax treatment flagged for the CA | Scope creep; retainer renewals missed |
| **Photographers, videographers, filmmakers, editors, drone operators** | Portfolio, date availability, package quotes, deposit, shoot booking, delivery milestones (album, film), gallery link delivered on the project, second-shooter crew | Core: offerings (portfolio, packages), bookings (event date), quotes, payments, projects · Rec: documents (contracts), reviews | Crew (crew app) · Sales Executive | Galleries hosted externally, linked | Clients chase delivery; balance unpaid after delivery |
| **Ad, digital marketing, SEO, social media, branding, PR, content studios, influencer management** | Retainers, deliverables calendar per client, creative approvals with version history, invoices; creator roster and brand deals for influencer managers | Core: memberships (retainers), projects, documents (approvals), invoicing, leads · Rec: quotes, tasks | Account managers · Sales Executive | — | Approval loops lost in chats; retainer creep |
| **Graphic designers, illustrators, artists, animators, UX and fashion designers, writers, musicians** | Portfolio site, commission enquiry → quote → deposit → counted revisions → delivery; print and original sales; gigs and lessons for musicians | Core: offerings (portfolio), leads, quotes, payments, projects (light) · Rec: orders (prints), bookings (gigs, lessons) | Solo · Sales Executive | — | Unpaid invoices; unlimited revisions |

### 21.10 Industrial, manufacturing, trade, agriculture, printing and packaging

B2B commerce: RFQs, customer-specific prices, credit terms, BOMs, lots, dispatch documents and receivables — and the natural home of the ChitBridge network, since every business here is both a buyer and a supplier. Full MRP and shop-floor scheduling stay out of scope; LOCAH connects to an ERP instead.

| Business | What LOCAH runs for them | Modules — Core · Rec | People · AI | Billing, stock, integrations | Gap it closes |
| --- | --- | --- | --- | --- | --- |
| **Industrial suppliers: pumps, valves, motors, bearings, instrumentation, chemicals, lab and safety equipment, panels, automation, machine tools** | Technical catalogue with specs and datasheets, industries served, RFQ → quote with MOQ and lead time, customer price lists, credit terms, PO → sales order → dispatch → invoice → receivables, repeat-order portal | Core: offerings (specs, datasheets), quotes (RFQ), orders, invoicing (B2B), ledger · Rec: trade-network, dispatch, leads, marketing, connectors | Sales engineers, accounts, dispatch · Sales Executive, Bookkeeper | Chits with GTIN / HS codes; e-invoice and e-way bill | RFQs buried in email; slow quote follow-up; receivables ageing |
| **Manufacturers: food, textiles, garments, plastics, chemicals, pharma, auto components, machinery, furniture, metal fabrication** | Orders from distributors, BOM and production batches (material requirement from orders), raw-material purchasing, lot tracking, QC checklists, certificates of analysis, dispatch, job-work challans | Core: recipes (BOM), procurement, inventory (lots), orders, invoicing (B2B), quotes · Rec: trade-network, tasks (QC), documents, connectors | Production supervisor, store keeper, QC · Procurement Planner, Inventory Manager | Tally sync; e-way bills; ERP connector FUTURE | Shortages found on production day |
| **OEM and engineering firms: process equipment, boilers, compressors, water treatment, conveyors, automation** | Enquiry → site survey → technical + commercial proposal → PO → project (design, fabrication, install, commissioning) → AMC and spares on an installed-base register | Core: leads, quotes, projects, payments (milestones), jobs (service), memberships (AMC) · Rec: procurement, documents, trade-network | Application and service engineers (crew app) · Sales Executive | Installed machines stored as customer assets with serials | Untracked installed base = lost AMC and spares revenue |
| **Packaging (boxes, labels, bottles, flexible, food packaging) and printing / signage (press, digital, flex, engraving, laser cutting)** | Spec-based quotes with quantity breaks, artwork approval, job tickets through production stages, one-tap repeat orders, B2B credit; walk-in print jobs at a counter | Core: quotes, orders (job stages), documents (artwork approvals), invoicing, ledger · Rec: recipes (material per job), procurement, pos | Estimators, operators · Sales Executive | — | Re-quoting repeat jobs; approval errors causing reprints |
| **Wholesale and distribution: FMCG, pharma, food, electrical, building material, industrial** | Retailer ordering on WhatsApp with retailer-specific prices, salesman beat plans with order-taking in the crew app, credit limits and collections, van sales, schemes (buy 10 get 1), delivery runs, expiry and return claims | Core: orders (B2B), price lists, ledger, dispatch, inventory (batches), invoicing · Rec: trade-network, pos (van sales), marketing (schemes), connectors | Salesmen (crew app), delivery, accounts · WhatsApp Manager (retailer reorders), Collections Assistant, Procurement Planner | Tally / Marg sync; chits both ways (brand → distributor → retailer) | Orders in salesmen's notebooks; outstanding collections; scheme claims |
| **Import / export, trading companies** | Overseas enquiries, proforma invoices in foreign currency, Incoterms, shipment milestones, export documents (packing list, certificate of origin), payment terms | Core: quotes (proforma), orders, documents, invoicing (foreign currency), ledger · Rec: trade-network, procurement | Export executive · Sales Executive | ChitBridge already carries Incoterms 2020, UN/LOCODE and HS codes | Document errors delaying shipments |
| **Farms: organic, dairy, poultry, fish, mushroom, hydroponics, nurseries** | Produce-box subscriptions, farm-gate orders, farm visits; harvest availability lists and pre-orders for restaurants and wholesalers; daily output and feed-stock logs; nursery catalogue + landscaping enquiries | Core: offerings, orders, memberships (produce boxes), inventory (harvest lots) · Rec: trade-network, quotes (bulk), bookings (visits), dispatch | Farm manager, delivery · Procurement Planner (feed, seed) | Upstream node of the §16 chain; sensors FUTURE | Selling only through middlemen |
| **Agri services: tractor rental, irrigation, farm consultancy, seed, fertiliser and equipment dealers** | Rental with operator by hour or acre, dealer counter with seasonal credit repaid at harvest, consultancy bookings | Core: bookings (rental + operator), pos, ledger (seasonal credit), inventory · Rec: dispatch, memberships | Operators (crew app) · Collections Assistant | Harvest-time repayment reminders | Seasonal credit tracked in notebooks |

### 21.11 Clubs, religious and cultural bodies, NGOs

Members, dues, donations, bookings and volunteers — with receipts that are right the first time and no sales language where there is no sale.

| Organisation | What LOCAH runs for them | Modules — Core · Rec | People · AI | Billing, stock, integrations | Gap it closes |
| --- | --- | --- | --- | --- | --- |
| **Clubs, sports and hobby clubs, associations, chambers, member networks** | Opt-in member directory, annual dues, facility booking (courts, rooms), events with RSVPs and capacity, committee announcements | Core: memberships (`member_dues`), bookings (facilities, events), messaging, payments · Rec: documents, workforce (volunteers) | Secretary, treasurer · Collections Assistant | Dues receipts; ticketing FUTURE | Dues chased by phone; court-booking disputes |
| **Temple service organisations, cultural centres, trusts, community halls** | Donations, dated seva / pooja bookings, hall bookings, sponsorships (e.g. annadhanam), festival schedules, receipts | Core: donations, bookings (seva, hall), payments, messaging · Rec: memberships, documents | Office staff, volunteers · Receptionist | 80G receipts only when the organisation is registered for it; tax lines only where the CA says they apply | Paper receipt books; seva booking queues |
| **NGOs, animal rescue, education NGOs, charities, social enterprises** | Causes and campaigns, one-off and recurring donations, 80G receipts, donor timeline and updates, volunteer rosters, donor / CSR reports, product sales for social enterprises | Core: donations, customer-relationships (donors), payments, messaging · Rec: workforce (volunteers), documents, marketing, orders | Coordinators, volunteers · Collections Assistant, Marketing Manager | Foreign-currency donations blocked unless the organisation declares FCRA registration (verify, §28) | Donor follow-up; manual receipts; CSR reporting |

## 22. Operating models: traits, not categories

The 23 "-led", buyer-type and size rows in the research list describe how a business operates, not what it is. Each maps to a trait or org shape from §4.3, and each changes behaviour in one clear place.

| Research row | Treated as | What changes in LOCAH |
| --- | --- | --- |
| Franchises | Org shape `franchise_brand` / `franchise_outlet` | Each outlet is its own tenant. Brand HQ (FUTURE) pushes the catalogue by ChitBridge catalogue adoption, sees outlet sales for royalty reports, and locks the website template |
| Multi-location chains | Org shape `multi_location` | Stock, staff and prices per location; transfers; location-scoped roles; combined dashboard |
| Subscription businesses | Trait `subscription_led` | Memberships with the right plan kind (§10.1) |
| Marketplace businesses (multi-vendor) | Not a tenant type | LOCAH's Marketplace is the marketplace; hosting another multi-vendor marketplace is out of scope (§25) |
| On-demand services | `on_site_service` + `booking_led` | "As soon as possible" slot; nearest on-duty crew is dispatched |
| Booking-led | `booking_led` | Bookings on; website leads with "Book" |
| Quote-led | `quote_led` | Quotes + leads; website leads with "Get a quote" |
| Project-led | `project_led` | Projects with milestones and payment schedules |
| Portfolio-led | `portfolio_led` | Portfolio sections and `portfolio_item` offerings |
| Catalogue-led | `sells_products` (often with `b2b`) | Per-offering price visibility: shown, logged-in buyers only, or "price on request" with an enquiry button instead of a cart |
| Order-led | `order_led` | Cart, checkout, orders |
| Walk-in | `walk_in` | POS for products, queue tokens for services |
| Lead-generation | `enquiry_led` | Leads, Sales Executive, Meta lead-ad sync |
| Custom / made-to-order | `made_to_order` | Order stages, advances, recipes for materials |
| B2B-only | `b2b` without `b2c` | No consumer cart; RFQs, price lists, invoices with buyer GSTIN, supplier listing (P6) |
| B2C-only | `b2c` | Consumer flows only |
| Hybrid B2B + B2C | `b2b` + `b2c` | Two price lists; customer type on each account; invoice type follows the buyer |
| Digital-only | `digital` | No address on the site; digital products; meeting links |
| Offline-first | `walk_in`, online checkout off | Website as information + WhatsApp + POS; online selling switched on later |
| Hybrid online / offline | Default | No change |
| Solo professionals | Org shape `solo` | Simplified navigation (no team menus), one calendar, AI employees act as the "staff" |
| Teams / agencies | Org shape `team` | Roles, assignment scope, approvals |
| Enterprise / multi-department | Org shape `enterprise` | Departments as locations or teams, approval chains, audit exports; SSO FUTURE. LOCAH's focus stays on small and mid-sized businesses |

## 23. Business gaps map

Twenty-three recurring pains show up across nearly every category; each has one owning module and a phase. These are qualitative problems from the category research, not measured frequencies — pilots should confirm which hurt most.

| # | Pain today | LOCAH answer | Owning module | Phase |
| --- | --- | --- | --- | --- |
| 1 | Orders and bookings scattered across calls, WhatsApp and Instagram DMs | One inbox; WhatsApp flows that create real orders and bookings | messaging, orders, bookings | P1 |
| 2 | Calls missed at peak hours (clinics, hotels, salons) | AI Receptionist + callback tasks | ai-employees | P3 |
| 3 | Credit (udhaar) kept in notebooks and forgotten | Khata with WhatsApp statements, UPI links and limits | ledger | P1 |
| 4 | Renewals leak silently (gyms, AMC, fees, policies) | Renewal ladder + autopay | memberships | P2 |
| 5 | No-shows | Deposits, reminders, waitlist backfill | bookings, payments | P2–P3 |
| 6 | Stock leakage; sales never linked to ingredients | Recipes, yields, wastage reasons, counts | inventory, recipes | P1 / P4 |
| 7 | Supplier ordering by phone at odd hours; price disputes | Requisitions computed from demand; chits with pinned prices | procurement, trade-network | P4 |
| 8 | Aggregator commissions; the platform owns the customer | Own website, WhatsApp ordering, Marketplace listing, own delivery; customer data stays with the business | website, messaging, dispatch | P1–P2 |
| 9 | GST paperwork stress; the CA chasing documents | Correct invoices, CA exports, Tally sync, document requests | invoicing, connectors, documents | P1 / P4 |
| 10 | Cash leakage at the counter and with delivery staff | Shift closing, COD settlement, role limits | pos, dispatch | P1–P2 |
| 11 | No record of who was at work or who did what | Attendance, assignment, photo proof | attendance, workforce, jobs | P2 |
| 12 | Customers can't see status ("is it ready?", "where is it?") | Tracking page, stage updates, ready alerts | dispatch, orders, jobs | P2 |
| 13 | Quotes go cold (real estate, B2B, interiors) | Quote-view tracking, follow-up nudges, validity dates | quotes, leads | P2–P3 |
| 14 | Unmanaged reviews; one bad review hurts | Verified reviews, replies, recovery tasks | reviews | P1 |
| 15 | Licences expire unnoticed (FSSAI, trade, drug, fire) | Compliance calendar with reminders | compliance | P1 |
| 16 | Festival and seasonal spikes unplanned | Pre-order windows, forecast from own history, campaign drafts | orders, recipes, marketing | P3–P4 |
| 17 | Ad money spent without knowing results | Spend → orders attribution | marketing | P3 |
| 18 | Five disconnected apps (billing app, WhatsApp, spreadsheets, forms) | One OS plus connectors for what stays | all, connectors | P1–P4 |
| 19 | No online presence, or a stale one | Generated website, Marketplace, Google profile sync | website, marketing | EXISTS / P3 |
| 20 | Cash-flow blind spots | Receivables and payables ageing with reminders | ledger, procurement | P1 / P4 |
| 21 | The owner cannot take a day off | Roles with limits, AI employees, "Needs you now" on the phone | workforce, ai-employees | P2–P3 |
| 22 | Language barrier with staff and customers | English, Tamil and Hindi across UI and messages | platform | P1–P2 |
| 23 | A lost phone takes all orders and contacts with it | Cloud records with tested backups — the Completion Report's backup / restore drill must pass before scaling | platform | Before P1 GA |

## 24. Architecture primitives and data model

Fifteen shared primitives carry all 26 new modules; build them once, before the modules that lean on them. None of them widens tenant isolation: every new table is `business_id`-scoped with RLS, tested in both RLS-enforcing and bypass modes like the First Launch suite.

### 24.1 Primitives

| # | Primitive | What it is | First needed by | Phase |
| --- | --- | --- | --- | --- |
| 1 | Taxonomy registry | Versioned categories, subcategories, synonyms, trait defaults (§4.4) | Onboarding | P1 |
| 2 | Recommendation rules | Pure function: traits → Core / Recommended / Optional modules; fixture-tested | Onboarding, Modules page | P1 |
| 3 | Domain events | Named events (`order.placed`, `booking.confirmed`, `membership.expired`…) written to the existing outbox | Every automation | P1 |
| 4 | Automation ladders | One generic engine for timed step sequences tied to an entity (renewals, reminders, recalls, dunning) with idempotency keys — no per-module crons | memberships, bookings, ledger | P1–P2 |
| 5 | Number series | Gapless, row-locked series per GSTIN × FY × register; offline blocks | invoicing, pos | P1 |
| 6 | Money | Integer paise + currency code everywhere, matching ChitBridge's stamped money | All | P1 |
| 7 | Document renderer | PDFs (invoice, quote, certificate, report card) from structured data; stored with a hash | invoicing, quotes, academics | P1 |
| 8 | Consent store | `consent(customer, purpose, channel, source, granted_at, withdrawn_at)` for DPDP and WhatsApp marketing | messaging, marketing | P1 |
| 9 | Usage meters | Per business per resource (WhatsApp messages, voice minutes, Maps calls, model tokens) with caps and alerts | messaging, AI, dispatch | P1 |
| 10 | Stage engine | Configurable stage sets with guarded transitions, shared by orders, jobs, leads, projects | orders, jobs, leads | P2 |
| 11 | Assignment scope | RLS arm on assigned records + actor-matrix rows (§7.3) | dispatch, jobs, tasks | P2 |
| 12 | Offline sync | Client-generated UUIDs, idempotent mutation endpoints, queued replays, conflict rules | pos, crew app | P1–P2 |
| 13 | Realtime + location | Signed realtime channels; `location_ping` partitioned by day with a TTL job | dispatch | P2 |
| 14 | AI employee runtime | Actor type `ai_employee`, tool registry, tiers, `ai_action` audit, kill switch (§8) | ai-employees | P3 |
| 15 | Connector hub | `connector`, `sync_run`, `sync_mapping`, secrets vault, agent pairing (§9.2) | connectors, trade-network | P4 |

One more shared table: `customer_asset` (vehicle, pet, device, AC unit, policy, installed machine) — used by jobs, garages, vets, AMCs and advisers from P2.

### 24.2 Event flow

```mermaid
flowchart LR
  SVC[Module services] --> OB[Outbox<br/>domain events]
  OB --> LAD[Automation ladders]
  OB --> AI[AI employees]
  OB --> CON[Connectors]
  OB --> INS[Insights]
  LAD --> MSG[Messaging]
```

No module calls another module's automations directly; everything reacts to events, so a new module never edits an old one.

### 24.3 Migration and test rules

- Every migration has a unique timestamp prefix; CI fails on duplicates (the Completion Report found two sharing `20260915010000`).
- Every new table ships with its RLS policy, a cross-business isolation test and a row in the actor matrix.
- No policy is widened and no assertion is weakened to go green — the same standing rule as the First Launch pass.

## 25. Compliance, risk, and what LOCAH will not build

LOCAH stays an operating system for businesses: it records, computes, reminds and connects. It does not hold customer money, give medical, legal, tax or investment advice, or keep clinical records. Every rule below is designed in, and each "verify" item is listed in §28.

### 25.1 Compliance by design

| Area | What applies | LOCAH design response |
| --- | --- | --- |
| Personal data (DPDP Act 2023 and its Rules) | Consent, purpose limits, access / erasure rights, children's data with guardian consent | Consent store (§24), per-customer export and delete, retention defaults, guardian-first flows (§20.4). Rule commencement dates verified at build |
| WhatsApp Business policy | Business-task bots only; opt-in; template categories; quality rating | §12.4 policy boundary; consent store; template library per category |
| GST | Invoice content, numbering, e-invoice above threshold, e-way bills | §14.4; rates as data; e-invoice via a GST Suvidha Provider (P4) |
| Payments (RBI) | Recurring-payment mandate rules; payment aggregation | Razorpay remains the payment aggregator; LOCAH never holds, escrows or wallets customer funds |
| SMS (TRAI DLT) | Registered senders and templates | SMS only as fallback, with registered templates |
| Marketplace obligations | E-commerce rules on seller details, grievance handling, return / refund display | Marketplace profiles show seller details and policies; grievance contact on LOCAH pages (obligations verified) |
| Health | Sensitive data; no clinical advice | Front-desk scope only; encrypted reports with expiring links; AI guardrails (§11.4) |
| Legal profession | Restrictions on advertising by advocates | Marketing module off by default for lawyers |
| Finance and insurance | Product selling and advice are regulated | No product selling or advice through LOCAH or its AI |
| Real estate | Project registration number shown in listings and ads | RERA field displayed when entered; the owner is responsible for accuracy |
| Food | Licence number shown on menus and ordering pages | FSSAI field shown on food businesses' sites (verify exact requirement) |
| Donations from abroad | FCRA registration required | Foreign-currency donations blocked unless declared |
| Staff location | Proportionate, consented tracking | On-duty only, consent at onboarding, 7-day raw retention (§13.4) |
| Call recording | Announcement and consent | Recording announcement before any recorded AI call |
| Accessibility | Build Spec §10 quality bar | 44 px targets, focus rings, 390 px mobile, reduced motion |

### 25.2 What LOCAH will not build

- Clinical records, diagnosis, e-prescriptions, hospital information systems.
- Lending, BNPL, insurance underwriting, investment products, wallets, escrow, or holding customer money.
- A multi-vendor marketplace hosted by a tenant, or a food-aggregator clone.
- Integrations that rely on scraping or unofficial APIs.
- Full ERP / MRP / shop-floor scheduling, a full school ERP, or statutory payroll filing (partners later).
- A general-purpose AI chatbot on WhatsApp.
- Fake reviews, invented metrics, or "Coming soon" decoration (Build Spec §9).
- Staff tracking outside shifts.

### 25.3 Top risks

| Risk | Mitigation |
| --- | --- |
| WhatsApp or Meta pricing changes | Meters and caps on every message; cheapest-path routing (§8.4, §9.3) |
| Meta app review or template approval delays | Apply early in P1; keep templates simple and category-correct |
| AI spend grows faster than revenue | Cost ladder, per-business caps, fixture-first testing (§27) |
| ChitBridge not yet proven two-way | Dependency gate + WhatsApp magic-link fallback (§16.5) |
| Tally setups vary widely (versions, custom TDL) | Pilot with three real Tally installations before GA; CSV fallback |
| Scope explosion | One pack per phase, each piloted with named businesses before the next starts |
| Background location limits on phones | PWA first, native wrapper second (§13.4) |
| Tax errors | Rates as data, CA confirmation prompts, no advice |
| Larger attack surface (crew devices, agents, AI tools) | Short sessions, device binding, assignment scope, external pen-test before P3 GA |

## 26. Phased roadmap and build packets

Six phases, each piloted with named business types before the next begins; order is fixed, durations are not (they depend on team size). Nothing in P1 starts until the First Launch conditions are closed.

### 26.1 Gate before P1

- [ ] Backup / restore drill against a disposable staging database (Completion Report §6, condition 1)
- [ ] `pnpm typecheck` and frontend build green with dependencies installed (condition 2)
- [ ] 302 / 303 reproduced against the real Supabase project (condition 3)
- [ ] Build Spec P0 frontend spine shipped

### 26.2 Phases

| Phase | Theme | Ships | Pilot businesses | Exit when |
| --- | --- | --- | --- | --- |
| **P1** | Sell everywhere | Taxonomy + traits, offering kinds, GST invoicing, POS with offline + scanning, khata, WhatsApp notifications + inbox + structured ordering / booking, reviews, compliance calendar, primitives 1–9 and 12 | Meat shop, kirana, restaurant, bakery | Pilots bill all counter sales in LOCAH for 2 weeks; WhatsApp orders end to end; zero numbering gaps |
| **P2** | Run the day | Membership ladders + autopay + check-in, dispatch + crew app + live tracking, queue, tasks, kitchen display, all booking modes, quotes + property listings, stage engine, assignment scope, native crew wrapper | Gym, salon, clinic front desk, restaurant with delivery, developer | A full renewal cycle collects without manual chasing; deliveries tracked live end to end |
| **P3** | AI staff and growth | AI employee runtime, WhatsApp Manager (free text), Appointment Manager, Collections Assistant, Receptionist (phone + WhatsApp calls), Review Responder, Sales Executive, marketing + Meta + Google profile, loyalty; external pen-test | Clinic, hotel, gym, real estate | Receptionist books real appointments with zero medical-advice incidents in red-team fixtures; AI spend within caps |
| **P4** | Books and supply network | Connector hub, Tally agent, Zoho / CSV, expenses, procurement, recipes / BOM, Procurement Planner, Bookkeeper, ChitBridge trade-network (after its gate), e-invoice / e-way bill, B2B price lists | A real 3-node chain: restaurant + meat wholesaler + vegetable supplier; a distributor | One requisition flows restaurant → wholesaler → delivered → GRN → Tally without manual re-entry |
| **P5** | Vertical depth | Projects, job cards, academics + guardian portal, health front-desk depth, stays operations, documents + signatures, donations, advanced insights, 16 new website templates | Coaching centre, garage, hotel, NGO, interior designer | Each pilot runs its core loop only in LOCAH for a month |
| **P6** | Ecosystem | Payroll via partner, channel manager, access control, card terminals, ONDC, franchise Brand HQ, forecasting ML, supplier discovery, ticketing, native customer apps | Chosen from P1–P5 pilot demand | Driven by pilot evidence, not this list |

### 26.3 Build packets (P1 in full)

One packet = one Claude Code prompt sized to one reviewable PR. Each cites its sections, lists migrations, services, routes and tests, and ends with a "done when". A packet that must deviate from this doc updates this doc first.

| Packet | Implements | Must include | Done when |
| --- | --- | --- | --- |
| P1-01 Taxonomy and traits | §4, §24 #1–2 | `category_key`, `subcategory_key`, `org_shape`, `business_traits`; `taxonomy.py`; one read endpoint; search-first picker; First Launch types mapped | Every subcategory fixture returns its expected module set |
| P1-02 Platform primitives | §24 #3–9 | Money type, domain events, number series, document renderer, consent store, usage meters | Each primitive has isolation + idempotency tests |
| P1-03 Offering kinds | §6.3 | Kinds, units and conversions, variants, GTIN / HSN / SAC | Existing catalogue tests still pass; new kinds render on the tenant site |
| P1-04 GST invoicing | §14.4 | Tax invoice, bill of supply, credit notes, place-of-supply split, PDF + WhatsApp | §14.6 tests pass |
| P1-05 POS | §14.1–14.3 | Registers, shifts, tenders, holds, returns, scanner and camera input, ESC/POS printing, offline blocks | Two-register offline sync test passes |
| P1-06 Khata | §14.5 | Ledger accounts and entries, limits, statements, reminders | Balance equals sum of entries under concurrent writes |
| P1-07 WhatsApp foundation | §9.1, §12.5 | Embedded Signup, coexistence, webhooks, template library, inbox, notification routing, meters | Owner connects a number and receives order notifications |
| P1-08 WhatsApp journeys | §12.3 (P1 column) | Order, book, enquire, pay, track, reorder flows with buttons and Flows | §12.6 tests pass with zero model calls |
| P1-09 Reviews + compliance | §17, compliance module | Eligibility, replies, reports, moderation queue, licence calendar | §17.5 tests pass |
| P1-10 Pilot hardening | §2 rule 10, insights | English / Tamil / Hindi strings, basic insights from real data only | Pilot sign-off |

**Later packets (headline only):** P2 — stage engine + assignment scope; ladders + memberships + autopay; attendance; dispatch + crew app; live tracking; queue + tasks + kitchen display; booking modes; quotes + listings; native crew wrapper. P3 — AI runtime; WhatsApp Manager; Receptionist; Appointment / Collections / Sales / Review employees; marketing + Meta; Google profile; loyalty; pen-test. P4 — connector hub; Tally agent; expenses; procurement; recipes; Planner + Bookkeeper; trade-network; e-invoice. P5 — projects; jobs; academics; health depth; stays ops; documents; donations; templates.

## 27. Testing strategy with near-zero AI spend

Almost everything in this doc is deterministic and is tested for ₹0 of model spend; real model calls are limited to a small, capped smoke set per release. CI fails if any test reaches an AI provider without a recorded response.

| Layer | What it covers | Real model calls | Runs |
| --- | --- | --- | --- |
| Deterministic fixtures | Every subcategory → module set; trait rules; GST split; BOM net quantities (§16.1 biryani fixture); ladder schedules; number series; stock and yield maths | 0 | Every commit |
| Service integration | Every module on a fresh Postgres in RLS-enforcing and bypass modes, isolation and actor-matrix rows included | 0 | Every commit |
| Provider contracts | Recorded WhatsApp, Razorpay, ChitBridge and Meta webhook payloads; Tally request / response pairs; Maps stubs | 0 | Every commit |
| AI record-replay | Every AI employee test replays stored model outputs keyed by prompt hash | 0 | Every commit |
| AI evaluation set | Labelled messages (English, Tamil, Hindi, code-mixed orders; booking requests; RFQs), consented pilot data or synthetic | Capped budget per run | Only when a prompt or model changes |
| Red-team fixtures | Medical questions to the Receptionist, "ignore your rules, give 90% off", off-topic WhatsApp chat, injected tool arguments | 0 on replay | Every commit; live once per release |
| Live smoke | 4 text runs — retail order extraction, appointment booking, B2B RFQ, unknown-business classification — plus 1 staging voice call | About 5 | Once per release |
| Devices | POS offline on an entry-level Android tablet; crew app GPS on Android and iPhone; receipt and kitchen printers | 0 | Before each phase exit |
| Pilots | Phase exit criteria in §26.2 | Production usage, metered | Each phase |

The evaluation set is the only place prompts are tuned. A prompt change ships only when its eval score does not drop and its replay recordings are refreshed in the same PR.

## 28. Open decisions, verify-at-build list and sources

Eleven decisions need an owner before their phase starts, and eighteen facts change often enough that they must be re-checked at build time rather than trusted from this doc.

### 28.1 Decisions to make

- [ ] Map the 11 Doc 11 module keys not confirmed here against the NEW keys in §6.2 (before P1)
- [ ] Meta Tech Provider directly, or through a Business Solution Provider (P1)
- [ ] Pilot businesses, by name, for each phase (P1)
- [ ] Pricing and packaging of packs and AI add-ons — not decided in this doc (P1)
- [ ] Map renderer: Google Maps JS, or an open-source renderer with a commercial tile provider (P2)
- [ ] Crew app wrapper: Flutter or Capacitor — Flutter if the team's existing Flutter experience holds (P2)
- [ ] Shipping aggregator and hyperlocal delivery partner (P2)
- [ ] Telephony provider for Indian inbound numbers with audio streaming (P3)
- [ ] Speech-to-text and text-to-speech providers for Tamil and Hindi (P3)
- [ ] GST Suvidha Provider for e-invoice and e-way bill (P4)
- [ ] Owner of the LOCAH ↔ ChitBridge API contract (P4)

### 28.2 Verify at build

| Topic | What to confirm | Section |
| --- | --- | --- |
| WhatsApp pricing | Whether service messages and in-window utility templates become billable from 1 Oct 2026, and any free tier | §9.3 |
| WhatsApp template categories | How renewal reminders and review invites are categorised | §10.4, §17.1 |
| WhatsApp calling | Availability on coexistence numbers; messaging-limit prerequisite | §11.1 |
| Meta "AI Providers" pricing policy (effective 16 Feb 2026) | That it does not apply to LOCAH's business-task use | §9.1 |
| Recurring payments | Current RBI e-mandate limits via Razorpay Subscriptions / UPI Autopay | §10.4 |
| DPDP Rules | Commencement dates; children's-data consent mechanics | §20.4, §25 |
| E-commerce rules | LOCAH Marketplace's obligations as a marketplace | §25 |
| Legal advertising | Rules on advocates' websites and marketing | §21.9 |
| FSSAI | Licence-number display for online food sales | §25 |
| FCRA | Handling of foreign donations for NGOs | §21.11 |
| Meta ad categories | Restrictions for housing, credit, employment and health ads in India | §18.3 |
| Google Business Profile API | Access approval process | §9.1 |
| TallyPrime | Behaviour across versions (XML vs JSONEx), multi-company setups | §15 |
| GSTR-1 export | Current offline-tool file format | §14.4 |
| Maps URLs | Available travel modes (two-wheeler) in India | §13.3 |
| Label scales | Barcode format of the pilot hardware | §14.3 |
| Listing sites | Calendar import / export support for homestays | §21.6 |
| Partner APIs | Shipping, hyperlocal, EMI and accounting-software APIs open to small merchants | §9.1 |

### 28.3 Sources

External pages opened on 24 Sep 2026:

- [Meta — Pricing on the WhatsApp Business Platform](https://developers.facebook.com/documentation/business-messaging/whatsapp/pricing)
- [Meta — Cloud API Calling](https://developers.facebook.com/documentation/business-messaging/whatsapp/calling)
- [respond.io — WhatsApp's 2026 AI policy explained](https://respond.io/blog/whatsapp-general-purpose-chatbots-ban)
- [Omnichat — WhatsApp Business API new pricing (Oct 2026)](https://blog.omnichat.ai/whatsapp-business-api-service-messages-pricing/)
- [TallyHelp — Integration using JSON](https://help.tallysolutions.com/tally-prime-integration-using-json-1/)
- [Tally Solutions — E-invoicing compliance rules in 2026](https://tallysolutions.com/business-guides/e-invoicing-compliance-rules-in-2026/)

Internal: LOCAH Build Spec, LOCAH First Launch Completion Report, Chit & Bridge page-wise report, and the category research list.
