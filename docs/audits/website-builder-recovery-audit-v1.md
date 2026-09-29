# LOCAH Website Builder — Recovery Audit (Phase 1) · v1

Date: 2026-09-29 · Scope: Website Builder / Business Interview / CreativeDirector /
MediaDirector / renderer / AI providers. **Audit only — no product code changed.**

| | |
|---|---|
| Current base | `origin/claude/phase-b-final-integration` @ `187fd8c20339aab52d81cfbb7c1438899a7ef118` (advanced past `d851b32` while the prompt was written; `d851b32` is 4 commits below it) |
| Audit branch | `claude/compassionate-allen-hlpq6p` (the branch this session is required to use; the prompt suggested `claude/website-creative-audit`). Based on the SHA above. Nothing was pushed to the integration branch. |
| History | The clone was shallow; it was unshallowed (`git fetch --unshallow --all`) and every PR head fetched (`refs/pull/*`). Full reachable history: **207 commits**, 17 remote branches, 1 PR. |

### How to read the evidence labels

- **EXECUTED** — I ran it in this session (zero AI calls: `LOCAH_TEST_NO_EXTERNAL_AI=1`).
- **STATIC** — traced by reading the code; not run.
- **LOCAL_HISTORY_CHECK_REQUIRED** — cannot be settled from GitHub; needs the old PC / staging DB.

What was executed: `uv run python -m platform_testing.website_fixtures` (23 businesses through the
real interview with scripted model readings, composed exactly as Build composes, no model, no
images), and 109 existing unit tests (`test_website_design_system`, `test_site_composer`,
`test_interview_media`, `test_interview_semantics`, `test_website_copy`, `test_gemini_provider`,
`test_image_generation`) → **109 passed**. Nothing was run against Postgres, Gemini, or a browser.

---

## 0. Executive summary — why the owner path is weaker than the earlier sites

The earlier high-quality sites (meat shop, premium home kitchen, strength gym, Chennai property
developer, Ishant Proteins) were **live runs on 2026-09-23** under **CreativeDirector v2**
(commits `48c6723` → `f65914b`). Their own commit messages say so ("the first live Gemini run of the
meat shop", "the live home-food build", "the live gym", "From the final screenshots … real-estate",
"the live Ishant Proteins run"). All of that code is **still in the integration history** — nothing
was lost in a stale branch. What changed is what the pipeline *decides* by default. Ranked root causes:

| # | Root cause | Introduced | Evidence |
|---|---|---|---|
| RC1 | **Draft-visual consent is almost never obtained, so zero images are drawn.** MediaDirector draws only when `visual_consent == "draft_visuals"`. The photos question moved from tier-0 (asked before "ready", worded *"…If not, I can create draft visuals so the website doesn't look empty"*) to *enrichment* (never asked before "ready" for most trades), and its new wording (*"Do you have photos…? Real photos always come first"*) makes a short "No" record `no_visuals`. | `5c4aa2a` (09-26) | STATIC + transcript `docs/phase-a/interview-transcripts/home-food-model.md`: 3 questions, "That's all, build it", photos never asked |
| RC2 | **v3 routes every business without owner uploads to a text-first composition.** All image-led variants (`overlay`, `cinema`, `storefront`, `gallery`, `contact_sheet`, `plant`, `horizon`) require `has_media`, which counts only `USER_UPLOAD` non-logo assets. AI drafts never count, and the variant is chosen *before* any image is drawn. | `c5fedc7` (09-27) | EXECUTED: 23/23 fixtures get a no-photo variant, incl. all five golden business types |
| RC3 | **Truth rule removed the pictures the golden sites used**: no per-dish or per-project visuals; property developers, architects, interiors and photographers get **no generated imagery at all**. | `c5fedc7` | STATIC (`media_director.py:86-96`); diff of `c5fedc7` removes the per-item/per-project branch |
| RC4 | **Personalization is silently discarded if the owner types during it.** After Build, every chat message patches the draft (`updated_at` bump); the personalization job then marks itself `superseded` and the owner keeps the deterministic preview (no AI copy, drawn pictures not placed). The chat is not disabled while the job runs. | `00767be` (09-27) | STATIC (not reproduced) |
| RC5 | **The fallback site is thin.** Without model copy the hero headline is the business name, the subheadline is the owner's raw first sentence (even raw Tanglish), items have no lines, and the story section only exists if a model wrote `about`. | design | EXECUTED: 0/23 fixtures have a story section; home-food subheadline = "Naan veetla irundhu home food pannuren" |
| RC6 | **One page skeleton for every business.** `compose_site` emits hero → browse → (ordering strip) → story → CTA band → contact. Variety is theme tokens (fonts, palette, cards). | design | EXECUTED: 21/23 fixtures are `hero > category tiles > (fulfilment) > centered CTA > contact` |
| RC7 | **The model's creative latitude shrank.** v2 gave the model each profile's `fits` + `summary`; v3 gives three "feel" words per allowed family (≤3 families). The model can pick a family, two colours and copy — nothing about structure, hero, media or type. | `c5fedc7` | STATIC |

None of these is a provider problem: Gemini is already the default everywhere.

---

## 1. Branch / commit recovery map

### 1.1 What exists on GitHub

