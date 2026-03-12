# Architecture Direction

## Application Structure
- **Frontend:** `frontend/` (Next.js) handles user workflows, form UX, and API consumption.
- **Backend:** `easy_ecom/api` and domain/data layers handle validation, authorization, orchestration, and persistence.
- **Database:** PostgreSQL is the runtime source of truth for auth, catalog, inventory ledger, transactions, and reporting.
- **Legacy Streamlit:** retained only for controlled transition, not canonical runtime.

## Data Flow
1. Frontend sends authenticated, tenant-context API requests.
2. Backend validates payload semantics and role/tenant authorization.
3. Backend executes business logic using domain services and repository adapters.
4. Database commits transactional state (including inventory ledger rows).
5. Backend returns normalized API contract responses to frontend.

## API Boundaries
- Frontend never bypasses backend for business writes.
- Backend owns business-rule enforcement and identity/tenant guarantees.
- Request/response schema changes must be versioned or coordinated across affected modules.

## Database Ownership Rules
- Schema constraints, indexes, and foreign keys protect business invariants.
- Variant-level stock truth is authoritative; product-level stock is derived only.
- Inventory ledger is immutable truth; denormalized fields are derived aids.

## AWS Deployment Direction
- Frontend: AWS Amplify.
- Backend: AWS App Runner.
- Database: AWS RDS PostgreSQL.
- Secrets/config: managed environment variables and secure secret injection.

## Performance and Cost Principles
- Optimize for correctness first, then efficiency.
- Prefer indexed tenant-scoped queries and narrow payloads.
- Avoid N+1 and full-table scans on hot tenant paths.
- Keep background processing minimal and justified.
- Favor simple managed patterns over costly complexity.
