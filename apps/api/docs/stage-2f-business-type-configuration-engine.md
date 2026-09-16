# Stage 2F — Business-Type Configuration Engine

## Purpose

Central resolver that translates a Business's declared `business_type` into a fully resolved operational configuration profile. Recommendations only — does not activate modules or grant entitlements (Document 07 BTYPE-002).

## Endpoints

| Method | Path | Permission |
|--------|------|------------|
| GET | `/v1/platform/business-types` | Authenticated |
| GET | `/v1/platform/business-types/{type_id}/profile` | Authenticated |
| GET | `/v1/platform/businesses/{id}/configuration/profile` | `configuration.read` |
| GET | `/v1/platform/businesses/{id}/configuration` | `configuration.read` |
| PATCH | `/v1/platform/businesses/{id}/configuration/type` | `configuration.update` |

## Resolution merge order

1. Canonical Business-Type Profile (in-code registry)
2. Explicit Business settings (`settings.configuration`, `settings.preferences`)
3. Entitlements layer — placeholder
4. Permissions layer — placeholder

Business settings override profile terminology and operational defaults per Document 07 §17.

## Events

- `business_type.changed`
- `configuration.resolved`
- `configuration.profile.updated`

Worker handlers registered as Stage 2 stubs.

## Supported types

First Launch subset from Document 11: `retail`, `restaurant`, `cafe`, `hotel`, `homestay`, `salon`, `spa`, `gym`, `studio`, `clinic`, `professional_service`, `education`, `other`, `not_sure`.

Null/legacy `business_type` resolves to `not_sure`.

## Type change rules

- Allowed after onboarding with `confirm_type_change: true`
- Optimistic concurrency via optional `version`
- Closed businesses rejected via `assert_business_mutable`
