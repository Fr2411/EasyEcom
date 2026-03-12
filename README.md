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


## Agent governance and decision boundaries

The repository now includes dedicated instruction files for Codex agents to keep work scoped and production-safe:

- Root governance: `AGENTS.md`
- Business/technical source docs: `docs/business-rules.md`, `docs/architecture.md`, `docs/tenant-data-model.md`, `docs/pricing-strategy.md`
- Scoped agent rulebooks: `frontend/AGENTS.md`, `backend/AGENTS.md`, `db/AGENTS.md`, `ai/AGENTS.md`
- Frontend rulebook now explicitly documents UI/UX operating principles for dense business workflows (tables, variant-aware forms, role-aware visibility, dashboard usefulness, and request-efficiency expectations).

When implementing changes, use these files as guardrails for tenant isolation, variant-level stock truth, auditability, and cross-layer contract consistency.

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

## Dashboard module delivery (Phase 3)

- `docs/phase3_dashboard_v2.md` — Dashboard v2 implementation details (real metrics, tenant-scoped API contract, deferred metrics, and UI building blocks).
- Dashboard frontend route (`/dashboard`) is now an operational read-first module backed by real API data (`GET /dashboard/overview`) with loading/error/empty states.

## Customers module delivery (Phase 4)

- `docs/phase4_customers_module.md` — Customers MVP implementation details (tenant-scoped CRUD API, PostgreSQL model/migration updates, and deferred CRM work).
- Customers frontend route (`/customers`) is now an operational module with tenant-scoped list/search/create/edit flows backed by backend APIs (`GET/POST/PATCH /customers`).

Phase 2 backend outcomes:
- Canonical FastAPI router now intentionally mounts all implemented business routers (`dashboard`, `products`, `products-stock`, `inventory`, `sales`) in addition to health/auth/session.
- Dashboard tenant access is locked to authenticated session `client_id` (query-string tenant override is ignored).
- Runtime storage selection now honors `STORAGE_BACKEND=csv` for local/test runs without forcing Postgres initialization.



## Inventory module delivery (Phase 6)

Phase 6 adds a production inventory operations module:
- Backend inventory APIs now include stock overview, movement ledger, item detail, and tenant-safe manual adjustment workflows.
- Inventory list projection is now focused on available/sellable stock rows, while quantities/values are merged from stock ledger and movement history using a canonical item_id (variant when present, otherwise product).
- Frontend now includes `/inventory` as the single stock workspace: find/create product, variant onboarding, available stock table, movement ledger, detail panel, and stock adjustment action flow.
- Existing sales-created stock reductions remain visible through the same ledger source (`inventory_txn`), with no duplicate subtraction logic.

## Sales module delivery (Phase 5)

- `docs/phase5_sales_module.md` — Sales MVP implementation details (tenant-scoped API endpoints, PostgreSQL schema additions, transactional stock impact, and deferred scope).
- Sales frontend route (`/sales`) is now an operational module with recent list/search, phone-first customer capture (auto-prefill/create), multi-line create workflow, and detail inspection backed by real backend APIs (`GET/POST /sales`, `GET /sales/{sale_id}`, `GET /sales/form-options`).


## Finance module delivery (Phase 7)

- `docs/phase7_finance_module.md` — Finance MVP implementation details (tenant-scoped APIs, PostgreSQL schema updates, expense tracking, and truthful metric rules).
- Finance frontend route (`/finance`) is now an operational module with summary cards, expense create/list flow, receivables/payables tables, and transaction history backed by backend APIs (`GET /finance/*`, `POST/PATCH /finance/expenses`).


## Returns module delivery (Phase 8)

- `docs/phase8_returns_module.md` — Returns MVP implementation details (tenant-scoped API endpoints, PostgreSQL schema additions, stock restoration and sale-finance adjustment integrity rules, and deferred scope).
- Returns frontend route (`/returns`) is now an operational module with recent list/search, sale lookup, line-based return creation with eligibility validation, and return detail inspection backed by real backend APIs (`GET/POST /returns`, `GET /returns/{return_id}`, `GET /returns/sales-lookup`, `GET /returns/sales/{sale_id}`).

## Admin & roles hardening delivery (Phase 9)

