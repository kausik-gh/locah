"""Sector playbooks (MD §21; PDF §18), operating models (MD §22) and gaps map
(MD §23). A playbook row is COMPLETE when the taxonomy maps its subcategories,
a fixture asserts its Core/Recommended modules, and every Core module is
COMPLETE."""

from __future__ import annotations

from tools.ledger.model import Row, Section, r

S, P, C, A, F = "NOT_STARTED", "PARTIAL", "COMPLETE", "ACTIVATION_REQUIRED", "FUTURE"


def pb(id: str, ph: str, src: str, fam: str, core: str, rec: str) -> Row:
    return r(id, ph, src, f"{fam} — Core: {core} · Rec: {rec}", "playbook", "NEW", S,
             "no trait→module fixture yet", test="✗ fixture")


food = Section("AQ. Playbook 21.1 Food and fresh commerce", "", [
    pb("PB-101", "P2", "MD §21.1", "Meat, chicken, fish shops", "offerings (weighed), orders, payments, inventory (yield), pos, fulfilment, dispatch", "messaging, ledger, procurement, trade-network"),
    pb("PB-102", "P1", "MD §21.1", "Grocery, kirana, supermarket", "pos, invoicing, inventory (batches, expiry), ledger, orders, payments", "fulfilment, dispatch, loyalty, procurement, connectors"),
    pb("PB-103", "P2", "MD §21.1", "Fruit, vegetable, dairy, egg sellers", "memberships (recurring_delivery), orders, dispatch, ledger, payments", "pos, inventory (perishable), procurement"),
    pb("PB-104", "P1", "MD §21.1", "Home kitchens, pickles, podi, snacks, sweets, home bakers, chocolates", "offerings, orders, payments, fulfilment", "recipes, inventory (batches), invoicing, marketing, reviews"),
    pb("PB-105", "P4", "MD §21.1", "Tiffin services, meal subscriptions, cloud kitchens", "memberships (recurring_delivery), orders, kitchen, dispatch, recipes", "procurement, inventory, reviews"),
    pb("PB-106", "P2", "MD §21.1", "Restaurants, cafés, QSR, pubs", "offerings (menu + modifiers), orders, pos, kitchen, payments, invoicing, bookings (table)", "recipes, inventory, procurement, trade-network, dispatch, loyalty, reviews, marketing"),
    pb("PB-107", "P1", "MD §21.1", "Bakeries, sweet shops", "pos, orders (dated pre-orders), offerings (weighed + custom), payments (advance)", "recipes, kitchen, dispatch, marketing, loyalty"),
    pb("PB-108", "P4", "MD §21.1", "Catering, canteens", "leads, quotes, bookings (event date), payments (milestones), recipes, procurement", "trade-network, workforce, invoicing (B2B), ledger"),
])

retail = Section("AR. Playbook 21.2 Retail and custom products", "", [
    pb("PB-201", "P1", "MD §21.2", "Clothing, footwear, fashion retail", "offerings (variants), pos, inventory, orders, payments, fulfilment, invoicing", "loyalty, marketing, reviews, connectors"),
    pb("PB-202", "P1", "MD §21.2", "Electronics, mobile stores", "offerings (serialised), pos, inventory (serials), invoicing, payments", "jobs, bookings, leads"),
    pb("PB-203", "P1", "MD §21.2", "Jewellery", "offerings (formula-priced), pos, invoicing, inventory (per piece), orders", "leads, bookings (consultation)"),
    pb("PB-204", "P2", "MD §21.2", "Furniture, home decor, kitchenware", "offerings, orders, quotes, payments (advance), fulfilment, dispatch", "bookings, jobs (installation), procurement"),
    pb("PB-205", "P1", "MD §21.2", "Hardware, sports, stationery, books, toys, gifts", "pos, inventory, invoicing, ledger, orders", "quotes, loyalty, procurement, connectors"),
    pb("PB-206", "P1", "MD §21.2", "Cosmetics, optical", "pos, inventory (batches), orders, invoicing", "jobs (lens orders), bookings, loyalty"),
    pb("PB-207", "P2", "MD §21.2", "Tailors, bridal wear, designer labels", "orders (stages), customer-relationships (measurements), bookings (fittings), payments (advance)", "marketing, reviews"),
    pb("PB-208", "P2", "MD §21.2", "Uniform suppliers, custom T-shirts, embroidery", "quotes, orders, invoicing (B2B), ledger", "procurement, recipes, documents (approvals), trade-network"),
    pb("PB-209", "P1", "MD §21.2", "Leather goods, bags, handmade crafts", "offerings, orders, payments, fulfilment", "marketing, reviews, quotes (wholesale), recipes"),
])

