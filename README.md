# Easy_Ecom

EasyEcom is temporarily reset to an auth-only foundation while the product is rebuilt.

## Current runtime scope
- Frontend: Next.js in `frontend/`
- Backend: FastAPI in `easy_ecom/api`
- Database: PostgreSQL via `DATABASE_URL`
- Active backend routes: `/health`, `/auth/*`, `/session/me`
- Active frontend routes: existing sidebar URLs remain, but business pages are placeholders

## What was intentionally removed
- Catalog, inventory, sales, finance, returns, purchases, reporting, admin, integrations, AI review, automation, and settings business logic
- Business API schemas, services, tests, and module docs
- Business-specific frontend workspaces and API client wrappers

## What remains on purpose
- AWS connectivity contract for Amplify, EC2-based deployment flow, and RDS
- Login/session flow and super-admin bootstrap
- App shell, sidebar navigation, branding, and shared auth/UI utilities

## Local setup
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e .[dev]
cp .env.example .env
python3 -m easy_ecom.scripts.init_data
python3 -m uvicorn easy_ecom.api.main:app --reload
```

Frontend:
```bash
cd frontend
npm install
cp .env.example .env.local
npm run dev
```

## Database reset assets
- Auth-only schema bootstrap is defined in `easy_ecom/data/store/postgres_models.py`
- Auth seed/bootstrap lives in `easy_ecom/scripts/init_data.py`
- Destructive reset SQL lives in `easy_ecom/migrations/20260314_auth_only_foundation.sql`

## Deployment
- Frontend connectivity remains through Amplify config in `amplify.yml`
- Backend connectivity remains through the existing startup entrypoint in `startup.sh`
- Existing EC2 deployment helper is preserved in `scripts/deploy_prod.sh`