- `docs/phase9_admin_roles.md` — Admin & Roles hardening implementation details (tenant-scoped admin APIs, backend role enforcement, and deferred audit/password reset boundaries).
- Admin frontend route (`/admin`) is now an operational module with tenant users list, role assignment controls, active/inactive toggles, add-user workflow, and admin access-denied/empty/loading states backed by backend APIs (`GET/POST/PATCH /admin/users`, `PATCH /admin/users/{user_id}/roles`, `GET /admin/roles`, `GET /admin/audit`).


## Settings module delivery (Phase 10)

- `docs/phase10_settings_module.md` — Settings MVP implementation details (tenant-scoped business profile APIs, operational preferences persistence, sequence preference storage, access-control boundaries, and deferred activation items).
- Settings frontend route (`/settings`) is now an operational module with business profile, preferences, sequence settings, and tenant context sections backed by backend APIs (`GET/PATCH /settings/business-profile`, `GET/PATCH /settings/preferences`, `GET/PATCH /settings/sequences`, `GET /settings/tenant-context`).


## Purchases module delivery (Phase 11)

- `docs/phase11_purchases_module.md` — Purchases MVP implementation details (tenant-scoped purchase APIs, PostgreSQL schema additions, stock-in inventory impact, finance expense/payables integration, and deferred procurement complexity).
- Purchases frontend route (`/purchases`) is now an operational module with recent list/search, purchase create workflow, line-item stock-in editor, and purchase detail inspection backed by real backend APIs (`GET/POST /purchases`, `GET /purchases/{purchase_id}`, `GET /purchases/form-options`).



## Reporting & Analytics delivery (Phase 12)

- `docs/phase12_reporting_analytics.md` — Reporting & Analytics MVP implementation details (tenant-safe APIs, truthful metric derivation, and deferred metric boundaries).
- Reports frontend route (`/reports`) is now an operational analytics module with date range filters, overview KPIs, and sectioned sales/inventory/products/finance/returns/purchases reporting backed by backend APIs (`GET /reports/*`).
- Reports frontend now uses partial-load behavior (`Promise.allSettled`) so individual section failures show targeted warnings instead of blanking the full page when overview is available.


## AI readiness foundation (Phase 13)

- `docs/phase13_ai_readiness.md` — AI-readiness implementation details (tenant-scoped read-only context contracts, automation-safe inbound inquiry hook, and deferred external-channel scope).
- Backend now exposes typed AI-safe context APIs (`/ai/context/*`) and internal automation hook entrypoint (`POST /ai/hooks/inbound-inquiry`) grounded on canonical PostgreSQL business data with strict session tenant isolation.


## External channel integration foundation (Phase 14)

- `docs/phase14_channel_integration_foundation.md` — channel integration foundation details (tenant-scoped channel registry, verified inbound webhook ingestion, conversation/message persistence, outbound dispatch intent preparation, and AI-safe hook compatibility).
- Backend now exposes protected channel management + communication log APIs under `/integrations/*` and a signature-verified external ingestion route (`POST /integrations/inbound/{provider}`) that resolves tenant/channel safely.
- Frontend route `/integrations` is now an operational admin module for channel setup, status visibility, and recent communication event previews.

## Human-reviewed AI response workflow (Phase 15)

Phase 15 adds a controlled AI-assisted response workflow for external channel conversations:

- Tenant-scoped AI review inbox (`/ai/review`) for inbound conversations
- Grounded AI candidate generation from Phase 13 context services
- Human edit/approve/reject flow with explicit approval gate before send
- Send path routed through Phase 14 outbound preparation
- Persisted audit trail of AI draft, final text, approver/sender, and send result

See `docs/phase15_human_reviewed_ai_workflow.md` for endpoint and state-model details.

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


## Controlled partial automation (Phase 16)

Phase 16 introduces controlled partial automation on top of channel integrations + AI review:
- Tenant-scoped automation policy controls (enable/disable, emergency stop, per-category toggles).
- Explicit automation evaluate/run APIs with low-risk category gating.
- Auto-send only for policy-approved, grounded low-risk responses; otherwise fallback to human review drafts.
- Auditable automation decision history and queue endpoints.

See `docs/phase16_controlled_partial_automation.md` for full implementation and safety details.


## Frontend design system refresh (Next.js app shell)

