# Phase 11 — Purchases / Stock-In module

## What was implemented

Phase 11 delivers a production-grade Purchases MVP across FastAPI + Next.js with PostgreSQL-backed persistence patterns aligned to existing Sales/Inventory/Finance modules.

Implemented:
- Tenant-scoped purchases API (`GET /purchases`, `GET /purchases/form-options`, `GET /purchases/{purchase_id}`, `POST /purchases`).
- Transactional purchase creation with header + line persistence.
- Stock-in impact recorded in `inventory_txn` (`txn_type=IN`, `source_type=purchase`, `source_id=purchase_id`).
- Finance impact recorded as a truthful expense row (`category=Purchases`) using caller-provided payment status (`paid/unpaid/partial`).
- Purchases list/search/detail and create workflow in frontend.
- Purchase numbering now tenant-configurable via settings sequence prefix (`purchases_prefix`).

## API endpoints added/changed

### Added
- `GET /purchases`
  - Tenant-scoped list.
  - Searchable by purchase number, date, reference, supplier, and product (line snapshot/id).
- `GET /purchases/form-options`
  - Tenant-scoped product/variant and supplier lookup for create form.
- `GET /purchases/{purchase_id}`
  - Tenant-scoped purchase detail with lines.
- `POST /purchases`
  - Creates purchase + lines, writes stock-in inventory movements, writes purchase expense.

### Changed
- Settings sequences now include `purchases_prefix` in:
  - `GET /settings/sequences`
  - `PATCH /settings/sequences`

## Schema/migration changes

Migration added: `easy_ecom/migrations/20260314_phase11_purchases_module.sql`
- Adds `tenant_settings.purchases_prefix` with default `PUR`.
- Adds `purchases` table.
- Adds `purchase_items` table.
- Adds indexes for list/query paths.

Model updates:
- `TenantSettingsModel` adds `purchases_prefix`.
- Added `PurchaseModel`, `PurchaseItemModel`.

## Stock and finance integrity rules

- All reads/writes are scoped to authenticated `client_id`.
- Product/supplier references are validated against tenant ownership before write.
- Purchase lines reject invalid quantities (`<=0`) and negative costs.
- Purchase creation writes header, lines, inventory stock-in movements, and finance expense in one DB transaction.
- Inventory stock-in uses canonical movement ledger (`inventory_txn`) and avoids duplicate stock logic.
- Finance impact intentionally uses existing expense/payables model (no fake AP subledger).

## Tenant isolation rules

- Endpoints require authenticated session user.
- Every query in purchases service includes tenant filter.
- Detail endpoints return 404 for cross-tenant IDs.
- Cross-tenant product/supplier references are rejected with 400 validation errors.

## Deferred by design (truthful scope control)

- PO approval workflow.
- Partial receiving / GRN lifecycle.
- Advanced supplier management portal.
- Landed-cost allocation and tax-engine behavior.
- Dedicated accounts payable ledger beyond existing finance expense model.
- Multi-warehouse receiving rules.

## Forward preparation

Phase 11 prepares cleanly for:
- Reporting (purchase trends, supplier spend, margin vs COGS baselines).
- AI-assisted operations (reorder suggestions, supplier cost anomaly detection).
- Future supplier workflow evolution (supplier scorecards, PO lifecycle) without replacing current truthful stock-in path.
