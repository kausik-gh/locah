# Stage 2G — Subscription, Module & Entitlement Resolution Engine

## Purpose

Canonical entitlement authority determining module access, feature availability, usage limits, and platform capabilities. No billing, checkout, or payment-provider integration in this stage.

## Endpoints

| Method | Path | Permission |
|--------|------|------------|
| GET | `/v1/platform/plans` | Authenticated |
| GET | `/v1/platform/modules` | Authenticated |
| GET | `/v1/platform/modules/{id}` | Authenticated |
| GET | `/v1/platform/features` | Authenticated |
| GET | `/v1/platform/features/{id}` | Authenticated |
| GET | `/v1/platform/businesses/{id}/entitlements` | `entitlements.read` |
| GET | `/v1/platform/businesses/{id}/capabilities` | `entitlements.read` |
| PATCH | `/v1/platform/businesses/{id}/entitlements/overrides` | `entitlements.update` |
| PATCH | `/v1/platform/businesses/{id}/entitlements/plan` | `entitlements.update` |

## Resolution merge order

1. Business Type Configuration (recommendations only)
2. Plan Registry (`foundation` default)
3. Module Registry + DB `commercial_entitlements`
4. Business overrides (`metadata.commercial.overrides`)
5. Usage enforcement — placeholder

## Events

- `entitlement.updated`
- `module.enabled` / `module.disabled`
- `feature.enabled` / `feature.disabled`
- `business.override.updated`

## Default plan

All businesses without an explicit plan resolve to `foundation`, which includes Platform Core plus First Launch optional modules (5 Full + 5 Basic per Document 11).
