# Phase 1 — Current Architecture Assessment

## 1) Frontend structure (Next.js)

### What exists now
- App Router structure is under `frontend/app/` with authenticated routes grouped in `frontend/app/(app)/`.
- Authentication state is centralized in `AuthProvider`, and protected/public-only gating is enforced in `AuthRouteGuard`.
- Root layout wraps the app with auth context; protected layout wraps app pages in `AppShell` (sidebar + top header).
- Navigation currently includes Home, Dashboard, Products & Stock, Sales, Customers, Purchases, Settings.

### What is production-grade already
- Cookie-based auth bootstrap via `/auth/me` with `credentials: include` is in place.
- Guard UX includes loading/error states and retry path for transient backend/network failures.
- Login flow handles 401/5xx/network errors explicitly.

### Gaps / risks on frontend
- Most business pages are placeholders (`dashboard`, `sales`, `customers`, `purchases`, `settings`).
- No Next routes yet for finance, returns, admin despite legacy scope.
- `products-stock` API client still sends static dev headers (`X-User-Id`, `X-Client-Id`, `X-Roles`), which are unnecessary since backend reads cookie session.
- No shared module-level state/query caching strategy yet (e.g., React Query/SWR), which will matter as module complexity grows.

---

## 2) Backend structure (FastAPI + domain services)

### What exists now
- FastAPI app is created in `easy_ecom/api/main.py` with CORS + cookie credentials enabled.
- Dependency layer creates a `ServiceContainer` with auth, products, inventory, dashboard, and sales services.
- Session token is signed using `SESSION_SECRET` and parsed from cookie into typed user payload.
- Domain services are rich and already include business logic for:
  - catalog/variants/stock
  - inventory FIFO and deductions
  - sales lifecycle + payments + shipments
  - dashboard and metrics/reconciliation
  - returns/refunds
  - customers, clients, users, finance

### Critical integration gap
- Canonical router registration (`easy_ecom/api/routers/__init__.py`) currently mounts only:
  - health
  - auth
  - session
  - products-stock
- Routers for `dashboard`, `sales`, `products`, `inventory` exist but are **not included** in canonical `api_router`.
- Result: significant backend capability exists in code but is not reachable from production API surface.

---

## 3) DB/RDS integration path

### Current path
- Runtime store uses Postgres by default via `build_runtime_store(settings)`.
- `Settings` prioritizes `DATABASE_URL`; fallback DSN builder exists for host/port/db/user/password.
- SQLAlchemy engine/session factory are used for auth repo and tabular store operations.
- Runtime startup ensures table existence based on `TABLE_SCHEMAS` and writes to Postgres tables through `PostgresTableStore`.

### Important characteristics
- `PostgresTableStore` creates all columns as `TEXT`; typing is handled at service layer via pandas coercion.
- ORM models exist for core auth/product/inventory/import tables, while broader business tables are managed through tabular schema + dynamic table access.
- Migration file currently includes `users.password_hash` addition for secure auth transition.

### Risks to manage
- TEXT-everywhere schema can hide data quality issues (numeric/date coercion failures) until runtime.
- Two Postgres access styles coexist (ORM for auth repo + tabular DataFrame-based repositories).
- Need clear migration governance before adding new entities for purchases/finance depth.

---

## 4) Working flows available today

1. **Auth/session**: login, logout, current user checks via secure cookie.
2. **Products & stock workspace** (web): snapshot load and save for product + variants + stock posting.
3. **Underlying domain logic** (service layer): dashboard metrics, sales operations, returns logic, finance calculations, customer service.

---

## 5) Broken / missing flows (for production web)

1. Dashboard UI still placeholder; no mounted dashboard API route.
2. Sales page placeholder; mounted API only includes `/products-stock` and auth/session/health.
3. Customers page placeholder; no customers API route.
4. Purchases module undefined in current schema/UI/API.
5. Finance, returns, admin modules not in Next.js routes and not exposed as mounted API routers.
6. Tenant-admin workflows (client/user management) remain only in deprecated Streamlit.

---

## 6) Technical debt to respect carefully

- Legacy Streamlit is still the feature blueprint; replacement must preserve business semantics.
- Multi-tenant safety depends on consistent `client_id` scoping in every repository/service path.
- Sales/returns/finance side effects are interdependent; must preserve sequencing and auditability.
- Avoid large refactors of storage abstraction in Phase 2; use existing service contracts first.
- Avoid bypassing backend with direct frontend DB assumptions; maintain API boundary.

---

## 7) Safest implementation order (validated against current code)

1. **Stabilize API surface registration** (mount existing routers with RBAC/session checks).
2. **Dashboard web module** (read-heavy, low write risk) using existing service outputs.
3. **Customers module** (simple CRUD/search; dependency for sales UX quality).
4. **Sales module** (draft/order/payment lifecycle) after customers and dashboard telemetry are visible.
5. **Inventory dedicated workflows** (adjustments, lot explorer) while reusing current inventory service.
6. **Finance module web UI** (ledger + metrics) with strict role restrictions.
7. **Returns module** (approval/refund + restock side effects).
8. **Admin module** (tenant/user management with audit trail).
9. **Settings module** (profile/session/org preferences).
10. **Purchases advanced module** (new entities if required after confirming current operational model).

This order minimizes operational risk by shipping read surfaces first, then progressively introducing write-heavy lifecycle workflows.