beauty = Section("AS. Playbook 21.3 Beauty, fitness and pets", "", [
    pb("PB-301", "P2", "MD §21.3", "Salons, barbers, nail studios", "offerings (services), bookings, workforce, queue, payments, pos", "memberships (packages), loyalty, reviews, marketing, inventory"),
    pb("PB-302", "P5", "MD §21.3", "Spas, massage centres, skincare clinics", "bookings (provider + room), workforce, payments, documents", "memberships, loyalty (gift balance), marketing"),
    pb("PB-303", "P5", "MD §21.3", "Makeup artists, bridal makeup, tattoo and piercing studios", "bookings, payments (deposit), documents (consent), offerings (portfolio)", "quotes (bridal packages), reviews, marketing"),
    pb("PB-304", "P5", "MD §21.3", "Beauty academies", "academics, memberships (fees), bookings", "—"),
    pb("PB-305", "P2", "MD §21.3", "Gyms, CrossFit, powerlifting", "memberships, attendance, payments, bookings", "workforce, pos, marketing, reviews"),
    pb("PB-306", "P2", "MD §21.3", "Yoga, Pilates, dance fitness, martial arts, meditation", "bookings (class), memberships, payments", "attendance, academics (grades), marketing"),
    pb("PB-307", "P2", "MD §21.3", "Personal trainers, nutrition coaches", "bookings, memberships (session packs), payments", "documents, messaging"),
    pb("PB-308", "P2", "MD §21.3", "Pet shops, pet food", "pos, inventory, orders, payments", "memberships (recurring_delivery), dispatch"),
    pb("PB-309", "P2", "MD §21.3", "Grooming, boarding, training, dog walking", "bookings (appointment, stay), customer-relationships (pet profiles), payments", "dispatch, tasks, memberships (walk packs)"),
    pb("PB-310", "P2", "MD §21.3", "Veterinary clinics", "bookings, queue, workforce, pos, memberships (wellness plans)", "messaging"),
])

health = Section("AT. Playbook 21.4 Healthcare, therapy, care and labs", "Front desk only; never the clinical record.", [
    pb("PB-401", "P2", "MD §21.4", "Hospitals, polyclinics", "bookings (provider/department), queue, workforce, payments, invoicing", "documents, messaging, reviews"),
    pb("PB-402", "P2", "MD §21.4", "Clinics: dental, eye, ENT, dermatology, paediatrics, fertility, physiotherapy", "bookings, queue, payments, memberships (session packs, plans)", "documents, reviews"),
    pb("PB-403", "P5", "MD §21.4", "Diagnostic centres, medical labs", "offerings (tests), bookings, dispatch, documents (reports), payments", "invoicing (B2B), marketing"),
    pb("PB-404", "P1", "MD §21.4", "Pharmacies", "pos, inventory (batches), orders, invoicing, payments", "dispatch, procurement, trade-network, memberships (refills)"),
    pb("PB-405", "P2", "MD §21.4", "Home nursing, caregivers, ambulance services", "workforce, dispatch, memberships (service_contract), attendance", "documents, tasks"),
    pb("PB-406", "P2", "MD §21.4", "Elder care, assisted living", "bookings (long stay), memberships, tasks", "documents, messaging"),
    pb("PB-407", "P2", "MD §21.4", "Therapy: psychologists, counsellors, speech, occupational, rehab", "bookings, memberships (session packs), payments", "documents (intake, consent)"),
    pb("PB-408", "P5", "MD §21.4", "Daycare, play schools, activity centres, kids' sports", "memberships (fee_plan), attendance, academics, payments", "documents, messaging"),
    pb("PB-409", "P2", "MD §21.4", "Maternity services", "bookings, memberships (packs), payments", "—"),
    pb("PB-410", "P5", "MD §21.4", "Testing, calibration, R&D, inspection labs", "quotes, jobs, documents (certificates), invoicing (B2B), ledger", "dispatch (sample pickup), bookings (inspection visits)"),
])

