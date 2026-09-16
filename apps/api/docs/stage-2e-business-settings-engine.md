# Stage 2E — Business Settings & Configuration Engine

Authority: Document 04 Part 8; Document 11 `core-settings`; Stage 2A `businesses.settings` / `metadata`.

## Endpoints

Base: `/v1/platform/businesses/{business_id}`

| Method | Path | Permission |
|---|---|---|
| GET/PATCH | `/settings` | `settings.read` / `settings.update` |
| GET/PATCH | `/profile` | `settings.read` / `settings.update` |
| GET/PATCH | `/branding` | `settings.read` / `settings.update` |
| GET/PATCH | `/preferences` | `settings.read` / `settings.update` |

Optional PATCH body field `version` enables optimistic concurrency against `businesses.version`.

## Storage

- **Regional + notifications + branding + operational prefs:** `businesses.settings` JSONB
- **Profile fields:** `business_profiles` + `businesses.display_name`
- **Onboarding flag:** `businesses.metadata.onboarding.completed`
- **Visibility:** `businesses.visibility`

No new tables.

## Events

`business.settings.updated`, `business.profile.updated`, `business.branding.updated`, `business.preferences.updated`
