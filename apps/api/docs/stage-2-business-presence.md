# Stage 2 — Business Presence

Modules: `core-website`, `core-workspace` · Doc 08 §6.1 · Doc 11 §17.2 · Doc 12 §11–§12

## Scope verification (pre-implementation)

**Confirmed:** `core-website` and `core-workspace` are Platform Core groups, not optional modules.

> Doc 08 §6.1: Every Business receives these 10 Core capability groups… Website/Public Presence `core-website` · Workspace Foundation `core-workspace`. “These are not optional installable modules…”

> Doc 08 §6.4: Every Business receives `core-website`.

> Doc 11 §17.2 Exit: a new Business receives a useful draft early; draft is editable and publishable; Website renders without arbitrary code; AI failure does not block manual/deterministic completion.

> Doc 12 §11.1 / §12.1: structured Website model; `website.generate` async job; deterministic fallback always produces a valid draft; never block Business creation because AI failed.

Website is provisioned automatically at Business creation (same transaction as BusinessProfile), and a `website.generate` job is enqueued without awaiting AI.

---

## APIs

| Method | Path | Permission |
|--------|------|------------|
| POST | `/v1/b/{business_id}/website/generate` | `website.edit` |
| GET | `/v1/b/{business_id}/website` | `website.read` |
| PATCH | `/v1/b/{business_id}/website/pages/{page_id}` | `website.edit` |
| PATCH | `/v1/b/{business_id}/website/sections/{section_id}` | `website.edit` |
| PATCH | `/v1/b/{business_id}/website/theme` | `website.edit` |
| GET | `/v1/b/{business_id}/website/preview-token` | `website.read` |
| POST | `/v1/b/{business_id}/website/publish` | `website.publish` |
| GET | `/v1/public/websites/{slug}` | public |
| GET | `/v1/public/websites/{slug}/pages/{page_slug}` | public |

Public UI: `apps/web` `/{slug}` and `/{slug}/{pageSlug}` (published or preview token).

Workspace UI: `apps/workspace` `/b/{businessId}` CORE-001–007.

## Events

`website.draft_generated`, `website.published`, `website.generation_failed`

## Tests

- `apps/api/tests/test_website_kernel.py`
- `apps/api/tests/test_website_generation.py`
- `apps/api/tests/test_website_publish.py`

---

# Stage 2 Engineering Report

## 1. Executive Summary

Stage 2 implements **Business Presence**: structured Website domain (already migrated), AI-assisted generation with mandatory deterministic fallback, draft editing, preview tokens, publish lifecycle, Workspace CORE-001–007 shells, and public `/{slug}` rendering. Finance/Accounting was not created. Frozen kernels were reused, not duplicated.

## 2. Implemented Components

| Component | Role |
|-----------|------|
| ORM models | Website, WebsiteVersion, WebsitePage, WebsiteSection, WebsiteSectionType, WebsiteGenerationJob |
| `WebsiteService` | Provision shell, aggregate load, replace draft from generation |
| `PageService` / `SectionService` / `WebsiteVersionService` | Draft editing |
| `WebsiteGenerationService` | Enqueue + execute `website.generate` with AI→fallback |
| `WebsitePublishService` | Preview JWT (10 min), publish copy, public load |
| `AIModelProvider` + `UnavailableAIProvider` | Doc 12 §12.2 abstraction; FL-DEC-015 unresolved |
| `fallback_generator` | Always-valid draft by business type |
| `AsyncJobService` | Enqueue into `platform_async_jobs` |
| Worker handler | `website.generate` in `job_runner` |
| Routers | `v1_website`, `v1_public_websites` |
| Workspace UI | CORE-001–007 under `/b/{businessId}` |
| Web UI | Public section renderer at `/{slug}` |

## 3. Database Changes

Existing migration (no redesign): `infra/supabase/migrations/20260713100000_stage2_business_presence.sql`

Tables per Doc 12 §11.1 / §12.4. Section types seeded in `infra/supabase/seed/00_platform.sql`.

## 4. Domain Models

Exactly: Website, WebsiteVersion, Page (`website_pages`), Section, SectionType, WebsiteGenerationJob. Theme and navigation remain JSONB on WebsiteVersion (Doc 12 §11.1).

## 5. Services

Focused services listed above. Orders/Payments/etc. untouched. Generation never blocks `create_business`.

## 6. APIs

Doc 12 `/v1/b/{business_id}/website/*` paths implemented. Public read via `/v1/public/websites/{slug}` for apps/web SSR/ISR.

