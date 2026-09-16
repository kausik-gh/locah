# LOCAH — Product & Frontend Build Spec

**Status:** authoritative for the frontend build pass. Product decisions are
**already made** here — execute them, do not re-litigate them.
**Authority order:** Doc 12 → Doc 11 → Doc 10 → Doc 09 → this document.
This document never overrides a canonical doc; where it appears to, the doc wins.

---

## 0. What the inspection actually found

Read before building. These are verified facts about the repo, not impressions.

| Area | Finding |
|---|---|
| `apps/web` (public) | Next 14 App Router. **No CSS file, no font, no design system.** Every screen is inline `React.CSSProperties`. `layout.tsx` is 291 bytes. |
| `packages/ui` | **Effectively empty** — `src/index.ts` is 217 bytes. Nothing shared between apps. |
| `apps/workspace` | Routes for *every* module already exist (orders, bookings, payments, customers, memberships, inventory, fulfilment, workforce, leads, locations, team, modules, notifications, settings, website). Each page is 3–7 KB — wired and working, but thin. Has a real design system already: `globals.css` + `components/ui.tsx` + self-hosted General Sans. |
| `SectionRenderer.tsx` | **Renders 6 of the 13 section types the backend can generate.** `menu_section`, `plans_section`, `rooms_section`, `classes_section`, `gallery`, `enquiry_form`, `location_list` all fall through to a literal `"Unsupported section type: …"` string **on the live customer-facing website**. Zero `layout_variant` support — all ~30 declared variants ignored. |
| `WebsitePageView.tsx` | Hardcodes Georgia serif + `#faf8f4` for **every** tenant. A hotel, a gym and a restaurant render identically. |

**Therefore the headline problem was never "the homepage looks plain."** It is
that the website builder — the product's core differentiator — emits pages that
are literally broken for 5 of the 11 supported business types. A restaurant's
Menu page, a gym's Plans page and a hotel's Rooms page do not render. Fix that
first; it changes more of the demo than any amount of marketing polish.

---

## 1. One brand, three visual contexts

They must **not** look the same. This is the single most important design rule
in the product.

| Context | Where | Feel | Ground |
|---|---|---|---|
| `locah-public` | Homepage, Marketplace, pricing, For Businesses | Editorial, confident, product-website | Navy `#1B1F3B` + warm paper; orange **only** for the primary action |
| `locah-app` | Workspace, Admin | Data-dense, daylight, operator-first | Existing `apps/workspace/globals.css` — **locked, do not restyle** |
| `locah-site` | A tenant's published website | Looks like **that business** | Driven by the business's own theme record |

**Hard rule:** no LOCAH brand colour may appear on a tenant website, except the
one quiet "Powered by LOCAH" line in the footer. If a generated hotel site shows
LOCAH navy, that's a bug.

### Brand tokens (already committed in `packages/ui/src/tokens.css`)

```
--locah-ink        #1B1F3B   deep navy — the brand ground
--locah-ink-2      #262B4F   raised navy surface
--locah-periwinkle #9BA3D0   from the mark's inner dots
--locah-cream      #F7F4EF   warm paper
--locah-accent     #E8622C   ORANGE — primary action only, never decoration
```

Orange discipline: **one** orange element per viewport. The primary CTA, or one
accent word in a headline — never both, never a field of orange cards.

---

## 2. What is already committed (do not rebuild)

Four files are in the repo and are the foundation for everything else:

| File | What it gives you |
|---|---|
| `packages/ui/src/tokens.css` | All brand tokens, fluid type scale, spacing, elevation, motion, **and the `--site-*` tenant theme contract with 5 personality presets** |
| `packages/ui/src/public.css` | Complete marketing/Marketplace system — nav, buttons, cards, media cards, chips, search, stats, product frames, floating callouts, steps, empty/skeleton states, footer |
| `packages/ui/src/website.css` | **All 13 section types × every layout variant**, theme-driven, plus tenant nav/footer |
| `apps/web/src/components/website/{SectionRenderer,LiveItemsSection,WebsitePageView}.tsx` | Complete renderer for all 13 types; theme + personality mapping |