The production Next.js frontend (`frontend/`) now uses a shared visual design system intended for a premium SaaS admin experience while preserving all existing routes, API contracts, and auth behavior:

- **Tokenized foundation:** centralized color palette, typography rhythm, border radii, elevation shadows, and surface/background states in `frontend/app/globals.css`.
- **Global app shell:** grouped icon sidebar navigation, contextual top header, stronger active states, and improved utility/action areas through reusable layout components.
- **Session actions in navigation:** left sidebar now includes a persistent bottom-positioned **Log out** control that posts to `/auth/logout` and redirects users to `/login`, so sign-out is always accessible from protected workspace routes.
- **Reusable primitives:** harmonized card, table, form field, badge, and status patterns reused across all operational modules (dashboard, inventory, sales, customers, finance, settings, integrations, AI review, etc.) to reduce style drift.
- **Dashboard/UI polish:** executive KPI card presentation, clearer hierarchy for list/table sections, refined spacing, and cleaner empty/loading/error visual states.
- **Auth experience:** redesigned login screen with a branded premium split layout while keeping existing sign-in logic, API usage, and redirect behavior unchanged.

This update intentionally focuses on design language and maintainability (shared style tokens + reusable class patterns) rather than changing business logic.


## Inventory quantity model (single-location)

Inventory is modeled per-tenant as a **single location** with separated quantities:

- `on_hand_qty`: physically received stock in possession.
- `incoming_qty`: pending inbound stock not yet received into on-hand.
- `reserved_qty`: currently defaults to `0` (reservation-ready field for future).
- `sellable_qty`: `max(0, on_hand_qty - reserved_qty - safety_stock_qty)` with `safety_stock_qty=0` for now.
- `stock_value`: computed from on-hand lots only (`on_hand_qty * unit_cost` at lot level).
- Shared stock semantics are centralized in `easy_ecom/domain/services/stock_policy.py` and reused by Inventory, Sales, Dashboard/metrics, Reports, and Purchases services to keep cross-tab stock totals consistent.
- Inventory UI now shows available/sellable rows by default and pairs this with the integrated "Find or create product" flow to add new or existing product stock from one tab.
- Product search autocomplete in the Inventory "Find or create product" workflow now enforces a minimum of 1 character before showing results, preventing empty-query result lists and clearing suggestions when the input is reset.
- Product identity "Features (comma-separated)" input now preserves in-progress commas while typing so users can enter multiple features without delimiter loss.
- Manual adjustments stay available via `POST /inventory/adjustments` (`stock_in`, `stock_out`, `correction`) and continue to write movement ledger entries used by Sales visibility.

## Phase 17: Multi-tenant stock/returns schema hardening (audit + refactor)

This repository now adopts a stricter domain contract for inventory and document integrity in shared-table PostgreSQL deployments.

### Canonical business model

- `products`: catalog parent/base records only (non-stock-holding).
- `product_variants`: stock-holding SKU records.
- `purchases` + `purchase_items`: procurement documents.
- `inventory_txn`: single source of truth stock ledger.
- `sales_orders` + `sales_order_items`: sales documents.
- `sales_returns` + `sales_return_items`: return documents.
- `shipments`: fulfillment documents.

### Root cause summary from audit

- Legacy schema drift from CSV-era design kept many business fields as `VARCHAR/TEXT` and avoided foreign keys.
- Variant identity was overloaded into `product_id` in transaction tables, causing ambiguous joins and weak validation.
- Duplicate return domains (`returns/return_items` and `sales_returns/sales_return_items`) were both present, increasing long-term divergence risk.
- Product variant options were duplicated both as CSV columns on `products` and as rows in `product_variants`.

### Key decisions

- Variant-aware stock movements now persist both:
  - `product_id` (catalog parent)
  - `variant_id` (actual SKU when applicable)
- Service-level stock calculations now resolve by SKU-first identity through `inventory_txn` (with backward-compatible fallback for legacy rows).
- `sales_returns/sales_return_items` remains the active returns domain. `returns/return_items` are treated as legacy/deprecated compatibility tables.
- Product CSV variant columns (`sizes_csv/colors_csv/others_csv`) are deprecated as storage fields on `products`, but `ProductService.create` still consumes provided values to bootstrap `product_variants` rows for backward-compatible flows.

