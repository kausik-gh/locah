# Website Creative System v4 — Handoff

Branch: `claude/compassionate-allen-hlpq6p`. It now contains the latest `origin/claude/phase-b-final-integration` (`a2047cb`), merged in. Nothing was pushed to the integration branch.
Audit and golden analysis: `docs/audits/website-builder-recovery-audit-v1.md`, `docs/audits/golden-reference-analysis-v1.md`.

## ACTIVATION CHECK — STATUS

```
REAL_GEMINI_IMAGES_VERIFIED      = NO   (blocked: no GEMINI_API_KEY in this environment)
MANUAL_IMAGE_GENERATION_VERIFIED = NO   (buttons verified end to end with stand-in pixels; not with Gemini)
NO_IMAGE_OWNER_FLOW_VERIFIED     = NO   (verified with stand-in pixels; not with Gemini)
SAFE_TO_INTEGRATE                = NO   (set only after the three above are YES)
```

**What is missing: exactly one credential, `GEMINI_API_KEY`.**
- It is set nowhere in this container, and this environment has no Supabase Storage project.
- The network is not the problem. `generativelanguage.googleapis.com` is reachable: the tunnel is established and Google answers 403 for the missing key.
- `IMAGE_PROVIDER` defaults to `gemini`.
- `GEMINI_IMAGE_MODEL` defaults to `gemini-3.1-flash-image`. Whether that is still Google's *current* image model can only be confirmed with a key. The check script lists Google's models and fails if the configured one isn't there.

**To finish, run one command with the key:**

```
GEMINI_API_KEY=… IMAGE_PROVIDER=gemini GEMINI_IMAGE_MODEL=<current image model> \
  tools/acceptance/stack/db.sh locah_accept && \
  uv run python tools/acceptance/stack/gemini_verify_v4.py acceptance-out/gemini --local-storage
python -m http.server 8899 -d acceptance-out/gemini/media &   # (--local-storage only)
tools/acceptance/stack/api.sh & tools/acceptance/stack/web.sh &
node tools/acceptance/owner_sites.mjs acceptance-out/gemini   # 1440 + 390 screenshots
```

Notes on the command:
- Use `SUPABASE_URL` + `SUPABASE_SERVICE_ROLE_KEY` instead of `--local-storage` to persist to real Storage.
- `gemini_verify_v4.py` refuses to run without a key and names what is missing. It computes the flags itself; they can only be YES from a real run. `--self-test` exercises the harness with labelled plates and always reports NO.

| # | Item | Status |
|---|---|---|
| 1–5 | Real Gemini, config, five real owner flows, screenshots, per-hero checks | **Blocked (no key).** Scripted in `gemini_verify_v4.py`. Its self-test run passed all 11 hero checks for every site (persisted MediaAsset, MediaPlan hero slot, preview, publish, gemini_generated/draft, provenance, approvable, replaceable, removable). The "returned by Gemini" check needs the real run. |
| 6 | Workspace: Hero → Generate → Generate new → Keep → Remove → Upload | Clicked in a real browser (`tools/acceptance/editor_pictures.mjs`) with stand-in pixels: **9/9 pass**. This found and fixed a real bug: a just-generated picture showed no draft label and no *Keep*, and *Remove* left the old thumbnail. *Upload my photo* needs a Storage signed-upload URL, which the local stack has none of; the replace-with-uploaded path is covered by API tests and the verifier. With real Gemini: **not verified**. |
| 7 | Controls for every media-capable section; none for factual slots | **Done.** One server decision, `media_director.image_policy`. |
| 8 | Manual generation across 9 unrelated archetypes | **Done** at the Gemini boundary (`test_website_manual_images.py`): home food, restaurant, gym, property, industrial, clinic, salon, tuition, repair. No business-specific code. |
| 9 | No uploads → Gemini drafts automatically | Automatic drafting is proven with stubbed image bytes (`test_website_creative_v4`, self-test: 2–7 drafts per site). With real Gemini: **not verified**. |
| 10 | Uploaded hero wins | **Done**: API test plus the verifier self-test. |
| 11 | Menu PDF with real Gemini extraction | **Blocked (no key).** Scripted in the verifier: every item and price returned must be printed in the PDF. Governance is covered by `test_interview_documents.py` with a replayed reading. |
| 12 | Parallel flakes | **Root-caused and fixed** (see §8). |
| 13 | IST/UTC date flakes | **Fixed.** Tests only; reproduced and verified with `faketime` at 21:00 and 23:50 UTC. |
| 14 | Merge latest integration branch | **Done.** Merged 10 commits (`a2047cb`). Migration version clash found and fixed (see §7). |
| 15 | Full gate | Migrations (90, fresh DB), API + worker suite, ruff, mypy, web / workspace / contracts tsc + lint, browser flows: **all green** (§8). |
| 16 | This handoff | Updated. |

