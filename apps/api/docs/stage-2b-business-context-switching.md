# Stage 2B — Business Context Switching (developer notes)

Authority: Document 05 CTX-* context rules; Document 12 request context + `/v1/platform/*`.

## Endpoint

`POST /v1/platform/businesses/{business_id}/switch`

Body (optional):

```json
{ "set_as_default": true }
```

Requires authentication and an **active** membership in `{business_id}`.

Rejects pending / suspended / removed memberships, soft-deleted businesses, and
closed businesses (resource-state gate → `CONFLICT`).

## Preference updates

| Field | On switch | On create |
|---|---|---|
| `last_business_id` | Always updated | Set |
| `default_business_id` | Updated only when `set_as_default=true` | Set |
| `primary_business_id` | **Never** overwritten | Set only if absent |

## Header restore (`X-Operating-Context: business`)

1. Explicit `X-Business-Id` → use it (must be accessible)
2. Else `default_business_id`
3. Else `last_business_id`
4. Else no business context (Personal)

Malformed `X-Business-Id` → `VALIDATION_ERROR`.

Inaccessible explicit Business → `MEMBERSHIP_REQUIRED` / `RESOURCE_NOT_FOUND`.

## Events

- Outbox: `business.context_switched` (worker stub-registered)
- Audit: `business.context_switched`
- Audit: `default_business_changed` when default actually changes
