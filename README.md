# EasyEcom

EasyEcom is a multi-tenant commerce operating system for growing businesses. It combines day-to-day operations (catalog, inventory, sales, finance, reporting) with tenant-scoped data foundations for AI-assisted sales workflows.

## Overview
EasyEcom is designed for businesses that buy/import products, store inventory, sell through operational teams, and need accurate, auditable data for both human operations and AI-driven customer engagement.

Core product outcomes:
- Centralized commerce operations across catalog, stock, purchases, sales, returns, and finance.
- Strict tenant isolation for all business data.
- Variant-level inventory truth with ledger-based auditability.
- Production-ready cloud deployment on AWS.

## Core Capabilities
- Multi-tenant authentication and role-based access controls.
- Catalog and variant management for saleable SKUs.
- Inventory tracking through auditable transaction flows.
- Purchase, sales, customer, and returns workflows.
- Finance and reporting endpoints for operational visibility.
- Integration surfaces for channels and AI sales-agent workflows.
- Super-admin controls for tenant onboarding and governance.

## System Architecture
- Frontend: Next.js (`frontend/`)
- Backend API: FastAPI (`easy_ecom/api`)
- Data layer: PostgreSQL + SQLAlchemy models
- Migration system: versioned SQL migrations (`easy_ecom/migrations/versions/`)
- Deployment targets: AWS Amplify (frontend) + AWS EC2 (backend) + AWS RDS (database)

## Business-Critical Data Rules
EasyEcom follows strict domain rules in implementation:
- Tenant isolation is mandatory for all reads and writes.
- Stock is tracked at `variant` level, not parent `product` level.
- Inventory truth is ledger-driven and auditable.
- Production changes prioritize correctness and safety over convenience.

## Local Development
### Backend
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
cp .env.example .env
python3 -m easy_ecom.scripts.migrate
python3 -m easy_ecom.scripts.init_data
python3 -m uvicorn easy_ecom.api.main:app --reload
```

### Frontend
```bash
cd frontend
npm install
cp .env.example .env.local
npm run dev
```

If using the live backend from local frontend:
```bash
cd frontend
echo 'NEXT_PUBLIC_API_BASE_URL=https://api.easy-ecom.online' > .env.local
```

## Deployment
### Backend (EC2)
```bash
./scripts/deploy_prod.sh
```

This deployment flow:
- builds a backend release artifact,
- uploads to EC2,
- installs dependencies,
- applies migrations,
- seeds baseline data,
- restarts the API service.

### Frontend (Amplify)
Production frontend deployment is triggered by pushes to `main` through:
- `.github/workflows/deploy-production.yml`

Manual Amplify trigger helper (optional):
```bash
AMPLIFY_APP_ID=<app-id> AMPLIFY_BRANCH=main ./scripts/trigger_amplify_deploy.sh
```

### Post-Deploy Smoke Check
```bash
API_BASE_URL=https://api.easy-ecom.online ./scripts/auth_deploy_smoke.sh
```

## Operations Scripts
- `scripts/deploy_prod.sh`: backend production deploy
- `scripts/build_backend_release.sh`: backend release bundle
- `scripts/auth_deploy_smoke.sh`: API smoke checks
- `scripts/reset_rds_to_auth_core.sh`: auth/core reset (destructive)
- `scripts/reset_rds_to_full_foundation.sh`: full reset (destructive)

## Repository Structure
- `easy_ecom/`: backend application, domain logic, data layer, migrations
- `frontend/`: web app (Next.js)
- `scripts/`: deployment and operational automation
- `.github/workflows/`: CI/CD workflows
- `docs/`: architecture and business documentation

## Security and Access
- Passwords are stored as hashes only.
- Tenant boundaries are enforced across API and data access paths.
- Super-admin capabilities are intentionally restricted to governance operations.

## License
This project is licensed under the terms in [LICENSE](LICENSE).
