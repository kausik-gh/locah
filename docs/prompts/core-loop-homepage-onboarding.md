The Core Loop — Homepage, Business Onboarding, Module Claim
Work Order for Opus / Claude Code
Before anything else: re-verify every claim below against the current state of `main` yourself. This was checked against a specific clone at a specific moment — things may have changed since. Do not trust these findings as current fact; use them as a starting map and confirm or correct each one.
Why this work order exists
Every prior stage built real, working, tested infrastructure — website generation, marketplace, orders, bookings, payments, modules, notifications. None of it is reachable by an actual new user, because the one thing that was never built is the front door. Verified directly:

* `apps/web/src/app/page.tsx` — the literal homepage — renders a page titled "Identity Foundation", dumping the logged-in user's raw JSON profile with a logout button. This is Stage 1 debug scaffolding, never replaced.
* There is no route, anywhere in `apps/web`, that explains what the platform is or offers a choice between "I run a business" and "browse the marketplace."
* There is no UI to create a business. The only way to create one is `tools/create_business.py`, a CLI script.
* Module recommendation data exists and is real — `business_type_profiles/registry.py` has `ModuleSeed(module_id, rationale, rank)` per business type per Document 07 §10 — but there is no endpoint exposing it as a recommendation, and no UI presenting or letting someone claim it.

This is the actual founder intent, stated directly: a visitor lands on a real homepage, sees the platform, chooses "I run a business" or "browse marketplace," and if they're a business — go through onboarding that collects what's needed, generates their real website live (the Stage 2 engine already does this — connect to it, don't rebuild it), then recommends modules for their business type, lets them claim/activate what they want, and from that point Orders/Bookings/Payments/etc. actually work because the modules are now active.
Every backend piece this needs already exists and is tested. This work order is entirely about connecting them into one real, visible, walkable flow — not building new business logic.
Section 1 — A real homepage (`apps/web/src/app/page.tsx`)
Replace the "Identity Foundation" page entirely. Requirements:

* Explains what the platform is, in one clear sentence a stranger would understand — not the "infrastructure layer" framing, the concrete version: a business gets a real website, a marketplace listing, and working commerce/booking, in one place.
* Two clear paths: "I run a business" → business onboarding (Section 2) and "Browse businesses" → the existing `/marketplace` (already built, don't touch it — just link to it).
* Does NOT require login to view. Login/signup happens when someone actually commits to one path (starting business onboarding, or a consumer action like checkout/booking that already requires an identity).
* A logged-in visitor with an existing business should land somewhere useful (their Workspace), not on the same generic landing page — check `/v1/me` or equivalent for existing businesses and route accordingly.

Keep this simple and functional. This is not the place for the cinematic design pass — that comes later, once the flow itself is real. Plain, clear, correctly structured HTML/Next.js is the bar here.
Section 2 — Business onboarding flow (new, real UI)
This is the core gap. Build the actual sequence, consuming existing APIs:

1. Business basics — name, business type (the real `SUPPORTED_BUSINESS_TYPES` list), initial location. This is what `tools/create_business.py` does via `POST /v1/platform/businesses` — call that same endpoint from real UI instead of a script.
2. Website generation, live and visible — immediately after business creation, trigger generation (already automatic per Stage 2 — confirm whether it's already async-triggered on business creation, or needs an explicit call here) and show real progress, not a fake spinner: pending → generating → draft ready. Land on an actual preview of the generated website when done. This is the single most important moment in the whole flow — the platform's core promise made visible in real time. If Stage 2's generation pipeline already exists and works (it does, verified earlier), this step is almost entirely UI work consuming what's there.
3. Module recommendations — call the business-type profile data (`business_type_profiles/registry.py`'s `module_seeds`) via a new, thin endpoint if one doesn't exist yet (check first — it may not). Present the recommended modules for this business type, ranked, with their stated rationale. This is real data, not invented copy.
4. Claim/activate — let the owner select which recommended modules to activate (and browse the rest of the module catalog if they want more, reusing the Module Catalog page already built in Stage 7 Section 3). Calls the existing module-enable API.
5. Arrival — land in the real Workspace (`apps/workspace`, already built) for the new business, with the just-activated modules genuinely showing real Workspace pages, because they're genuinely active.

Confirm as you build: does completing step 4 actually make Orders/Bookings/ Payments/etc. immediately functional for that business, end to end? That's the real test of whether this loop is real, not just visually complete.
Section 3 — The "browse marketplace" path
Should already work — `/marketplace` exists from Stage 3. Verify it's reachable from the new homepage, verify it still functions against the current (now-cleaned) database, and fix anything broken. Do not rebuild this.
Section 4 — Verify the full loop, manually, as a real user would
This is the actual acceptance test for this work order, and it should be run for real, not just reasoned about:

1. Open the homepage fresh, no login.
2. Choose "I run a business."
3. Sign up.
4. Go through onboarding — real business info, watch the website actually generate, see real module recommendations, claim a few.
5. Land in a real Workspace with those modules active.
6. As a different, second identity: browse the marketplace, find that business, place a real order or booking through it (guest checkout, already proven to work).
7. Back as the business owner: confirm that order/booking shows up in their Workspace.

Report the exact result of each step, including anything that breaks. This is what "the frontend actually works" means — not typecheck passing, not unit tests passing, an actual person completing the actual loop your founder document describes.
Scope boundaries — do not do these here

* No visual/cinematic design pass (that's the separate Prompt A/B work, still pending — this work order makes the loop real, not beautiful).
* No changes to the website generation engine itself, the module system, or any backend service — this is entirely about the missing connective UI and the one or two thin endpoints Section 2.3 might need.
* No Razorpay work — stays out of scope until real keys are provided.

Report
State plainly, for each section: what already existed and just needed wiring, what had to be built new, and the result of the Section 4 manual walkthrough — step by step, including failures. If the loop breaks anywhere, say exactly where, don't paper over it.