- **Every Website commit on any ref is an ancestor of the integration branch.** Only two commits
  on GitHub are *not* in it: `9c21d46` (`main`, "save": kitchen files + TECHNOVA deck + a dangling
  `apple-design` submodule pointer) and `8b495b8` (`cashfree-sandbox`, payments WIP). Neither
  touches Website code.
- **No teammate branch touches Website code.** Of the 15 `parallel/*` / `claude/*` branches, only
  `claude/p2-02-memberships-wip` touches one website file (`packages/ui/src/website.css`, membership
  styles) and it is already merged.
- **Authorship.** Every commit touching Website/interview code is by `Kausik GH` (56), `Claude`
  (7) or the `kausik-gh` initial import (1). There is no other author on this code in GitHub history.
- **No branch named web-builder, website, creative or media exists, now or in any fetched ref.**
  PR refs: only `refs/pull/1` (reviews/compliance).

### 1.2 The Website timeline (all on the integration line)

| Date | Commit | What it did | Status now |
|---|---|---|---|
| 09-16 | `f878779` | **Squashed import** of a pre-existing repo: 527 files / 100k lines incl. website kernel, questionnaire, fallback generator, section registry, renderer, migrations dated 2026-08-03 and 2026-09-01 | Base of everything; pre-09-16 history **not on GitHub** |
| 09-16 | `955f3d4` | Replace Gemini with **xAI Grok** for website generation | Superseded by `78d5817` |
| 09-16/17 | `8e583b1`, `34fa7b2` | Type-aware generation; **Grok Imagine** pictures as media assets (`website_images.py`) | Legacy path, off by default |
| 09-21 | `e3c027c`, `daacef6`, `c9ae942` | Composition + 9 v1 templates (`template_registry.py`), governed generation plan | Templates still reachable in Workspace |
| 09-22 | `b67824e` | Business Interview + voice + `design_strategy.py` | `design_strategy` now only on the unreachable template path |
| 09-23 | `78d5817` | **Gemini-first** runtime, Gemini Live voice, image generation behind `IMAGE_PROVIDER` | Active |
| 09-23 | `7261b30` | Discovery planner, live website draft, tiers | Partly superseded by `5c4aa2a` |
| 09-23 | **`48c6723`** | **CreativeDirector v2 + MediaDirector + site_composer**; reference profiles written from the founder's reference screenshots; photos/draft-visual consent in tier 0; per-dish/per-project visuals | **The golden-sample era.** Code still present, but decisions overridden by v3 |
| 09-23 | `ed73dfb`, `3aa786a`, `6aef25b`, `9a5bae1`, `754bbaf`, `f65914b` | Fixes from the **live** meat-shop, home-food, gym and real-estate runs | Mostly still active |
| 09-26 | **`5c4aa2a`** | Coverage-driven interview + question budget; photos → *enrichment*; new photo wording | **RC1** |
| 09-27 | **`c5fedc7`** | Design system v3: dimensions → 10 families → variants; truth rule; semantic validator; distinctness; site-lab fixtures | **RC2, RC3, RC7** |
| 09-27 | **`00767be`** | Keep talking to LOCAH after build (edits as structured state) | **RC4** (race) |
| 09-29 | `366ad71`, `bcc660b` | Module-aware site capabilities (P1-10C); EN/TA/HI site words | Active, valuable |

### 1.3 LOCAL_HISTORY_CHECK_REQUIRED

1. **Pre-09-16 history.** `f878779` is a squash. If teammates built Website work before 09-16 it
   exists only in the original repo. Useful evidence from the old PC:
   `git log --all --stat -- python/core/platform_core/website packages/ui/src/website.css apps/web/src/components/website`,
   `git branch -a -vv`, `git reflog --all`, `git worktree list`.
2. **`.agents/skills/apple-design`** — only on `main`'s "save" commit, as a gitlink to
   `da2da6dd03aacf06da3fecf205347601d38bb141` with **no `.gitmodules`**. Its content and origin
   URL are not in the repo. If this was the "design skill", recover the folder or its remote URL.
3. **The golden sites' actual data is in the database, not git.** The most valuable recovery is
   the staging Supabase rows from 2026-09-23: `website_generation_jobs` (`intake.composer =
   'creative-v2'`, `provider_usage->>'reference_profile'`), `website_versions` with
   `theme->'creative_direction'->>'version' = '2.0'`, their sections, and `media_assets` whose
   `storage_key LIKE 'generated/%'` created that day. That gives the exact payloads and drawn
   images behind the screenshots.
4. **`docs/build/`** (LOCAH-BUILD-SPEC.md, EXECUTION-PLAN.md) is git-ignored by the `build/` rule
   (noted in `docs/phase-a/PHASE-A.md`). Copies are in `Claude outputs/`; confirm they are current.

---

## 2. Current real owner generation flow

1. **Start** — `POST /v1/platform/businesses/start` → `services/business.py: start_conversation`.
2. **Talk** — `POST /v1/b/{id}/interview` (`routers/v1_business_interview.py`) →
   `BusinessInterviewService.execute` → `BusinessInterviewOrchestrator` turn: one Gemini call
   (`purpose=business.interview`, `orchestrator.py:351/620`) returns `TurnIntelligence`
   (facts, answered targets, media intent, website draft); deterministic governance merges it;
   `coverage.py` decides readiness; `planner.py` picks the next ask. Blueprint saved in
   `businesses.metadata.interview` (JSON).
