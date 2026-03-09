# AWS Target Architecture (Single Source of Truth)

## Canonical decisions
- **Frontend:** `frontend/` (Next.js) on AWS Amplify
- **Backend:** `easy_ecom/api` (FastAPI) on AWS App Runner
- **Database:** AWS RDS PostgreSQL (`DATABASE_URL`)
- **Auth/users/roles:** PostgreSQL tables (`users`, `user_roles`, `roles`)
- **Secrets/config:** Amplify/App Runner environment variables and AWS secret flow
- **CSV:** migration tooling only, not runtime persistence
- **Streamlit:** not in runtime path

## Runtime flow
1. Amplify-hosted frontend calls API URL from `NEXT_PUBLIC_API_BASE_URL`.
2. FastAPI request container initializes Postgres-backed tabular store and service layer repositories.
3. Domain services perform all reads/writes against Postgres tables.
4. Auth validates user credentials and roles from Postgres and issues signed session cookies.

## Storage strategy
- All business entities share a single runtime repository strategy:
  - clients, users, roles, user_roles
  - products, product_variants, inventory_txn
  - customers, sales_orders, sales_order_items, invoices, shipments, payments
  - ledger, sequences, audit_log, returns, return_items, refunds
- CSV files are retained only for import/reconciliation scripts.

## Deployment intent
- **Canonical backend host:** AWS App Runner (`apprunner.yaml`, `startup.sh`).
- **Canonical frontend host:** AWS Amplify (`amplify.yml`).
- `frontend/amplify.yml` is maintained as a secondary copy for frontend-scoped CI use; root `amplify.yml` remains canonical for repo-root Amplify integration.

## Transition notes
- Streamlit code remains present but is intentionally disconnected from production startup.
- Super-admin env credentials are bootstrap-only seeding knobs for `init_data.py`.
