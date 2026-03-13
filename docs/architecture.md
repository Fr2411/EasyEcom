# Architecture Direction

## Current foundation
- Frontend shell: Next.js placeholder application in `frontend/`
- Backend shell: FastAPI auth/session/health service in `easy_ecom/api`
- Runtime data source: PostgreSQL through `DATABASE_URL`
- Bootstrap: `easy_ecom/scripts/init_data.py` seeds roles and an optional super-admin

## Preserved infrastructure contracts
- Amplify remains the frontend hosting path
- EC2-backed deployment wiring remains preserved in repo scripts
- RDS remains the database boundary
- Existing env var names and startup entrypoints stay stable during the rebuild

## Deliberately removed from runtime
- Business write/read flows for catalog, inventory, sales, customers, finance, returns, purchases, reports, integrations, AI review, automation, admin, and settings
- Business schema ownership outside the auth core
- Business calculations and derived reporting logic

## Rebuild rule
- New features must be added back intentionally from this auth-only baseline instead of reviving deleted modules.
