# Easy_Ecom

Enterprise-grade multi-tenant inventory, sales, and finance web app built with Streamlit + CSV persistence.

## Features
- Multi-tenant architecture with strict `client_id` scoping.
- RBAC roles: `SUPER_ADMIN`, `CLIENT_OWNER`, `CLIENT_MANAGER`, `CLIENT_EMPLOYEE`, `FINANCE_ONLY`.
- Product catalog, inventory lots, FIFO depletion, sales flow (order/invoice/shipment), customer CRM, ledger finance.
- Login-first app flow: login page is the landing page and successful login redirects to dashboard.
- Inventory and sales UI are product-name driven (dropdowns) with stock-aware selection; Product IDs are system-generated.
- Client and super-admin dashboards with KPI cards, date-filtered Plotly charts, and cross-client health monitoring.
- Sequence generation per client/year (`INV`, `SHP`, `LOT`).
- Append-only transaction tables and audit-ready architecture.
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
- Inventory uses `inventory_txn.csv` append-only with lot-level tracking and strict tenant filtering by `client_id`.
- Product IDs are generated as `<product_name_normalized>_<lot_id>` when stock is added; users select by product name in UI.
- OUT transactions allocate stock FIFO by lot in `InventoryService.allocate_fifo`, grouped by product name for intuitive sales execution.
- Sales confirmation auto-generates order, invoice, shipment, inventory out rows, and earning ledger post.
- Invoice status updates from payment aggregation.
- Profit MTD = sales earnings - OUT transaction COGS - expense ledger.
- Dashboard KPIs include stock value, revenue/expenses/profit MTD, orders + AOV MTD, and outstanding invoices.
- Dashboard analytics include revenue trends, inventory value by product, product aging, margin vs sell speed bubble, income vs expense trends, and lot profitability recovery.
- Super admin dashboard supports global/specific-client toggle with aggregate bars (revenue and inventory value by client) and health flags (negative stock, inactive 14+ days).
- User accounts are stored in `users.csv` with plain-text passwords (as requested) and compared directly at login.
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
