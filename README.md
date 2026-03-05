# Easy_Ecom

Enterprise-grade multi-tenant inventory, sales, and finance web app built with Streamlit + CSV persistence.

## Features
- Multi-tenant architecture with strict `client_id` scoping.
- RBAC roles: `SUPER_ADMIN`, `CLIENT_OWNER`, `CLIENT_MANAGER`, `CLIENT_EMPLOYEE`, `FINANCE_ONLY`.
- Product catalog, inventory lots, FIFO depletion, sales flow (order/invoice/shipment), customer CRM, ledger finance.
- Client-level currency support (`currency_code` required, `currency_symbol` optional) with shared money formatter across dashboard/sales/finance screens.
- Product master pricing controls (`default_selling_price`, `max_discount_pct`) with role-gated pricing editor in Inventory.
- Returns workflow with request/approval, refund records, automatic refund expense ledger posting, and optional restocking.
- Login-first app flow: before authentication, sidebar navigation is hidden so only the login page is visible; successful login redirects to dashboard.
- Inventory and sales persist stable `products.product_id` UUIDs end-to-end (sales items + inventory txns), while keeping product names as display snapshots.
- Client and super-admin dashboards with KPI cards, date-filtered Plotly charts, and cross-client health monitoring.
- Sequence generation per client/year (`INV`, `SHP`, `LOT`).
- Append-only transaction tables and audit-ready architecture.
- Inventory and finance transactions persist `user_id` to keep operator-level traceability for manual and auto-posted entries.
- CSV persistence with file locks and repository abstraction for DB migration readiness.

## Project Structure
Implemented under `easy_ecom/` with layers:
- `app/` Streamlit pages and UI.
- `core/` config, security, RBAC, IDs, audit utility.
- `domain/models` Pydantic validation contracts.
- `domain/services` business logic.
- `data/store` CSV schema and storage.
- `data/repos` repository adapters.
- `scripts/init_data.py` table bootstrapping + role seed + super admin creation.
- `tests/` core service tests.

## Setup
```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .[dev]
cp .env.example .env
python easy_ecom/scripts/init_data.py
streamlit run easy_ecom/app/main.py

# opens on Login page; after authentication app redirects to Dashboard
```

## Critical Logic
- Inventory uses `inventory_txn.csv` append-only with lot-level tracking, strict tenant filtering by `client_id`, and actor tracking through `user_id`.
- Legacy sales item rows that stored `product_name` in `sales_order_items.product_id` are migrated with `easy_ecom/scripts/migrate_sales_items_product_id.py` (idempotent, tenant-scoped, preserves `product_name_snapshot`).
- OUT transactions allocate stock FIFO by lot in `InventoryService.allocate_fifo`, keyed by stable `product_id` with lot kept in `lot_id`.
- Sales confirmation auto-generates order, invoice, shipment, inventory out rows, and earning ledger post; generated inventory/ledger rows inherit the initiating `user_id`.
- Sales page pre-fills item unit price from product default pricing; discounts are bounded by `max_discount_pct` and enforced in UI + service layer before cart/order writes.
- Sales page includes a sales records grid that is strictly tenant-scoped (`client_id`) and shows per-order invoice/payment balance details for the logged-in client only.
- Sales records grid normalizes invoice status into a dedicated `invoice_status` column before display, avoiding `status` column collisions with sales order status during joins.
- Refund approval flow (`returns.csv`, `return_items.csv`, `refunds.csv`) is restricted to non-employee roles and posts ledger `expense` category `Refunds`.
- Invoice status updates from payment aggregation.
- KPIs/charts are computed by `MetricsService` (`easy_ecom/domain/services/metrics_service.py`) as the single source of truth.
- Revenue = ledger `entry_type=earning`; Expenses = ledger `entry_type=expense`; COGS = inventory OUT `total_cost`; Profit = Revenue - Expenses - COGS (date-range aware).
- AOV = Revenue / confirmed orders count (guarded for divide-by-zero).
- Outstanding invoices = unpaid/partial invoice `amount_due` minus aggregated payments.
- Stock value by product = sum of positive lot balances (`current_qty_lot * unit_cost_lot`) aggregated to product.
- Product aging = sold% `(total_in-current_qty)/total_in`, remaining% `current_qty/total_in` with zero guards.
- Margin% = `(revenue-cogs)/revenue` with zero-revenue guard.
- Sell speed = units sold in last 30 days / 30.
- Lot recovery = revenue allocated to consumed lots using order+product unit-price allocation from OUT `source_id`.
- Dashboard KPIs include stock value, revenue/expenses/profit MTD, orders + AOV MTD, and outstanding invoices.
- Dashboard analytics include revenue trends, inventory value by product, product aging, margin vs sell speed bubble, income vs expense trends, and lot profitability recovery.
- Super admin dashboard supports global/specific-client toggle with aggregate bars (revenue and inventory value by client) and health flags.
- Data integrity warnings are surfaced in dashboard (negative stock, unmapped product IDs, missing lot IDs on OUT, numeric coercions) and are audit-logged.
- User accounts are stored in `users.csv` with plain-text passwords (as requested) and compared directly at login.
- COGS excludes taxes by design; COGS is derived strictly from inventory OUT `total_cost` (= `qty * unit_cost` from lot transactions).
- Logged-in user email is shown in the top-left sidebar for quick operator context.
- The default "main" entry in sidebar navigation is hidden after login to declutter tab navigation.
- Product features input accepts free-form text (line breaks, commas, or bullet points) and is normalized to JSON (`{"features": [...]}`) before persistence.

## Defaults
- `ALLOW_BACKORDER=false` blocks overselling.
- `CREATE_DEFAULT_CLIENT=false` avoids sample tenant creation by default.
- Super admin bootstrap credentials are configured via env as `SUPER_ADMIN_EMAIL=frabby24@gmail.com` and `SUPER_ADMIN_PASSWORD=Fr@241189`.

## Quality
Run checks:
```bash
pytest
ruff check .
black --check .
```


### Realtime refresh behavior
- Dashboard, Inventory, Sales, and Customers pages include manual **Refresh** buttons.
- Dashboard includes optional timed auto-refresh (5/10/15/30s) via `streamlit-autorefresh`.
- Dashboard renders `Last refreshed at <timestamp>` for operator visibility.

### Sales customer type-ahead + auto-save
- Sales flow accepts freeform customer entry.
- Case-insensitive exact name match is tenant-scoped and can disambiguate matching customers.
- On sale confirm: unmatched customers are auto-created; matched customers are auto-updated when edited fields changed.
- Auto-create/auto-update actions are audit-logged.
