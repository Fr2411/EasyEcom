# Phase 8 Returns Module MVP

## Implemented
- Added tenant-scoped Returns MVP API on FastAPI/PostgreSQL.
- Added operational Next.js Returns workspace for list/create/detail flows.
- Added transactional return creation with sale-line eligibility validation.
- Added stock restoration via `inventory_txn` with `source_type=sale_return`.
- Added truthful sales/finance impact by reducing `sales_orders.grand_total` and recalculating outstanding/payment status.

## API Endpoints
- `GET /returns`
- `POST /returns`
- `GET /returns/{return_id}`
- `GET /returns/sales-lookup`
- `GET /returns/sales/{sale_id}`

All require authenticated session + role page access, and all data is scoped by `user.client_id`.

## Schema / Migration
- New table `sales_returns`
- New table `sales_return_items`
- Migration file: `easy_ecom/migrations/20260312_phase8_returns_module_mvp.sql`

## Integrity Rules
- Return sale must belong to tenant.
- Return lines must belong to selected sale.
- Return qty must be `<= sold_qty - prior_returned_qty` per line.
- Header + line records + inventory updates + sale financial adjustments are committed in one DB transaction.
- Inventory movement source is explicit (`sale_return`) to keep one stock truth.

## Finance Behavior
- Applied in MVP: sale total and outstanding are reduced by return total.
- Payment status is recalculated (`paid`/`partial`/`unpaid`) from paid vs adjusted total.
- Deferred: explicit overpayment/credit-note ledger and payment-gateway refund orchestration.

## Tenant Isolation Rules
- Every returns endpoint and every read/write query includes `client_id` filtering.
- Cross-tenant sale or return references resolve to not found/invalid.

## Deferred (Intentional)
- Purchase returns
- Reverse logistics/courier pickup
- Condition-based warehouse workflows
- Exchange workflow
- Gateway refund integrations
- Automated tax recomputation beyond current sale line/total model

## Preparation for Next Phases
- Returns now uses stable sales line linkage and explicit inventory movement provenance.
- This supports upcoming Admin/Settings hardening and future Purchases returns parity.
