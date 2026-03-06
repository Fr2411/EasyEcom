# Easy_Ecom

Enterprise-grade multi-tenant inventory, sales, and finance web app built with Streamlit + CSV persistence.

## Features
- Multi-tenant architecture with strict `client_id` scoping.
- RBAC roles: `SUPER_ADMIN`, `CLIENT_OWNER`, `CLIENT_MANAGER`, `CLIENT_EMPLOYEE`, `FINANCE_ONLY`.
- Product catalog, inventory lots, FIFO depletion, sales flow (order/invoice/shipment), customer CRM, ledger finance.
- Client-level currency support (`currency_code` required, `currency_symbol` optional) with shared money formatter across dashboard/sales/finance screens.
- Product master pricing controls (`default_selling_price`, `max_discount_pct`) with role-gated pricing editor in Inventory.
- Sales workspace includes **Sell**, **Cart**, and **Sales Records** tabs so confirmed sales history remains visible alongside invoice/payment status.
- Returns workflow with request/approval, refund records, automatic refund expense ledger posting, and optional restocking.
- Login-first app flow: before authentication, sidebar navigation is hidden so only the login page is visible; successful login redirects to dashboard, and the sidebar top-left always shows the EasyEcom app brand.
- Inventory and sales can persist either parent `products.product_id` or `product_variants.variant_id` (variant-level stock/sales), while keeping product names as display snapshots.
- Client and super-admin dashboards with KPI cards, date-filtered Plotly charts, and cross-client health monitoring.
- Sequence generation per client/year (`INV`, `SHP`, `LOT`).
- Append-only transaction tables and audit-ready architecture.
- Inventory and finance transactions persist `user_id` to keep operator-level traceability for manual and auto-posted entries.
- CSV persistence with file locks and repository abstraction for DB migration readiness.
- Super Admin **Data Manager** tab (inside Admin page) for controlled CSV inspection/editing with schema checks, backups, high-risk save confirmation, and direct CSV download.

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

If you see `ModuleNotFoundError: No module named 'reportlab'`, reinstall project dependencies from the repo root:

```bash
pip install -e .[dev]
# or minimum fix
pip install reportlab
```