## Manual picture controls (item 7)

`media_director.image_policy(theme, section_type, layout_variant)` is the only rule. The editor reads it from the draft payload (`section.image_policy`) and keeps no list of its own.

| Picture | Policy | Editor offers |
|---|---|---|
| Hero, story (`about`), closing band (`cta_band`) | `draw` (mood) | Generate a picture · Generate a new picture · Keep this picture · Remove · Replace with my photo |
| Category / product / dish cards (`category_showcase`, `product_showcase`) | `draw` (representative), one card at a time; the card's name is the subject | the same, per card |
| Gallery | `real_photo` | Upload / replace / remove only, with "This should be a real photo of your work — upload one instead." |
| Project cards; any card on an evidence-led site (property projects, portfolio) | `real_photo` | the same |
| Plan cards, text-only sections | none | — |

`POST …/sections/{id}/generate-image` now:
- takes `{list_key, index}` for a card;
- answers `needs_real_photo` for factual slots;
- records `generated_for` (`editor:hero`, `editor:product_showcase:items.0`) and the prompt version;
- **refuses another business's section.** Before this, it checked the section id only, a cross-tenant write that has now been fixed and tested.

---

## Commits

| Checkpoint | Commit | What |
|---|---|---|
| 2A | `f0bbc09` | Pictures by default, MediaPlan before the design, truth classes, one shoot brief, owner-edits-win merge, Gemini only |
| 2B | `da89397`, `3c3d0d6` | Per-business page architecture, designed headlines without a model, colour words, story, one CTA decision, mobile strategy |
| 2C | `963fbb5` | Menu / catalogue / PDF reading with owner confirmation; media provenance; draft approve / replace / remove |
| 2D | `2239d24` | Owner flow for five businesses, the fixes it found, screenshots |
| merge | `1529579` | `origin/claude/phase-b-final-integration` (`a2047cb`) merged in; v4 migration renumbered |
| flakes | `3254daf` | Test job drains scoped to their business; date tests use the business day |
| item 7/8/10 | `782e775` | Editor picture controls from `image_policy`; per-card generation; cross-tenant fix |
| verifier | `ff5d56b` | `gemini_verify_v4.py` |
| editor fix | `4e7a226` | Just-generated picture is a draft at once; Remove clears at once; stand-in API for click-through |

## 1. SUMMARY

LOCAH now builds image-led, business-specific websites by default. An owner with no photos gets draft pictures (labelled as drafts, never shown as their own photos), unless they explicitly ask for a text-only site. Pictures are planned before the design is chosen, and all of them are drawn from one shoot brief, so the page reads as one visual world. The five golden-reference kinds each get their own composition, typography, palette and page structure, derived from what the owner said. Nothing is hardcoded per business.

## 2. WHAT THE RUN SHOWS (2D)

`tools/acceptance/stack/owner_flow_v4.py` drives the product's own path for five owners:

1. Create Business.
2. Talk to LOCAH, through the interview API, answering whatever LOCAH asks.
3. Build.
4. The real `website.generate` worker job: MediaPlan, CreativeDirector, composition, draft merge.
5. Publish.

`tools/acceptance/owner_sites.mjs` then screenshots the public route `/<slug>` at 1440 and 390.

| Business | Hero | Palette | Page (in order) |
|---|---|---|---|
| Nalla Veedu Kitchen (home food) | `editorial_overlay` | forest_turmeric | hero → dish cards → how ordering works → CTA → contact |
| Grit Barbell Club (gym) | `cinematic` | black_volt | hero → programmes → memberships (₹2500 / ₹6500 / PT packs) → good to know → CTA → contact |
| Aranya Homes (developer) | `airy_split` | sky_navy | hero → project cards with the owner's statuses → good to know → CTA → contact |
| Ishant Proteins (meat) | `commerce_split` | charcoal_chili | delivery strip → hero → category boards with cuts → how ordering works → CTA → contact |
| Torque Flow (industrial) | `commerce_split` | slate_cobalt | hero → product range → industries served → CTA → contact |