3. **Ready** — `coverage.readiness` sets `ready_at` after essentials + high-value asks or budget
   (3–7 follow-ups). Checkpoint message offers "build now or keep refining".
4. **Confirm** — `ConfirmSheet.tsx`; pressing Build is the confirmation.
5. **Build** — `BusinessInterviewService.build` (`business_interview.py:863`):
   enables approved+entitled modules, patches profile/contact/type/logo,
   `creative = template source != USER_STATEMENT` (always true from the current UI, `:985`),
   **deterministic** `direct()` + `compose_site(with_draft(bp, None))` → draft written
   immediately (`generated_by="interview_template"`), then enqueues `website.generate`
   (`:1030`) and, only if an owner-requested hero artwork exists, `interview.generate_media` (`:1042`).
6. **Worker** — `job_runner.py` → `WebsiteGenerationService.execute_job` → `is_interview_job` →
   `personalize_job` → `_personalize_creative` (`:1068`):
   in parallel, **one Gemini call** `generate_creative_plan` (creative choices + copy, 45 s) and
   `media_director.draw_missing` (Gemini image model, ≤7 images, 75 s each, 3 at a time —
   **only with consent**). Then `compose_site` again with the AI direction and governed copy.
7. **Apply or discard** — if the draft changed since Build → `superseded` (`:1175`); if the
   model failed and nothing was drawn → `fallback_used` (preview kept); else the draft is replaced
   (`generated_by="interview_personalization"`).
8. **Preview** — `apps/web/src/app/start/[businessId]/website/*`: `LivePreview` polls job status;
   `WebsiteTalk` beside it; public renderer `WebsitePageView` → `SectionRenderer`; capabilities from
   `website/capabilities.py` at render time.
9. **After build** — every chat message → `talk_to_website` → `website_edits` → deterministic
   recompose → section patches (`business_interview.py:640-643, 673`).

Other generation paths that still exist:

| Path | Entry | Reachable by an owner? |
|---|---|---|
| Legacy questionnaire generator (`fallback_generator`, `generation_plan`, `_try_ai`) | `POST /website/generate` (`v1_website.py:88`) | API only — no UI caller |
| Interview + v1 template (`build_preview`, `design_strategy.generate_website_plan`) | interview action `template` | Contract only — current UI never sends it |
| **v1 templates replacing the draft** | Workspace → Website → Templates (`page.tsx:132`) → `templates/apply` | **Yes** — bypasses CreativeDirector |
| Section "Generate a picture" | Workspace preview editor → `sections/{id}/generate-image` | **Yes** — uses the legacy abstract `hero_prompt` |
| Auto website images | `media.generate_website_images` | Only if `AUTO_GENERATE_WEBSITE_IMAGES=1`, legacy path only |

---

## 3. Business Interview

**Exists and is strong:** 80 trade playbooks, 25 discovery targets, 24 asks, EN / Tanglish / Tamil
wording, text and Gemini Live voice, a coverage model that asks by information gain within a
3–7 question budget, contextual reading of short replies, corrections, a typed understanding
panel, a website draft with provenance, and an evaluation harness (23 owners × model / no model,
`docs/phase-a/interview-transcripts/SUMMARY.md`).

**Adaptive:** which asks are relevant (from observed characteristics + playbook prior), their
order, their wording per trade, the budget, readiness.

**Hardcoded:** the ask catalogue and its wording, readiness rules, and the importance of each
target per trade (`coverage.importance`).

**Missing / regressed:**

- Draft-visual consent is enrichment for every trade whose playbook `media` is not `critical`
  (`coverage.py:174-175`); before readiness only `blocking` / `high_value` asks run
  (`planner.py:192`). The planner's photo wording (`planner.py:124`) dropped the draft offer that
  the discovery target still has (`discovery.py:429`). A short "No" → `no_visuals`
  (`orchestrator.py:967, 974-988`). → **RC1**.
- No "I have a menu → upload it" behaviour: attachments are images only, classified by the
  owner's words (`attachment.ts`), never read.
- No explicit confirmation of what will go on the site beyond the understanding panel; a
  "missing optional enrichment" list exists ("Still worth knowing").

## 4. BusinessBlueprint

`interview/models.py` `BusinessBlueprint` (Pydantic, stored in `businesses.metadata.interview`):
identity, classification/category, operating model and patterns, locations, offerings text,
`taxonomy` (groups → items with price, unit, sold_by), customer actions, operational
characteristics, brand/tone/colours, logo state, `media_assets` (with `source`
USER_UPLOAD / AI_GENERATED), `media_generation_requests`, recommended / approved / declined modules,
`known_facts` / `unconfirmed_facts` with provenance, `discovery` state per target, `website_draft`
(headline, subheadline, about, CTA, offerings, owner claims — each with provenance), readiness,
`visual_consent`, `website_prefs` (feel, lead section), messages.

