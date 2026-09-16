/**
 * Product facts for LOCAH's own marketing surfaces.
 *
 * Every module id here exists in `module_definitions`, and the First Launch
 * split follows Doc 11 §5.2 — the reference-model table that says which modules
 * each kind of business actually gets at launch. Roadmap modules are listed
 * separately and labelled, never mixed in: a capability page that implies a
 * shipped feature is a lie the demo cannot survive.
 */

export type Module = {
  id: string
  name: string
  /** Plain-language answer to "why would my business need this?" */
  blurb: string
}

/** Always on. Granted to every Business by the platform, not chosen. */
export const CORE_MODULES: Module[] = [
  { id: 'core-business-identity', name: 'Business Identity', blurb: 'Your business as the single tenant everything else hangs off.' },
  { id: 'core-business-profile', name: 'Business Profile', blurb: 'The public face of your business — name, story, contact, hours.' },
  { id: 'core-website', name: 'Website', blurb: 'Your structured site: pages, sections, theme, publishing.' },
  { id: 'core-marketplace-presence', name: 'Marketplace Presence', blurb: 'How customers find you when they search LOCAH.' },
  { id: 'core-locations', name: 'Locations', blurb: 'Where you trade from, and the hours each place keeps.' },
  { id: 'core-team-access', name: 'Team & Access', blurb: 'Invite your staff and decide what each of them can do.' },
  { id: 'core-notifications', name: 'Notifications', blurb: 'What needs your attention, as it happens.' },
  { id: 'core-settings', name: 'Settings', blurb: 'Business-wide configuration in one place.' },
]

/** Switchable at First Launch. Doc 11 §5.2. */
export const LAUNCH_MODULES: Module[] = [
  { id: 'offerings-catalog', name: 'Offerings', blurb: 'Everything you sell — dishes, services, rooms, plans, products. Fills your website and your checkout from one list.' },
  { id: 'orders', name: 'Orders', blurb: 'What customers bought, what state it is in, and what you owe them next.' },
  { id: 'bookings', name: 'Bookings', blurb: 'Appointments, tables, rooms and classes against real availability.' },
  { id: 'payments', name: 'Payments', blurb: 'Take money online or on collection, and see what has actually settled.' },
  { id: 'memberships', name: 'Memberships', blurb: 'Plans with validity — gym memberships, class packs, subscriptions.' },
  { id: 'customer-relationships', name: 'Customers', blurb: 'Who bought what, when, and how often — built from real orders.' },
  { id: 'leads', name: 'Leads', blurb: 'Enquiries that are not yet sales: capture, follow up, win or lose.' },
  { id: 'inventory', name: 'Inventory', blurb: 'Stock counts that stop you selling what you do not have.' },
  { id: 'fulfilment', name: 'Fulfilment', blurb: 'Pickup and delivery, with the states your staff actually work through.' },
  { id: 'workforce', name: 'Workforce', blurb: 'Your staff and providers, and who can be booked for what.' },
]

/** Real modules in the registry, not yet part of First Launch. Say so. */
export const ROADMAP_MODULES: Module[] = [
  { id: 'analytics', name: 'Analytics', blurb: 'Deeper reporting beyond the Workspace summary.' },
  { id: 'invoicing', name: 'Invoicing', blurb: 'Invoices and receivables for businesses that bill.' },
  { id: 'loyalty', name: 'Loyalty', blurb: 'Points, tiers and rewards for repeat customers.' },
  { id: 'marketing', name: 'Marketing', blurb: 'Campaigns and promotional audiences.' },
  { id: 'messaging', name: 'Messaging', blurb: 'External channels for reaching customers directly.' },
  { id: 'reviews', name: 'Reviews', blurb: 'Feedback tied to a real transaction, not anonymous ratings.' },
  { id: 'queue-operations', name: 'Queue Operations', blurb: 'Walk-in queues and token management.' },
  { id: 'b2b-network', name: 'B2B Network', blurb: 'Supplier and partner discovery between businesses.' },
  { id: 'business-passport', name: 'Business Passport', blurb: 'A verified credential dossier for your business.' },
  { id: 'business-community', name: 'Business Community', blurb: 'Posts and follows between local businesses.' },
  { id: 'payroll', name: 'Payroll', blurb: 'Compensation and payout coordination for staff.' },
]

/** Doc 11 §5.2 reference models — the business kinds LOCAH is designed around. */
export type ReferenceModel = {
  name: string
  examples: string
  path: string
  modules: string[]
}

export const REFERENCE_MODELS: ReferenceModel[] = [
  {
    name: 'Food business',
    examples: 'Restaurant, café, home-food seller',
    path: 'Menu → order → payment or cash on collection → pickup or your own delivery',
    modules: ['Offerings', 'Orders', 'Payments', 'Inventory', 'Fulfilment', 'Bookings'],
  },
  {
    name: 'Appointment services',
    examples: 'Salon, spa, consultant',
    path: 'Service → who is free → slot → booking → payment or deposit',
    modules: ['Offerings', 'Bookings', 'Payments', 'Workforce', 'Customers'],
  },
  {
    name: 'Membership business',
    examples: 'Gym, studio, club',
    path: 'Plan or class → enrolment → payment → validity → book a session',
    modules: ['Offerings', 'Memberships', 'Payments', 'Bookings', 'Workforce'],
  },
  {
    name: 'Accommodation',
    examples: 'Hotel, homestay',
    path: 'Room → dates and guests → availability → reservation → deposit or pay at property',
    modules: ['Offerings', 'Bookings', 'Payments', 'Customers'],
  },
  {
    name: 'Retail commerce',
    examples: 'Furniture, clothing, electronics',
    path: 'Products → discovery → purchase or enquiry → payment → order → fulfilment',
    modules: ['Offerings', 'Orders', 'Payments', 'Inventory', 'Fulfilment', 'Leads'],
  },
  {
    name: 'High-frequency retail',
    examples: 'Supermarket, grocery',
    path: 'Products → stock → cart → checkout → pickup or delivery',
    modules: ['Offerings', 'Orders', 'Payments', 'Inventory', 'Fulfilment'],
  },
  {
    name: 'Lead-driven business',
    examples: 'Real estate, car dealer, interior designer',
    path: 'Listing → enquiry → lead → contact → qualify → won or lost',
    modules: ['Offerings', 'Leads', 'Customers'],
  },
  {
    name: 'Professional services',
    examples: 'Agency, lawyer, accountant',
    path: 'Website or search → service → enquiry → follow-up',
    modules: ['Offerings', 'Leads', 'Customers'],
  },
  {
    name: 'Education & cohorts',
    examples: 'Tuition centre, coaching, academy',
    path: 'Course or plan → enrolment and payment → validity → scheduled class',
    modules: ['Offerings', 'Memberships', 'Payments', 'Bookings', 'Workforce'],
  },
  {
    name: 'Repair & home services',
    examples: 'Plumber, electrician, appliance repair',
    path: 'Request → lead or booking → who and when → completion → payment',
    modules: ['Offerings', 'Leads', 'Bookings', 'Payments', 'Workforce'],
  },
  {
    name: 'Rental & resources',
    examples: 'Equipment, vehicle, venue rental',
    path: 'Resource → period availability → reservation → deposit → return',
    modules: ['Offerings', 'Bookings', 'Payments', 'Inventory'],
  },
]
