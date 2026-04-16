# Backend Status Baseline (TEA-31)

Date: 2026-04-16
Scope: backend architecture map, tenant/stock invariant risk scan, and priority actions

## 1) Coverage Map (reviewed this cycle)

### API boundary and auth flow
- `easy_ecom/api/dependencies.py`
- `easy_ecom/api/routers/catalog.py`
- `easy_ecom/api/routers/inventory.py`
- `easy_ecom/api/routers/sales.py`
- `easy_ecom/api/routers/sales_agent.py`

### Domain services and invariants
- `easy_ecom/domain/services/commerce_service.py`
- `easy_ecom/domain/services/sales_agent_service.py`
- `easy_ecom/domain/services/reports_service.py`
- `easy_ecom/domain/services/transaction_service.py`

### Persistence schema and migration posture
- `easy_ecom/data/store/postgres_models.py`
- `easy_ecom/migrations/versions/20260315_0001_product_ready_foundation.sql`
- `easy_ecom/migrations/versions/20260315_0004_variant_first_commerce_indexes.sql`

### Business contract docs cross-check
- `docs/business-rules.md`
- `docs/tenant-data-model.md`
- `docs/architecture.md`

## 2) Early High-Risk Findings (tenant isolation + variant-ledger correctness)

### P0-A: Tenant-safe referential integrity is not fully enforced at DB level
Risk: high

Evidence:
- Foundation migration defines tenant columns but references many relations by entity ID only, not `(client_id, id)` composite keys:
  - `product_variants.product_id` in `easy_ecom/migrations/versions/20260315_0001_product_ready_foundation.sql:218`
  - `purchase_items.variant_id` in `easy_ecom/migrations/versions/20260315_0001_product_ready_foundation.sql:262`
  - `inventory_ledger.variant_id` in `easy_ecom/migrations/versions/20260315_0001_product_ready_foundation.sql:273`
- Tenant-safe FK expectation is explicitly documented in `docs/tenant-data-model.md`.

Impact:
- Service-layer filters are strong, but DB constraints do not fully prevent cross-tenant relational mismatch under manual SQL or future query regressions.

Invariant status:
- Violates strict “tenant-safe foreign key rule” at DB enforcement layer.

### P0-B: Foundation migration contains destructive DDL in versioned path
Risk: high

Evidence:
- `easy_ecom/migrations/versions/20260315_0001_product_ready_foundation.sql:3` through `:27` drops core operational tables with `CASCADE`.

Impact:
- Unsafe replay blast radius for production-like environments if run incorrectly.

Invariant status:
- Conflicts with production-safe migration requirements.

### P1-A: Variant-level stock truth is correctly ledger-driven in critical flows
Risk: controlled (positive baseline)

Evidence:
- Stock map derives on-hand from `SUM(quantity_delta)` grouped by `variant_id` in `easy_ecom/domain/services/commerce_service.py:195`.
- Receipt flow writes `InventoryLedgerModel` with `variant_id` in `easy_ecom/domain/services/commerce_service.py:1503`.
- Adjustment flow writes `InventoryLedgerModel` with `variant_id` in `easy_ecom/domain/services/commerce_service.py:1579`.

Impact:
- Core invariant “stock lives at variant level and ledger is truth source” is implemented in critical inventory paths.

Invariant status:
- Pass in reviewed paths.

### P1-B: Authorization guard placement is split (router + service)
Risk: medium

Evidence:
- Router-level page checks exist on some overview endpoints (for example `easy_ecom/api/routers/inventory.py:24`) while many operational handlers rely on service checks.
- Service-level guard exists in commerce service (`easy_ecom/domain/services/commerce_service.py:138`) and is called in mutation/listing paths.

Impact:
- Current behavior is mostly safe, but enforcement style drift can cause future misses.

Invariant status:
- Security mostly intact; maintainability risk remains.

## 3) Architecture Map (backend data-flow)
- Request auth/session: `api/dependencies.py` parses signed session and constructs authenticated user context.
- Router layer: thin orchestration in `api/routers/*`.
- Domain layer:
  - `commerce_service.py` handles catalog/inventory/purchases/sales/returns
  - `sales_agent_service.py` handles AI-sales channel/conversation flows
  - `reports_service.py` computes aggregated reporting from transactional tables
- Persistence layer:
  - SQLAlchemy models in `data/store/postgres_models.py`
  - SQL migrations in `migrations/versions/*`

## 4) Invariant Checks Snapshot
- Tenant isolation in service queries: generally present (client filters observed across core service paths).
- Variant-first stock identity: present in ledger and transaction line handling paths reviewed.
- Ledger-based inventory truth: present in stock computation and write-paths reviewed.
- DB-level tenant-safe FK enforcement: incomplete (P0).
- Production-safe migration posture: incomplete (P0).

## 5) Priority Backlog (P0/P1)

### P0
1. Enforce tenant-safe composite FK constraints across transactional tables (TEA-33).
2. Replace destructive versioned migration behavior with production-safe migration/reset split (TEA-34).

### P1
1. Standardize authorization guard pattern across routers/services and add explicit regression tests (TEA-35).
2. Add DB CHECK constraints for core quantity/price invariants with data backfill validation (TEA-36).

## 6) Blockers Requiring PM/User Input
- No technical blocker to continue execution.
- TEA-34 resolved on 2026-04-16:
  - destructive DDL removed from versioned `20260315_0001_product_ready_foundation.sql`
  - explicit ops-only reset path added via `scripts/reset_rds_to_full_foundation.sh`