edu = Section("AU. Playbook 21.5 Education, tutors and creators", "", [
    pb("PB-501", "P5", "MD §21.5", "Coaching institutes (NEET/JEE), tuition centres", "academics, attendance, memberships (fee_plan), payments, leads", "documents, messaging, marketing"),
    pb("PB-502", "P5", "MD §21.5", "Schools, preschools (full ERP FUTURE)", "leads, memberships (fees), academics (light), messaging", "documents"),
    pb("PB-503", "P5", "MD §21.5", "Language, music, dance, coding academies", "academics, bookings (class), memberships, payments", "attendance, marketing"),
    pb("PB-504", "P5", "MD §21.5", "Vocational institutes, driving schools", "academics, bookings (vehicle + instructor), memberships (fees)", "documents, dispatch"),
    pb("PB-505", "P2", "MD §21.5", "Individual tutors", "bookings, memberships (session packs), payments", "academics (light), messaging"),
    pb("PB-506", "P2", "MD §21.5", "Online educators, course sellers (LMS FUTURE)", "offerings (digital), orders, payments, memberships", "marketing, academics (cohorts)"),
    pb("PB-507", "P2", "MD §21.5", "YouTubers, influencers, podcasters, newsletter creators", "website, leads, quotes, bookings (1:1), payments", "offerings (merch, digital), memberships, invoicing"),
    pb("PB-508", "P2", "MD §21.5", "Coaches, speakers, authors", "leads, quotes, bookings, payments", "offerings, marketing"),
])

stays = Section("AV. Playbook 21.6 Travel, stays, events, rentals and spaces", "", [
    pb("PB-601", "P2", "MD §21.6", "Hotels, resorts (rate plans P5; channel manager FUTURE)", "bookings (stay), offerings (room types), payments (deposit), tasks (housekeeping), invoicing", "pos (charge to room), documents (guest ID), reviews, marketing"),
    pb("PB-602", "P2", "MD §21.6", "Homestays, hostels, villa rentals", "bookings (stay), payments, tasks", "documents, reviews"),
    pb("PB-603", "P5", "MD §21.6", "Travel agencies, tour operators, pilgrimage tours, guides", "offerings (packages), quotes, bookings (departures), payments (milestones), documents", "leads, marketing, reviews"),
    pb("PB-604", "P5", "MD §21.6", "Adventure tourism", "bookings, documents (waivers), payments", "rentals, reviews"),
    pb("PB-605", "P5", "MD §21.6", "Event and wedding planners, decorators", "leads, quotes, projects, payments, tasks", "procurement, trade-network, documents"),
    pb("PB-606", "P5", "MD §21.6", "Mandapams, banquet and community halls", "bookings (event date), quotes, payments (advance), documents", "tasks, reviews"),
    pb("PB-607", "P2", "MD §21.6", "Florists, DJs, sound and light rental, invitation printers", "bookings, orders, dispatch", "quotes, tasks"),
    pb("PB-608", "P5", "MD §21.6", "Rentals: cars, bikes, cameras, tools, equipment, party gear, furniture, costumes, dresses", "offerings (rental_resource), bookings (rental), payments (deposit), documents, tasks", "dispatch, jobs (maintenance), reviews"),
    pb("PB-609", "P2", "MD §21.6", "Co-working, office rental, meeting rooms, incubators", "memberships (access), bookings (rooms), invoicing (B2B), payments", "attendance, ledger"),
    pb("PB-610", "P4", "MD §21.6", "Warehousing, cold storage, self-storage, document storage", "memberships (service_contract), inventory (client-owned stock), invoicing (B2B), ledger", "dispatch, documents"),
])

