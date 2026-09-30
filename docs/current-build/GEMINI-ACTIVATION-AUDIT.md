============================================================
LOCAH GEMINI ACTIVATION AUDIT
============================================================

Date: 2026-09-30 (IST). Machine: founder's Mac, local stack only.
No hosted Supabase, no Railway, no main, no active Claude branch was touched.

AUDIT BRANCH:
cursor/gemini-activation-audit (worktree `../locah-gemini-audit`; this file is
its only commit; upstream deliberately unset so it can never push to the
Website branch by accident)

BASE WEBSITE-V4 HEAD:
origin/claude/compassionate-allen-hlpq6p = f2c6353a7ede027eb01350cb5eac97c69b03aff3

OBSERVED FINAL-RELEASE HEAD:
origin/claude/final-release-candidate = 42ff0e9c5a243802658972d3dcb07962d1b20cdd
At push time final-release had advanced to 8c90aeb (demo seed, a refunds fix,
AI-employee runtime); none of those commits touches a file audited here, and
Website-v4 is not yet merged into it.
(also observed: main 9c21d46, claude/phase-b-final-integration a2047cb — unchanged
throughout)

------------------------------------------------------------
GOOGLE MODEL ACCESS
------------------------------------------------------------

`GET /v1beta/models` with the local key: HTTP 200, 61 models.

gemini-3.8-flash:        VISIBLE (text default — used, works)
gemini-3.5-flash:        VISIBLE (fallback)
gemini-3.1-flash-lite:   VISIBLE (fallback)
gemini-3.1-flash-image:  VISIBLE (image default — used, works)
gemini-3-pro-image:      VISIBLE (A/B only)
gemini-3.8-live:         VISIBLE (voice default in interview/voice.py; not exercised)

The local key is 53 characters, not the classic `AIza…` shape; it is valid
(newer Google key format). Its value was never printed.

------------------------------------------------------------
LOCAL ENVIRONMENT
------------------------------------------------------------

GEMINI_API_KEY:              PRESENT (repo-root .env; same fingerprint in
                             apps/web/.env, apps/workspace/.env, apps/admin/.env)
AI_PROVIDER:                 gemini (.env)
IMAGE_PROVIDER:              NOT SET → code default gemini
VOICE_PROVIDER:              NOT SET → code default gemini
GEMINI_*_MODEL overrides:    NOT SET → code defaults (above)
LOCAH_TEST_NO_EXTERNAL_AI:   NOT SET in .env / shell. ENABLED (=1) by the pytest
                             session (platform_testing.ai_guard) and by the local
                             acceptance launchers tools/acceptance/stack/api.sh and
                             worker.sh — correct: ordinary tests cannot spend.
AUTO_GENERATE_WEBSITE_IMAGES: NOT SET (correct — see NORMAL OWNER WEBSITE PATH)

Local hygiene (files are git-ignored, nothing committed):
- `apps/web/.env` and `apps/workspace/.env` hold server secrets
  (GEMINI_API_KEY, SUPABASE_SERVICE_ROLE_KEY, DATABASE_URL). Next.js only ships
  NEXT_PUBLIC_* to the browser, so this is not a browser leak, but the frontends
  should not hold them. Remove them there.
- Local `DATABASE_URL`/`API_DATABASE_URL` point at the HOSTED Supabase project.
  Anything run with `.env` loaded writes to production. Every run in this audit
  used `uv run --no-env-file` and an explicit local DATABASE_URL.
- `XAI_API_KEY` is still in the local .env; Website-v4 no longer reads it.

------------------------------------------------------------
RAILWAY
------------------------------------------------------------

API GEMINI KEY:        NOT INSPECTABLE
WORKER GEMINI KEY:     NOT INSPECTABLE
API KILL SWITCH:       NOT INSPECTABLE
WORKER KILL SWITCH:    NOT INSPECTABLE
MODEL OVERRIDES:       NOT INSPECTABLE

