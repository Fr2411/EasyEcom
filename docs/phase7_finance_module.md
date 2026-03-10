# Phase 7 — Finance MVP Module

## What was implemented

Phase 7 introduces a production-grade, tenant-scoped Finance MVP in the canonical FastAPI + Next.js stack:

- Added real Finance backend APIs for overview, expenses, receivables, payables, and transaction history.
- Added a PostgreSQL-backed `finance_expenses` table for durable expense tracking.
- Extended `sales_orders` with payment fields required for truthful receivables tracking (`amount_paid`, `outstanding_balance`, `payment_status`).
- Added Finance frontend module at `/finance` with operational cards, expense capture, receivables/payables views, and transaction list.
- Preserved strict auth and tenant isolation by scoping every endpoint and DB read/write to authenticated `user.client_id`.

## API endpoints added/changed

### Added

- `GET /finance/overview`
- `GET /finance/expenses`
- `POST /finance/expenses`
- `PATCH /finance/expenses/{expense_id}`
- `GET /finance/receivables`
- `GET /finance/payables`
- `GET /finance/transactions`

### Changed

- `POST /sales` now initializes finance-relevant receivable fields on created sale rows:
  - `amount_paid = 0`
  - `outstanding_balance = grand_total`
  - `payment_status = unpaid`

## Schema/migration changes

Migration added:

- `easy_ecom/migrations/20260311_phase7_finance_mvp.sql`

It performs:

1. `ALTER TABLE sales_orders` to add:
   - `amount_paid`
   - `outstanding_balance`
   - `payment_status`
2. Backfill defaults for existing `sales_orders` rows.
3. Add indexes for payment status and outstanding balance filters.
4. Create `finance_expenses` table with indexes by tenant/date/status/category.

## Finance truthfulness rules

- Overview metrics are derived from persisted data only (sales orders + finance expenses).
- Receivables are computed only from sales rows with `payment_status in (unpaid, partial)`.
- Payables are computed from expense rows with `payment_status in (unpaid, partial)`.
- If a metric/data stream is not present in persisted rows, APIs return empty values rather than fabricated numbers.
- Transactions list includes only entries backed by stored rows (sales + expenses).

## Tenant isolation rules

- All finance endpoints require authenticated session.
- Every query includes `client_id = user.client_id` constraints.
- Expense update/read paths return `404` when a row is not found inside current tenant.
- Cross-tenant rows are never exposed through finance APIs.

## Intentionally deferred

- Full accounting ledger/journal engine (double-entry).
- Tax/VAT engine, bank reconciliation, payroll, depreciation.
- Balance sheet/P&L statement generation.
- Supplier master lifecycle; payables currently scoped to unpaid/partial expenses.
- Invoice settlement workflow beyond storing receivable state fields.

## Preparation for next phases

This module creates the operational finance foundation needed by upcoming phases:

- **Returns:** reverse cash/stock effects can be reflected in transaction history.
- **Admin:** finance activity can be audited by tenant and user.
- **Settings:** category/payment policy normalization can evolve from real usage.
- **Purchases:** supplier payables can be linked into existing payables view without redesigning module boundaries.