## Critical Logic
- Inventory uses `inventory_txn.csv` append-only with lot-level tracking, strict tenant filtering by `client_id`, actor tracking through `user_id`, and shared canonical product normalization (products first, then variants, with legacy lot-id/product-name references mapped when possible and only truly broken rows flagged).
- Legacy sales item rows that stored `product_name` in `sales_order_items.product_id` are migrated with `easy_ecom/scripts/migrate_sales_items_product_id.py` (idempotent, tenant-scoped, preserves `product_name_snapshot`).
- OUT transactions allocate stock FIFO by lot in `InventoryService.allocate_fifo`, keyed by operational inventory identity (`variant_id` for variant rows, otherwise parent `product_id`) with lot kept in `lot_id`.
- Sales confirmation auto-generates order, invoice, shipment, inventory out rows, and earning ledger post; generated inventory/ledger rows inherit the initiating `user_id`.
- Sales page pre-fills item unit price from product default pricing; discounts are bounded by `max_discount_pct` and enforced in UI + service layer before cart/order writes.
- Sales page wires `ProductVariantsRepo` into `SalesService` so variant IDs selected in Sell tab resolve correctly during minimum-price validation and confirmation (prevents false "Product not found" for valid variants).
- Sales page includes a tenant-scoped (`client_id`) latest-50 confirmed sales grid sourced from reconciled confirmed orders, with item-presence and ledger-posting/mismatch flags for operational-financial alignment.
- Reconciliation now treats ledger `earning` rows with `source_type=sale` as valid when `source_id` points to either a sales `order_id` or an `invoice_id` that maps to an order, preventing false orphan-ledger warnings in Sales Records.
- Cart tab for draft sales orders groups carts by customer, supports draft line edits/removals, and confirms drafts into invoice + shipment with idempotency checks.
- Invoice and shipping mark downloads are generated on-demand as PDFs using `reportlab` (`easy_ecom/app/ui/documents.py`).
- Sales records grid normalizes invoice status into a dedicated `invoice_status` column before display, avoiding `status` column collisions with sales order status during joins.
- Refund approval flow (`returns.csv`, `return_items.csv`, `refunds.csv`) is restricted to non-employee roles and posts ledger `expense` category `Refunds`.
- Invoice status updates from payment aggregation.
- KPIs/charts and operational records now share `DataReconciliationService` (`easy_ecom/domain/services/data_reconciliation_service.py`) so Inventory, Sales Records, and Dashboard use the same normalized/reconciled rows, including variant-aware fields (`parent_product_id/name`, `variant_id/name`) plus canonical parent identity for analytics.
- Sales analytics now run through a shared normalized sales-items layer in `DataReconciliationService.normalized_sales_items`, exposing `inventory_product_id` (operational stock unit), `parent_product_id`, nullable `variant_id`, `canonical_product_id` (parent analytics key), product/variant snapshots, qty/price/line totals, order status, and ledger linkage flags.
- Revenue (operational truth) = sum of confirmed `sales_orders.grand_total`; ledger earning rows are treated as financial reflection and surfaced for reconciliation when orphaned/mismatched. Expenses = ledger `entry_type=expense`; COGS = inventory OUT `total_cost`; Profit = Revenue - Expenses - COGS (date-range aware).
- Profit terms are now explicit: **Gross Profit = Revenue - COGS** and **Net Operating Profit = Revenue - COGS - Expenses**. Dashboard cards/charts use these names consistently.
- AOV = Revenue / confirmed orders count (guarded for divide-by-zero).
- Outstanding invoices = unpaid/partial invoice `amount_due` minus aggregated payments.
- Stock value by product = sum of positive lot balances (`current_qty_lot * unit_cost_lot`) aggregated to product.
- Product aging = sold% `(total_in-current_qty)/total_in`, remaining% `current_qty/total_in` with zero guards.
- Margin% = `(revenue-cogs)/revenue` with zero-revenue guard, and margin rollups now aggregate variant sales to parent product (`canonical_product_id`).
- Sell speed = units sold in last 30 days / 30.
- Lot recovery = revenue allocated to consumed lots using normalized confirmed sales items joined by `(order_id, canonical_product_id)`, preventing parent/variant mismatch drift.
- Dashboard is redesigned into six business sections: (1) Business Health Snapshot, (2) Trend View, (3) Product Performance, (4) Inventory Health, (5) Financial/Receivables Health, and (6) Data Trust/Reconciliation.
- Dashboard KPI naming now uses locked formulas: Revenue = confirmed sales totals; COGS = inventory OUT tied to sales; Gross Profit = Revenue - COGS; Net Operating Profit = Revenue - COGS - Expenses; Gross Margin % = Gross Profit / Revenue.
- Dashboard snapshot cards now include Revenue, Gross Profit, Net Operating Profit, Gross Margin %, Inventory Value, Outstanding Receivables, and Data Health Score.
- Trend view now presents revenue, gross profit, net operating profit, expenses, and inventory value trends without duplicated or ambiguous chart semantics.
- Product performance section keeps the Gross Margin % vs Sale Speed chart (parent-product rollup) and adds top/bottom product rankings for revenue, gross profit, margin risk, and slow/dead stock.
- Financial/receivables section adds unpaid confirmed sales and receivables trends, while data trust section surfaces simplified trust for non-admin and detailed reconciliation counts/issues for super admin.
- Super admin dashboard supports global/specific-client toggle with aggregate bars (revenue and inventory value by client) and health flags.
- Data integrity warnings are surfaced in dashboard (negative stock, unmapped product IDs, missing lot IDs on OUT, numeric coercions), with admin-reviewable structured issue rows from reconciliation checks.
- Sales integrity warnings now classify identity quality correctly: valid parent item, valid variant item, legacy-repairable row, and truly broken/unknown row (only truly broken rows are flagged as errors).
- Dashboard/admin includes a structured reconciliation health scorecard (`confirmed sales with items`, `confirmed sales missing items`, `confirmed sales with ledger post`, `orphan ledger sale earnings`, `valid variant-linked sales items`, `legacy repairable sales rows`, `truly broken sales identities`, `unmapped inventory rows`, `client mismatch issues`).
- Optional repair script `easy_ecom/scripts/reconcile_legacy_references.py` provides dry-run by default and `--apply` mode to rewrite fixable legacy inventory product references while reporting orphan ledger earnings.
- User accounts are stored in `users.csv` with plain-text passwords (as requested) and compared directly at login.
- Authentication is restricted to `SUPER_ADMIN` only; non-super-admin user records cannot log in.
- Super admin authentication is always sourced from `.env` (`SUPER_ADMIN_EMAIL`, `SUPER_ADMIN_PASSWORD`), and login still works even if `users.csv` is empty.
- COGS excludes taxes by design; COGS is derived strictly from inventory OUT `total_cost` (= `qty * unit_cost` from lot transactions).
- Logged-in user email is shown in the top-left sidebar for quick operator context.
- The default "main" entry in sidebar navigation is hidden after login to declutter tab navigation.
- Product features input accepts free-form text (line breaks, commas, or bullet points) and is normalized to JSON (`{"features": [...]}`) before persistence.
- Admin Data Manager validates required table columns from schema, creates timestamped backups before overwrite, and flags high-risk tables (`users`, `roles`, `ledger`, inventory/sales transaction files) with extra save confirmation.

