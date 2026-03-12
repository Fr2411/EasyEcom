# AGENTS.md

## Scope

This folder owns schema migrations, constraints, indexes, views, and data integrity protections.

---

## Rules

- Schema changes must protect tenant safety and stock correctness.
- Prefer explicit foreign keys, uniqueness rules, and indexes where they protect business truth.
- Migrations must be production-safe.
- Avoid destructive changes without a safe rollout path.
- Backfill legacy data carefully and explicitly.

---

## Inventory Model

- `variant_id` is the stock-holding identity.
- Inventory ledger rows must support variant-level traceability.
- Parent product may exist for catalog grouping, but not as the sole stock identity.

---

## Migration Discipline

Every migration should answer:
- what business rule it enforces
- what legacy data it impacts
- whether it is safe for current production traffic
- whether indexes are needed for new access patterns
