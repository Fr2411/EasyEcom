# Easy_Ecom

Enterprise-grade multi-tenant inventory, sales, and finance web app built with Streamlit + CSV persistence.

## Features
- Multi-tenant architecture with strict `client_id` scoping.
- RBAC roles: `SUPER_ADMIN`, `CLIENT_OWNER`, `CLIENT_MANAGER`, `CLIENT_EMPLOYEE`, `FINANCE_ONLY`.
- Product catalog, inventory lots, FIFO depletion, sales flow (order/invoice/shipment), customer CRM, ledger finance.
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
```

## Critical Logic
- Inventory uses `inventory_txn.csv` append-only with lot-level tracking.
- OUT transactions allocate stock FIFO by lot in `InventoryService.allocate_fifo`.
- Sales confirmation auto-generates order, invoice, shipment, inventory out rows, and earning ledger post.
- Invoice status updates from payment aggregation.
- Profit MTD = sales earnings - OUT transaction COGS - expense ledger.
- User creation validates tenant-scoped identity inputs with Pydantic models, including normalized and validated email format checks.

## Defaults
- `ALLOW_BACKORDER=false` blocks overselling.
- `CREATE_DEFAULT_CLIENT=false` avoids sample tenant creation by default.

## Quality
Run checks:
```bash
pytest
ruff check .
black --check .
```
