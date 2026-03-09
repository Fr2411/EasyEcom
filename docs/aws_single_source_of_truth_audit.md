# AWS Single Source of Truth Audit

## Classification legend
1. KEEP as-is
2. KEEP but REWIRE to AWS
3. MIGRATE from CSV/local to Postgres/AWS
4. DELETE as dead/legacy code
5. TEMPORARILY KEEP for controlled transition

## Module audit

| Path | Current responsibility | Local/CSV/legacy assumption | Target AWS responsibility | Action | Risk | Blocks SSoT |
|---|---|---|---|---|---|---|
| `frontend/` | Product UI (Next.js) | Some localhost defaults in env examples | Amplify-hosted canonical UI | 2 (env/docs rewired) | Low | No |
| `easy_ecom/api/` | FastAPI API routers and app factory | Mixed backend data wiring in dependencies | Canonical API runtime on App Runner/EC2 | 3 (rewired dependencies to Postgres runtime store) | Medium | Previously yes |
| `easy_ecom/domain/` | Business logic services/models | Repos were storage-agnostic but effectively CSV-backed | Keep services, run via Postgres-backed store | 2 | Medium | Previously yes |
| `easy_ecom/data/store/csv_store.py` | CSV table persistence | Local file runtime storage | Migration tooling only | 5 | Low | No (after rewiring runtime) |
| `easy_ecom/data/store/postgres_*` | SQLAlchemy engine/models and Postgres repos | Bounded Products & Stock only | Full runtime persistence substrate | 3 (added tabular Postgres runtime store) | Medium | Previously yes |
| `easy_ecom/data/repos/csv/` | Repository adapters for all business entities | Assumed CSV store object | Keep adapters; point them to Postgres tabular store in runtime | 3 | Medium | Previously yes |
| `easy_ecom/data/repos/postgres/` | Partial Postgres repos (auth + products/stock) | Partial dual-path implementation | Keep auth repo; runtime unified by Postgres store | 5 | Low | No |
| `easy_ecom/scripts/init_data.py` | Bootstrap tables/roles/super-admin | Created/seeded CSV files | Bootstrap Postgres tables/data only | 3 | Medium | Previously yes |
| `easy_ecom/scripts/*import*` & migration scripts | CSV->Postgres migration/reconciliation | CSV source assumptions | One-time migration only | 5 | Low | No |
| `easy_ecom/app/` | Legacy Streamlit UI | Legacy runtime/UI path | Transition-only, out of production startup | 5 | Low | Previously yes |
| `startup.sh` | Runtime entrypoint | Started Streamlit | Start FastAPI only | 3 | Low | Yes |
| `apprunner.yaml` | Backend deployment config | Historically Streamlit runtime | Canonical backend deployment (FastAPI) | 2 | Low | Yes |
| `amplify.yml` | Frontend deployment config | Mixed with duplicate config variant | Canonical frontend deployment | 2 | Low | No |
| `frontend/amplify.yml` | Duplicate frontend build config | Incorrect nested `cd frontend` flow | Keep as aligned fallback copy | 2 | Low | No |
| `.env.example` | Backend env template | Localhost defaults + real credentials pattern + CSV default | AWS-safe template with RDS DSN and bootstrap-only seed | 3 | Medium | Yes |
| `.gitignore` | Ignore patterns | Did not ignore root `.env` | Ignore sensitive env files | 2 | Low | Yes |
| `pyproject.toml` | Python deps | Includes Streamlit deps | Keep for transition window | 5 | Low | No |
| `README.md` | Project docs | Mixed architecture guidance (CSV default / Streamlit runtime) | Single-source AWS canonical docs | 3 | Medium | Yes |

## Auth/session findings
- Runtime auth is handled through `AuthService` and Postgres-backed user/role reads in API dependencies.
- Super-admin env credentials are now treated as **bootstrap seed only** through `init_data.py`, not a second runtime auth source.
- Session uses signed cookie payload (`core/session.py`) with server-side credential validation against Postgres.

## Remaining controlled-transition items
- Legacy Streamlit code in `easy_ecom/app/` remains in repo for reference/parity but is removed from runtime entrypoints.
- CSV store and CSV migration scripts remain for historical imports/reconciliation, not production persistence.

## Known blockers
- Repository policy currently blocks direct deletion/edit of tracked root `.env`; operationally it must be removed from version control in a follow-up privileged maintenance step.
