# Website Creative System v4 — Handoff

Branch: `claude/compassionate-allen-hlpq6p` (not merged anywhere; `claude/phase-b-final-integration` untouched).
Audit and golden analysis: `docs/audits/website-builder-recovery-audit-v1.md`, `docs/audits/golden-reference-analysis-v1.md`.

| Checkpoint | Commit | What |
|---|---|---|
| 2A | `f0bbc09` | Pictures by default, MediaPlan before the design, truth classes, one shoot brief, owner-edits-win merge, Gemini only |
| 2B | `da89397` + `3c3d0d6` | Per-business page architecture, designed headlines without a model, colour words, story, one CTA decision, mobile strategy, v1 templates retired from the owner path |
| 2C | `963fbb5` | Menu / catalogue / PDF reading with owner confirmation; media provenance; draft approve/replace/remove in the editor |
| 2D | this commit | Real owner flow run for five businesses, fixes from it, screenshots, this handoff |

---

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

1. Apply migration `infra/supabase/migrations/20261001100000_website_v4_media_provenance_and_documents.sql`. It adds the provenance columns and the private `owner-documents` bucket with folder policies, and it is idempotent (applied twice locally).
2. Set `GEMINI_API_KEY` on the API and worker. Optionally set `GEMINI_DOCUMENT_MODEL` and `IMAGE_PROVIDER=gemini`.
3. Deploy the worker with the new job type `interview.read_document`.
4. Remove any `XAI_API_KEY` / `AI_PROVIDER=grok` settings; they are no longer read.
5. **Before calling this done, run one real Gemini pass** of `owner_flow_v4.py` without the image stubs, in a staging environment, and look at the pictures. That is the one thing this branch could not verify.

## 8. VERIFICATION

What was **executed** (local Postgres 16 with all migrations):
- **Full API + worker suite:** 1298 passed, 3 failed. The failures are `test_invoicing_gst` and `test_khata` ×2, all asserting a date one day off (IST/UTC day boundary when run after ~18:30 UTC). They are in code this branch does not touch, and the same class of failure was seen before v4.
- **Parallel-run flakes (xdist `-n 8`), each seen once and passing on rerun:**
  - `test_website_creative_v4::test_owner_changes…` (all draws reported failed);
  - `test_interview_documents::test_the_owner_attaches_a_menu…`.

  Both passed alone and in two further parallel runs. The cause is not yet found. Suspected shared module state between DB tests in one worker.
- **Static checks:** ruff clean; mypy clean (577 files); web and workspace `tsc` + ESLint clean.
- **Owner flow:** the five-business run and screenshots above.

**Not run:**
- real Gemini (text, image, document, voice);
- a real Supabase Storage upload of a document (only the mocked boundary is tested);
- the browser upload of a PDF in the interview UI (typechecked and linted, not clicked through).

## 9. OPEN ITEMS

- One real-Gemini acceptance pass (see §7.5).
- Stories without Gemini: offer the story question before the build checkpoint for trades whose golden sample leans on story (home food, gym).
- The model-down reader (Gemini unreachable) is improved but still coarse. For example, the home kitchen's prices said in a sentence are not itemised.
- Investigate the two parallel-run flakes.

## 10. SAFE TO INTEGRATE

**YES, behind activation.**

The code is complete for 2A–2D, and statically and behaviourally tested locally. With no `GEMINI_API_KEY` it degrades to the deterministic path shown in the screenshots, without breaking. Visual quality at the golden level depends on real Gemini pictures, which have not been observed; do the §7.5 pass before announcing it. Do not merge automatically: integrate into `claude/phase-b-final-integration` by the normal review.
