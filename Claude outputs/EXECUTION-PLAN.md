# LOCAH — Frontend build: execution plan

For the Claude Code session running on the machine with a working shell.
Each phase is bounded, verifiable, and ends with a command that must pass.

**Read `docs/build/LOCAH-BUILD-SPEC.md` first.** Every product decision is
already made there. Do not re-open them — build.

**Standing rules for every phase**

- Reuse existing APIs, routes and components. Improve in place; rewrite only
  where the spec says to.
- Never invent backend functionality to make a screen look finished. If a
  capability doesn't exist, the UI says what *is* possible.
- After every phase: `pnpm typecheck` must pass. Fix what you broke; leave
  pre-existing `mypy`/format drift alone.
- Do not touch `apps/api`, `python/`, or `infra/` except for the one additive
  change named in Phase 4. The backend is at 302/303 and is not in scope.

---

## Phase 0 — Wire the design system (~15 min)

Four files are already committed: `packages/ui/src/{tokens,public,website}.css`
and the three rewritten components in `apps/web/src/components/website/`.

```
1. packages/ui/package.json — expose the CSS (exports map, or import by path).
2. Copy apps/workspace/src/app/fonts/ → apps/web/src/app/fonts/.
3. apps/web/src/app/layout.tsx — import tokens.css, public.css, website.css;
   apply the General Sans variable; <body className="locah-public">.
4. apps/workspace — import tokens.css BEFORE globals.css. Nothing there should
   change visually; if it does, tokens.css is being imported too late.
5. Delete the now-dead inline style objects in apps/web/src/app/page.tsx.
```

