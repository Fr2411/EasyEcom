# Phase 6 — Inventory Ledger / Stock Movement Module

## What was implemented

Phase 6 delivers a tenant-scoped operational Inventory module across FastAPI and Next.js:

- Added canonical inventory APIs for stock overview, movement ledger, item detail, and manual adjustments.
- Added strict tenant checks so inventory item references and all reads/writes are constrained to authenticated `client_id`.
- Added adjustment workflow support for stock-in, stock-out, and correction adjustments with reason/note/reference metadata.
- Added production-facing inventory UI (`/inventory`) with stock table, movement ledger, filters, detail panel, and adjustment form.
- Preserved existing `/inventory/add` endpoint for backward compatibility.

## API endpoints added/changed

### Added

- `GET /inventory`
  - Returns stock overview grouped by product/variant inventory item.
  - Supports `q` search.

- `GET /inventory/movements`
  - Returns movement ledger entries with signed quantity and per-item running balance.
  - Supports `item_id`, `movement_type`, `start_date`, `end_date`, `limit` filters.

- `GET /inventory/{item_id}`
  - Returns stock summary + recent movement history for a single item.

- `POST /inventory/adjustments`
  - Accepts:
    - `stock_in` (positive quantity)
    - `stock_out` (positive quantity)
    - `correction` (signed quantity delta)
  - Optional fields include `unit_cost`, `reason`, `note`, `reference`.

### Preserved

- `POST /inventory/add`
  - Kept for backward compatibility with existing flows.

## Schema / migration changes

- No schema migration required in this phase.
- Reused existing canonical inventory transaction storage (`inventory_txn`) and existing product/variant tables.

## Inventory integrity rules in this module

- All endpoints require authenticated user context.
- All reads and writes are scoped by `user.client_id`.
- Adjustment item references are validated against tenant-owned products/variants.
- Invalid adjustment payload shapes are rejected.
- Stock-out and negative corrections use existing FIFO deduction path to prevent bypassing current stock logic.
- Movement history is generated from persisted transaction rows; no synthetic/fake records are introduced.

## Tenant isolation rules

- Stock overview and movement queries are always filtered by authenticated `client_id`.
- Detail reads only return tenant-owned item data.
- Adjustments reject cross-tenant item references.

## Sales and manual adjustment interaction

- Sales stock reductions already written to `inventory_txn` (source `sale`) are surfaced by `GET /inventory/movements` and item detail history.
- Manual adjustments write inventory movement transactions through the existing inventory service.
- No duplicate sale subtraction logic was added.

## Intentionally deferred

- Multi-warehouse transfer workflows.
- Reservation engine.
- Purchase-order/GRN lifecycle orchestration.
- Batch/lot expiry and valuation extensions.
- Forecasting and dead-stock analytics.

## How this prepares Phase 7+

Phase 6 provides auditable stock movement primitives needed for:

- Finance reconciliation (COGS/profit explainability).
- Returns workflows requiring stock restoration traces.
- Admin and audit surfaces that need trustworthy per-tenant stock movement history.
