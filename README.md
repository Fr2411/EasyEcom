# Easy_Ecom

EasyEcom is in the platform foundation phase: the shared tenant-safe core is live, the main business workspaces are mounted, and the remaining placeholder surface is isolated instead of mixed into the core engine.

## Current runtime scope
- Frontend: Next.js in `frontend/`
- Backend: FastAPI in `easy_ecom/api`
- Database: PostgreSQL via `DATABASE_URL`
- Active backend routes: `/health`, `/auth/*`, `/session/me`, plus mounted business routers for dashboard, catalog, inventory, purchases, customers, sales, returns, finance, reports, integrations, sales agent, AI review, admin, and settings
- Active frontend routes: `Home`, `Dashboard`, `Catalog`, `Inventory`, `Purchases`, `Sales`, `Customers`, `Finance`, `Returns`, `Reports`, `Integrations & Channels`, `Sales Agent`, `AI Review Inbox`, `Admin`, and `Settings`
- `Automation` remains the only intentionally blank workspace

## What is rebuilt in this foundation pass
- Versioned SQL migrations replace runtime-only schema drift for PostgreSQL
- Typed core and business tables now exist in the SQLAlchemy model layer
- Shared request ID middleware, structured API errors, and super-admin tenant onboarding are restored
- Variant-first inventory, sales, returns, finance, reporting, integration, and AI review flows are wired through typed API clients and backend services
- The legacy `/products-stock` route redirects to `/catalog`

## What remains on purpose
- AWS connectivity contract for Amplify, EC2-based deployment flow, and RDS
- Login/session flow and super-admin bootstrap
- App shell, navigation, branding, and shared auth/UI utilities
- The remaining placeholder route for `Automation`

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

If you want the local frontend to use the live AWS backend instead of a local API, set:
```bash
cd frontend
echo 'NEXT_PUBLIC_API_BASE_URL=https://api.easy-ecom.online' > .env.local
```

If you want full local development, keep `.env.local` pointed at `http://localhost:8000` and run the FastAPI server locally first.

## Database foundation assets
- Typed runtime models live in `easy_ecom/data/store/postgres_models.py`
- Versioned SQL migrations live in `easy_ecom/migrations/versions/`
- Migration runner lives in `easy_ecom/scripts/migrate.py`
- Seed/bootstrap lives in `easy_ecom/scripts/init_data.py`

## Deployment
- Frontend connectivity remains through Amplify config in `amplify.yml`
- Backend connectivity remains through the existing startup entrypoint in `startup.sh`
- Existing EC2 deployment helper is preserved in `scripts/deploy_prod.sh`
- GitHub Actions can now trigger the backend EC2 deploy using `.github/workflows/deploy-backend.yml`

## Repo Guardrails
- Run `./scripts/check_repo_surface.sh` to fail fast on tracked local venvs, IDE state, backup/debug copies, logs, build metadata, and other files that should not reach production
- Keep runtime deploys focused on source, migrations, and server scripts only

## Super Admin Password Flow

User setup and password recovery are handled directly by super admin from the admin panel.

Behavior:
- New client users are created with an admin-entered password
- If a user forgets the password, super admin can set a new one from `/admin`
- Passwords are stored only as hashes; admins never read them back from the system

## AWS shortcuts

Backend deploy to AWS EC2:
```bash
./scripts/deploy_prod.sh
```

What it does:
- SSH into the EC2 app host
- upload a backend release artifact for the selected Git ref/SHA
- sync runtime files into the EC2 project directory
- install Python dependencies
- run database migrations
- seed baseline data
- restart the backend service

GitHub-driven backend deploy:
- Production deploy is manual-only via `.github/workflows/deploy-backend.yml` (`workflow_dispatch`)
- Use `develop` as staging integration and promote to `main` only after staging validation
- Required GitHub Secrets:
  - `EC2_HOST`
  - `EC2_USER`
  - `EC2_SSH_PRIVATE_KEY`
  - optional `API_BASE_URL` for post-deploy smoke checks

Staging workflow checks:
- Local internal preview-before-push: `./scripts/local_preview_before_push.sh`
- Shared quality gate (local + CI): `./scripts/staging_quality_gate.sh`
- GitHub staging gate workflow: `.github/workflows/staging-policy-gate.yml`
- Branch protection rollout helper: `./scripts/apply_branch_protection.sh`
- Policy reference: `docs/staging-workflow-policy.md`

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

## Controlled reset scripts
- Auth-only reset (legacy auth/core only):
```bash
./scripts/reset_rds_to_auth_core.sh
```
- Full foundation reset (destructive; drops all public tables, then re-runs migrations + seeds):
```bash
./scripts/reset_rds_to_full_foundation.sh
```

Destructive reset logic is intentionally kept outside versioned migrations.

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
- Password: use the password from your AWS secret manager or EC2 environment
- SSL: `require` or `preferred` without strict hostname verification

Keep the gateway terminal open while DBeaver is connected.

Optional local CLI check through the same tunnel:
```bash
./scripts/db_psql.sh
```
Update to trigger Amplify rebuild Fri Mar 27 17:23:03 +04 2026
