Website Generation Overhaul + Workspace Cleanup
Mega Work Order for Claude Code
Sequencing: this comes after the immediate-priorities work order (performance diagnosis, Razorpay connect, location cleanup) already handed off. Do these sections in order; each is checkpointed on its own, per the project's standing discipline (targeted tests per change, full suite only at real milestones, diffs shown before anything touching schema/auth).
0. Security — the exposed Gemini key
The founder has explicitly authorized using this key now and will rotate it later: `AIzaSyA0Qm6IIhHIv3qBDn3-QpzRcUZlhcbB72A`

* Store as `GEMINI_API_KEY` in `.env` only. Never in any committed file, never in any client-side/`NEXT_PUBLIC_*` variable, never returned in any API response.
* Add `gemini_api_key` / `GEMINI_API_KEY` to the AUD-11 redaction filter's keyword list — confirm it would actually be caught if it ever appeared in a log line, the same way `service_role` was checked and added earlier.
* Set a reminder note in memory: this key needs rotation once the founder generates a fresh one — don't silently forget this is a temporary key.

1. Documentation amendment — this must happen, additively
Several real product decisions were just made in conversation that aren't reflected in Documents 08-12. Update them following the same additive, dated-amendment discipline Document 08 §25.3 already establishes elsewhere in this project (a recorded amendment pass, not a silent rewrite that pretends this was always the plan) — because it wasn't; it was decided now, and the documents should say so honestly.
Find and correct/extend:

* Document 12 §11-12 (Website architecture, AI generation) — clarify explicitly: AI generates CONTENT ONLY (copy, image selection, layout variant choice within existing section types) and NEVER platform mechanics (cart behavior, checkout flow, stock display, nav structure, order confirmation) — those are fixed, tested code, identical across every business, never AI-authored. If anything in the current text implies AI has broader scope than this, correct it.
* Document 12 §12 — the generation questionnaire. Document the structured, one-shot generation model precisely: a thorough, skippable, business-type-aware questionnaire (Section 3 below) feeds ONE `generate_structured` call per business — never a multi-turn chat with the end user. Note explicitly this was a deliberate decision to keep cost low and output safe/bounded.
* Document 12 / Document 09 — prebuilt templates. Document the model once Section 2 below is built: externally-sourced design references translated into the existing theme/SectionType system (Option A above), never raw external HTML/JS rendered directly. State why, citing the existing "no arbitrary HTML/JS" principle this is consistent with, not in tension with.
* Document 09 CORE-005/006/007 (Website Pages/Theme/Preview&Publish) — document the inline click-to-edit interaction pattern from Section 4 below as part of these pages' spec.
* Remove/correct anything in the existing text that now conflicts with the above — don't leave two contradictory descriptions standing.

Report exactly which documents/sections you touched and quote the before/ after of anything you corrected rather than just added.
2. Prebuilt template pipeline (Option A — confirmed direction)
This section only activates once the founder drops an export into a folder. For now:

1. Define the folder location and expected input shape — since we don't yet know what the external builder will export (could be a Framer/Webflow HTML export, a Figma export, or just images), design the intake to accept whatever's plausible: images extracted separately, a documented process for reading exported code as a design reference (colors, fonts, spacing, layout patterns) rather than assuming a specific format now.
2. When something is actually dropped in, the task is: extract the real design decisions (palette, typography, imagery style, section layout preferences) and encode them as a new theme definition in the existing `WebsiteVersion.theme` JSONB shape and any new `SectionType` layout variants needed — NOT copy any raw HTML/CSS/JS into the rendering path.
3. If the export contains something the current 13 `SectionType`s can't represent, flag it back rather than inventing a new arbitrary section type unilaterally — new section types are a real schema/architecture decision (per standing discipline: schema changes get shown before applied).

This section may sit idle until the founder provides the export — don't block other sections on it.
3. The generation questionnaire — thorough, skippable, business-type-aware
Build a structured (not conversational) intake feeding one `generate_structured` call, replacing/extending the current minimal onboarding fields from `/start`.
Design constraint, stated explicitly: every question must map to content the existing 13 `SectionType`s can actually render. Don't ask about capabilities the platform doesn't have a slot for yet (e.g. don't ask about a blog if there's no blog section type). The floor is "as thorough as a professional web developer interviewing a client before building a site," bounded by what can actually be built with what exists today.
Universal questions (every business type), all skippable:

* Logo: upload / generate a placeholder / skip for now
* Hero image: upload / choose from a curated set / generate / skip
* Tone: a few concrete slider pairs (e.g. warm↔minimal, playful↔professional, bold↔understated) rather than an open text box
* Color: choose from curated preset palettes (not logo-extraction yet — that's an explicitly deferred v2 item, don't build it now)
* What to lead with: top 1-2 things a first-time visitor should notice
* Contact/location display preferences (already partially collected — extend, don't duplicate)
* Social links, hours — standard footer content
* Any specific words/phrases they want used, or avoided

Business-type-specific questions, pulled per type (extend the existing `business_type_profiles` pattern — this is real design work per type, not one generic form):

* Home food: per menu item — name, description, and ask if they want optional fields like health benefits, dietary tags, spice level, serving size — each individually skippable, shown as suggestions not requirements
* Salon/spa/services: per service — description, duration hint, what makes it different
* Retail: per product — description, materials/care details if relevant
* Clinic/professional: per service — description, what to expect

Every optional field must be presented as a real suggestion with an example, not a blank box — the goal is to lower the barrier to answering well, the way a developer would prompt a client rather than just asking an open question and waiting.
The single generation call: assembles all answered (non-skipped) fields into one prompt, calls `generate_structured` once, maps the result into the existing Page/Section structure exactly as the current pipeline already does. Skipped fields get sensible defaults from the deterministic fallback logic already built — reuse it, don't duplicate it.
Do not build per-field "improve this" AI helpers or single-section regenerate in this pass — those are legitimate fast-follow ideas, explicitly out of scope for now until the core flow is proven.
4. Inline click-to-edit preview (for template-based sites)
In the website preview (used for the prebuilt-template path), add:

* Click an existing image (logo, hero, etc.) → upload flow to replace it in place, writing through the existing content-update API, not a new storage path.
* Double-click any text block → inline edit, saving through the existing section content-update API (same validation, same content-safety checks already enforced — this is not a new unsafe input surface, just a nicer way to trigger the same existing update call).

This is additive UI on top of existing update endpoints — no new backend logic should be needed unless something's genuinely missing; if so, flag it rather than assume and build new API surface silently.
5. Workspace cleanup
Run Prompt B from `frontend-design-work-order.md` (already written, not yet executed) — the grouped-nav, shared-table, restrained-motion redesign of `apps/workspace`. Do not re-derive a new design direction; that file is the spec.
Reporting
Report each numbered section separately as it completes, not one giant report at the end. Section 2 may report "idle, no export provided yet." Flag anything that turns into a real architecture/schema decision rather than resolving it silently — same standing rule as every prior stage.
