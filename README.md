# Easy_Ecom

Enterprise-grade multi-tenant commerce platform with a **Next.js frontend** and **Python backend services**.

## Architecture (Current Direction)
- **Frontend (primary UI):** `frontend/` (Next.js App Router, TypeScript), targeted for AWS Amplify deployment.
- **Backend:** Python application and service/domain layers under `easy_ecom/`.
- **Legacy UI:** Streamlit app remains temporarily for maintenance and parity checks, but is **deprecated as product UI**.

## Features
- Multi-tenant architecture with strict `client_id` scoping.
- RBAC roles: `SUPER_ADMIN`, `CLIENT_OWNER`, `CLIENT_MANAGER`, `CLIENT_EMPLOYEE`, `FINANCE_ONLY`.
- Product catalog, inventory lots, FIFO depletion, sales flow (order/invoice/shipment), customer CRM, ledger finance.
- Client-level currency support (`currency_code` required, `currency_symbol` optional) with shared money formatter across dashboard/sales/finance screens.
- Unified **Catalog & Stock** workspace now runs as a compact operator workflow with a single searchable product chooser (includes inline “Add new product”), compact product master fields, dual-mode variant editing (existing-grid + add-row vs new-generation + add-row), shared-cost helper, and inline stock posting on save.
- Product master pricing controls (`default_selling_price`, `max_discount_pct`) are managed directly in Catalog & Stock during save.
- Sales workspace includes **Sell**, **Cart**, and **Sales Records** tabs so confirmed sales history remains visible alongside invoice/payment status.
- Returns workflow with request/approval, refund records, automatic refund expense ledger posting, and optional restocking.
- Inventory and sales can persist either parent `products.product_id` or `product_variants.variant_id` (variant-level stock/sales), while keeping product names as display snapshots.
- Client and super-admin dashboards with KPI cards, date-filtered Plotly charts, and cross-client health monitoring.
- Sequence generation per client/year (`INV`, `SHP`, `LOT`).
- Append-only transaction tables and audit-ready architecture.
- Inventory and finance transactions persist `user_id` to keep operator-level traceability for manual and auto-posted entries.
- CSV persistence with file locks and repository abstraction for DB migration readiness.

## Project Structure
- `frontend/`: Next.js frontend app (App Router, route shells, navigation).
- `easy_ecom/`: Python backend code.
  - `app/`: Legacy Streamlit pages and UI (**deprecated for primary product UI**).
  - `core/`: config, security, RBAC, IDs, audit utility.
  - `domain/models`: Pydantic validation contracts.
  - `domain/services`: business logic.
  - `data/store`: CSV schema and storage.
  - `data/repos`: repository adapters.
  - `scripts/init_data.py`: table bootstrapping + role seed + super admin creation.
  - `tests/`: core service tests.

## Setup

### Backend (Python service)
```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .[dev]
cp .env.example .env
python easy_ecom/scripts/init_data.py
```

Optional backend CORS configuration for frontend environments:

```bash
# comma-separated exact origins (defaults to localhost Next.js dev origins)
CORS_ALLOW_ORIGINS=http://localhost:3000,http://127.0.0.1:3000
```

`*.amplifyapp.com` origins are also allowed via regex in the FastAPI app middleware.

### Frontend (Next.js primary UI)
```bash
cd frontend
npm install
cp .env.example .env.local
npm run dev
```

### Optional: legacy Streamlit UI (deprecated)
```bash
streamlit run easy_ecom/app/main.py
```

If you see `ModuleNotFoundError: No module named 'reportlab'`, reinstall project dependencies from the repo root:

```bash
pip install -e .[dev]
# or minimum fix
pip install reportlab
```

## Frontend migration foundation (Next.js + Amplify)

### Routes scaffolded (App Router)
- `/`
- `/dashboard`
- `/products-stock` (priority shell)
- `/sales`
- `/customers`
- `/purchases`
- `/settings`

### Shared app shell
- Reusable sidebar
- Reusable top header
- Responsive content layout

### Amplify deployment
- `amplify.yml` at repository root configures Amplify for the `frontend/` app.
- `frontend/amplify.yml` is also included for frontend-local build/deploy configuration.
- Set `NEXT_PUBLIC_API_BASE_URL` in Amplify environment variables.



### Products & Stock frontend workspace (production page)
- Route: `frontend/app/(app)/products-stock/page.tsx` now renders a real compact operator workspace (no placeholder shell copy).
- UI is composed from reusable components under `frontend/components/products-stock/`:
  - `product-chooser.tsx`: single searchable chooser with inline `Add new product: "<typed>"` option.
  - `product-identity.tsx`: compact identity form (name/supplier/category/description/features) with searchable supplier/category and inline add.
  - `variant-generator.tsx`: new-product mode CSV-driven variant generation (size/color/other).
  - `variant-grid.tsx`: editable compact variants table with qty/cost/price/max discount, remove action, and same-cost helper.
  - `save-summary.tsx`: sticky save/reset bar, validation feedback, and live summary totals.