Screenshots are in `docs/current-build/v4-screens/` (`contact-sheet.jpg`, `<kind>-desktop.jpg` at 1440, `<kind>-mobile.jpg` at 390), and the run data is in `owner-flow-results.json`.

**What is real and what is a stand-in in this run** (be precise about this):
- **Real:** every product step and all the code: interview, planner, blueprint, MediaPlan, CreativeDirector (deterministic path), composer, draft merge, validation, publish, and the public renderer.
- **Scripted model readings:** the conversation readings are the acceptance personas' recorded model readings (`platform_testing/interview_personas.py`, served by the replay provider). This is the project's existing stand-in for Gemini's reading.
- **Not run:** the creative plan model call. It had no recording, so the deterministic direction and designed words were used, as ships when Gemini is unreachable. I did not write website copy to make screenshots look better.
- **Stand-in pixels:** picture pixels are labelled `STAND-IN` gradient plates. Gemini image generation was **not run** (no key; outbound image hosts are blocked here). Where each picture goes, its prompt, its truth class and its provenance are real.
- `--model-down` mode runs the same flow with free text and no model reading at all.

**Bugs the run found that fixtures had hidden (all fixed, all tested in `test_website_owner_words.py`):**
- "cut fresh to order" was read as *order online*, which gave the meat shop an app-like layout and a text hero.
- A developer who said "calm, green" got the clinic family (`calm_professional`); the property family now owns *calm*.
- The model-down listing made groups like "We deliver around Nookampalayam"; it now keeps only things sold.
- Volunteered opening hours were lost or filed as the gym's plans; hours are now captured whatever was asked.
- Fitness, property, B2B and portfolio pages had no slot for "good to know" (trial, hours, place). The trial line was a garbled summary; it is now the owner's own sentence.
- "3 km kulla" (Tamil: within 3 km) rendered as "Delivered around 3 Km Kulla"; it is now "Delivered within 3 km".
- A home kitchen showed "Store pickup"; it now says "Pickup available" / "from our home".
- "Industries we serve" listed *Hosur*; places are stripped.
- Project cards showed a generic "PROJECTS" label and the name twice; they now show the name plus the status the owner gave ("Ready to move", "Under construction", "Upcoming").
- The gym's "See plans" pointed at plans that were never shown. Plans now come from the owner's own answer: a price only where they said a number.

## 3. COMPARISON WITH THE GOLDEN SAMPLES

**Matches the golden direction:**
- Home food, gym and meat each have their own art direction on the shared skeleton:
  - home food: editorial serif on dark photographic ground;
  - gym: condensed monumental caps, volt accent, footer wordmark;
  - meat: dark commerce split with a red frame and category boards.
- None of the contact-sheet anti-patterns (giant initials, identical template) remain.

**Still behind the golden samples (honest):**
1. Pixels. The golden quality depends on the photography. The v4 prompts are art-directed (one brief per site, hero framing per composition), but real Gemini output has **not** been seen in this branch.
2. Story sections. They appear only when the owner tells a story in English or when Gemini writes the copy. In the scripted runs the conversation reached the build checkpoint first, so no story section appeared.
3. Dish/product descriptions. These come from the creative model; without it, cards show names only.

## 4. ARCHITECTURE PRESERVED

All of the following are unchanged in contract:
- interview orchestration;
- 80 playbooks;
- blueprint provenance;
- copy governance;
- semantic validator;
- the 10 families and `site-studio.css` / `site-families.css`;
- capabilities (one CTA decision in `website/capabilities.py`, renderer `liveAction` gate);
- owner-edits-win (now a fingerprint merge, never "superseded");
- the kill switch `LOCAH_TEST_NO_EXTERNAL_AI`;
- EN/TA/HI;
- the job architecture.

## 5. PROVIDERS

- Gemini only. xAI/Grok is removed from text, image and voice.
- `AI_PROVIDER` / `IMAGE_PROVIDER` / `VOICE_PROVIDER` accept `gemini` or `replay`; anything else is unavailable, with a warning.
- Model choice is centralised in `website/ai_provider.py` (`model_for`, thinking levels, fallback models, `GEMINI_DOCUMENT_MODEL`).
- Document reading uses Gemini structured output with the file inline.

## 6. TRUTH, SAFETY, TENANCY

- **Truth classes** are factual / representative / mood / graphic:
  - Factual slots (a developer's projects, a photographer's work) are **never drawn**. `build_prompt` raises for them.
  - Drafts are `gemini_generated`, `approval_state=draft`, and record their slot, job and prompt version. The editor says "Draft picture by LOCAH" and offers *Replace with my photo / Keep this picture / Remove*.
