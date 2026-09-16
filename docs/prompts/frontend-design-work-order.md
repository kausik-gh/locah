Startup Platform — Frontend Design Work Order

Three surfaces, three treatments. Design tokens below are generated from the Origin design-intelligence database, not invented — use them as given.

Context that changes everything about these prompts: the frontend already exists. 36 Workspace routes, 6 admin pages, the public web app, all functional and wired to real APIs. This is a design pass over working software, not a greenfield build. No prompt below should change data-fetching, routing, or gate/permission logic — only what things look, feel, and move like.

## Locked design tokens

### Public surface — `apps/web`

```css
:root {
  --color-background: #0B1220;   /* Deep Ink Blue */
  --color-foreground: #E8EDF5;
  --color-primary:    #3B5BFF;
  --color-accent:     #7AA2FF;
  --color-muted:      #5B6478;
  --color-border:     #1A2438;
}
```

Style: Dark Premium Minimalism. Type: Neue Montreal (headings, weight 500–600) + Inter (body, 400). Motion tier: Subtle — 200–300ms, no decorative motion.

### Workspace + Admin — `apps/workspace`, `apps/admin`

```css
:root {
  --color-background: #F8FAFC;   /* Slate Enterprise */
  --color-foreground: #1E293B;
  --color-primary:    #2563EB;
  --color-accent:     #EA580C;
  --color-muted:      #64748B;
  --color-border:     #E2E8F0;
}
```

Style: Data-Dense Dashboard. Type: General Sans, single family across all weights. Motion: minimal — instant feedback on state change only.

Light workspace, dark public is deliberate: operators work in daylight for hours, visitors arrive for minutes.

---

## PROMPT A — Public surface (`apps/web`)

This is where the cinematic treatment belongs. Paste as one block.

```
Redesign the public surface of Startup Platform — apps/web — a platform where
local businesses get a real website, a marketplace listing, and working
commerce in one place. Visitors are two kinds of people: business owners
deciding whether to sign up, and customers who landed on a specific business.

The app already works. Do not change routing, data fetching, auth, or any
API call. This is a visual and motion pass over functioning pages.

Generate hero and section imagery with the Higgsfield MCP FIRST, confirm the
media IDs, then build around them. No placeholder images.

## Design system — use exactly, do not substitute

Background #0B1220 · Foreground #E8EDF5 · Primary #3B5BFF · Accent #7AA2FF ·
Muted #5B6478 · Border #1A2438
Headings: Neue Montreal, weight 500-600. Body: Inter, 400. Load via next/font.
Motion tier: subtle. 200-300ms, power2.out. No decorative motion anywhere.

Tone: confident, technical, plain. Think a developer-tools landing page, not a
small-business marketing site. Hard edges, generous whitespace, asymmetric
grid. Explicitly avoid: gradient meshes, floating 3D blobs, illustrated
characters, stock-photo handshakes, rounded-everything, purple-to-pink
gradients, badge soup.

## Asset generation order

1. **The master shot** — a real small business interior at working hours, shot
   like documentary photography, not advertising: a neighbourhood cafe mid-
   service, natural window light, slight motion blur on a moving hand,
   shallow depth of field. Cool grade to sit against #0B1220. This is the
   most important asset — everything else derives from it.

2. **Five business-type variants**, generated image-to-image FROM the master so
   grade, light temperature, and shooting style match exactly: a salon chair
   mid-appointment, a small retail counter, a gym floor, a clinic waiting
   room, a restaurant pass. Same camera language across all six. These
   represent the reference business models the platform actually serves.

3. **Three device stills** — the generated business website on a laptop, the
   Workspace on a desktop, a booking confirmation on a phone. Clean, straight
   on, same cool grade. Background removal on all three.

4. **One texture plate** — an abstract dark field with fine grain, for section
   backgrounds. No objects.

## Stack

Keep the existing Next.js App Router setup. Add GSAP + ScrollTrigger and Lenis.
Framer Motion for micro-interactions only. No Three.js — there is nothing here
that needs real 3D, and adding it would cost load time for no gain.

Register GSAP inside gsap.context() scoped to a ref, revert on unmount — App
Router remounts leak ScrollTrigger instances otherwise. Lazy-load any heavy
client component with next/dynamic, ssr: false.

## Sections in order

Hero → What it actually does → **The generation moment (showpiece)** →
Business types → Marketplace preview → Pricing → Footer

## Copy

Write like an engineer explaining a system to another engineer. Short
declarative sentences with full stops. Every feature line carries one concrete
mechanic nobody could guess — how the website gets generated, what happens to
stock at order placement, what a customer sees when a business is closed.

Banned: "empower", "seamless", "unlock", "supercharge", "all-in-one",
"revolutionize", "game-changing", "take your business to the next level",
"everything you need", any sentence of the form "where X meets Y".

Example of the right register: "Your website is live before you finish
onboarding. If the AI is down, a deterministic generator builds it instead —
you will not know the difference." Not: "Effortlessly create a stunning
website that showcases your brand."

## The generation moment — the showpiece

Dedicated pinned section, roughly mid-page. Give it the most attention. This
is the product's actual promise, made visible.

A single business goes from nothing to live, in four hard-cut states, driven
by scroll progress through the pin:

  01  EMPTY        A business name and a type. Nothing else.
  02  GENERATING   Structured sections appearing — hero, offerings, contact.
  03  EDITED       An owner adjusting content in place.
  04  LIVE         The finished site, and a marketplace listing beside it.

Mechanism: a fixed-size frame, centred, that does NOT resize. Inside it, the
four states cross-cut — each state's image cuts in as the previous cuts out,
no crossfade, no dissolve. Drive the cuts from scroll progress with
ScrollTrigger scrub, since these are static images with no independent
timeline. A counter reads 01 / 04 in the accent colour, top-left of the frame.
A thin accent line beneath the frame tracks pin progress edge to edge.

Beneath the frame, one line of copy per state, cutting with it — the concrete
mechanic of that step, not a description of it.

The headline splits above and below the frame so type never collides with the
image. Scrolling backward runs the sequence in reverse.

## Animation elsewhere — restrained on purpose

Scroll-triggered reveals: opacity + 12px y-translate, 240ms, power2.out,
staggered 60ms. Once, not on every re-entry.
Business-type cards: 2px lift on hover, 180ms. Use gsap.quickTo on y — these
are a grid of many hoverable cards and per-hover tweens will churn.
No custom cursor. No parallax on anything except the hero background, and
there at 0.3 rate, not more.
Respect prefers-reduced-motion: disable all scroll animation, keep the pin but
make the showpiece a static four-up grid instead.

## Constraints

Every animated property is transform or opacity. Never width, height, margin,
or top. next/image with explicit dimensions everywhere — CLS on a landing page
is the one thing that makes craft read as cheap. Poster frames on any video.

## Deliverable

Production-ready code. All Higgsfield assets integrated, no placeholders.
Open the result at 1440px, check it yourself, and fix anything misaligned,
overlapping, or trapped below the fold. Report what you found.
```

