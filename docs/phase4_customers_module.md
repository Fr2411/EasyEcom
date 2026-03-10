# Phase 4 — Customers Module (MVP)

## Implemented

- Added a production Customers API module with tenant-scoped CRUD endpoints.
- Replaced the Next.js Customers placeholder page with an operational module:
  - searchable list/table
  - empty/loading/error states
  - create flow
  - detail/edit panel
- Added PostgreSQL customer model/repository and migration support for customer records.

## API endpoints

All endpoints require authenticated session cookie and are scoped to `user.client_id`.

- `GET /customers?q=` — list tenant customers with optional search by name/phone/email
- `POST /customers` — create customer
- `GET /customers/{customer_id}` — fetch one customer in tenant scope
- `PATCH /customers/{customer_id}` — update customer profile fields

## Schema / migration changes

- Added SQLAlchemy `CustomerModel` in `easy_ecom/data/store/postgres_models.py`.
- Added migration `easy_ecom/migrations/20260310_customers_module_mvp.sql`:
  - creates `customers` table if missing
  - adds `updated_at` column when upgrading existing table
  - adds tenant lookup indexes (`client_id`, `client_id + full_name`)
- CSV schema map updated to include `updated_at` in `customers.csv` for parity in local csv mode.

## Tenant isolation rules

- API never accepts client_id override from request payload/query/path.
- All list/read/update/create operations derive tenant context from `get_current_user().client_id`.
- Detail/update return `404` for customer IDs outside the authenticated tenant.

## Deferred intentionally

- Customer balances / credit limits
- Communication history / CRM timeline
- Segmentation and dedupe workflows
- Bulk import UX

## Phase 5 readiness (Sales)

This Customers MVP now provides a stable customer master-data foundation for Sales:

- fast customer lookup for order creation
- consistent tenant-safe customer identifiers
- editable core profile data for invoicing/shipping workflows