- Data source is currently mocked through `frontend/lib/mocks/products-stock.ts` using an API-like contract (`getProductsStockSnapshot`, `saveProductStock`) so backend wiring can replace it later with minimal UI changes.
- Variant math and transformation helpers live in `frontend/lib/products-stock/variant-utils.ts` and are reused by the workspace flow.
- Test coverage for the page behavior is in `frontend/__tests__/products-stock.test.tsx`.

## AWS App Runner
This repo includes `apprunner.yaml` at the repository root for legacy Python/Streamlit hosting on AWS App Runner.

- Runtime: `python311`
- Pre-run step installs the package with `python3 -m pip install .` (required for Python 3.11 revised build flow)
- Runtime command delegates to `startup.sh` so initialization runs once, then `exec` hands over to Streamlit as the long-running foreground process

`startup.sh`:
- Runs `python3 -m easy_ecom.scripts.init_data`
- Starts Streamlit bound to `0.0.0.0` on `PORT` (defaults to `8080`)

```bash
./startup.sh
```


## Order Lifecycle (New)
EasyEcom now uses explicit lifecycle dimensions instead of a single confirm-all status:

- `order_status`: `draft -> placed -> confirmed -> cancelled/closed`
- `payment_status`: `unpaid`, `partially_paid`, `paid`, `partially_refunded`, `refunded`, `failed`
- `fulfillment_status`: `unfulfilled`, `ready_to_pack`, `packed`, `shipped`, `delivered`, `delivery_failed`, `returned`
- `return_status`: `none`, `return_requested`, `approved`, `received`, `inspected`, `refund_approved`, `refund_completed`, `rejected`

### Lifecycle rules
- Draft orders are editable carts.
- `place_order_from_draft` locks commercial values and customer snapshot and ensures one invoice per order.
- `confirm_order` is the operational acceptance point and **stock deduction point** (stock is validated at place/confirm, deducted on confirm).
- Payments are recorded separately (`record_payment`) and support partial payments; overpayments are blocked by default.
- Shipments are never auto-created on place/confirm and must be created explicitly (`create_shipment_for_order`).
- Returns and refunds are separated: request/approve/receive/inspect/issue_refund.

### Single-source commercial totals
Everywhere in code and UI:

`subtotal = sum(qty * unit_selling_price)`  
`grand_total = subtotal - discount + tax + delivery_cost`

Financial fields maintained on orders/invoices:
- `amount_paid`: successful payment aggregate
- `amount_refunded`: successful refund aggregate
- `balance_due = grand_total - amount_paid + amount_refunded`

Invoices are financial documents and are updated to mirror payment/refund status and due balance.

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
- Sales now follows a cart-first draft workflow: Sell tab adds lines into per-customer draft carts (with optional force-new-cart), Cart tab provides full draft workspace (pricing/meta, line edits, empty/cancel/confirm), and confirmation remains all-or-nothing with stock + price revalidation.
- Cart/order totals use a consistent formula across draft compute + confirmation + invoice + ledger posting: `grand_total = subtotal - discount + tax + delivery_cost`; delivery customer charge stays in grand total while delivery expense is posted separately when configured.
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
- Catalog & Stock save flow supports create/update product master, duplicate-safe variant upsert/update, and stock posting only for rows with positive qty and cost while preserving append-only inventory/FIFO behavior and tenant isolation.

## Defaults
- `ALLOW_BACKORDER=false` blocks overselling.
- `CREATE_DEFAULT_CLIENT=false` avoids sample tenant creation by default.
- Project default super admin credentials are prefilled as `SUPER_ADMIN_EMAIL=frabby24@gmail.com` and `SUPER_ADMIN_PASSWORD=Fr@241189` in `.env.example` (copy/update in `.env` as needed) to preserve super-admin-only login even when `users.csv` is empty/inaccessible.

## Quality
Run checks:
```bash
pytest
ruff check .
black --check .
```

## FastAPI API skeleton

Backend API bootstrap is wired through `easy_ecom/api/app.py` and is bootable with uvicorn:

```bash
uvicorn easy_ecom.api.app:app --reload
```

The initial API layer includes:

- CORS middleware configured from `CORS_ALLOW_ORIGINS` (localhost defaults) plus `*.amplifyapp.com` via regex.
- `GET /health` returning `{"status": "ok"}`.
- Central router registration (`easy_ecom/api/routers/__init__.py`) so follow-up routes can be added in-place without touching app startup flow.

This keeps the current CSV-backed service/repository architecture intact while establishing a stable API entrypoint for adding `/session/me` and `/products-stock/*` routes in the next step.
