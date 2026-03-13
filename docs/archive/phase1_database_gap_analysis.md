# Phase 1 — Database Gap Analysis (PostgreSQL / RDS)

This analysis is grounded in existing repository schema contracts and runtime code paths.

## 1) Currently used table landscape

Primary runtime schema comes from `TABLE_SCHEMAS` and is materialized by `PostgresTableStore.ensure_table`.

### Core auth & tenancy
- `clients`
- `users`
- `roles`
- `user_roles`

### Product and stock core
- `products`
- `product_variants`
- `inventory_txn`
- `sequences`

### Sales lifecycle core
- `sales_orders`
- `sales_order_items`
- `invoices`
- `shipments`
- `payments`

### CRM/finance/returns/audit
- `customers`
- `ledger`
- `returns`
- `return_items`
- `refunds`
- `audit_log`

### Import/ops support (ORM-defined)
- `import_runs`
- `import_errors`

## 2) Observed implementation reality

- Auth is explicitly PostgreSQL + SQLAlchemy session based (`PostgresAuthRepo`) and uses `users` + `user_roles`.
- Most domain repositories still use tabular/pandas patterns over Postgres tables through `PostgresTableStore`.
- Existing `postgres_models.py` only declares ORM models for subset tables (clients/users/products/variants/inventory/imports), not full commerce set.
- All dynamically created tabular columns are TEXT, so numeric/date correctness depends on service-layer coercion.

## 3) Table usage by current production web paths

| Area | Web/API Reachable Now | Tables effectively in use |
|---|---|---|
| Auth/session | Yes (`/auth/login`, `/auth/me`, `/auth/logout`) | `users`, `user_roles` |
| Products-stock workspace | Yes (`/products-stock/snapshot`, `/products-stock/save`) | `products`, `product_variants`, `inventory_txn` (+ option lists from products) |
| Dashboard | Not mounted in canonical router | Service references `inventory_txn`, `ledger`, `sales_orders`, `sales_order_items`, `invoices`, `payments`, `products`, `product_variants`, `clients` |
| Sales lifecycle | Router exists but not mounted | `sales_orders`, `sales_order_items`, `invoices`, `shipments`, `payments`, `inventory_txn`, `ledger`, `customers`, `audit_log` |
| Customers/Finance/Returns/Admin | Legacy only / no canonical web API | Uses corresponding tables listed in schema |

## 4) Gaps and missing fields (high-confidence)

## A) Strongly needed constraints/index improvements
Current table contracts include `client_id` but there is no explicit DB-level RLS/foreign key/index strategy in code for many tables.

Recommended future migrations:
- Add composite indexes on `(client_id, <frequent_filter_column>)` for high-volume tables:
  - `sales_orders(client_id, timestamp)`
  - `inventory_txn(client_id, product_id)`
  - `sales_order_items(order_id, product_id)`
  - `payments(client_id, invoice_id)`
  - `ledger(client_id, timestamp)`
  - `returns(client_id, status)`
- Add unique constraints where domain expects uniqueness (e.g., order/invoice/shipment sequence IDs).

## B) Type hardening
Current TEXT-everywhere approach risks silent invalid data.

Recommended migration path (incremental, non-breaking):
1. Add typed shadow columns for amounts/timestamps on critical tables.
2. Backfill + validate coercion.
3. Move services to typed columns.
4. Remove legacy text columns once stable.

## C) Purchases module structural gap
- No explicit `purchase_orders` / `purchase_order_items` tables currently defined.
- Legacy behavior approximates purchases via manual stock-in + ledger.

Recommendation:
- Treat purchase orders as **Phase 3+** schema additions unless business requires immediate PO workflow.
- Until then, keep inventory stock-in as canonical inbound flow.

## D) Bundles / kits gap
- No clear bundle/kit entities in existing schema contracts.

Recommendation:
- Defer bundle schema introduction until products/inventory/sales MVP parity is complete.
- Candidate future tables: `bundles`, `bundle_items`, and stock deduction expansion rules.

## 5) Tables that exist but are underused by web app today

- `sales_orders`, `sales_order_items`, `invoices`, `shipments`, `payments`: service-ready but not yet exposed through mounted web module APIs.
- `ledger`: used in legacy pages/services, not yet surfaced in Next web.
- `returns`, `return_items`, `refunds`: implemented in services/legacy but absent in web module.
- `audit_log`: written by service flows but not operationalized in admin web monitoring.

## 6) Multi-tenant scoping risk review

### Current state
- Session payload contains `client_id`; most service entrypoints use user client scope.
- Legacy and service code heavily assumes `client_id` filtering in pandas operations.

### Risks
- Any newly added API that forgets `client_id` filter can leak cross-tenant data.
- Super-admin global views must be explicit and auditable; default should remain tenant-scoped.

### Guardrails for future phases
- Enforce `client_id` in every repository query path by contract.
- Add automated tests for cross-tenant leakage per module.
- Consider DB-level reinforcement (RLS or strict service-layer policy + query helpers).

## 7) Migration needs for future phases

1. **Short-term (before module expansion)**
   - Mount existing routers and validate schema parity in staging RDS.
   - Add indexes for common client-scoped queries.
2. **Mid-term (sales/finance/returns web rollout)**
   - Introduce typed monetary/date columns in key tables.
   - Add constraints and data validation migrations.
3. **Long-term (advanced modules)**
   - Add purchase and bundle schemas only after operational model confirmation.