**Wiring required (Phase 0, ~10 min):**

1. `packages/ui/package.json` — add `"./styles/*": "./src/*.css"` to `exports`
   (or simply import by path; the files are plain CSS with no build step).
2. `apps/web/src/app/layout.tsx` — import `tokens.css`, `public.css`,
   `website.css`; add General Sans (copy `apps/workspace/src/app/fonts/`);
   put `className="locah-public"` on `<body>`.
3. `apps/workspace` — import `tokens.css` **before** its own `globals.css`.
   Workspace tokens win; nothing there changes visually.
4. Run `pnpm typecheck` and fix any import-path nits before continuing.

---

## 3. Business type → capability → pages

Canonical keys live in `python/core/platform_core/website/section_registry.py`
(`PAGES_BY_BUSINESS_TYPE`). **Use these exact keys.** Module sets come from
Doc 11 §5.2 (Reference Validation Matrix) — they are not invented here.

| Type key | Shown to user as | Default modules (Doc 11 §5.2) | Generated pages | Personality |
|---|---|---|---|---|
| `restaurant` | Restaurant | offerings-catalog, orders, payments, inventory, fulfilment | Home, Menu, About, Contact | warm |
| `cafe` | Café | offerings-catalog, orders, payments, inventory, fulfilment | Home, Menu, About, Contact | warm |
| `home_food` ★ | Home food business | offerings-catalog, orders, payments, fulfilment | Home, Menu, About, Contact | warm |
| `retail` | Retail store | offerings-catalog, orders, payments, inventory, fulfilment, leads | Home, Products, About, Contact | clean |
| `salon` | Salon | offerings-catalog, bookings, payments, workforce, customer-relationships | Home, Services, About, Contact | premium |
| `spa` | Spa & wellness | offerings-catalog, bookings, payments, workforce, customer-relationships | Home, Services, About, Contact | premium |
| `hotel` | Hotel | offerings-catalog, bookings, payments, customer-relationships | Home, Rooms, About, Contact | premium |
| `homestay` | Homestay / B&B | offerings-catalog, bookings, payments, customer-relationships | Home, Rooms, About, Contact | premium |
| `gym` | Gym / fitness | offerings-catalog, memberships, payments, bookings, workforce | Home, Plans, Classes, About, Contact | bold |
| `studio` | Studio / classes | offerings-catalog, memberships, payments, bookings, workforce | Home, Classes, About, Contact | bold |
| `education` | Coaching / academy | offerings-catalog, memberships, payments, bookings, workforce | Home, Courses, About, Contact | clean |
| `professional_service` | Professional service | offerings-catalog, leads, customer-relationships | Home, Services, About, Contact, Enquire | clean |
| `real_estate` ★ | Real estate | offerings-catalog, leads, customer-relationships, bookings | Home, Listings, About, Contact, Enquire | clean |
| *(none)* | Something else | offerings-catalog, leads | Home, About, Contact | clean |

★ = **the only backend change this pass needs.** Add `home_food`,
`real_estate` to `PAGES_BY_BUSINESS_TYPE` (and to the DB `business_type`
allow-list if one exists). Purely additive, ~10 lines, no schema migration.
Everything else maps onto keys that already exist.

**Do not** add "Events / Experiences" — nothing in First Launch scope backs it.
Offer "Something else" instead; that path is real.

---

## 4. Onboarding — five steps, no more

The current `/start` flow works but reads like a form. Rule: **LOCAH does the
work, the owner answers questions a human would ask.** Anything that can be
inferred, defaulted, or asked later in Workspace must not appear here.

