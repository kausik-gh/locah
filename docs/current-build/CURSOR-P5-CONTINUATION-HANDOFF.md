# CURSOR P5 CONTINUATION HANDOFF

Projects, job cards, and academics. Continued from the Codex checkpoint. Not rebuilt.

BRANCH
parallel/codex-projects-jobs-academics

WORKTREE
C:\Users\KausikGH\.codex\worktrees\projects-jobs-academics\Locah

HEAD SHA
The tip is the commit that adds this file. Read it with `git rev-parse HEAD` on this branch. Product work ends at 73343cd24c51ecbe475d3d456bef08047c60891b.

CODEX CHECKPOINT SHA
38aee4a1f1e18b683f80c079a1b0655c0008c239

MAIN BASE SHA
1cb02e1449815ecf365a976d1694c9bd6681b2c2

COMMITS
- 38aee4a1f1e18b683f80c079a1b0655c0008c239 wip(p5): checkpoint codex projects jobs academics
- 7e6e1e0c9e049c319b9fb38fab8aa715dcac3095 fix(p5): harden codex projects jobs academics
- 58a7b3ae6ad4a2391e19a1d45a0987ad55a8d0d6 chore(integration): wire projects jobs academics
- 73343cd24c51ecbe475d3d456bef08047c60891b test(p5): verify jobs academics on local postgres
- docs commit that adds this handoff

MIGRATIONS
No new migration. Codex migrations were replayed as written:

- 20260930150000_p5_project_milestones.sql
- 20260930151000_p5_job_cards.sql
- 20260930152000_p5_academics.sql