**Reaches generation:** everything via `direct()` (dimensions), `compose_site` (taxonomy, facts,
draft wording, discovery quotes, media), and `generate_creative_plan` (facts ≤400 chars each, the
owner's last 10 messages, `website_brief`).

**Lost or weak on the way:**

- The owner's `brand.story` answer is only a pull quote; the story body must be model-written
  (`site_composer.py:433-455`) → no story when the model is unavailable.
- Owner colours are recognised only as hex codes (`creative_director.py:340-343`): "green and gold"
  is ignored.
- `has_media` ignores approved AI visuals (`design_system.py:192`).
- Uploaded photos attach to items only when the upload's *label* slug starts with the item name
  (`media_director.py:168-171`, `site_composer` → `picture_for`) — fragile.
- The Build-time snapshot is what personalization composes from; later artwork on the live
  Blueprint is not merged in (see §6 bug B2).

## 5. CreativeDirector

`interview/creative_director.py` (v3.0) + `interview/design_system.py`.

- **Archetype** (`derive_archetype`): 8 archetypes from observed characteristics and words.
- **Dimensions** (`read_dimensions`): offering, journey, primary action, positioning, personality,
  energy, media importance, `has_media`, density, locality, portfolio, audience, trust,
  transaction, service mode — from the owner's words, with the playbook as prior.
- **10 families** (Editorial Warm, Premium Dark, Modern Commerce, Playful Editorial, Calm
  Professional, Monumental, Portfolio/Sketchbook, Technical B2B, Airy Property, Local Friendly),
  each with 3–4 palettes (31 in all) and 3–5 variants. A variant fixes hero layout, nav, type system, cards,
  image treatment, rhythm, surface, footer, motion, category/product layouts.
- **Reference profiles** (`REFERENCE_PROFILES`, 7) — the v2 design languages written *from the
  founder's reference screenshots*; in v3 only `story_variant` and `image_style` still come from
  them (`family.base_profile`).
- **Model call** (`generate_creative_plan`, `:535`): one Gemini call, `purpose=website.personalization`,
  temperature 0.5, 6000 tokens, 45 s; may choose a family among ≤3 allowed, two hex colours, and
  copy. `validate_repairing` + `govern_copy` + `direct()` are the authority.

**Design decisions actually available:** family, variant (→ hero layout, nav, type pair, card
style, image treatment, rhythm, surface, footer, motion, browse layout), palette (31 recipes),
headings/CTA wording. **Not decided anywhere:** section architecture, section rhythm per business,
proof/trust placement, CTA hierarchy beyond one primary, image crop/aspect per section, mobile
recomposition, business-specific micro-details.

**Used by the owner path?** Yes — `direct()` at Build and `generate_creative_plan` in the worker.

**Problems:** RC2, RC6, RC7; restaurant and café resolve to `service_appointment` (EXECUTED),
which removes the order label and changes media budget; image-led variants unreachable without
uploads; `allowed_families` recomputes `choose()`; owner colour only as hex.

## 6. MediaDirector

`interview/media_director.py` (+ `interview/media.py` for logo / owner-requested hero,
`services/website_images.py` for legacy/editor).

- **Uploaded media:** owner photos (`USER_UPLOAD`) always win per slot; hero role → hero; business
  role → story; offering/gallery matched to category/item by label slug.
- **Generated media:** `plan_slots` = hero + one per category (budget by archetype:
  commerce 5, menu 6, **fitness 0**, others 3) + a story picture for 4 archetypes; prompts are
  *photographic* in the reference profile's `image_style`, forbidding text/people/logos; drawn only
  when `visual_consent == "draft_visuals"` (`:208`) and `may_draw` (`:90`); cached per slot key;
  stored as media assets; recorded on the Blueprint as `AI_GENERATED`.
- **No-image behaviour:** nothing drawn → split heroes show a single **monogram letter**
  (`SectionRenderer.tsx:382-397`); centred/left heroes become type-on-ground with family CSS
  (letterpress rules, gradients, circles in `site-families.css`); categories become tiles with a
  small initial; boards hide their media column; CTA band `centered`; story falls to `text_only`.

**Problems / bugs:**

- RC1, RC3.
- **B1 (conflicting prompt philosophies).** `media_director.prompt_for` asks for "a realistic,
  professional draft photograph"; `image_generation.hero_prompt` / `offering_prompt` (used by the
  owner-requested hero job and the Workspace "Generate a picture") demand "abstract … must read
  clearly as artwork, not a photograph", keyed on `business_type` only.
- **B2 (owner-requested hero artwork dropped).** `interview/media.py:173-178` leaves placement to
  personalization while the job is pending/running, but `_personalize_creative` never calls
  `place_ready_artwork` and composes from the Build snapshot. If the artwork finishes first, it
  never reaches the draft. The test `test_artwork_waits_for_personalization_instead_of_touching_the_draft`
  mocks the placement and does not catch this. STATIC.
- **B3.** The owner-requested hero prompt takes its palette from the v1 template registry
  (`interview/media.py:60-64`), not the creative direction.
- **Provenance is weak:** `media_assets` has no provenance columns (`models.py:56`); AI origin
  lives in the Blueprint JSON, `alt_text` strings, the `generated/` storage prefix and an audit row.
  Model and prompt are not stored. Editor-generated images are not on the Blueprint at all. No
  public "illustrative" label.
- No replace / regenerate / approve / remove workflow for draft visuals as a set.

## 7. Website schema + renderer

