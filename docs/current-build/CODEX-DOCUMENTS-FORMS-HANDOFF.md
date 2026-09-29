# CODEX Documents / Forms / Signatures — Cursor handoff

## Branch and SHAs

| Field | Value |
| --- | --- |
| **BRANCH** | `parallel/codex-documents-forms` |
| **ORIGINAL BASE SHA** | `1cb02e1449815ecf365a976d1694c9bd6681b2c2` |
| **CODEX CHECKPOINT SHA** | `ee4c73f176d9f61228c7392fa400b87c5755a52b` (`wip(documents): preserve codex forms signatures implementation`) |
| **HEAD SHA** | _(see `git rev-parse HEAD` after final push)_ |

## CURSOR COMMITS

After checkpoint:

- `feat(documents): complete workspace and public forms flows`
- `test(documents): add browser acceptance script`
- `chore(integration): wire documents nav and permission copy`
- `docs: complete documents forms handoff`

## MIGRATION

- `infra/supabase/migrations/20260930240000_documents_forms.sql`
- **MIGRATION REPLAY RESULT**: Applied cleanly on disposable DB `locah_docs_scratch` @ `localhost:54329` (full migration chain + seed).

## WHAT CODEX IMPLEMENTED

- SQL schema: templates, versioned forms, requests (token hash), submissions, signatures, private `document_files` (bytea), expiring access links, activity log, RLS, immutability triggers, scoped token helper functions.
- `DocumentWorkflows` service: validation, version pinning, typed/drawn signatures, upload fulfilment, merchant file access tokens.
- `v1_documents.py`: merchant + public token routes; download router for expiring file access.
- Permissions identifiers + event catalogue entries.
- API router mounted in `main.py`.
- Postgres integration tests (`test_document_workflows_postgres.py`).
- Workspace server actions + `RequestComposer` / `TemplateComposer` (partial).

## WHAT CURSOR FINISHED / FIXED

### Document templates

- Workspace `TemplateComposer` wired on Documents page (templates tab).

### Forms

- `/b/{businessId}/forms` list, `/forms/new`, `/forms/{formId}` with `FormComposer` (version on edit).
- `list_forms` now returns `consent_text` and `guardian_required` for the current version.

### Form versioning

- Unchanged Codex semantics; UI saves new versions via `POST /forms/{id}/versions`.

### Submissions

- Documents page links to `GET /submissions/{id}` detail summary.

### Signatures

- Public panel: typed (name match) and drawn (canvas strokes) on customer link.

### Document requests

- Documents page: summary cards, recent/received/templates tabs, form + upload request composers.

### Private file access

- Merchant `FileAccessButton` → short-lived API download path (no permanent public URL).

### Immutability

- Preserved from Codex migration/tests; no API path to rewrite signed submissions.

### RLS

- Preserved; postgres tests confirm tenant isolation and token scoping.

### Permissions

- `documents.read`, `documents.manage`, `documents.request` (TS + Python).
- Permission words in `role_templates.py` for role editor copy.

### Events

- `document.created`, `document.requested`, `document.uploaded`, `form.submitted`, `document.signed`.

### API

- Audited `v1_documents.py`; no duplicate domain added.

### Workspace UI

- `documents/page.tsx`, forms routes, nav entries under Customers.

### Public customer UI

- `apps/web/src/app/document-request/[slug]/[token]/` with form + upload flows.

## DATABASE TEST RESULT

```
3 passed in test_document_workflows_postgres.py
(localhost:54329/locah_docs_scratch)
```

## STATIC CHECKS

| Check | Result |
| --- | --- |
| **RUFF** | Pass on `document_workflows.py`, `v1_documents.py` |
| **MYPY** | Not run (not part of standard gate for this packet) |
| **TSC workspace** | Pass after building `@platform/config`, `@platform/auth`, `@platform/contracts` |
| **TSC web** | Pass |
| **LINT workspace** | Pass (`next lint`) |
| **BUILD** | Not run (dev servers not required for this handoff) |

## PLAYWRIGHT / BROWSER RESULT

- Script added: `tools/acceptance/phase_b/p2_documents_forms.mjs`
- **Not executed** in this session: local API/Workspace/Web stack and `acceptance-out/session.json` were not running. Re-run with acceptance stack per `tools/acceptance/README.md`.

## CLAUDE INTEGRATION CONTRACTS

Stable hooks (no cross-module wiring in this branch):

- **Quotes**: accepted quote → agreement/signature request (`POST /v1/b/{id}/documents/requests`, `related_type=quote`).
- **Memberships**: plan/waiver → form request (`related_type=membership`).
- **Bookings**: intake/consent link (`related_type=booking`).
- **Jobs / Academics / Compliance / Supply**: use `related_type` + `related_id` on requests; no FK sprawl.
- **Messaging**: deliver `public_path` from create-request response (one-time link).

## SHARED FILES TOUCHED

- `apps/api/src/platform_api/main.py`
- `packages/permissions/src/identifiers.ts`
- `python/core/platform_core/permissions.py`
- `python/core/platform_core/events/catalogue.py`
- `apps/workspace/src/lib/workspace-nav.ts`
- `python/core/platform_core/authorization/role_templates.py`

## PARTIAL / ACTIVATION_REQUIRED

- WhatsApp send of request links (DC-05): link is created in Workspace; messaging module not wired here.
- PDF rendering of signed submissions through `DocumentStore`: not hooked (future immutable export).
- Browser acceptance: run locally before merge to main.

## KNOWN LIMITATIONS

- Only one signature field per form (service rule).
- File uploads capped at 5 MB, PDF/JPEG/PNG/WebP.
- Merchant download links expire in 5 minutes.

## KNOWN MERGE RISKS

- Nav + `role_templates.py` may conflict with parallel module branches.
- Module enablement: businesses need `documents` module active (entitlement + enable).

## READY_TO_INTEGRATE

**YES** — backend and postgres proofs pass; UI and public flows implemented. Run `p2_documents_forms.mjs` on the local acceptance stack before production promotion.