build = Section("AW. Playbook 21.7 Real estate, design-build, construction, energy and environment", "", [
    pb("PB-701", "P5", "MD §21.7", "Developers, builders, plot sellers", "offerings (projects, units), leads, quotes, bookings (site visits), projects, payments (schedule), documents", "marketing, procurement, trade-network"),
    pb("PB-702", "P5", "MD §21.7", "Brokers, agencies, rental agencies, commercial real estate", "offerings (listings), leads, bookings (site visits), documents", "memberships (rent), invoicing, marketing"),
    pb("PB-703", "P5", "MD §21.7", "Property management, co-living", "memberships (rent), bookings (long stay), jobs, payments, ledger", "documents, tasks"),
    pb("PB-704", "P5", "MD §21.7", "Architects, interior designers, landscape architects", "offerings (portfolio), leads, quotes (BOQ), projects, documents (approvals), payments", "procurement, trade-network, tasks"),
    pb("PB-705", "P5", "MD §21.7", "Modular kitchens, renovation, furniture designers", "bookings (measurement), quotes, projects, jobs (installation), payments", "procurement, recipes (BOM), dispatch"),
    pb("PB-706", "P5", "MD §21.7", "Contractors: civil, electrical, plumbing, painting, roofing, flooring, fabrication, waterproofing, HVAC", "quotes, projects, workforce (site attendance), procurement, invoicing (B2B), ledger", "jobs, documents, trade-network"),
    pb("PB-707", "P5", "MD §21.7", "Solar EPC, EV charging, battery storage, generator rental", "leads, bookings (survey), quotes, projects, documents, memberships (AMC)", "jobs (service), marketing"),
    pb("PB-708", "P5", "MD §21.7", "Waste management, recycling, composting, water treatment, environmental consultancy", "memberships (service_contract), dispatch (recurring), documents, invoicing", "quotes, jobs"),
])

field = Section("AX. Playbook 21.8 Home/repair services, automotive, logistics, security, facilities, staffing", "", [
    pb("PB-801", "P5", "MD §21.8", "Home services: cleaning, pest control, plumbing, electrical, appliance/AC/RO, gardening", "bookings, jobs, dispatch, payments, memberships (AMC)", "inventory (van stock), quotes, reviews, marketing"),
    pb("PB-802", "P2", "MD §21.8", "Laundry, dry cleaning", "orders (stages), dispatch, pos, payments", "memberships, ledger"),
    pb("PB-803", "P5", "MD §21.8", "Repair specialists and IT support", "jobs, customer-relationships (assets), payments, invoicing", "inventory (parts), quotes, memberships (AMC), dispatch"),
    pb("PB-804", "P5", "MD §21.8", "Car and bike dealers, used cars", "offerings (vehicles), leads, bookings (test drive), quotes, documents", "marketing, invoicing, jobs (service)"),
    pb("PB-805", "P5", "MD §21.8", "Garages, mechanics, car wash, detailing, tyres, batteries, spare parts", "jobs, customer-relationships (vehicles), bookings, inventory (parts), invoicing, payments", "memberships, procurement, ledger, reviews"),
    pb("PB-806", "P5", "MD §21.8", "Car rental, driver services", "bookings, dispatch, payments, documents", "expenses"),
    pb("PB-807", "P5", "MD §21.8", "Courier, packers and movers, trucking, freight, fleet", "quotes, orders (shipments), dispatch, documents, invoicing, ledger", "expenses, workforce, trade-network"),
    pb("PB-808", "P2", "MD §21.8", "Taxi, bus operators, last-mile delivery companies", "bookings (seats, trips), dispatch, ledger, invoicing", "connectors, expenses"),
    pb("PB-809", "P5", "MD §21.8", "Security agencies, alarm and fire-safety firms", "memberships (service_contract), workforce, attendance, invoicing (B2B), documents", "jobs, payroll FUTURE"),
    pb("PB-810", "P2", "MD §21.8", "Facilities management, commercial cleaning, maintenance, manpower", "memberships, workforce, attendance, tasks, invoicing", "inventory (per-site consumables), jobs"),
    pb("PB-811", "P5", "MD §21.8", "Recruitment, temp staffing, domestic-help agencies", "leads, projects, documents, invoicing", "memberships (guarantee period), workforce"),
])