| Step | Route | Asks | Notes |
|---|---|---|---|
| 1 | `/start` | **What kind of business?** | Visual grid of the 14 types above, with a one-line plain description each. This single answer drives modules, pages, personality and every later question. |
| 2 | `/start/basics` | Business name · City · Phone or email | Three fields. Slug is derived and shown inline (`locah.app/your-name`), editable but pre-filled. |
| 3 | `/start/about` | One textarea: *"In a couple of sentences — what do you do, and who for?"* · optional logo · optional photo | **One** free-text box. This is the AI's main input. Never ask for "tagline", "mission", "values" separately. |
| 4 | `/start/capabilities` | *"What do you want to do online?"* | Checklist **pre-ticked** from the type's default modules, each with a plain-English line ("Take orders and payments"). Owner unticks what they don't want. This is the entitlement/module choice, surfaced honestly — not a fake feature list. |
| 5 | `/start/[businessId]/website` | Generating… → preview | Existing `WebsiteQuestionnaire` already covers the type-specific detail; keep it, restyle it. |

**Type-specific questions (step 3 add-on, max 2 extra fields):**

- restaurant / cafe / home_food → *"Cuisine or speciality?"* · *"Delivery, pickup, or both?"*
- salon / spa → *"Main services?"* · *"How many people on the team?"*
- gym / studio → *"What do you teach or train?"* · *"Do you sell memberships, drop-ins, or both?"*
- hotel / homestay → *"How many rooms or units?"* · *"Check-in / check-out times?"*
- retail → *"What do you sell?"* · *"Do you ship, or is it pickup?"*
- professional_service / real_estate → *"What services do you offer?"* · *"How should enquiries reach you?"*

That is the whole adaptive surface. Do not exceed two extra fields per type.

---

## 5. Page-by-page build order

Priority ordering, not a wish list. **P0 is the demo.** If time runs out, P0
alone must be able to be shown end to end.

### P0 — the demonstrable spine

| # | Page | Route | Build notes |
|---|---|---|---|
| 1 | Public home | `/` | §6 below. The single most-seen screen. |
| 2 | Marketplace | `/marketplace` | Hero search, category chip rail, business grid using `.lc-mediacard`. Must not look restaurant-only — lead with mixed types. |
| 3 | Search results | `/search` | Query echo, result count, refine rail (type · city), same card. Real `no_results` / `sparse_market` states from the API — those states already exist, use them. |
| 4 | Business profile | `/marketplace/[slug]` | Cover, logo, type, city, capability actions (Order / Book / Enquire) driven by `capability_flags` from the API. Offerings preview. Link through to the tenant site. |
| 5 | Tenant website | `/[slug]`, `/[slug]/[pageSlug]` | **Already done** — the three committed components. Just verify against each type. |
| 6 | Onboarding | `/start/*` | §4 above. |
| 7 | Website preview + editor | workspace `/website/*` | §7 below. |
| 8 | Workspace home | `/b/[businessId]` | §8 below. |
| 9 | Orders | `/b/[businessId]/orders` + detail | Board/list, status pills, real actions. Page exists — upgrade, don't rewrite. |
| 10 | My Activity | `/activity` | Consumer view. Orders, bookings, payments, memberships. Never mix in owner operations. |

### P1 — completeness

11 Offerings · 12 Bookings + detail · 13 Customers + detail · 14 Payments + detail
· 15 Memberships · 16 Inventory · 17 Fulfilment · 18 Workforce · 19 Leads
· 20 Notifications · 21 Modules · 22 Settings · 23 Team · 24 Locations
· 25 Checkout `/[slug]/checkout` · 26 Booking flow `/[slug]/book`
· 27 Order tracking `/[slug]/track/[orderId]`

All 27 already have routes. The work is **visual + state completeness**, not
new plumbing: real empty states, loading skeletons, error recovery, sensible
column sets, working actions.

### P2 — marketing depth

28 For Businesses · 29 Solutions (by business type — reuse §3 table)
· 30 Pricing · 31 Resources/Help · 32 About · 33 Admin surfaces
· 34 Login/signup polish

---

## 6. Public homepage — exact structure

Do not deviate. This is the "understand the product in 30 seconds" screen.