- **Payload:** `pages[] → sections[] {section_type_id, layout_variant, content, is_visible}`,
  `navigation`, `theme_hints` (validated by `validation/website.py`; section types in
  `website/section_registry.py`). Creative sections: `hero`, `category_showcase`,
  `product_showcase`, `fulfilment_strip`, `about`, `cta_band`, `contact` (+ auto sections for
  plans, booking, shop, reviews added at render time by `capabilities.auto_sections`).
- **Theme consumed:** `WebsitePageView.tsx` turns `design_family`, `design_variant`, `rhythm`,
  `image_treatment`, `surface`, `footer_style`, `type_system`, `card_style`, `nav_style`,
  `motion_intensity`, `reference_profile`, palette colours into `data-*` attributes / CSS vars.
  **All v3 creative fields are consumed** — there is no "renderer ignores creative output" bug.
- **CSS:** `site-studio.css` (v2 reference-profile rendering; **unchanged since 09-23**, 19
  `data-profile` rule groups) + `site-families.css` (v3, 587 lines) + `website.css`.
  The renderer can still draw the golden compositions (`editorial_overlay`, `cinematic`,
  `commerce_split` with product panel, `airy_split` with architecture, `menu_grid` with photos).
- **Discarded / unused:** `creative_direction.reasons`, `dimensions`, `words`, `cta_tone` travel
  in the theme but only `data-*` values drive rendering; `hero_density`, `content_density`,
  `mobile_priority` are read but not set by the creative composer.
- **Fallbacks:** unknown values fall back to finite defaults; a missing image yields the no-image
  variants above.

## 8. AI provider map

**GEMINI (default for every purpose):**

| Capability | Code | Default model |
|---|---|---|
| Structured text | `website/ai_provider.py` `GeminiProvider` (`:405`), `get_ai_provider()` (`:592`) | `gemini-3.8-flash`, fallbacks `gemini-3.5-flash, gemini-3.1-flash-lite`; `GEMINI_INTERVIEW_MODEL`, `GEMINI_WEBSITE_MODEL` overrides |
| Interview turns | `orchestrator.py:351, 620` (`business.interview`) | as above, thinking low |
| Creative plan + copy | `creative_director.py:535` (`website.personalization`) | thinking medium |
| Legacy strategy/generation | `design_strategy.py:612, 668`; `website_generation.py:174` | reachable only via legacy paths |
| Images | `website/image_generation.py` `_generate_gemini` | `gemini-3.1-flash-image` (`GEMINI_IMAGE_MODEL`) |
| Voice | `interview/voice.py:291-420` (ephemeral token) + `voice/gemini-live.ts` | `gemini-3.8-live` |
| Document / image understanding | **none** | — |

**GROK / XAI — dead by default, live by configuration (not removed):**

- `AI_PROVIDER=xai|grok` → `GrokProvider` (`ai_provider.py:82, 617`) serves *all* text purposes.
- `IMAGE_PROVIDER=xai|grok` → xAI images (`image_generation.py:311-391`, `grok-imagine-image-2.0`).
- `VOICE_PROVIDER=xai|grok` → xAI realtime secrets (`voice.py:37-47, 245-289`) + `voice/realtime.ts`.
- Env: `XAI_API_KEY`, `XAI_MODEL`, `XAI_IMAGE_MODEL`, `XAI_VOICE_MODEL`, `XAI_VOICE` (`.env.example:62-64, 98-102`).
- Guard/logging: `ai_guard.py` host list, `logging.py:50` redaction.
- Stale comments/messages: `services/media.py:312` ("Grok Imagine"), `services/website_images.py:4`,
  `services/website_generation.py:175-178` (error text names `XAI_API_KEY`), `.env.example:98-100`
  (voice "uses the same XAI_API_KEY" — the default is Gemini), `docs/prompts/website-generation-overhaul.md`,
  `docs/current-build/HANDOFF.md`.
- Tests: `test_ai_provider.py`, `test_image_generation.py`, `test_business_interview_voice.py`,
  `test_website_generation.py`, `test_business_interview.py`, `test_ai_guard.py`,
  `test_logging_redaction.py`, `conftest.py`.
- `.env.example` omits `IMAGE_PROVIDER`, `VOICE_PROVIDER`, `GEMINI_WEBSITE_MODEL`,
  `GEMINI_IMAGE_MODEL`, `GEMINI_FALLBACK_MODEL`.

**OTHER:** `ReplayProvider` (`AI_PROVIDER=replay`, local acceptance) and scripted providers in
tests. `ai_guard.py` lists `api.openai.com` / `api.anthropic.com` as blocked hosts only — there is
no OpenAI or Anthropic client. "Claude integration hooks" (`growth/contracts.py`,
`tasks/compliance_hook.py`) are code seams, not AI calls.

**Recommended:** Gemini only, behind one boundary (text/structured, image, document/vision,
live voice). Remove `GrokProvider`, the xAI image branch, xAI realtime and `realtime.ts` together
with their env, guard entries and tests, after re-tracing callers (list above is complete as of
`187fd8c`).

## 9. Old / team Website branches

