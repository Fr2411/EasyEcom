# Phase 2 – API Hardening Summary

## Scope completed

Phase 2 focused on backend API safety and tenant correctness without changing authentication architecture or frontend behavior.

### 1) Canonical router surface made explicit

The canonical API router now intentionally mounts all currently implemented business modules:

- `health`
- `auth`
- `session`
- `dashboard`
- `products`
- `products-stock`
- `inventory`
- `sales`

This closes the previous mismatch where business routers existed in code but were not all mounted in the canonical router.

### 2) Tenant isolation hardening

- Dashboard summary no longer accepts or honors a caller-supplied tenant override.
- Dashboard data is now always read from the authenticated session user `client_id`.

This removes a direct cross-tenant leakage path (`/dashboard/summary?client_id=...`).

### 3) Runtime backend selection hardened

- Historical note: runtime previously honored a CSV fallback path; the active runtime is now Postgres-only.
- This keeps test/staging behavior predictable and prevents accidental DB access in CSV-mode API flows.

### 4) API/auth/tenant tests expanded

Added/updated tests cover:

- authenticated smoke for mounted business routes
- unauthenticated rejection for protected business routes
- dashboard tenant lock to session tenant
- malformed session token missing `client_id`

## Tenant risks closed in Phase 2

1. **Dashboard cross-tenant query parameter override**: closed by enforcing session tenant only.
2. **Inconsistent canonical API exposure**: closed by mounting all intentional routers.
3. **Backend mode drift (CSV env trying Postgres)**: closed by respecting runtime backend setting.

## Canonical routers after hardening

Mounted in `easy_ecom/api/routers/__init__.py`:

- `/health`
- `/auth/*`
- `/session/*`
- `/dashboard/*`
- `/products/*` and `/stock/*`
- `/products-stock/*`
- `/inventory/*`
- `/sales/*`

## Intentionally deferred to Phase 3

- deeper role-matrix authorization expansion beyond current page-access checks
- DB-level tenant constraints/index migration work not required for current API safety fixes
- module-by-module completion for still-placeholder business domains
- centralized API error envelope standardization beyond current FastAPI defaults