**Verify:** `pnpm typecheck` passes · `pnpm dev` runs · visit `/` (it will look
unstyled-but-clean — that's expected, Phase 2 rebuilds it) · visit any published
tenant site and confirm sections now render with real styling.

---

## Phase 1 — Prove the website builder (highest leverage) (~1 h)

This is the phase that changes the demo most. The renderer is written; this
phase proves it against every business type.

```
Create one test business per personality (restaurant, hotel, gym,
professional_service) through the real onboarding + generation flow.
For each: publish, open the public site, screenshot every generated page.

Confirm:
- No page anywhere renders "Unsupported section type".
- Menu / Rooms / Plans / Classes pages render real records.
- The four sites look like FOUR DIFFERENT BUSINESSES, not one site in four
  colours. If they don't, the personality preset isn't being applied — check
  data-personality on the site root in WebsitePageView.
- No LOCAH navy or orange appears on any tenant site except the footer line.
```

If a list section renders empty, check whether `fetchPublicOfferings` returns
`offering_type` / `category` / `image_url`. If it doesn't, adding those three
fields to the public offerings payload is the correct minimal fix — it is what
`menu_section` categorisation and card imagery read.

**Verify:** four visibly distinct, complete websites. Keep the screenshots —
they are the product imagery for Phase 2.

---

## Phase 2 — Public homepage + shell (~2 h)

Build to `LOCAH-BUILD-SPEC.md` §6, exactly that section order.

```
apps/web/src/components/public/
  SiteNav.tsx      — .lc-nav, links per spec §6.1, Get started = .lc-btn--primary
  SiteFooter.tsx   — .lc-footer, four columns
  ProductFrame.tsx — .lc-frame wrapper + .lc-float callouts
Then rebuild apps/web/src/app/page.tsx per §6 (nine bands).
Use the Phase 1 screenshots as the product imagery.
Keep the existing signed-in OwnerHome branch — restyle it, don't delete it.
```

Rules: one orange element per viewport · real numbers only · no stock photos of
people in offices.

**Verify:** `/` at 1440px and 390px. A stranger should be able to say what LOCAH
does after 30 seconds without scrolling past band 3.

---

## Phase 3 — Marketplace as a consumer product (~2 h)

`/marketplace`, `/search`, `/marketplace/[slug]` — spec §5 rows 2–4.

```
Hero search (.lc-search) + category chip rail (.lc-chiprail).
Business grid using .lc-mediacard. Lead the default view with MIXED business
types — this is where the "it isn't restaurant software" point is won or lost.
Wire the real states the API already returns: results / no_results /
sparse_market. Do not invent a fourth.
Business profile: capability actions driven by capability_flags from the API —
Order / Book / Enquire appear only when the flag is true.
```

**Verify:** search a real term, get real results; search nonsense, get the real
`no_results` state; open a profile and reach the tenant site and back.

---

## Phase 4 — Onboarding (~2 h)

Spec §4. Five steps, two extra fields max per type.

```
Backend (the ONLY backend change this pass):
  python/core/platform_core/website/section_registry.py
  → add `home_food` and `real_estate` to PAGES_BY_BUSINESS_TYPE
    (home_food: home/menu/about/contact; real_estate: home/listings/about/
     contact/enquire). Additive only. If a DB business_type CHECK constraint
     exists, extend it in a new migration — do not edit an applied one.

Frontend: rebuild /start as the 5-step flow. Type grid first — it drives
everything. Keep and restyle the existing WebsiteQuestionnaire for step 5.
Pre-tick modules from the spec §3 table. Show the derived slug inline.
```

**Verify:** run onboarding end to end for `home_food` and for `gym`. The two
flows must ask visibly different questions and produce visibly different sites.

---

## Phase 5 — Workspace depth (~3 h)

Every route already exists. This is completeness, not construction.

```
Order: home → orders → offerings → bookings → payments → customers →
       the rest.

Workspace home: rebuild to spec §8 — three bands (Needs you now / Today /
Your business). Delete any card that doesn't drive a decision.

Every list page: loading skeleton, useful empty state, recoverable error,
sensible columns, working row actions. Use the existing components/ui.tsx
(DataTable, EmptyState, StatusPill, PageHeader) — do not invent a second kit.

Navigation: AppSidebar must hide modules the business hasn't enabled. A
restaurant should not see Memberships.
```

**Verify:** click every sidebar item for a brand-new business — no crash, no
blank page, no dev placeholder text anywhere.

---

## Phase 6 — Website editor (~2 h)

Spec §7. The owner never sees JSON or the words "section type".

```
Preview-first canvas (PreviewCanvas.tsx already exists — build on it).
Section list with human labels from website_section_types.label.
Add-section offers only types valid for enabled modules.
Per-section form generated from content_schema.
Theme = primary colour + personality preset, live preview.
Publish = one button → success state linking to the live URL.
```

**Verify:** change a headline, replace an image, reorder two sections, publish,
see it live. Without ever seeing a raw field name.

---

## Phase 7 — Consumer flows + final pass (~2 h)

```
/activity, /[slug]/checkout, /[slug]/book, /[slug]/track/[orderId].
Consumer surfaces must never show owner operations.
Then sweep every P0 route at 390px and 1440px.
```

**Final verify:**

```
pnpm typecheck          # must pass
pnpm build              # apps/web, apps/workspace, apps/admin
pnpm lint
cd apps/api && pytest -q # must still be 302 passed / 1 known ambiguity
```

---

## The demo script this produces

Rehearse it once before showing anyone.

1. `/` — *"This is LOCAH."*
2. `/marketplace` — *"This is where customers find local businesses."* Show mixed types.
3. **Get started** → type grid → *"LOCAH asks what kind of business you are."*
4. Answer 5 steps → *"It understands, and builds the site."*
5. Preview → edit a headline → publish.
6. Open the live site — *"That's a real website, on its own URL."*
7. Back to Marketplace — *"And it's discoverable."*
8. Order or book as a customer → pay/COD → confirmation.
9. `/activity` — *"The customer tracks it here."*
10. Workspace → *"And the owner runs the whole business here."* Orders, bookings, customers, payments, insights.

If all ten steps work, LOCAH demos as a product. Everything else is polish.