| Branch / commit | Purpose | Useful for Website? | Grok? | Recommendation |
|---|---|---|---|---|
| 15 `parallel/*`, `claude/*` branches | Business OS lanes (supply, inventory, jobs, quotes, queue, kitchen, dispatch, growth, attendance, documents, memberships, stage engine, reviews) | No (0 website files; memberships-wip adds plan styles to `website.css`, merged) | No | IGNORE (already merged) |
| `main` @ `9c21d46` "save" | Kitchen files + TECHNOVA deck + dangling `apple-design` gitlink | Possibly the design skill | No | LOCAL_HISTORY_CHECK_REQUIRED for the skill |
| `cashfree-sandbox` @ `8b495b8` | Payments WIP | No | No | IGNORE |
| `refs/pull/1` | Reviews/compliance | No | No | IGNORE |
| `48c6723` v2 creative director (in history) | Archetype → reference profile; photos/consent tier 0; per-dish/per-project visuals | **Yes** — the golden-era logic | No (Gemini) | PORT IDEA / MANUAL REIMPLEMENT — NEEDS SAMPLE REVIEW |
| `ed73dfb` | Profile `fits`/`summary` given to the model | Yes | No | PORT IDEA |
| `3aa786a`, `754bbaf` | Story picture per archetype incl. real estate; "one continuous photograph" prompt | Yes | No | PORT IDEA (story subjects still exist in `_STORY`, unreachable for property) |
| `955f3d4`, `34fa7b2` | Grok text + Grok Imagine | Only the persistence pattern (already reused) | **Yes** | IGNORE (remove Grok) |
| `e3c027c` v1 templates | 9 templates | Palettes only as a source for tests | No | Retire from owner UI after sample review |

No branch is SAFE_TO_MERGE for Website: there is nothing un-merged to merge. "Recovery" means
restoring specific decisions that later commits overrode.

## 10. Design skills / recipes recovered