No Railway CLI is installed on this machine and there is no Railway
credential here. Nothing was read, changed or deployed. See RAILWAY ACTION
REQUIRED for the exact matrix.

DO NOT PRINT SECRET VALUES — none were.

------------------------------------------------------------
LOCAH USAGE CAP
------------------------------------------------------------

model_tokens cap:
- Per business, per month, in `usage_meters.cap`. NULL = no cap. There is no
  plan default: a cap exists only when someone sets it (Settings › Usage, i.e.
  `PUT /v1/platform/businesses/{business_id}/usage/model_tokens/cap` with
  `{"cap": <int|null>}`, permission settings.update). A set cap carries forward
  to later months.
- `UsageMeterService.over_cap` is true only when a cap is set AND used ≥ cap.
  It is checked before the creative model call in
  `BusinessInterviewService._personalize_creative` (and the generic generator);
  over cap → deterministic direction and designed words (fallback_reason
  recorded on the job). It does not gate interview turns or document reading.
- Raise or clear it with the route above (cap null = unlimited). Do not bypass.

demo business over cap:
UNKNOWN — the demo business lives on hosted Supabase, which this audit does
not touch. Read-only check the founder can run in the Supabase SQL editor:
  select resource, period, used, cap from usage_meters
  where business_id = '<demo business id>' and resource = 'model_tokens'
  order by period desc limit 3;

------------------------------------------------------------
NORMAL OWNER WEBSITE PATH
------------------------------------------------------------

actual call chain (code-read and proven by runs below):

Business Interview (API) → Build → BusinessInterviewService.build():
  creative = template_preferences.source != "USER_STATEMENT"
  → direct() + plan_media() → compose_site() → immediate preview
  → job intake {"blueprint": …, "composer": "creative-v2"}
  → AsyncJobService.enqueue("website.generate")
worker: platform_worker.job_runner → job_type "website.generate"
  → WebsiteGenerationService.execute_job
  → is_interview_job(job) (the job carries the Blueprint) → personalize_job
  → composer == "creative-v2" → _personalize_creative()
  → over_cap check → Gemini creative plan (gemini-3.8-flash)
  → plan_media() → draw_missing() → Gemini images (gemini-3.1-flash-image)
  → MediaAsset rows (gemini_generated, draft, generated_for, job, media-v4.1)
  → compose final site → preview → Publish

The legacy AUTO_GENERATE_WEBSITE_IMAGES job (website_generation.py:697) sits
after the interview path has already returned, so it never runs for an
interview-built site. Setting it would not add pictures to v4 sites; it would
only affect the generic generator. Leave it unset.

creative-v2 reached:  YES (every site: composer creative-v2, creative_strategy "ai", fallback none)
MediaPlan:            YES (hero, story, category/item slots; truth classes respected)
draw_missing:         YES (media_drawn 2–5 per site, media_failed 0)

Worker proof: one extra owner flow (meat shop) built with jobs NOT inert, so
Build enqueued a real `website.generate` async job; the worker's own session
factory (`create_worker_session_factory(role="service")`) and dispatcher
(`poll_and_execute_jobs`, exactly what `platform_worker.main` loops on) claimed
and completed it in one round: async job completed / last_error none;
generation job completed, attempt 1, creative-v2, ai, gemini-3.8-flash,
media_drawn 5, media_failed 0; 5 MediaAssets gemini_generated / draft /
media-v4.1 (hero, category:chicken, category:mutton, category:fish-seafood,
story). This is the worker code path, run locally with storage redirected to
disk — not a deployed Railway worker process.

------------------------------------------------------------
REAL GEMINI TEXT
------------------------------------------------------------

PASS

model: gemini-3.8-flash (GeminiProvider.generate_structured, purpose website)
latency: ~3.0 s; structured JSON parsed; usage logged (prompt/output/thinking units)
error: none (after top-up — see ROOT CAUSE)
The verifier's five real conversations: 36 interview turns, fallback_reason null on all.

------------------------------------------------------------
REAL GEMINI IMAGE
------------------------------------------------------------