- **Documents:**
  - They sit in the private `owner-documents` bucket, are read with the service role, and are scoped to the business on every read. A cross-tenant attempt is tested and rejected.
  - Document text is treated as data in the prompt.
  - A price must contain a digit. Unclear lines arrive unticked. A printed phone or hours is shown to confirm, never applied silently.
- No secrets are in prompts. Content stays structured, with no generated code.

## 7. ACTIVATION REQUIRED

1. Apply migration `infra/supabase/migrations/20261001110000_website_v4_media_provenance_and_documents.sql`. It was **renumbered** from `20261001100000`: the integration branch added `20261001100000_whatsapp_connection_calling.sql` with the same version, and Supabase keys migrations by that version. It is idempotent.
2. Set `GEMINI_API_KEY` on the API and worker. `IMAGE_PROVIDER=gemini` is the default. Set `GEMINI_IMAGE_MODEL` to Google's current image model; the default is `gemini-3.1-flash-image`, and the verifier confirms it exists. Optionally set `GEMINI_DOCUMENT_MODEL`.
3. Deploy the worker with the new job type `interview.read_document`.
4. Remove any `XAI_API_KEY` / `AI_PROVIDER=grok` settings; they are no longer read.
5. Run `gemini_verify_v4.py` (top of this file) and the screenshots, and look at the pictures. Only then set the four flags.

## 8. VERIFICATION

What was **executed**, on the merged branch head against local Postgres 16 with all 90 migrations applied fresh:
- **Full API + worker suite:** 1335 passed, 0 failed, under `pytest -n 8`. (Two further full runs were in progress at the time of this commit; their results follow in the next commit.)
- **Parallel flakes, root cause:**
  - Five test modules (`test_website_publish`, `test_marketplace_*` ×4) drained the async-job queue **unscoped**. Under `pytest -n` every worker shares one database, so they could claim another test's `website.generate` or `interview.read_document` job and run it in a process without that test's stubs. That produced "every draw failed" and "document superseded", exactly the two flakes.
  - `claim_job_batch` / `poll_and_execute_jobs` now take an optional `business_id` (test isolation, like the existing `job_type`; production omits it), and each drain is scoped to its own business.
  - A regression test (`test_a_business_scoped_claim_never_takes_another_business_job`) guards it.
- **Date flakes, root cause:** `test_khata` / `test_invoicing_gst` compared against `date.today()` (container UTC) while the app dates in Asia/Kolkata (`local_today()`); from 18:30 to 24:00 UTC they differ by a day. The tests now use `local_today()`. With `faketime`: failing before at 21:00 UTC, 42/42 passing after at 21:00 and 23:50 UTC and on the real clock. No app code changed.
- **Static checks:** ruff clean; mypy clean (592 files); web, Workspace and contracts `tsc` + ESLint clean.
- **Browser (headless Chromium, local stack):**
  - `tools/acceptance/flows.mjs`: **13/13** at desktop and **13/13** at phone size (talk-first, category-first, voice, Tamil, property, portfolio, industrial, model-down, "build it", refine, corrections, voice then typing, talk-to-edit).
  - Editor picture buttons: **9/9** (stand-in pixels).
- **Verifier harness** (`gemini_verify_v4.py --self-test`): five owner flows, 11/11 hero checks each, manual controls 7/7, upload wins. Flags correctly **NO**.

**Not run:**
- real Gemini (text, image, document, voice);
- real Supabase Storage;
- the browser upload path (needs Storage signed URLs).

## 9. OPEN ITEMS

- The real-Gemini activation run (top of this file). It is the only blocker.
- Stories without Gemini: offer the story question before the build checkpoint for trades whose golden sample leans on story (home food, gym).
- The model-down reader (Gemini unreachable) is improved but still coarse. For example, a developer's projects said in a sentence are not itemised; with Gemini the reading does this.
- Removing a picture in the editor does not mark that slot "removed" in the Blueprint's MediaPlan. A later full rebuild could draw that slot again; owner-edited sections are kept by the merge.

## 10. SAFE TO INTEGRATE

**NO: not yet.** The code for every item is in place and green locally. The three Gemini verifications cannot run without `GEMINI_API_KEY`, and this check was defined to be set only after them. With a key, one command (top of this file) produces the evidence and the flags. Do not merge automatically.