Replay context: disposable Postgres 127.0.0.1:54330, database locah_p5_replay, user postgres, trust. Bootstrap infra/deploy/ci-bootstrap.sql, then every infra/supabase/migrations/*.sql in this worktree sorted by name (77 files), then infra/supabase/seed/00_platform.sql. Exit 0. This worktree does not contain supply, growth, kitchen, or dispatch migrations, and those were not mixed in. Hosted Supabase was not written.

PROJECTS IMPLEMENTED
The existing project remains the commercial and coordination record: customer, shared stage track, milestones on project phases, responsible person, related job cards. A project page can start a job card for that customer and project. Money stays in invoicing. No second stage engine.

JOBS IMPLEMENTED
Distinct job card: business, customer, location, optional project, title, problem, work performed, priority, schedule, assignee, status, parts. Lifecycle is server-validated: new, assigned, inspecting, awaiting_approval, approved, in_progress, waiting_parts, quality_check, completed, cancelled. Completed and cancelled are terminal. Completion requires work performed. Parts are consumed only from in_progress, waiting_parts, or quality_check, through StockService.consume_for_job. Provenance stays on jobs_parts (item, quantity, inventory movement, idempotency key).

ACADEMICS IMPLEMENTED
Courses, batches, class sessions, enrolments, assessments, results, announcements, and My Academics for the signed-in guardian or adult student. Fees, instalments, and attendance are not stored here. A session id is an occurrence Attendance can reference later.

WHAT CODEX HAD ALREADY BUILT
Schema, models, services, API routers, workspace list/detail pages, job transitions, part idempotency, project-to-job listing, academics portal function, permissions, and events. About 2,203 lines at 38aee4a. Focused unit tests had passed before this continuation. The modules could not be switched on (built was false), the workspace had no nav entries, technician and teacher roles were empty and not offerable, a class with no room crashed, and a project could list jobs but not start one.

WHAT CURSOR FIXED/FINISHED
- Typed the session clash query so a missing room or teacher is a real null, not an untyped parameter.
- Allowed jobs.read, jobs.complete, jobs.use_parts, academics.read, and academics.teach on assignment-scoped custom roles. Left inventory.read off that allowlist, so a custom assignment role still cannot open the stock book.
- Gave the built-in technician job read, complete, and parts, plus inventory.read so they can pick a part. Gave the teacher academics.read and academics.teach only. Both roles are offerable in the workspace when their module is on.
- Marked jobs and academics built, entitled as before, and added them to the workspace nav.
- Project page starts a linked job card without copying the project into the job. source_type stays manual, so more than one job can sit on one project.
- Local database test and a Desktop Chrome path.

PARTIAL
- Technician stock view is the existing inventory read, not a van-only slice. Van stock is still later inventory work.
- The staff batch page lists the assessment title and maximum. The mark and teacher note are stored and shown on My Academics. The staff page does not repeat the mark.
- Browser consumption uses a fresh idempotency key per submit. Replay of the same key was proved in the database test, not by clicking twice in the browser.

ACTIVATION_REQUIRED
Turn on projects, jobs, and academics for a business. Jobs needs inventory when parts are recorded. Academics needs offerings-catalog. Assign technician or teacher with location_ids empty (assignment scope). A manager still needs at least one location.

DATABASE TEST RESULTS
Disposable locah_p5_replay. No skips.

pytest tests/test_p5_operations.py tests/test_p5_domain_guards.py tests/test_permissions.py tests/test_roles_and_scope.py tests/test_projects.py

39 passed, 0 failed, 0 skipped.

The operations test covers milestone create, project-to-job link, illegal job completion, assigned worker access, unrelated worker denied, manager list, stock 20 then consume 3 then replay then consume 2, cross-business job read, course, batch, enrol, session, result, guardian portal, and platform_api RLS.

RLS RESULTS
Under role platform_api: business B sees 0 of business A's jobs and 0 courses. Business A with app.current_assignee set to the assigned technician sees that one job. API: the other technician gets 403 on the job and does not see it in the list. A stranger business cannot read the job.

INVENTORY IDEMPOTENCY RESULT
Database test: on hand 20, consume 3 with key bolt-1, on hand 17, same key returns the same jobs_parts row and stays 17, then key bolt-2 quantity 2 leaves 15. Jobs call StockService.consume_for_job. They do not update inventory tables.

Browser: one "Record part used" of 3 moved 20 to 17. Completing the job left it at 17.

GUARDIAN PRIVACY RESULT
Database test: guardian portal returns only Asha and marks 16. An unrelated identity gets an empty portal. The same guardian against the other business gets an empty portal. A teacher cannot enrol. Another teacher cannot read the first teacher's sessions (403).

Browser, 390px My Academics: Asha, Foundation Mathematics, Morning 2026, class on 2 Oct 2026, September check 16 / 20, note Steady. Bharat is enrolled in the same batch and is not on that page.

PLAYWRIGHT RESULT
Desktop Chrome via playwright-core, local mock auth 127.0.0.1:54322, API 127.0.0.1:8010, workspace 127.0.0.1:3101, database locah_p5_replay. Script tools/acceptance/phase_b/p5_projects_jobs_academics.mjs. 12 passed, 0 failed.

- Create project Shop refit for Ravi site
- Add milestone Payment milestone
- Start job card Fit the shutter; project lists it; job links back to the project
- Assign Arun, move to work under way, record 3 shutter bolts, quality check, complete
- Stock 17 after the one consumption and still 17 after completion
- Course Foundation Mathematics, batch Morning 2026, enrol Asha with guardian and Bharat without, schedule Quadratic equations, save September check
- Guardian portal as above

A resource 404 from the browser probing the page, and a dev hydration warning about an extra style attribute on an input, were ignored. They are not application failures.

PERMISSIONS
Python and TypeScript identifiers were already aligned at the checkpoint (jobs.read/create/assign/complete/use_parts, academics.read/manage/teach). test_permissions passed.

Owner holds the full set. Manager gains the job and academic operational permissions. Technician: jobs.read, jobs.complete, jobs.use_parts, inventory.read, plus business/location/notification read. Not jobs.create or jobs.assign. Teacher: academics.read, academics.teach. Not academics.manage, not customers.read, not fees. Custom assignment roles may hold the job and teach permissions listed above, and still may not hold inventory.read.

EVENTS
Catalogue entries from the checkpoint were kept. No new event types. Existing names include job.created, job.assigned, job.status.changed, job.part.consumed, job.completed, academics.course.created, academics.batch.created, academics.session.scheduled, academics.student.enrolled, academics.assessment.created, academics.result.recorded, academics.announcement.created. Handlers were not given a new event per row change.

SHARED FILES TOUCHED
- python/core/platform_core/services/academics.py
- python/core/platform_core/authorization/assignment_scope.py
- python/core/platform_core/services/roles.py
- python/core/platform_core/authorization/role_templates.py
- python/core/platform_core/authorization/permission_registry.py
- python/core/platform_core/catalog/modules.py
- apps/workspace/src/lib/workspace-nav.ts
- apps/workspace/src/app/b/[businessId]/projects/[projectId]/page.tsx

Not changed in this continuation: main.py, permissions.py, identifiers.ts, events/catalogue.py, models.py, stock/service.py. Those were already in the Codex checkpoint.

CLAUDE INTEGRATION REQUIRED
Cherry-pick or merge this branch onto the integration line. The wiring commit 58a7b3ae6ad4a2391e19a1d45a0987ad55a8d0d6 is the shared-file slice: module built flags, nav, role templates, permission labels. The fix commit touches assignment_scope.py and roles.py. Do not renumber the three P5 migrations. Do not treat job cards as projects, and do not move fees or attendance into academics.

KNOWN LIMITATIONS
- No van or mobile stock location. The technician template can read business stock in order to pick a part.
- Staff batch page does not list entered marks; the guardian portal does.
- Photos on a job card are not a separate upload flow.
- Workspace shell, stage engine, memberships, and localization were left alone.

KNOWN MERGE RISKS
role_templates.py, assignment_scope.py, catalog/modules.py, permission_registry.py, roles.py, and workspace-nav.ts are shared with other lanes. Memberships must not grow a second enrolment or fee copy inside academics. Supply, growth, queue, kitchen, and dispatch were not merged into this branch.

READY_TO_INTEGRATE = YES