### Migration plan and sequencing

Use migration file:
- `easy_ecom/migrations/20260319_phase17_multi_tenant_stock_hardening.sql`

Recommended rollout order in production:
1. Deploy app code that can read/write both old and new representations (done in this refactor).
2. Apply schema migration to add variant columns, backfill, and tenant-safe FK/index/uniqueness constraints.
3. Run cleanup SQL checks (below) and remediate violating rows.
4. Enforce stricter typing migrations in a follow-up release:
   - convert timestamps to `TIMESTAMPTZ`
   - convert quantity/amount/cost fields to `NUMERIC(18,4)`
   - convert booleans to `BOOLEAN`
5. Archive and drop deprecated `returns/return_items` only after no reads/writes and historical migration sign-off.

### Manual cleanup queries (required before strict FK/type enforcement)

1. Orphan variants (tenant mismatch):
```sql
SELECT pv.client_id, pv.variant_id, pv.parent_product_id
FROM product_variants pv
LEFT JOIN products p
  ON p.client_id = pv.client_id
 AND p.product_id = pv.parent_product_id
WHERE p.product_id IS NULL;
```

2. Legacy return tables usage check:
```sql
SELECT COUNT(*) FROM returns;
SELECT COUNT(*) FROM return_items;
```

3. Post-backfill unresolved stock identity rows:
```sql
SELECT client_id, txn_id, product_id, variant_id
FROM inventory_txn
WHERE COALESCE(variant_id, '') = ''
  AND product_id IN (SELECT variant_id FROM product_variants);
```

4. Cross-tenant reference validation sample:
```sql
SELECT soi.order_item_id, soi.client_id, soi.order_id
FROM sales_order_items soi
LEFT JOIN sales_orders so
  ON so.client_id = soi.client_id
 AND so.order_id = soi.order_id
WHERE so.order_id IS NULL;
```

### Deprecated structures (phase-out)

- `returns`, `return_items`: deprecated in favor of `sales_returns`, `sales_return_items`.
- `products.sizes_csv`, `products.colors_csv`, `products.others_csv`: deprecated legacy option-storage.

Do not build new features on deprecated structures.

## Inventory frontend contract note

- Inventory UI now expects the backend stock shape fields: `on_hand_qty`, `incoming_qty`, `reserved_qty`, and `sellable_qty` (instead of legacy `available_qty`).
- The inventory workspace formats stock and currency values through defensive numeric formatters so malformed/null API values render as `0.00` instead of crashing the page.
- This keeps stock adjustment and movement ledger flows intact while matching the current inventory API response model.



## Frontend ↔ API ↔ RDS production readiness (diagnostic checklist)

If UI widgets show placeholders/empty values despite data in RDS, verify this exact chain end-to-end:

1. **Backend storage mode must be Postgres in production**
   - Set `STORAGE_BACKEND=postgres` and provide a valid `DATABASE_URL` (or full `POSTGRES_*` values).
   - If backend runs with CSV mode, several API modules intentionally return `501` because MVP endpoints are Postgres-only.

2. **Frontend API base URL must point to the FastAPI origin**
   - Set `NEXT_PUBLIC_API_BASE_URL` to your deployed API URL (for example `https://api.yourdomain.com`).
   - Keep this value aligned per environment (dev/staging/prod) so the browser does not call the wrong host.

3. **Cross-origin cookie auth must be configured for browser sessions**
   - Keep `credentials: include` in frontend calls and allow credentials in API CORS.
   - Configure backend cookie/security settings for HTTPS deployments:
     - `SESSION_COOKIE_SECURE=true`
     - `SESSION_COOKIE_SAMESITE=none` (cross-site SPA/API deployments)
     - `SESSION_COOKIE_DOMAIN` matching your top-level domain when needed.
   - Ensure `CORS_ALLOW_ORIGINS` contains your frontend domain(s).

4. **Run DB schema migrations before validating UI**
   - Apply all SQL files under `easy_ecom/migrations/` in order.
   - Missing tables/columns will surface as empty grids or API 5xx errors in modules like sales, finance, returns, purchases, and reports.