pro = Section("AY. Playbook 21.9 Professional, finance, technology, creative and media", "", [
    pb("PB-901", "P5", "MD §21.9", "CAs, accountants, tax consultants, company secretaries, bookkeeping", "memberships (retainers), tasks, documents, invoicing, ledger, compliance", "bookings, leads"),
    pb("PB-902", "P5", "MD §21.9", "Lawyers (marketing off by default)", "bookings, projects (matters), documents, invoicing", "memberships (retainers), leads"),
    pb("PB-903", "P2", "MD §21.9", "Management, HR, business and B2B consultants", "leads, quotes, projects, invoicing, ledger", "bookings, documents"),
    pb("PB-904", "P5", "MD §21.9", "Financial advisers, insurance agents, loan consultants, mortgage brokers, wealth managers", "leads, customer-relationships (policy assets), documents, bookings", "memberships (advisory fees), marketing (restricted)"),
    pb("PB-905", "P2", "MD §21.9", "Software, SaaS, IT services, web/app development, cybersecurity, cloud, data/AI", "leads, quotes, projects, memberships (retainers), invoicing", "jobs (tickets), documents"),
    pb("PB-906", "P2", "MD §21.9", "Photographers, videographers, filmmakers, editors, drone operators", "offerings (portfolio, packages), bookings (event date), quotes, payments, projects", "documents (contracts), reviews"),
    pb("PB-907", "P5", "MD §21.9", "Ad, digital marketing, SEO, social, branding, PR, content, influencer management", "memberships (retainers), projects, documents (approvals), invoicing, leads", "quotes, tasks"),
    pb("PB-908", "P2", "MD §21.9", "Graphic designers, illustrators, artists, animators, UX/fashion designers, writers, musicians", "offerings (portfolio), leads, quotes, payments, projects (light)", "orders (prints), bookings (gigs, lessons)"),
])

industrial = Section("AZ. Playbook 21.10 Industrial, manufacturing, trade, agriculture, printing, packaging", "Full MRP / shop-floor scheduling out of scope.", [
    pb("PB-1001", "P2", "MD §21.10", "Industrial suppliers: pumps, valves, motors, bearings, instrumentation, chemicals, lab/safety equipment, panels, automation, machine tools", "offerings (specs, datasheets), quotes (RFQ), orders, invoicing (B2B), ledger", "trade-network, dispatch, leads, marketing, connectors"),
    pb("PB-1002", "P4", "MD §21.10", "Manufacturers: food, textiles, garments, plastics, chemicals, pharma, auto components, machinery, furniture, metal fabrication", "recipes (BOM), procurement, inventory (lots), orders, invoicing (B2B), quotes", "trade-network, tasks (QC), documents, connectors"),
    pb("PB-1003", "P5", "MD §21.10", "OEM and engineering firms", "leads, quotes, projects, payments (milestones), jobs (service), memberships (AMC)", "procurement, documents, trade-network"),
    pb("PB-1004", "P2", "MD §21.10", "Packaging and printing/signage", "quotes, orders (job stages), documents (artwork approvals), invoicing, ledger", "recipes, procurement, pos"),
    pb("PB-1005", "P4", "MD §21.10", "Wholesale and distribution", "orders (B2B), price lists, ledger, dispatch, inventory (batches), invoicing", "trade-network, pos (van sales), marketing (schemes), connectors"),
    pb("PB-1006", "P4", "MD §21.10", "Import / export, trading companies", "quotes (proforma), orders, documents, invoicing (foreign currency), ledger", "trade-network, procurement"),
    pb("PB-1007", "P2", "MD §21.10", "Farms: organic, dairy, poultry, fish, mushroom, hydroponics, nurseries", "offerings, orders, memberships (produce boxes), inventory (harvest lots)", "trade-network, quotes (bulk), bookings (visits), dispatch"),
    pb("PB-1008", "P2", "MD §21.10", "Agri services: tractor rental, irrigation, farm consultancy, seed/fertiliser/equipment dealers", "bookings (rental + operator), pos, ledger (seasonal credit), inventory", "dispatch, memberships"),
])

community = Section("BA. Playbook 21.11 Clubs, religious and cultural bodies, NGOs", "No sales language where there is no sale.", [
    pb("PB-1101", "P5", "MD §21.11", "Clubs, sports and hobby clubs, associations, chambers, member networks", "memberships (member_dues), bookings (facilities, events), messaging, payments", "documents, workforce (volunteers)"),
    pb("PB-1102", "P5", "MD §21.11", "Temple service organisations, cultural centres, trusts, community halls", "donations, bookings (seva, hall), payments, messaging", "memberships, documents"),
    pb("PB-1103", "P5", "MD §21.11", "NGOs, animal rescue, education NGOs, charities, social enterprises", "donations, customer-relationships (donors), payments, messaging", "workforce (volunteers), documents, marketing, orders"),
])

