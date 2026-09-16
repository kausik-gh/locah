# Stage 2H — Central Authorization & Permission Resolution Engine

## Purpose

Single runtime authority for authorization. All permission checks flow through `AuthorizationService.authorize()`.

## Endpoints

| Method | Path | Permission |
|--------|------|------------|
| GET | `/v1/platform/roles` | Authenticated |
| GET | `/v1/platform/permissions` | Authenticated |
| GET | `/v1/platform/businesses/{id}/permissions/matrix` | `permissions.read` |
| GET | `/v1/platform/businesses/{id}/permissions/effective` | `permissions.read` |
| GET | `/v1/platform/businesses/{id}/permissions/snapshot` | `permissions.read` |
| PATCH | `/v1/platform/businesses/{id}/members/{membership_id}/permissions/overrides` | `permissions.update` |

## Resolution merge order

1. System role (Primary Owner / Manager / Member base grants)
2. Membership role (applied templates + explicit grants)
3. Membership overrides (grant/deny records)
4. Custom roles — placeholder
5. ABAC — placeholder

## Events

- `permission.override.created` / `permission.override.removed`
- `authorization.snapshot.updated`
- `role.changed` (worker stub; emitted on future role-change integration)

## Integration

- `TeamService.resolve_permissions` delegates to `AuthorizationService`
- `require_business_actor` uses `AuthorizationService.authorize`
- Snapshot includes Stage 2G capability summary
