# TEA-31 Backend and Data-Flow Baseline Audit (2026-04-16)

## Scope
- Tenant isolation and authorization boundaries
- Variant-first stock ownership and inventory truth
- Data-flow consistency across API -> service -> persistence
- Migration and schema safety for production

## What Was Reviewed
- API routers and dependency auth path
- Commerce, sales-agent, reports, and transaction services
- Core commerce foundation migrations and table constraints
- Existing backend business-rule docs

## Baseline Summary
- Variant-first stock logic is implemented in service layer and ledger writes are variant-scoped.
- Tenant filtering is implemented broadly in service queries.
- Main gaps are in DB-level tenant-safe referential integrity and migration safety posture.

## Findings

### 1. High: Tenant-safe FK rule is enforced in app code but not strongly enforced in DB constraints
Evidence:
- Many tables carry `client_id`, but FK references use only entity IDs (for example `product_variants.product_id`, `purchase_items.variant_id`, `inventory_ledger.variant_id`) without composite tenant-safe FK coupling in the foundation migration: `20260315_0001_product_ready_foundation.sql` lines 215-241, 258-266, 270-278.
- The business rule explicitly requires tenant-safe FK behavior for transactional rows: `docs/tenant-data-model.md`.

Risk:
- A future query bug or manual SQL path can create cross-tenant relational links that pass simple ID-based FK checks.
- This weakens the non-negotiable tenant-isolation guarantee.

Recommendation:
- Add composite unique constraints and composite FKs keyed by `(client_id, <entity_id>)` for tenant-bound relations.
- Backfill validation query before migration to detect any existing mismatches.

### 2. High: Foundation migration is destructive and not production-safe if accidentally reapplied
Evidence:
- `20260315_0001_product_ready_foundation.sql` starts with broad `DROP TABLE IF EXISTS ... CASCADE` across core operational tables (lines 3-27).

Risk:
- Any mistaken execution path for this migration script can erase production data.
- Conflicts with required production-safe migration behavior.

Recommendation:
- Replace destructive bootstrap behavior with additive/idempotent DDL migration strategy.
- Guard destructive reset logic behind explicit one-off reset scripts (outside versioned migrations).

### 3. Medium: Authorization checks are split between router and service, creating enforcement drift risk
Evidence:
- Routers often protect only `/overview` while operational endpoints rely on service-internal checks (e.g., `catalog.py` line 22 vs lines 26-92, `inventory.py` line 24 vs lines 28-113, `sales.py` line 25 vs lines 29-165).
- Service-layer checks exist and work (e.g., `commerce_service.py` line 138 and callers such as lines 1558+).

Risk:
- Future endpoints can accidentally miss authorization checks if contributors assume a single enforcement location.

Recommendation:
- Standardize one authoritative pattern:
  - either router-level `require_page_access` for every handler,
  - or a single shared dependency decorator for module routers.
- Keep service checks as defense-in-depth for critical mutations.

### 4. Medium: Core quantity/price invariants depend mostly on app validation, not DB CHECK constraints
Evidence:
- Schema defines numeric fields for prices/quantities in foundation migration but without corresponding non-negative/check constraints for critical business invariants (`20260315_0001_product_ready_foundation.sql` around products, variants, purchase items, ledger).

Risk:
- Direct SQL writes or future buggy code paths can persist invalid negatives/inconsistent values, undermining stock and pricing correctness.

Recommendation:
- Add targeted DB CHECK constraints for non-negative quantity/price fields where domain rules require it.
- Keep service validation; use DB checks as final guardrail.

## Positive Controls Observed
- Variant-level inventory truth from ledger totals in stock map computation: `commerce_service.py` lines 195-214.
- Variant-level auditable stock movement writes for receipts and adjustments: `commerce_service.py` lines 1502-1518 and 1578-1594.
- Tenant filters are consistently applied in most high-risk query paths.

## Proposed Sub-Issue Sequence
1. P1 (High): Enforce tenant-safe composite FK strategy in commerce transactional schema.
2. P2 (High): Refactor destructive foundation migration path into production-safe migration/reset split.
3. P3 (Medium): Unify authorization enforcement pattern across routers/services and add regression tests.
4. P4 (Medium): Add DB-level CHECK constraints for inventory/pricing invariants.

## Exit Criteria for TEA-31
- Audit report documented with actionable, prioritized backlog.
- Follow-up execution tracked as child issues under TEA-31.
