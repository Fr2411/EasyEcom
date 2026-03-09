# Easy_Ecom

EasyEcom is a multi-tenant commerce platform with:
- **Canonical frontend:** Next.js app in `frontend/` (AWS Amplify)
- **Canonical backend:** FastAPI app in `easy_ecom/api` (AWS App Runner)
- **Canonical data/auth source:** AWS RDS PostgreSQL

Legacy Streamlit pages under `easy_ecom/app/` are retained only for controlled transition and are **not part of production runtime**.

## Runtime architecture (single source of truth)

1. Frontend (`frontend/`) calls FastAPI (`easy_ecom/api/main.py`).
2. FastAPI services use repository adapters backed by PostgreSQL tables.
3. Users, roles, inventory, products, customers, sales, finance, sequences, and audit all run through PostgreSQL at runtime.
4. CSV assets are migration/bootstrap tooling only (`easy_ecom/scripts/*import*`, migration scripts).

## Local setup (AWS-aligned)

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .[dev]
cp .env.example .env
python -m easy_ecom.scripts.init_data
python -m uvicorn easy_ecom.api.main:app --reload
```

Frontend:
```bash
cd frontend
npm install
cp .env.example .env.local
npm run dev
```

## Deployment

### Production backend deploy shortcut

Use the production deploy helper for backend and/or database schema changes:

```bash
./scripts/deploy_prod.sh
```

### Frontend (canonical)
- AWS Amplify using root `amplify.yml` (appRoot: `frontend`).

### Backend (canonical)
- AWS App Runner using `apprunner.yaml`.
- Runtime command is `./startup.sh`, which initializes bootstrap data then runs:
  - `uvicorn easy_ecom.api.main:app --host 0.0.0.0 --port $PORT`

## Configuration

Use AWS-managed environment variables / secrets injection in Amplify and App Runner.

Key backend vars (see `.env.example`):
- `DATABASE_URL` (RDS DSN)
- `SESSION_SECRET`
- `CORS_ALLOW_ORIGINS`
- optional bootstrap seed: `SUPER_ADMIN_EMAIL`, `SUPER_ADMIN_PASSWORD`

Key frontend vars (`frontend/.env.example`):
- `NEXT_PUBLIC_API_BASE_URL`
- `NEXT_PUBLIC_SESSION_COOKIE_NAME`

## Migration and legacy

- CSV files in `easy_ecom/data_files/` are no longer a production persistence path.
- Keep migration scripts for one-time import and reconciliation.
- Streamlit UI is deprecated and excluded from production startup.