PASS

model:   gemini-3.1-flash-image
mime:    image/jpeg
bytes:   860,973 (smoke hero, 1376×768, 12.8 s); 19 images in the verifier run,
         5 in the worker proof, 4 in the A/B
error:   none

------------------------------------------------------------
REAL GEMINI DOCUMENT EXTRACTION
------------------------------------------------------------

PASS (with a caveat and a verifier defect)

- Legible menu PDF (36 px text) through `interview.documents.read`: kind menu,
  2 groups, 4 items — every name, price (e.g. "Rs 900") and unit exact, all
  confidence high. Nothing invented.
- The verifier's menu (tiny default bitmap font): 5 of 7 prices returned, each
  exactly as printed; 2 prices dropped (empty — never invented). The verifier
  still reports MENU_PDF_REAL_GEMINI = NO because of its own check (defect B2).
- Caveat: on a near-unreadable test print the reading is not stable between
  runs — one run dropped all prices, another misread one (printed 900 → read
  800). Every extracted line still waits for the owner's confirmation before it
  is used, which is the safety net; see B6.

------------------------------------------------------------
NO-IMAGE OWNER FLOW
------------------------------------------------------------

PASS

Five owners (home food, gym, real estate, meat shop, industrial B2B) uploaded
nothing and built: every hero has a real Gemini picture, 11/11 hero checks each
(persisted MediaAsset, MediaPlan hero slot, preview, publish, gemini_generated /
draft, provenance slot+job+prompt, approvable, replaceable, removable).

images planned / generated per site: home food 3, gym 2, real estate 2
(hero + story only — no generated project gallery), meat shop 5, industrial 2;
worker proof 5. Total draft pictures: 19.

Public pages (published, 1440 and 390, screenshots in
`acceptance-out/gemini-heroes/` on this machine): all six heroes render the
Gemini picture (12/12 loaded), alt text "Illustrative picture: …". The real
estate hero is "a calm, bright, welcoming interior" — mood, not the project.

------------------------------------------------------------
MANUAL GENERATION
------------------------------------------------------------

Hero:        PASS (real Gemini) — Generate a picture
Regenerate:  PASS — Generate a new picture, and the new picture is shown
Keep:        PASS
Remove:      PASS
Upload:      PASS through the API (owner photo replaces the draft; an owner's
             uploaded hero wins over generation — UPLOAD_WINS = YES).
             NOT verified: the browser upload widget, which needs a real
             Supabase Storage signed-upload URL (not configured locally).
Card:        PASS — a product card picture generated on its own

------------------------------------------------------------
STORAGE
------------------------------------------------------------

local only (`--local-storage`): the real Gemini bytes were written to disk and
served locally. Supabase Storage persistence, buckets and signed uploads were
NOT verified (no Storage project for local runs; hosted not touched).

------------------------------------------------------------
IMAGE MODEL QUALITY CHECK
------------------------------------------------------------

Same CreativeDirector prompts (captured from the worker-proof meat shop), one
generation per model, through LOCAH's generate_image. 1200×896 both.

gemini-3.1-flash-image (~11 s):
- Hero: curry-cut mutton, chicken pieces, red snapper, prawns, squid — exactly
  "chicken, mutton, fish & seafood", specific to an Indian meat shop. Drifts
  from the studio brief (room with brick wall, window).
- Card: the three asked-for items (curry cut, boneless, wings), raw and fresh.

gemini-3-pro-image (~20 s):
- Hero: more polished studio catalogue look, closer to the lighting / charcoal /
  red-accent brief — but no shellfish, and steak-like cuts that read "Western
  steakhouse" rather than an Indian mutton counter.
- Card: dramatic studio shot, but thighs and wings look marinated/glazed —
  wrong for a raw-meat shop; no clear curry cut.

recommended Railway override:
NONE. Keep the default gemini-3.1-flash-image. Pro trades subject accuracy for
studio polish at ~1.8× latency; for a business's own site, being right about
what the shop sells matters more. No artefacts or text in either model's four
images.

