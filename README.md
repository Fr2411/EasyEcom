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


## Auth session flow (cookie-based)

- `POST /auth/login` validates credentials against PostgreSQL, then issues signed cookie `easy_ecom_session` (`HttpOnly`, same-site/secure flags from backend config).
- Session payload stores `user_id`, `client_id`, `email`, `name`, `roles`, and expiry (`exp`) signed by `SESSION_SECRET`.
- `GET /auth/me` now uses strict session payload validation: missing cookie, bad signature, malformed payload, expired payload, or missing roles return `401 Unauthorized` (never `500`).
- Frontend route authorization now relies on backend session truth from `GET /auth/me` in `AuthProvider` + `AuthRouteGuard`; Next middleware cookie inspection was removed to prevent cross-origin cookie desync redirect loops.
- Frontend bootstrap (`AuthProvider`) keeps `credentials: include`, exposes a `refreshAuth()` retry path, and distinguishes bootstrap failures: `401` (`unauthorized`), `5xx` (`server`), network failures (`network`), and fallback unknown errors.
- Shared frontend API client (`frontend/lib/api/client.ts`) always sends cookies via `credentials: include`, maps transport failures to `ApiNetworkError`, and maps non-2xx responses to `ApiError` with HTTP status plus parsed JSON/text body for consistent auth/error handling.
- Protected app routes are wrapped in `AuthRouteGuard`; instead of returning `null`, they now render visible loading states during bootstrap/redirect and a visible retryable error state when `/auth/me` fails for non-`401` reasons.
- Protected app layout (`frontend/app/(app)/layout.tsx`) renders through `AppShell` inside `AuthRouteGuard`, so authenticated routes always mount sidebar/header/page chrome.
- Auth provider (`frontend/components/auth/auth-provider.tsx`) always mounts `AuthContext.Provider` with `user`, `loading`, `bootstrapError`, and `refreshAuth`, preventing context consumers from losing runtime state.
- Root layout (`frontend/app/layout.tsx`) wraps the entire frontend tree in `AuthProvider`, ensuring auth state is available across both public and protected routes.
- Login (`public-only`) routes also render a visible loading fallback while redirecting authenticated users to `/dashboard`, preventing blank-screen transitions.
- Login page uses shared auth bootstrap refresh immediately after successful sign-in so dashboard transition and auth context stay in sync.
- Dashboard route now always renders visible placeholder content inside `PageShell`, so post-login redirects never land on a blank screen even while KPI modules are still in development.


## Rebuild planning artifacts (Phase 1)

- `docs/phase1_feature_parity.md` — legacy-vs-web module parity map.
- `docs/phase1_architecture_assessment.md` — current frontend/backend/RDS architecture assessment.
- `docs/phase1_execution_plan.md` — module-by-module implementation roadmap.
- `docs/phase1_database_gap_analysis.md` — PostgreSQL/RDS table coverage and migration gap analysis.


## Rebuild hardening artifacts (Phase 2)

- `docs/phase2_api_hardening.md` — backend API surface hardening summary (canonical router registration, tenant isolation fixes, auth/tenant test additions, and deferred items).

Phase 2 backend outcomes:
- Canonical FastAPI router now intentionally mounts all implemented business routers (`dashboard`, `products`, `products-stock`, `inventory`, `sales`) in addition to health/auth/session.
- Dashboard tenant access is locked to authenticated session `client_id` (query-string tenant override is ignored).
- Runtime storage selection now honors `STORAGE_BACKEND=csv` for local/test runs without forcing Postgres initialization.

## Migration and legacy

- CSV files in `easy_ecom/data_files/` are no longer a production persistence path.
- Keep migration scripts for one-time import and reconciliation.
- Streamlit UI is deprecated and excluded from production startup.

## Local RDS Access (DBeaver / psql)

Step 1:
Run:
```bash
bash scripts/db_tunnel.sh
```

Step 2:
In DBeaver use:
- Host: 127.0.0.1
- Port: 5433
- Database: easyecom
- Username: easyecom_admin

Optional:
```bash
bash scripts/db_psql.sh
```

- This works because RDS is private and accessed via EC2 SSH tunnel.
- If SSH fails, check EC2 security group inbound rule for current public IP.