## Defaults
- `ALLOW_BACKORDER=false` blocks overselling.
- `CREATE_DEFAULT_CLIENT=false` avoids sample tenant creation by default.
- Set super admin bootstrap/login credentials in `.env` via `SUPER_ADMIN_EMAIL` and `SUPER_ADMIN_PASSWORD` (required for super admin login).

## Quality
Run checks:
```bash
pytest
ruff check .
black --check .
```

## AWS App Runner
This repo includes `apprunner.yaml` at the repository root for AWS App Runner deployments.

- Runtime: `python311`
- Pre-run step installs the package with `python3 -m pip install .` (required for Python 3.11 revised build flow)
- Runtime command delegates to `startup.sh` so initialization runs once, then `exec` hands over to Streamlit as the long-running foreground process

`startup.sh`:
- Runs `python3 -m easy_ecom.scripts.init_data`
- Starts Streamlit bound to `0.0.0.0` on `PORT` (defaults to `8080`)

```bash
./startup.sh
```

### Recommended App Runner console settings (MVP / lowest cost)
- Source directory: repository root (`/`)
- Runtime: Python 3.11 (managed)
- Port: `8080`
- Health check path: `/`
- CPU/Memory: `0.25 vCPU / 0.5 GB` to start (lowest practical baseline)
- Auto deploy trigger: `Manual` for cost control during MVP; switch to `Automatic` after release cadence stabilizes


### Realtime refresh behavior
- Dashboard, Inventory, Sales, and Customers pages include manual **Refresh** buttons.
- Dashboard includes optional timed auto-refresh (5/10/15/30s) via `streamlit-autorefresh`.
- Dashboard renders `Last refreshed at <timestamp>` for operator visibility.

### Sales customer type-ahead + auto-save
- Sales flow accepts freeform customer entry.
- Case-insensitive exact name match is tenant-scoped and can disambiguate matching customers.
- On sale confirm: unmatched customers are auto-created; matched customers are auto-updated when edited fields changed.
- Auto-create/auto-update actions are audit-logged.

## Recent enterprise updates
- Dashboard KPI now includes **Sold Qty MTD** and keeps Orders MTD as a secondary KPI.
- Product aging analytics include sold/remaining quantities with percentages.
- Added parent/variant model using `product_variants.csv` with per-variant stock and selling support.
- Cart confirmation now supports delivery cost on draft orders and auto-posts Delivery expense to ledger.
- Added migration scripts: `easy_ecom/scripts/migrate_sales_items_to_variants.py` and `easy_ecom/scripts/migrate_inventory_to_variants.py`.