5. **Validate with a quick API smoke sequence after deploy**
   - Login: `POST /auth/login`
   - Session: `GET /auth/me`
   - Dashboard: `GET /dashboard/overview`
   - Module checks: `GET /sales`, `GET /finance/overview`, `GET /inventory`, `GET /products-stock/snapshot`
   - If any return `501`, re-check backend storage mode and migration status.

6. **Recommended hardening for client-facing production**
   - Add request/response logging and correlation IDs at API gateway and app level.
   - Add health checks for DB connectivity, migration version, and session signing config.
   - Add frontend error telemetry (Sentry/Datadog) and alert on sustained API/network failures.
   - Add synthetic checks for core user flows: login → dashboard → sales list → inventory list.

This checklist keeps your existing architecture intact while removing the common integration gaps that make UI screens appear as placeholders.

## Phase 18: Variant-Only Operational Stock Identity Cleanup

This release enforces a single operational rule across stock-affecting flows: **stock lives on `product_variants.variant_id`**, while `products.product_id` remains catalog/reporting identity.

### What changed
- Added canonical backend aggregation (`SaleableItemsService`) for saleable stock by variant (`variant_id`, `product_id`, `sku`, `barcode`, product + variant names, available qty, price).
- Sales API and sales UI now operate on `variant_id` for cart lines, stock validation, and stock deduction.
- Sales item search now targets user-facing identifiers only: SKU, barcode, product name, variant name.
- Empty search query no longer dumps large saleable-item lists in sales item picker.
- Product variant model now includes optional `barcode`.
- SKU generation is now human-readable and tenant-scoped (`<PRODUCTCODE>-NNN`), and default variant creation remains automatic when no options are supplied.

### Migration highlights
- New migration: `20260320_phase18_variant_operational_identity.sql`.
- Adds `product_variants.barcode`, enforces non-null SKU storage, backfills legacy stock rows from parent products to variants when exactly one variant exists, and records unresolved ambiguous rows into `stock_identity_review_queue` for manual review.

### Legacy compatibility
- Parent `product_id` is retained in transaction rows for parent rollups and compatibility.
- Operational writes/reads in the updated sales flow now always bind to `variant_id`.


## Stock Identity Rule (Variant-Operational)

For all **new** operational data writes:

- `products` is the parent catalog entity.
- `product_variants` is the only sellable stock identity.
- Stock-affecting writes (`inventory_txn`, `purchase_items`, `sales_order_items`, `sales_return_items`) must include `variant_id`.
- `product_id` remains a parent/reporting reference only.

### Canonical stock source

The backend canonical source for saleable availability is `SaleableItemsService.list_saleable_variants(...)`, used by sales and purchase selectors. Search supports SKU, barcode, product name, and variant name.

### UX behavior

- Sales and purchases item pickers operate on variant IDs.
- Empty lookup query does not return a full product dump by default.

## Variant-first inventory write invariants (catalog + inventory + sales)

Recent hardening enforces variant identity for all future stock-affecting writes:

- **Catalog product upsert (`/products/upsert`) now guarantees at least one variant for new products.**
  - If a new product is submitted with blank variant attributes, EasyEcom auto-creates exactly one `Default` variant.
  - If opening stock (`qty` + `unit_cost`) is provided on blank variant rows during create, opening stock is written once against that default variant.
  - This prevents the previous failure mode where parent `products` saved successfully but no `inventory_txn` opening row was created.

- **Inventory writes are now variant-required.**
  - `variant_id` is required for `add_stock`, `create_incoming_stock`, `deduct_stock`, manual adjustments, inbound creation, and `/inventory/add` payloads.
  - `product_id` remains required as parent/reporting snapshot context.
  - Stock-affecting write calls that only rely on parent `product_id` are blocked by validation.

- **Sales stock path remains canonical and variant-ledger based.**
  - Saleable stock discovery and availability checks continue to read from variant-level ledger totals.
  - Sales OUT inventory transactions continue to persist with `variant_id`.

- **Data quality guardrails:**
  - Database migration `20260321_phase19_variant_strict_stock_writes.sql` enforces non-empty `variant_id` on `inventory_txn` rows.
  - Runtime validation now aligns with this invariant so malformed writes fail fast.

This means newly-created products cannot enter saleable inventory state with stock but without a variant, and future inventory movements are always variant-addressable.