---

## PROMPT B — Workspace (`apps/workspace`)

Deliberately the opposite prompt. Paste as one block, separately.

```
Design pass over apps/workspace — the operational surface a business owner uses
every working day to run orders, bookings, inventory, customers, leads,
memberships, payments, fulfilment, and staff. 36 routes, all functional.

This is NOT a marketing surface. Optimize for scanning speed and information
density, not first impressions. A person processing forty orders on a Tuesday
should never wait for an animation. If a choice trades clarity for beauty,
take clarity every time.

Do not change routing, data fetching, auth, gates, or permission logic. Visual
and interaction layer only.

## Design system — use exactly, do not substitute

Background #F8FAFC · Foreground #1E293B · Primary #2563EB · Accent #EA580C ·
Muted #64748B · Border #E2E8F0
Type: General Sans, single family, all weights. Load via next/font.

Light ground is deliberate — operators work in daylight for hours.

## What to build

1. **A real layout shell.** Persistent left sidebar: business switcher at top,
   then Core (Home, Website, Profile, Locations, Team, Settings), then Modules
   (only those active for this business — read the existing module state,
   don't invent it), then Notifications with an unread count. Collapsed state
   persists. Current route always visibly active.

2. **One shared table component** every list page uses. Dense rows (44px),
   zebra-free, 1px borders in --color-border, sticky header, column alignment
   by type (numbers right, dates right, text left, status as a pill). Empty,
   loading, and error states built in — not bolted on per page.

3. **One shared detail-page shell** — title row with primary action top-right,
   status pill, metadata strip, then content. Every detail page uses it so
   Orders and Bookings and Leads feel like one product.

4. **Status pills as a single system.** One component, one colour mapping,
   used everywhere. Never encode meaning in colour alone — every pill carries
   its label as text (accessibility, and it survives colour-blindness).

5. **Home** already has five adaptive states — keep the logic exactly, restyle
   to the system. Cards must look actionable, not decorative.

6. **Keep the existing GateNotice** for MODULE_NOT_ACTIVE / ENTITLEMENT_REQUIRED
   / PERMISSION_DENIED — restyle to the system, do not change its logic. It is
   a launch-readiness requirement, not a design element.

## Motion — almost none

Instant feedback on state change. No page transitions. No scroll animation.
No pinning. No parallax. Nothing that delays a click resolving.

Permitted, and this is the complete list:
- 2px hover lift on clickable cards, 180ms, power1.out, via gsap.quickTo
- 120ms fade on modal/drawer open
- Skeleton rows while a table loads
- Button press: scale(0.98), snap back

That is all. If an animation would make someone doing this task forty times
today wait even 200ms, it does not ship.

## Copy

Labels are nouns. Buttons are verbs. Error messages say what happened and what
to do next, never "Something went wrong." Empty states say what this page will
show and give the action that creates the first one.

## Constraints

Transform and opacity only. Tap targets 44px minimum. Every interactive element
keyboard reachable with a visible focus ring in --color-primary. Contrast 4.5:1
minimum on all text — check it, don't assume.

## Deliverable

Open it at 1440px and at 1280px, click through every route, fix anything
misaligned, overlapping, or unreachable. Report what you found.
```

---

## Third surface — generated business websites

Do not write a prompt for this one yet. These are structured, section-based sites the platform generates per business, rendered from a fixed SectionType registry (hero, about, offerings_list, menu_section, rooms_section, plans_section, classes_section, gallery, contact, cta_band, enquiry_form, location_list, text_block).

They need a different thing entirely: not one design, but a small set of themes that all thirteen section types render correctly in, for a cafe and a clinic and a gym alike. That is a theme-system design problem, and it deserves its own pass once you have seen the current output and decided how much per-business variation you actually want.

## Order to run these

1. Look at the current frontend first — before either prompt. You have not seen it yet, and you may find the Workspace layout is closer or further from usable than either of us assumes.
2. Prompt B (Workspace) before Prompt A (public). The Workspace is what a paying business owner uses every day; the landing page is what they see once. Also, the shared components in B (table, detail shell, status pills) pay off across 36 routes — the highest-leverage work on the whole frontend.
3. Prompt A once B lands.
4. Themes for generated sites last, as its own conversation.