Quality note (not model-specific): the real gym hero shows a real equipment
brand's name ("ROGUE") on the rack and plates, although prompts forbid logos —
see B5.

------------------------------------------------------------
ROOT CAUSE
------------------------------------------------------------

OTHER — the only blocker in the Website Claude's run was that its Claude Cloud
container had no GEMINI_API_KEY (the network and the code were fine). On this
machine the key exists, is valid, sees every expected model, and the full
Website-v4 real-Gemini verification passes.

OTHER (resolved) — GOOGLE BILLING: during this audit Google began answering
HTTP 402 "Your prepayment credits are depleted" for every model (the project
behind the local key ran out of prepaid credit). The founder topped up; calls
succeed again. If Railway uses the same Google project, production Gemini was
refusing in that window too.

STORAGE_NOT_CONFIGURED — for deployed-storage verification only (local runs).

Not causes: AI_KILL_SWITCH (not set outside tests), LOCAH_USAGE_CAP (no cap by
default), MODEL_ACCESS (all visible), WRONG_GENERATION_PATH (creative-v2 path
proven), WORKER_NOT_RUNNING (worker dispatch proven locally). Railway key
placement: UNKNOWN (not inspectable).

------------------------------------------------------------
CODE FIXES
------------------------------------------------------------

Changes made on this branch: NONE (documentation only). Every affected file is
owned by the Website-v4 lane (changed there since a2047cb, untouched by
final-release), so these are recommended patches for the Website Claude /
final integrator (CASE B).

B1 python/core/platform_core/website/ai_provider.py — `GeminiProvider._post` /
   `_structured`. HTTP 402 (billing / prepay depleted) is not in the permanent
   set (400, 401, 403, 404, 429): it raises RuntimeError("gemini unavailable
   (402)"), every fallback model is tried (3 calls per request, all 402 — the
   fallbacks share the project's billing), and callers record only
   `fallback_reason: "RuntimeError"` (seen on every interview turn during the
   402 window). Patch: treat 402 as `AIProviderPermanentError` and `break` on
   `exc.status in (401, 402, 403)` like the credential case; make the message
   say billing. Test: a stubbed 402 → exactly one call, permanent error.
B2 tools/acceptance/stack/gemini_verify_v4.py — `read_menu_pdf`: (a) compares
   the returned price "Rs 40" with printed "40", so every correct price counts
   as invented — compare digits only; (b) expects "Idli Podi 200 g" as the name
   while LOCAH correctly returns the size as `unit` — match name (+unit);
   (c) draws with PIL's tiny default bitmap font — use
   `ImageFont.load_default(size=32)` so the test reads a realistic menu.
B3 tools/acceptance/stack/gemini_verify_v4.py — `main()` says "Re-publish with
   the Gemini hero back on" but `verify_hero` ends with the Remove check and
   nothing puts the hero back, so the published sites (and screenshots) show
   the no-picture state. Patch: PATCH the hero's original `image_asset_id`
   back before re-publishing.
B4 tools/acceptance/owner_sites.mjs — shoots ~1.5 s after load, before a
   ~700 KB hero paints (desktop showed the monogram/overlay placeholder); wait
   for the hero `<img>`/background image to load. Its contact-sheet caption is
   hard-coded "stand-in plates, not Gemini output" — derive it from the report.
B5 python/core/platform_core/website/media_prompts.py — negatives forbid text,
   logos, labels, signage, but not brand/manufacturer names; the real gym hero
   shows "ROGUE" on equipment. Add "no brand names, trademarks or manufacturer
   markings on equipment, products or clothing". (A generated picture that
   shows a real brand can read as an endorsement.)
B6 python/core/platform_core/interview/documents.py — optional hardening:
   image-only pages with very small print gave unstable prices across runs at
   "high" confidence. Consider asking for the printed price string verbatim per
   line and marking `low` when it is not a clean number, or flagging every line
   of an image-only document for price checking. Owner confirmation remains
   mandatory either way.
