# Stage 2C — Business Membership Engine (developer notes)

Authority: Document 06 membership lifecycle; Document 12 §8 team permissions.

## Endpoints

Base: `/v1/platform/businesses/{business_id}/members`

| Method | Path | Permission |
|---|---|---|
| GET | `/members` | `team.read` |
| GET | `/members/{membership_id}` | `team.read` |
| PATCH | `/members/{membership_id}` | `team.update_role` |
| POST | `/members/{membership_id}/suspend` | `team.update_role` |
| POST | `/members/{membership_id}/reactivate` | `team.update_role` |
| DELETE | `/members/{membership_id}` | `team.remove` (self-leave allowed without it) |
| POST | `/members/transfer-ownership` | Primary owner only |

Path-scoped membership is resolved directly from `{business_id}`; headers are not required to match active context.

## States

`pending` → `active` | `removed`  
`active` → `suspended` | `removed`  
`suspended` → `active` | `removed`  
`removed` — terminal

## Roles

Canonical only: `primary_owner`, `manager`, `member`.  
`primary_owner` assignment is ownership transfer only.

## Events

Outbox + audit: `membership.updated`, `membership.suspended`, `membership.reactivated`, `membership.removed`, `ownership.transferred`
