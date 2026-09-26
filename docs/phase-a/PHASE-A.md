# Phase A — Create Business, Talk to LOCAH, the first website

Status: implemented on `main` (2026-09-27). This is the one current description
of Phase A. Where the older specification documents disagree, the amendment at
the end records what was built and why; the documents themselves were not
rewritten.

## The experience

Create Business → **Talk to LOCAH** (type, talk, or pick a kind first — none is
a gate) → LOCAH reads each answer, says back what it understood, asks a few
expert follow-ups → "I've got enough to make a strong first version"
→ confirmation → **Build my website** → the website, with the same
conversation beside it to keep changing it.

## Where things live

| Concern | Code |
|---|---|
| Start a Business to talk about (reuses an untouched draft) | `POST /v1/platform/businesses/start` · `services/business.py: start_conversation, adopt_name` |
| One interview for text and voice | `interview/orchestrator.py` (turn, `via`), `services/business_interview.py` |
| Reading answers by type (actions, hours, phone, place, offers, name) | `interview/reader.py` |
| What matters for THIS business, readiness, question budget | `interview/coverage.py` (monotonic `ready_at`) |
| The next question, wording, summaries, checkpoint | `interview/planner.py`, `interview/playbooks.py` |
| Kind of business: search, inference, correction | `catalog/taxonomy.py`, `orchestrator._update_category`, `corrections.py` |
| Typed side panel + read-back | `interview/understanding.py` |
| Design dimensions → 10 families → variant/palette | `interview/design_system.py`, `creative_director.py` (v3) |
| Truth rule for pictures | `interview/media_director.py: may_draw, plan_slots` |
| Semantic validator (meaning vs nav/CTA/titles/media) | `interview/semantic_design.py` (runs in every composition) |
| Distinctness | `interview/distinctness.py` |
| Editing by talking after build | `interview/website_edits.py`, `BusinessInterviewService.talk_to_website` |
| Renderer tokens for families | `packages/ui/src/site-families.css`, `components/website/WebsitePageView.tsx` |
| UI | `apps/web/src/app/start/**` |

## Zero AI spend in development

`LOCAH_TEST_NO_EXTERNAL_AI=1` refuses every Gemini/xAI/OpenAI/Anthropic text,
image and voice call before it leaves the process (and at the HTTP transport).
Tests enable it globally. Local acceptance uses `AI_PROVIDER=replay` and
`VOICE_PROVIDER=replay` (the latter only works while the kill switch is on).

## Evidence you can re-run

- Interview evaluation: `uv run python -c "from platform_testing.interview_eval import main; main()"` → `docs/phase-a/interview-transcripts/` (23 owners × scripted model / model down).
- Website fixtures: `uv run python -m platform_testing.website_fixtures <dir>`; screenshots `LOCAH_SITE_LAB_DIR=<dir> node tools/acceptance/sites.mjs <out>`.
- Browser flows A–M on a local stack: `tools/acceptance/README.md`.

## Amendment (2026-09-27) — where the older documents are superseded

1. **Questionnaire vs conversation (Docs 09–12, BUILD-SPEC §4).** Onboarding is
   a coverage-driven conversation with a question budget (≈3–6 simple, 5–8
   typical, 6–10 complex), not a fixed questionnaire. Photos, logo, prices and
   hours are enrichment offered after "enough for a first version".
2. **Pre-ticked tools (Capability Universe §21).** Recommended tools are never
   pre-approved and never block the first website. "Looks good" records
   approval; activation still follows entitlements at build; configuration is
   later, in the Workspace.
3. **Create Business form.** A name is no longer required before talking. The
   draft's placeholder address follows the real name once said.
4. **Template choice.** Owners are not shown templates. The look is decided
   from the business's dimensions; the model may only choose among families
   the evidence supports.
5. **Draft visuals.** Named dishes, projects, portfolio work and property are
   never drawn (truth rule), narrower than the earlier media plan.

## Known repository notes

- `.gitignore`'s `build/` rule also ignores `docs/build/`, so
  `LOCAH-BUILD-SPEC.md` and `EXECUTION-PLAN.md` are not in git (left as is).
- The marketplace groups 26 categories; the taxonomy has 32 + Other.
