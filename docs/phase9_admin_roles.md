# Phase 9 — Admin & Roles hardening

## Implemented scope

Phase 9 adds a real tenant-scoped Admin module with backend-enforced role checks and a production-facing Next.js UI:

- tenant admin API for users/roles
- user creation, profile updates, and active/inactive controls
- role assignment endpoint with escalation protections
- truthful deferred admin audit endpoint
- operational `/admin` UI for daily tenant user/role management

## Backend API endpoints

All endpoints require authenticated session + tenant context and are scoped to the current session `client_id`.

- `GET /admin/users`
- `POST /admin/users`
- `GET /admin/users/{user_id}`
- `PATCH /admin/users/{user_id}`
- `PATCH /admin/users/{user_id}/roles`
- `GET /admin/roles`
- `GET /admin/audit`

## Access control and tenant safety rules

- Allowed admin operators: `SUPER_ADMIN`, `CLIENT_OWNER`, `CLIENT_MANAGER`.
- Non-admin roles receive `403` on admin endpoints.
- All user read/write operations enforce `client_id` from session; cross-tenant lookup/update returns not found.
- Only `SUPER_ADMIN` can assign `SUPER_ADMIN` role.
- Self-deactivate is blocked for operational safety.
- Role checks are enforced in backend route handlers; frontend checks are only UX affordances.

## Data model and schema notes

- Reuses existing PostgreSQL canonical tables:
  - `users`
  - `user_roles`
- No migration required in this phase because required tables already exist in the current architecture.
- Email uniqueness is enforced in Admin service logic (global uniqueness to align with email-based login identity).

## Frontend delivery

- New operational route: `/admin`
- New admin workspace includes:
  - users list/table
  - role checkboxes per user
  - active/inactive toggle
  - create-user form
  - search/filter
  - empty/loading/access-denied states
- Navigation now includes Admin entry.

## Intentional deferrals

- Password reset/set by admin is deferred in this phase to avoid introducing insecure temporary-password flows.
- Tenant-scoped PostgreSQL audit event stream is not yet implemented; `/admin/audit` returns a truthful deferred response.

## Phase 9 to Phase 10 readiness

This phase prepares the platform for next modules (Settings hardening, Purchases, reporting, and AI-assisted ops) by:

- formalizing tenant-safe multi-user administration primitives
- strengthening backend as source of truth for role enforcement
- reducing operational risk from ad-hoc permission management