B7 python/core/platform_core/website/image_generation.py — small diagnostics:
   generated MediaAssets carry no width/height; the "empty image" log has no
   model; 401/404 map to the generic owner reason "error" (the log has the
   status code, so it stays diagnosable).

Diagnostics that already work (§38): no key (`website.image_generation.skipped
reason=no_image_provider_key`), kill switch (raises, never silent), HTTP
failures with status and Google's own message for text and image, quota vs
billing for images, fallback reason on the generation job, media_drawn /
media_failed, over-cap fallback reason.

------------------------------------------------------------
RAILWAY ACTION REQUIRED
------------------------------------------------------------

locah-api:
  GEMINI_API_KEY            (secret; must be a key of a project with credit)
  AI_PROVIDER=gemini
  IMAGE_PROVIDER=gemini
  VOICE_PROVIDER=gemini
  LOCAH_TEST_NO_EXTERNAL_AI must be ABSENT (or 0)
  optional, only to pin today's defaults explicitly:
  GEMINI_INTERVIEW_MODEL=gemini-3.8-flash
  GEMINI_WEBSITE_MODEL=gemini-3.8-flash
  GEMINI_DOCUMENT_MODEL=gemini-3.8-flash
  GEMINI_IMAGE_MODEL=gemini-3.1-flash-image
  GEMINI_FALLBACK_MODEL=gemini-3.5-flash,gemini-3.1-flash-lite
  SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY (Storage for pictures and uploads)

locah-worker (REQUIRED — it runs website.generate, interview.generate_logo,
interview.read_document):
  the same GEMINI_API_KEY, AI_PROVIDER, IMAGE_PROVIDER and model settings
  LOCAH_TEST_NO_EXTERNAL_AI ABSENT (or 0)
  SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY, DATABASE_URL

locah-web, locah-workspace:
  NO GEMINI_API_KEY, no SUPABASE_SERVICE_ROLE_KEY, nothing AI under NEXT_PUBLIC_*

Remove anywhere: AUTO_GENERATE_WEBSITE_IMAGES (not needed for v4),
XAI_API_KEY / XAI_* / AI_PROVIDER=grok|xai (no longer read after v4).
The xAI lines still in final-release's .env.example are expected to disappear
when Website-v4 is integrated.

Google side: keep prepaid credit on the project behind the production key (the
402 "prepayment credits are depleted" refusal stops every model at once).

------------------------------------------------------------
FLAGS
------------------------------------------------------------

REAL_GEMINI_TEXT_VERIFIED = YES
REAL_GEMINI_IMAGES_VERIFIED = YES
REAL_GEMINI_DOCUMENT_VERIFIED = YES
MANUAL_IMAGE_GENERATION_VERIFIED = YES   (browser upload widget: not verified — Storage)
NO_IMAGE_OWNER_FLOW_VERIFIED = YES
RAILWAY_API_AI_CONFIG_READY = UNKNOWN
RAILWAY_WORKER_AI_CONFIG_READY = UNKNOWN
CODE_BUG_FOUND = YES   (B1 product; B2–B4 verifier/harness; B5 prompt; none blocking)
CODE_FIX_COMMIT = NONE (all affected files are Website-v4-owned; patches recommended above)
SAFE_FOR_WEBSITE_CLAUDE_TO_CONSUME = YES

============================================================

How this was run (reproducible, local only):
- fresh local DB `locah_gemini` via tools/acceptance/stack/db.sh (all migrations
  through 20261001110000_website_v4_media_provenance_and_documents.sql);
- `gemini_verify_v4.py acceptance-out/gemini --local-storage` with the key injected
  into the process only, `uv run --no-env-file`, SUPABASE_* unset;
- one text / image / document call through GeminiProvider, image_generation and
  interview.documents; one owner flow through the worker dispatcher; the A/B;
- screenshots after putting each verifier site's own hero back through the editor
  API and publishing (the verifier's last check removes it — B3).