## 7. Authorization Integration

`website.read`, `website.edit`, `website.publish` via existing Authorization Engine / `require_business_actor`.

## 8. Audit Integration

`website.draft_generated`, `website.content_edited`, `website.published`, `website.generation_failed` (fallback path).

## 9. Outbox Integration

Same event types registered in worker `KNOWN_HANDLERS`. ISR revalidation hook deferred to event consumer side-effect (tag `website:{slug}` prepared in apps/web).

## 10. Resolver Design

`WebsiteResolver` — business-scoped website/draft/page/section lookup + serialization.

## 11. Validation Rules

- Section content vs SectionType schema
- No HTML/JS; no permanent external `http(s)` URLs (Doc 12 §12.5)
- Publish readiness: home + visible hero headline + profile present
- Concurrent generation rejected (`pending`/`running`)

## 12. Performance

Indexes from existing migration. Public pages use ISR `revalidate=60` + tag; preview `no-store`.

## 13. Testing Summary

Kernel CRUD/isolation/audit; generation fallback always valid; publish + preview expiry + `website.published` outbox.

## 14. Files Created

See git status — core website package, services, routers, tests, workspace CORE pages, web public renderer, this report.

## 15. Files Modified

- `python/core/platform_core/models.py`
- `python/core/platform_core/services/business.py` (provision + enqueue)
- `apps/api/src/platform_api/main.py`
- `apps/worker/.../job_runner.py`, `outbox_consumer.py`
- `packages/validation/src/index.ts`
- `.env.example`

## 16. Architectural Compliance

- Reused Business, Profile, Location, Authorization, Entitlement, Outbox, Audit, Worker
- No new queue mechanism
- No Finance/Accounting module
- No arbitrary HTML/theme CSS injection
- No marketplace indexing (Stage 3)
- Live AI provider not wired (FL-DEC-015; Doc 11 §26.2 permits deterministic fallback)

## 17. Implementation Decisions

| Decision | Citation |
|----------|----------|
| Auto-provision Website + enqueue generation at create | Doc 08 §6.4, Doc 12 §12.1 |
| Default AI = UnavailableAIProvider + fallback | Doc 11 §26.2 FL-DEC-015 |
| API under `/v1/b/.../website` | Doc 12 website routes |
| Theme/nav as JSONB on version | Doc 12 §11.1 |
| Preview JWT 10 minutes | Doc 12 §11.6 |
| Publish copies draft → new published version | Doc 12 §11.5 |

**Note:** Stage 1 already records Platform Core IDs (including `core-website`) in `BusinessModuleState` for entitlement continuity. Doc 08 says Core is not optional modules; changing that registry pattern is frozen Stage 1 scope and was not redesigned here.

## 18. Future Dependencies

- FL-DEC-015 live Gemini/OpenAI provider
- Async ISR revalidation handler on `website.published`
- Custom domain DNS automation (explicitly out of scope)
- Memberships/Leads module-contributed sections at render time
- Rich media upload UX beyond Brand placeholder

## 19. Risks

| Risk | Mitigation |
|------|------------|
| AI unavailable | Deterministic fallback always writes draft |
| Draft version accumulation | Latest draft by `created_at`; publish copies snapshot |
| Public leak of drafts | Public route requires published status unless preview token |

## 20. Verification Checklist

- [x] Scope: core-website / core-workspace Platform Core
- [x] Website auto-provisioned at Business creation
- [x] Generation job + fallback
- [x] Edit / preview / publish
- [x] Workspace CORE-001–007 shells
- [x] Public `/{slug}` renderer
- [x] No Finance/Accounting
- [x] No marketplace indexing

## 21. Integration Matrix

| System | Integration |
|--------|-------------|
| Business create | Provision website + enqueue `website.generate` |
| BusinessProfile | Publish readiness + generation context |
| Worker async jobs | `website.generate` |
| Outbox | draft_generated / published / generation_failed |
| Authorization | website.* permissions |
| apps/workspace | CORE pages |
| apps/web | Public SSR/ISR |

## 22. Scope Verification

**In scope (Doc 11 §17.2):** structured Website, AI+fallback generation, editing, preview/publish, Workspace shell/Home.

**Out of scope (not implemented):** Marketplace search (Stage 3), Memberships/Leads/Fulfilment/Workforce, custom domain automation, arbitrary custom code, multi-language website content, AI employee autonomy, Finance & Accounting.
