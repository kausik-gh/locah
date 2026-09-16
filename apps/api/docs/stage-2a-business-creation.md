# Stage 2A — Business Creation (developer notes)

Authority: Documents 04–07, 11 §17.2 entry (Business contracts), 12 §10.3 / §5.8.

## Endpoint

`POST /v1/platform/businesses` (authenticated; Doc 12 platform-scoped collection)

Request fields:

- `display_name` (required)
- `business_type` (optional; default `not_sure`; must be supported)
- `slug` (optional; conflict if taken; reserved slugs rejected)
- `logo_asset_id` (optional UUID referencing `media_assets`)
- `timezone`, `currency`, `country`, `language` (optional; validated subsets)

Response is hydrated: business + primary location + profile summary + membership +
operating context (role, permissions, current/default/primary flags).

## Defaults created in one transaction

- `businesses` row (`state=draft`) with `settings` / `metadata` JSONB
- Primary `business_locations` row (timezone + country)
- Active `primary_owner` membership
- `business_profiles` row (optional logo)
- Platform Core entitlements + module states
- Identity remembered context in `consumer_profiles.preferences`
  (`default_business_id`, `last_business_id`, `primary_business_id`)

## Events

Outbox (stub-handled by worker): `business.created`, `membership.created`, `business.initialized`

Audit: `business.created`, `membership.owner_assigned`, `business.configuration_initialized`

## Context restore

Clients send `X-Operating-Context: business`. If `X-Business-Id` is omitted, the
API restores the remembered default Business for the identity (Doc 05 restore semantics).
Path `/v1/b/{business_id}` remains the authoritative route-encoded Business context.
