# Easy_Ecom

EasyEcom is now in the first product-rebuild phase: the shared platform foundation is live again, and the business modules are being rebuilt intentionally on top of typed, tenant-safe tables.

## Current runtime scope
- Frontend: Next.js in `frontend/`
- Backend: FastAPI in `easy_ecom/api`
- Database: PostgreSQL via `DATABASE_URL`
- Active backend routes: `/health`, `/auth/*`, `/session/me`, plus canonical overview routes for dashboard, catalog, inventory, purchases, customers, sales, returns, finance, reports, admin, and settings
- Active frontend routes: pilot navigation for `Home`, `Dashboard`, `Catalog`, `Inventory`, `Purchases`, `Sales`, `Customers`, `Finance`, `Returns`, `Reports`, `Admin`, and `Settings`

## What is rebuilt in this foundation pass
- Versioned SQL migrations replace runtime-only schema drift for PostgreSQL
- Typed core and business tables now exist in the SQLAlchemy model layer
- Shared request ID middleware, structured API errors, invitation flow, and password-reset flow are restored
- Pilot information architecture is refined, and the legacy `/products-stock` route redirects to `/catalog`

## What remains on purpose
- AWS connectivity contract for Amplify, EC2-based deployment flow, and RDS
- Login/session flow and super-admin bootstrap
- App shell, pilot sidebar navigation, branding, and shared auth/UI utilities

## Local setup
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e .[dev]
cp .env.example .env
python3 -m easy_ecom.scripts.migrate
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

## Database foundation assets
- Typed runtime models live in `easy_ecom/data/store/postgres_models.py`
- Versioned SQL migrations live in `easy_ecom/migrations/versions/`
- Migration runner lives in `easy_ecom/scripts/migrate.py`
- Seed/bootstrap lives in `easy_ecom/scripts/init_data.py`

## Deployment
- Frontend connectivity remains through Amplify config in `amplify.yml`
- Backend connectivity remains through the existing startup entrypoint in `startup.sh`
- Existing EC2 deployment helper is preserved in `scripts/deploy_prod.sh`

## AWS shortcuts

Backend deploy to AWS EC2:
```bash
./scripts/deploy_prod.sh
```

What it does:
- SSH into the EC2 app host
- pull the latest code from `main`
- install Python dependencies
- run `python3 -m easy_ecom.scripts.migrate`
- run `python3 -m easy_ecom.scripts.init_data`
- restart `easy-ecom.service`

Frontend deploy to AWS Amplify:
```bash
AMPLIFY_APP_ID=<your-amplify-app-id> AMPLIFY_BRANCH=main ./scripts/trigger_amplify_deploy.sh
```

If your Amplify app is already connected to Git, pushing `main` also works:
```bash
git push origin main
```

Optional backend smoke check after deploy:
```bash
API_BASE_URL=https://<your-backend-domain> ./scripts/auth_deploy_smoke.sh
```

## DBeaver gateway to RDS

Start the SSH gateway from your laptop:
```bash
./scripts/dbeaver_gateway.sh
```

Then create a PostgreSQL connection in DBeaver with:
- Host: `127.0.0.1`
- Port: `5433`
- Database: `easyecom`
- User: `easyecom_admin`
- Password: use the current `POSTGRES_PASSWORD` from the EC2 `.env` or your AWS secret
- SSL: `require` or `preferred` without strict hostname verification

Keep the gateway terminal open while DBeaver is connected.

Optional local CLI check through the same tunnel:
```bash
./scripts/db_psql.sh
```
