# Stage 2D — Business Invitation Engine (developer notes)

Authority: Document 05 `JRN-MEM-001/003`; Document 06 invitation lifecycle; Document 12 team module.

## Endpoints

Base: `/v1/platform/businesses/{business_id}/invitations`

| Method | Path | Auth |
|---|---|---|
| POST | `/invitations` | `team.invite` |
| GET | `/invitations` | `team.read` |
| GET | `/invitations/{id}` | `team.read` |
| POST | `/invitations/{id}/resend` | `team.invite` |
| POST | `/invitations/{id}/accept` | Invitee (authenticated) |
| POST | `/invitations/{id}/decline` | Invitee (authenticated) |
| DELETE | `/invitations/{id}` | `team.invite` (revoke) |

Legacy Stage 1 `POST /v1/b/{id}/team/invitations` remains for backward compatibility.

## States

`pending` → `accepted` | `declined` | `revoked` | `expired`

## Events

Outbox + audit: `invitation.created`, `invitation.resent`, `invitation.accepted`, `invitation.declined`, `invitation.revoked`, `invitation.expired`

Acceptance also emits `membership.created` via `TeamService.create_membership_from_invitation`.