1. **Nav** (`.lc-nav`) — LOCAH · Marketplace · For Businesses · Solutions · Pricing · Resources | Log in · **Get started** (orange).
2. **Hero** — navy ground. Eyebrow "The operating layer for local business". Display headline: *"Local businesses,"* / *"limitless possibilities."* with one `.lc-mark` accent word. Lead paragraph, two CTAs (Get started / Explore Marketplace). Right: a real `.lc-frame` product shot with 2–3 `.lc-float` callouts (Today's orders · Website published · New booking). **Use real screenshots of your own Workspace**, not stock imagery.
3. **Proof strip** — 4 `.lc-stat`s. Only real numbers, or clearly labelled as illustrative. Do not invent "10,000 businesses".
4. **"From nothing to trading" journey** — 5 `.lc-step`s: Tell us about your business → We build your website → Choose what you sell → Publish → Get discovered & take orders. Each with a small product image.
5. **Capability grid** — `.lc-grid--3` of `.lc-card`s: Website, Orders, Bookings, Payments, Customers, Insights. One clear sentence each, no jargon.
6. **Built for your kind of business** — chip rail of the business types; selecting one swaps a preview image + a 2-line description. This is where you prove it isn't restaurant software.
7. **Marketplace band** (navy) — "Customers are already looking" + live business cards pulled from the real search API.
8. **Closing CTA** (cream) — single headline + Get started.
9. **Footer** (`.lc-footer`) — Product · Solutions · Marketplace · Company columns.

---

## 7. Website editor — what it must feel like

The owner must never see JSON, a schema, or the words "section type".

- **Preview-first.** The canvas is the page. Editing happens beside it, not instead of it.
- **Section list** shows human labels from `website_section_types.label` ("Hero / Banner", "Menu"), with move up/down, show/hide, delete.
- **Add section** offers only types valid for that business's enabled modules — a business without `bookings` must not be offered a Classes section.
- **Editing a section** = a small form of its real fields (headline, body, image), nothing more. Fields come from `content_schema`, already in the DB.
- **Theme** = choose primary colour + personality preset. Live preview. That is the whole theme UI.
- **Publish** = one button, one confirmation, one success state that links to the live URL and to the Marketplace listing.
- **AI assist** stays inside the structured model: it rewrites a section's
  content fields, it never emits HTML. If the AI provider is down, say so
  plainly and keep manual editing working (Doc 11 §6.2 requires the
  deterministic fallback — it already exists, surface it honestly).

---

## 8. Workspace home — answer three questions

Not a wall of cards. Exactly three bands:

1. **Needs you now** — pending orders, unconfirmed bookings, failed payments, low stock, unanswered leads. Empty state: *"Nothing needs you right now."* Each row links to the thing.
2. **Today** — revenue today, orders today, bookings today, new customers. Four `.lc-stat`s. Real data only; new businesses get a proper "no activity yet — here's what to set up" state.
3. **Your business** — website status (draft/published + link), Marketplace visibility, modules enabled, setup completion. This is the "is my business actually live?" answer.

Every metric must lead to a decision. Delete any card that doesn't.

---

## 9. Honesty rules — non-negotiable

- **Never fabricate data.** No fake charts, no invented counts, no placeholder customers. A new business sees a real empty state that explains what will appear.
- **Never fake a feature.** If something isn't supported, the UI says what *is*
  possible. No "Coming soon" scattered around as decoration.
- **Analytics** renders only what the API can actually compute. If the backend
  can't produce a trend series yet, show the counts it *can* and say the trend
  needs more history — do not draw a fake line.
- **B2B / ChitBridge** stays a separate deployed product. At most, a single
  honest "Coming to LOCAH" entry point in Solutions. Do not build a fake B2B
  surface inside the workspace.
- **Deferred modules** (Doc 11 §3.2) are not shown as toggles. They don't exist here.

---

## 10. Quality bar

- Type: General Sans everywhere. Display sizes fluid, body fixed at 16px.
- Every interactive target ≥ 44px. Visible focus ring, always.
- Every list has four states: loading (skeleton), empty (useful), error (recoverable), populated.
- Mobile works at 390px. Tables scroll in their own container; the page never scrolls sideways.
- Motion: ≤ 220ms, entrance only, and fully off under `prefers-reduced-motion` (already handled in `tokens.css`).
- No lorem ipsum. No emoji as iconography. No gradient for its own sake. No card with a number that doesn't inform a decision.