| Component | Where | Status |
|---|---|---|
| `REFERENCE_PROFILES` (7 languages from the founder's screenshots) | `creative_director.py:92` | **VALUABLE**, partly DISCONNECTED (only `image_style`, `story_variant`, CSS profile) |
| `PROFILES_FOR` archetype → profiles | `creative_director.py:201` | DEAD (v3 no longer reads it) |
| `_ARCHETYPE_PRIOR`, `derive_archetype` | `creative_director.py` | ACTIVE |
| 10 `FAMILIES`, 31 palettes, variant rules, `_PALETTE_BY_EVIDENCE` | `design_system.py` | ACTIVE, VALUABLE (image-led variants effectively DISCONNECTED without uploads) |
| Dimensions (`read_dimensions`) | `design_system.py:124` | ACTIVE, VALUABLE |
| 80 trade playbooks (nouns, headings, CTAs, families prior, media importance) | `playbooks.py` | ACTIVE, VALUABLE |
| `site-studio.css` reference-profile rendering | `packages/ui/src/site-studio.css` | ACTIVE, VALUABLE (unchanged since 09-23) |
| `site-families.css` family rendering incl. no-photo treatments | `packages/ui/src/site-families.css` | ACTIVE |
| Type systems / faces (14) | `site-fonts.ts`, CSS | ACTIVE |
| MediaDirector slots, budgets, `_STORY`, photographic prompts | `media_director.py` | ACTIVE but gated (RC1, RC3); `_STORY["real_estate_projects"]` DEAD |
| Abstract artwork prompts `_SCENE_BY_FAMILY` | `image_generation.py:41` | ACTIVE on legacy/editor paths; conflicts with photographic prompts (B1) |
| Semantic validator | `semantic_design.py` | ACTIVE, VALUABLE |
| Copy governance (`govern_copy`, `COPY_PROMPT`) | `website_copy.py` | ACTIVE, VALUABLE (strict: drops whole fields on unsupported claim words) |
| Distinctness signatures | `distinctness.py` | ACTIVE — measures theme tokens, not section architecture |
| `design_strategy.py` (v1 interview strategy) | `interview/design_strategy.py` | SUPERSEDED (template path only); `derive_strategy` still computed and stored in job intake, unused |
| v1 templates | `template_registry.py` | SUPERSEDED for interview; still owner-visible in Workspace |
| Legacy generator + questionnaire | `fallback_generator.py`, `questionnaire.py`, `generation_plan.py` | SUPERSEDED (API only) |
| `apple-design` skill | gitlink on `main` | UNRECOVERABLE from GitHub |

## 11. Why the earlier test websites looked better (evidence only)

1. They were **live runs** (Gemini text + Gemini images), not the current deterministic
   fixtures. The v3 site-lab fixtures are *weaker* than the owner path (no model, no images,
   `capabilities: {}`), so there is no hidden "demo mode" that beats production today.
2. **Consent was asked early, with the draft offer**, so pictures were drawn (commit messages:
   "The rebuild then redrew seven pictures").
3. **Every business got its image-led reference composition** (v2: archetype →
   `PROFILES_FOR[0]` → hero `commerce_split` / `editorial_overlay` / `cinematic` / `airy_split`)
   and the drawn hero filled it. In v3, with no uploads (EXECUTED): meat → `modern_commerce/catalogue`
   (`left_aligned`, text), home food → `editorial_warm/menu_board` (`left_aligned`, text), gym →
   `monumental/wordmark` (`centered`, duotone), property → `airy_property/brochure` (`airy_split`
   with CSS gradient), industrial → `technical_b2b/spec_sheet` (`left_aligned`, text).
4. **Dishes and projects were pictured** (per-item slots) so `menu_grid` / project cards showed
   photos; now `menu_grid` without item pictures falls to `category_boards` / `compact_list`.
5. **Property got architecture imagery** (hero + courtyard story picture); now none.
6. The model saw richer creative context (`fits` + `summary`).

Still to compare against the samples: exact hero/type/palette per sample vs v2 profile values;
whether the samples show per-item photos; whether any sample used owner uploads; mobile layouts.

## 12. Why no-image sites are weak — root cause

For a typical owner (answers 3 questions, presses Build): `visual_consent` stays `unknown`
(RC1) → `draw_missing` returns nothing → the direction had already picked a no-photo variant
(RC2) → split heroes show a monogram letter, others type-on-ground; categories become tiles with an
initial; no story picture; CTA band plain → if the owner typed after Build, or the model failed,
the copy is also the deterministic fallback (RC4, RC5). Image generation is **not failing** and the
provider is **not** misconfigured by default; it is **never requested**.
For property / portfolio trades it is **intentionally prohibited** (RC3).

## 13. Current personalization limits

- **Business understanding:** strong for facts and actions; weak for positioning/personality
  (regex words), owner colours (hex only), uploaded material (not read).
- **Creative differentiation:** family + variant + palette — real but token-level; the model
  cannot change structure; allowed set ≤3 families.
- **Media:** gated by consent and truth rule; no catalogue extraction; conflicting prompt styles;
  weak provenance.
- **Layout:** one skeleton; no plans table, project detail, RFQ/specs/applications,
  certifications, process, FAQ, testimonials-by-evidence sections in the creative composer
  (some appear via `auto_sections` when modules are ready).
- **Typography:** 14 type systems chosen by variant; no per-business type decisions.
- **Mobile:** specific fixes exist (wordmark sizing by longest word, menu cards one per row,
  sticky call bar); no explicit mobile recomposition decisions in the direction.
- **Module integration:** good at render time (readiness-based capabilities, auto sections, no
  dead buttons); compose-time CTAs use a separate rule set (`site_composer` `_BOOK_LABEL`,
  `_browse_cta`) from `capabilities.decide`.

## 14. Safe upgrades found in history (do not merge — port deliberately)

- `48c6723` discovery target wording + tier-0 placement of `media.photos` — still present in
  `discovery.py:429-437`; only the planner and importance changed.
- `48c6723` per-item / per-project slots in `plan_slots` (removed in `c5fedc7`) — port only after
  the founder decides the truth rule for dishes/projects.
- `48c6723` / `ed73dfb` reference-profile `fits` + `summary` in the model context.
- `754bbaf` / `3aa786a` story pictures per archetype (`_STORY`, still in code).
- v2 hero choice per archetype (`PROFILES_FOR[0].hero`) as the *default when a hero image will
  exist* (owner or generated).

## 15. Proposed Phase-2 architecture (proposal only)

1. **Business Interview** — ask photos/visuals once before "ready" for media-important trades with
   the draft offer, *or* default draft visuals on with a clear toggle on the Confirm sheet
   (founder decision). Add "I have a menu/catalogue → attach it".
2. **BusinessBlueprint** — add a `media_plan` (per section slot: source, status, provenance) and a
   `brand_mark` decision; keep facts/provenance as is.
3. **Catalogue ingestion** — accept PDF + images; one Gemini document call → taxonomy items with
   confidence; never invent price/spec; low-confidence rows go to the existing SetupOfferings panel.
4. **MediaDirector first, then CreativeDirector** — plan media before choosing the variant, so
   `has_media` means "the hero will have a usable picture" (owner → catalogue → existing →
   Gemini → intentional typographic). Priority chain as in the brief §12.
5. **CreativeDirector v4** — keep dimensions/families/palettes; restore reference-profile context
   for the model; let the model propose a validated *art direction* (hero composition, section
   architecture from a finite vocabulary, emphasis, CTA hierarchy, image treatment per section)
   that deterministic governance checks.
6. **Section architecture per business** — recipes per offering/journey from existing section
   types (plans for gyms, projects + site-visit for property, capabilities/applications/RFQ for
   B2B, menu + ordering for food); new section types only with explicit schema approval.
7. **Gemini provider boundary** — one module for text, image, document, live; remove Grok paths;
   store model + prompt hash + source on each generated asset.
8. **Image generation** — one prompt system (photographic, reference style, honest subjects),
   provenance columns on `media_assets`, owner replace/regenerate/approve/remove, optional public
   "illustrative" label.
9. **Logo fallback** — typographic wordmark from the type system by default; Gemini mark on request;
   fix palette source (B3).
10. **Renderer** — keep `site-studio.css` + `site-families.css`; review 390 px per family.
11. **Editing/regeneration** — fix the supersede race (block chat until personalization lands, or
    apply personalization then replay the owner's structured edits); fix B2.
12. **Module-aware actions** — compose-time CTAs from `capabilities.decide`.
13. **Validation** — extend distinctness to section architecture and image coverage; site-lab
    fixtures with stubbed generated media; screenshot regression at 1440 / 390.

## 16. Do not redo

Business Interview (coverage, planner, playbooks, reader, corrections, voice), Blueprint with
provenance, `govern_copy`, semantic validator, design-system dimensions + families + palettes,
`site-studio.css` / `site-families.css`, `website/capabilities.py` + auto sections, draft
race-protection idea (owner edits win), media assets via asset id only, `ai_guard` kill switch,
replay provider, interview evaluation harness, site-lab + `sites.mjs`, EN/TA/HI site words,
RLS / server-side authorization around all of it.

## 17. Questions the golden samples should answer

For each sample: business type and primary customer intent; hero composition (split / overlay /
cinematic / wordmark), image subject and treatment; display + body faces, scale, case; palette
roles (ground, ink, one accent?); section order and which sections exist; card/list system;
whether items/dishes/projects have pictures (owner or generated); CTA placement and count; trust
elements shown; spacing rhythm; mobile hero crop, headline wrap, CTA stacking, sticky actions;
logo/wordmark treatment; business-specific details. And globally: which samples used owner photos
vs generated images; whether generated dish/project/property images are acceptable to the founder
(this reverses PHASE-A amendment 5); whether draft visuals should be on by default.

---

## Appendix A — EXECUTED fixture output at `187fd8c` (no model, no images)

| Fixture | Family | Variant | Hero | Palette | Archetype | Images |
|---|---|---|---|---|---|---|
| meat-shop | modern_commerce | catalogue | left_aligned | charcoal_chili | product_commerce | 0 |
| restaurant | editorial_warm | split | editorial_split | burgundy_saffron | service_appointment | 0 |
| home-food | editorial_warm | menu_board | left_aligned | forest_turmeric | menu_commerce | 0 |
| bakery | local_friendly | noticeboard | editorial_split | brick_teal | menu_commerce | 0 |
| gym | monumental | wordmark | centered | black_volt | membership_fitness | 0 |
| salon | premium_dark | salon | centered | charcoal_brass | service_appointment | 0 |
| dental | calm_professional | practice | left_aligned | clinic_teal | service_appointment | 0 |
| hospital | calm_professional | reassure | editorial_split | clinic_teal | service_appointment | 0 |
| hotel | airy_property | estate | centered | sand_sage | service_appointment | 0 |
| real-estate | airy_property | brochure | airy_split | sky_navy | real_estate_projects | 0 |
| tuition | calm_professional | campus | editorial_split | harbour_navy | membership_fitness | 0 |
| photographer | portfolio_sketchbook | notebook | left_aligned | dusk_film | project_portfolio | 0 |
| industrial | technical_b2b | spec_sheet | left_aligned | slate_cobalt | b2b_rfq | 0 |
| logistics | technical_b2b | spec_sheet | left_aligned | slate_cobalt | b2b_rfq | 0 |
| florist | local_friendly | noticeboard | editorial_split | butter_green | product_commerce | 0 |
| interiors | portfolio_sketchbook | studio | editorial_split | dusk_film | project_portfolio | 0 |
| premium-butcher | premium_dark | counter | editorial_split | ebony_rose | product_commerce | 0 |
| family-butcher | editorial_warm | counter_book | editorial_split | terracotta_olive | product_commerce | 0 |
| meat-delivery-app | modern_commerce | app_like | centered | electric_cobalt | product_commerce | 0 |
| cafe | editorial_warm | letterpress | centered | burgundy_saffron | service_appointment | 0 |
| yoga-studio | calm_professional | retreat | centered | sage_clay | membership_fitness | 0 |
| law-firm | calm_professional | desk | left_aligned | harbour_navy | service_appointment | 0 |
| play-school | playful_editorial | sticker | editorial_split | lilac_lime | service_appointment | 0 |

Section sequences: 21 of 23 are `hero > category_showcase[tiles] > (fulfilment_strip) >
cta_band[centered] > contact[full]`; meat-shop / butchers use `product_showcase[category_boards]`;
real-estate uses `product_showcase[project_cards]`. No fixture has an `about` section.

Reproduce: `LOCAH_TEST_NO_EXTERNAL_AI=1 uv run python -m platform_testing.website_fixtures <dir>`.

## Appendix B — correctness defects found (independent of design direction)

| ID | Severity | Defect | Location | Evidence |
|---|---|---|---|---|
| B4 | High | Owner message during personalization discards it (`superseded`) | `business_interview.py:640-643, 1170-1176`; `website.py:388`; `WebsiteTalk.tsx` | STATIC |
| B2 | Medium | Owner-requested hero artwork never placed if it finishes before personalization | `interview/media.py:173-178`; `_personalize_creative` | STATIC |
| B5 | Medium | Short "No" to the photos question disables all draft visuals | `orchestrator.py:967, 983-988` | STATIC |
| B1 | Medium | Two contradictory image prompt systems | `media_director.py:134`; `image_generation.py:105, 160`; `website_images.py:94` | STATIC |
| B3 | Low | Owner-requested hero uses v1 template palette | `interview/media.py:60-64` | STATIC |
| B6 | Low | Workspace Templates can replace a creative draft with a v1 template | `apps/workspace/.../website/page.tsx:132` | STATIC |
| B7 | Low | `.env.example` stale for voice/image providers | `.env.example:45-102` | STATIC |
