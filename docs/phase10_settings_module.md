# Phase 10 — Settings + Business Profile + Operational Preferences

## What was implemented

Phase 10 replaces the Settings placeholder with a tenant-scoped, PostgreSQL-backed settings module across FastAPI + Next.js.

Implemented sections:
- Business Profile
- Operational Preferences
- Document / Sequence Preferences
- Tenant Access Context (read-only)

## Backend APIs

Added canonical settings endpoints:
- `GET /settings/business-profile`
- `PATCH /settings/business-profile`
- `GET /settings/preferences`
- `PATCH /settings/preferences`
- `GET /settings/sequences`
- `PATCH /settings/sequences`
- `GET /settings/tenant-context`

All endpoints:
- require authenticated session
- derive tenant from session `client_id`
- enforce page-level settings access checks
- restrict write endpoints to `SUPER_ADMIN`, `CLIENT_OWNER`, `CLIENT_MANAGER`
- return tenant-scoped records only

## Schema / migration changes

Added migration:
- `easy_ecom/migrations/20260313_phase10_settings_module.sql`

Added table:
- `tenant_settings`
  - `client_id` (PK)
  - `timezone`
  - `tax_registration_no`
  - `low_stock_threshold`
  - `default_payment_terms_days`
  - `default_sales_note`
  - `default_inventory_adjustment_reasons`
  - `sales_prefix`
  - `returns_prefix`
  - `updated_at`

Added ORM model:
- `TenantSettingsModel`

## Access-control rules

- Read: any role with existing Settings page access can read settings.
- Write: only admin/manager roles (`SUPER_ADMIN`, `CLIENT_OWNER`, `CLIENT_MANAGER`) can patch tenant settings.
- Missing tenant context is rejected by existing auth/session dependency path before settings logic runs.

## Tenant isolation rules

- Every API call resolves tenant by `user.client_id` from signed session.
- No path/query tenant identifier is accepted for reads or writes.
- Database access in settings service always filters by `client_id`.

## Active vs deferred settings

### Active now
- Business profile fields persisted for tenant (name, display/trading name, contact, address, currency, timezone, tax registration).

### Saved but intentionally deferred (not yet behavior-wired)
- default low-stock threshold
- default sales note
- default inventory adjustment reason presets
- default payment terms days
- sales/returns prefix preference activation in sale/return number generation

### Explicitly deferred
- Logo upload/media storage: deferred until tenant-safe media architecture exists.

## Frontend delivery

`/settings` is now a real module with:
- structured section cards
- loading/error/empty/read-only states
- admin/manager write boundary messaging
- separate save actions for each settings section

## Why this prepares next phases

Phase 10 establishes a tenant configuration substrate required for:
- Purchases defaults (supplier/payment term defaults)
- Reporting context standardization (timezone/currency profile)
- AI-assisted tenant behavior tuning using explicit per-tenant preference state
