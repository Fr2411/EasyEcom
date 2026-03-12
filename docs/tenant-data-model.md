# Tenant-Safe Data Model (Critical)

## Core Identity Semantics
- **Product = catalog-level identity** (descriptive grouping, merchandising, categorization).
- **Variant = stock-level identity** (actual saleable SKU and option combination).
- **Stock exists only at variant level**.

## Transactional Integrity Requirements
- Every inventory-affecting event must create an inventory ledger row.
- Ledger rows must include tenant-safe relationships (direct `tenant_id` and relevant business keys).
- Sales, purchases, and returns must reference variant identity for stock correctness.

## Tenant-Safe Foreign Key Rule
Every transactional row must carry tenant-safe foreign keys such that:
- joins can always enforce tenant boundaries,
- accidental cross-tenant linkage is prevented,
- reporting remains tenant-correct under all query paths.

## Source of Truth
- The inventory ledger is the truth source for stock state.
- Any summary table or cached quantity is derived data and must be reconcilable.
- If a mismatch exists, ledger truth wins.