opmodels = Section(
    "BB. Operating models — traits, not categories (MD §22)",
    "",
    [
        r("OM-01", "P6", "MD §22", "Franchises: each outlet its own tenant; Brand HQ (FUTURE) pushes catalogue, sees outlet sales, locks template", "catalog", "FUTURE", F, "org_shape value in P1; Brand HQ FUTURE"),
        r("OM-02", "P1", "MD §22", "Multi-location chains: stock, staff, prices per location; transfers; location-scoped roles; combined dashboard", "platform", "EXTEND", P, "locations + location_scope + per-location stock exist; transfers/combined dashboard absent"),
        r("OM-03", "P2", "MD §22", "Subscription businesses → memberships with the right plan kind", "memberships", "EXTEND", S, "plan kinds absent"),
        r("OM-04", "X", "MD §22 · §25.2", "Multi-vendor marketplace hosted by a tenant is out of scope", "—", "EXISTING", C, "not built, by design"),
        r("OM-05", "P2", "MD §22", "On-demand services: 'as soon as possible' slot; nearest on-duty crew dispatched", "dispatch", "NEW", S, "absent"),
        r("OM-06", "P1", "MD §22", "Booking-led: bookings on; website leads with 'Book'", "website", "EXTEND", P, "primary CTA derived from interview, not traits"),
        r("OM-07", "P1", "MD §22", "Quote-led: quotes + leads; website leads with 'Get a quote'", "website", "EXTEND", P, "as above"),
        r("OM-08", "P5", "MD §22", "Project-led: projects with milestones and payment schedules", "projects", "EXTEND", S, "milestones absent"),
        r("OM-09", "P1", "MD §22", "Portfolio-led: portfolio sections and portfolio_item offerings", "website", "EXTEND", P, "gallery sections; no portfolio_item kind"),
        r("OM-10", "P4", "MD §22", "Catalogue-led: per-offering price visibility (shown, logged-in buyers only, price on request with enquiry instead of cart)", "offerings-catalog", "EXTEND", P, "price_type 'enquiry' exists; no logged-in-buyer visibility"),
        r("OM-11", "P0", "MD §22", "Order-led: cart, checkout, orders", "orders", "EXISTING", C, "shipped", test="✓ test_checkout_flow"),
        r("OM-12", "P2", "MD §22", "Walk-in: POS for products, queue tokens for services", "pos/queue", "NEW", S, "absent"),
        r("OM-13", "P2", "MD §22", "Lead-generation: leads, Sales Executive, Meta lead-ad sync", "leads", "EXTEND", P, "leads exist"),
        r("OM-14", "P2", "MD §22", "Custom / made-to-order: order stages, advances, recipes for materials", "orders", "EXTEND", S, "absent"),
        r("OM-15", "P4", "MD §22", "B2B-only: no consumer cart; RFQs, price lists, invoices with buyer GSTIN, supplier listing (P6)", "platform", "EXTEND", S, "absent"),
        r("OM-16", "P0", "MD §22", "B2C-only: consumer flows only", "platform", "EXISTING", C, "default"),
        r("OM-17", "P4", "MD §22", "Hybrid B2B+B2C: two price lists; customer type per account; invoice type follows buyer", "platform", "NEW", S, "absent"),
        r("OM-18", "P1", "MD §22", "Digital-only: no address on the site; digital products; meeting links", "website", "NEW", S, "absent"),
        r("OM-19", "P1", "MD §22", "Offline-first: website as information + WhatsApp + POS; online selling switched on later", "website", "EXTEND", P, "website without commerce works; POS/WhatsApp absent"),
        r("OM-20", "P0", "MD §22", "Hybrid online/offline: default, no change", "platform", "EXISTING", C, "default"),
        r("OM-21", "P1", "MD §22", "Solo: simplified navigation (no team menus), one calendar, AI employees as staff", "core-workspace", "NEW", S, "absent"),
        r("OM-22", "P2", "MD §22", "Teams/agencies: roles, assignment scope, approvals", "team", "EXTEND", P, "roles exist; assignment/approvals absent"),
        r("OM-23", "P2", "MD §22", "Enterprise: departments as locations/teams, approval chains, audit exports; SSO FUTURE", "platform", "EXTEND", P, "audit events exist; exports/approval chains absent"),
    ],
)

