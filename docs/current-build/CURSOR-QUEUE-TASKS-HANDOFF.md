# Cursor handoff — Queue, Tasks, Checklists

Branch: `parallel/cursor-queue-tasks` (from `origin/main`). Main was not updated.

This lane owns the walk-in queue and the one shared Tasks domain. It does not own Memberships, the stage engine, Orders, Payments, Projects, Jobs, Academics, Loyalty, or Marketing.

## What shipped

Walk-in queue (`queue-operations`):

- A lane is one queue at a location. It can name a provider, a department, and a bookable resource.
- A token is `waiting`, `called`, `serving`, `served`, or `missed`.
- Board columns are Waiting, Called, Serving, and Done/Missed.
- Actions: issue, call next, call one token, start serving, mark done, miss, and requeue when the lane allows it.
- Waiting order is priority, then arrival. If the lane has an average service time, the board shows an estimated wait.
- A booking joins the same lane by `booking_id` only. The booking row is not copied and no second booking is created. Issuing the same booking again returns the open token.
- `queue.turn_soon` is the Messaging contract (token, how many are ahead, customer, booking). The handler writes `queue_turn_notices` once per visit. Messaging internals were not changed.

Tasks (`tasks`):

- One table, `tasks_tasks`. A task points at a business, customer, project, job, booking, order, compliance item, location, or staff assignment through `related_type` / `related_id`.
- There is no ProjectTasks, JobTasks, or ComplianceTasks engine. Job ids are stored as references; the Jobs lane still owns job records.
- Checklist items live on the task. A required step must be done before the task can be completed. A step can require a photo (`proof_media_id`).
- Repeatable lists are templates. Spawning with the same occurrence key returns the same task.
- Views: My tasks, Due today, Overdue, Unassigned, Open, Completed.
- Events: `task.created`, `task.assigned`, `task.due`, `task.completed`. Handlers claim `tasks_handler_receipts` so a redelivery does not schedule or notify twice.

Assignment scope is still P2-01. Tasks use `assignee_member_id`. Queue lanes and tokens use `provider_id`. Both are in the existing ORM filter, the write guard, and the existing RLS helpers. This lane did not add a second scope system.

## Claude — compliance hook

Compliance reminders are unchanged. When the `tasks` module is on, this creates one open task per licence or filing date. Calling it again for the same date returns that task.

```python
from platform_core.tasks.compliance_hook import create_task_for_compliance_due

await create_task_for_compliance_due(
    session, business_id=step.business_id, item_id=step.entity_id,
)
```

Call it at the end of `remind` in `python/core/platform_core/events/subscribers/compliance_due.py`. The first step of the ladder creates the task. Later steps of the same due date return it. A new due date uses a new key.

The same contract is `POST /v1/platform/businesses/{id}/tasks/from-compliance` with `{ "item_id" }`.

## Messaging — your turn soon

Subscribe to `queue.turn_soon`. Payload:

- `entry_id`, `lane_id`, `location_id`, `token_number`, `ahead`, `visit_cycle`
- `customer_contact_id` and `booking_id` when the desk recorded them
- `channel_hint`: `whatsapp`

Do not read queue tables to decide the copy. One notice row already exists in `queue_turn_notices` for that visit (`entry_id`, `visit_cycle`).

## Routes

- `POST/GET /v1/platform/businesses/{id}/queue/lanes`
- `GET /v1/platform/businesses/{id}/queue/lanes/{lane_id}` — the board
- `POST /v1/platform/businesses/{id}/queue/entries`
- `POST /v1/platform/businesses/{id}/queue/lanes/{lane_id}/call-next`
- `POST /v1/platform/businesses/{id}/queue/entries/{entry_id}/{call|serve|complete|miss|requeue}`
- `GET/POST /v1/platform/businesses/{id}/tasks`
- `POST /v1/platform/businesses/{id}/tasks/{task_id}/assign|start|complete`
- checklist item add and check, templates, and spawn

Workspace: `/b/{id}/queue` and `/b/{id}/tasks`, linked from Sell & serve when the module is on.

Permissions: `queue.read`, `queue.operate`, `queue.configure`, `tasks.read`, `tasks.manage`, `tasks.complete`.

## Migrations

Local only. Not applied to hosted Supabase.

- `infra/supabase/migrations/20260930180000_queue_operations.sql`
- `infra/supabase/migrations/20260930180100_tasks_checklists.sql`

## Tests

Local Postgres:

- `apps/api/tests/test_queue.py`
- `apps/api/tests/test_tasks.py`

Browser, against the local stack:

- `node tools/acceptance/phase_b/p2_queue_board.mjs`
- `node tools/acceptance/phase_b/p2_tasks_board.mjs`
