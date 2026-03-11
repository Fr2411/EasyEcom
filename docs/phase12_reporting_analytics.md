# Phase 12 — Reporting & Analytics MVP

## What was implemented

Phase 12 introduces a production reporting layer across Sales, Inventory, Products, Finance, Returns, Purchases, plus an Overview endpoint and frontend module (`/reports`).

Implementation is tenant-scoped and uses existing PostgreSQL business tables as the source of truth.

## API endpoints added

All endpoints are authenticated and use the session tenant (`user.client_id`) only:

- `GET /reports/overview`
- `GET /reports/sales`
- `GET /reports/inventory`
- `GET /reports/products`
- `GET /reports/finance`
- `GET /reports/returns`
- `GET /reports/purchases`

Supported filters:
- `from_date`
- `to_date`
- `product_id` (sales)
- `customer_id` (sales)
- `category` (inventory/products)

## Reporting entities / schema used

No new reporting tables were introduced.

Read models used:
- `sales_orders`
- `sales_order_items`
- `customers`
- `inventory_txn`
- `products`
- `finance_expenses`
- `sales_returns`
- `sales_return_items`
- `purchases`
- `purchase_items`

## Truthful metrics implemented

### Sales
- sales count (confirmed orders in range)
- revenue total (`sales_orders.grand_total`)
- day-level sales trend
- top products by sold qty / revenue
- top customers by revenue / sales count

### Inventory
- SKUs with positive stock (from signed `inventory_txn`)
- total stock units
- low stock items
- stock movement trend (`qty_in`, `qty_out`)

### Products
- highest-selling products (reuse sales aggregation)
- low/zero-movement products in range

### Finance
- expense total and trend (`finance_expenses.amount`)
- receivables total (`sales_orders.outstanding_balance`)
- payables summary (open purchase rows)
- net operating snapshot (`revenue - expenses`, without COGS)

### Returns
- returns count
- returned qty total
- return amount total

### Purchases
- purchases count
- purchases subtotal
- purchase trend (subtotal + quantity)

## Deferred metrics (intentional)

Deferred in API responses under `deferred_metrics`:

- `inventory_value`
  - Reason: lot-level outbound valuation data is not consistently captured; calculated value would be unreliable.
- `net_operating_snapshot` quality caveat
  - Snapshot is provided as revenue-expense only; COGS-backed net profit is deferred until cost capture is complete.

## Tenant isolation rules

- Endpoints require authenticated user session.
- Every query path applies `client_id == user.client_id`.
- No tenant identifier accepted from request path/query for scoping override.
- Cross-tenant reads return only tenant-scoped aggregates.

## Frontend module

- New route: `/reports`
- Includes:
  - date-range filter bar
  - overview KPI cards
  - section cards for sales, inventory, products, finance, returns, purchases
  - deferred metrics panel
- No fake data in runtime path; all data is API-backed.

## Migrations / indexes

- No migrations in this phase.
- No index changes in this phase.

## Phase 12 -> AI readiness

This phase prepares for future AI-assisted insights by establishing:
- stable tenant-safe reporting contracts
- deterministic KPI derivation rules
- explicit deferred-metric signaling for incomplete data models

Phase 13 can build on this with narrative insights and anomaly detection without changing canonical data ownership.