gaps = Section(
    "BC. Business gaps map (MD §23) — each pain closes when its owning module row closes",
    "",
    [
        r("GP-01", "P1", "MD §23 #1", "Orders/bookings scattered across calls, WhatsApp, DMs → one inbox + WhatsApp flows creating real orders/bookings", "messaging", "NEW", S, "see MS-*"),
        r("GP-02", "P3", "MD §23 #2", "Calls missed at peak → AI Receptionist + callback tasks", "ai-employees", "NEW", S, "see RC-*"),
        r("GP-03", "P1", "MD §23 #3", "Udhaar in notebooks → khata with statements, UPI links, limits", "ledger", "NEW", S, "see LG-*"),
        r("GP-04", "P2", "MD §23 #4", "Renewals leak → ladder + autopay", "memberships", "NEW", S, "see MB-*"),
        r("GP-05", "P2", "MD §23 #5", "No-shows → deposits, reminders, waitlist backfill", "bookings", "EXTEND", P, "deposits exist"),
        r("GP-06", "P4", "MD §23 #6", "Stock leakage → recipes, yields, wastage, counts", "inventory", "NEW", S, "see IN-*/RC-*"),
        r("GP-07", "P4", "MD §23 #7", "Supplier ordering by phone → requisitions from demand; pinned-price chits", "procurement", "NEW", S, "see PC-*"),
        r("GP-08", "P2", "MD §23 #8", "Aggregator commissions → own website, WhatsApp, Marketplace, own delivery", "website", "EXTEND", P, "website/marketplace exist"),
        r("GP-09", "P4", "MD §23 #9", "GST paperwork → correct invoices, CA exports, Tally, document requests", "invoicing", "NEW", S, "see IV-*"),
        r("GP-10", "P2", "MD §23 #10", "Cash leakage → shift closing, COD settlement, role limits", "pos", "NEW", S, "see PS-*/DP-*"),
        r("GP-11", "P2", "MD §23 #11", "No record of who worked → attendance, assignment, photo proof", "attendance", "NEW", S, "see AT-*"),
        r("GP-12", "P2", "MD §23 #12", "'Is it ready?/where is it?' → tracking page, stage updates, ready alerts", "dispatch", "EXTEND", P, "tracking page exists"),
        r("GP-13", "P3", "MD §23 #13", "Quotes go cold → view tracking, nudges, validity", "quotes", "EXTEND", P, "validity exists"),
        r("GP-14", "P1", "MD §23 #14", "Unmanaged reviews → verified reviews, replies, recovery", "reviews", "NEW", S, "see RV-*"),
        r("GP-15", "P1", "MD §23 #15", "Licences expire unnoticed → compliance calendar", "compliance", "NEW", S, "see CP-*"),
        r("GP-16", "P4", "MD §23 #16", "Festival spikes unplanned → pre-order windows, forecast, campaign drafts", "orders", "NEW", S, "absent"),
        r("GP-17", "P3", "MD §23 #17", "Ad money without results → spend → orders attribution", "marketing", "NEW", S, "see MK-07"),
        r("GP-18", "P4", "MD §23 #18", "Five disconnected apps → one OS plus connectors", "connectors", "NEW", S, "see CN-*"),
        r("GP-19", "P0", "MD §23 #19", "No online presence → generated website, Marketplace, Google profile sync (P3)", "website", "EXISTING", P, "website + marketplace shipped; GBP ACTIVATION"),
        r("GP-20", "P4", "MD §23 #20", "Cash-flow blind spots → receivables/payables ageing with reminders", "ledger", "NEW", S, "see LG-04"),
        r("GP-21", "P3", "MD §23 #21", "Owner cannot take a day off → roles with limits, AI employees, Needs you now on phone", "workforce", "NEW", S, "absent"),
        r("GP-22", "P2", "MD §23 #22", "Language barrier → English, Tamil, Hindi across UI and messages", "platform", "NEW", S, "English only; interview reads Tamil"),
        r("GP-23", "P1", "MD §23 #23", "Lost phone → cloud records with tested backups; backup/restore drill before scaling", "platform", "EXISTING", A, "cloud records exist; restore drill needs a staging DB (§26.1)"),
    ],
)

SECTIONS = [food, retail, beauty, health, edu, stays, build, field, pro, industrial, community, opmodels, gaps]
