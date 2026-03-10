# Phase 5 — Sales module MVP

## Implemented

- Added tenant-scoped FastAPI Sales endpoints backed by PostgreSQL data and authenticated session context.
- Replaced placeholder Next.js Sales route with an operational workspace for list/search/create/detail.
- Added transactional sale creation with multi-line cart support.
- Added stock validation and stock deduction writes as inventory `OUT` transactions inside the same DB transaction.

## API endpoints

- `GET /sales` — list recent tenant sales (search by sale number, customer name, timestamp text).
- `GET /sales/form-options` — list tenant customer and product/variant options for sale form.
- `POST /sales` — create a tenant sale with lines, totals, and stock deduction.
- `GET /sales/{sale_id}` — sale detail with header + lines.

## Schema / migration changes

- Added migration: `easy_ecom/migrations/20260310_sales_module_mvp.sql`
  - creates `sales_orders`
  - creates `sales_order_items`
  - adds tenant-focused indexes

## Inventory integrity rules

- Each sale line validates positive quantity and non-negative unit price.
- Each line validates product reference belongs to authenticated tenant (product or variant ID).
- Customer ID must belong to authenticated tenant.
- Stock availability is checked before write.
- Stock deduction is persisted as `inventory_txn` `OUT` rows with `source_type=sale` and sale source ID.
- Sale header + lines + stock deduction are committed atomically.

## Tenant isolation rules

- Endpoints require authenticated session.
- `client_id` is only sourced from signed session payload (`get_current_user`).
- Every read/write uses `client_id` in query predicates.
- Cross-tenant customer/product references are rejected.

## Deferred intentionally

- Returns/refunds workflow
- PDF invoicing
- Payment gateway integration
- Tax/discount engines beyond passed values
- Delivery/channel integrations
- Advanced bundle decomposition

## Phase linkage

This module prepares for next phases by introducing:

- canonical sale entities in PostgreSQL
- consistent `sale` source linkage into inventory transactions
- operational UI and API contracts that can be extended for finance posting, returns, and richer inventory controls
