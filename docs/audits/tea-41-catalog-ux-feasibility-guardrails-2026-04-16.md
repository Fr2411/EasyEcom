# TEA-41 Catalog UX Proposal Feasibility + API/Contract Guardrails (2026-04-16)

## Scope Note
- TEA-40 has no posted proposal/comment artifact yet.
- This review is therefore a guardrail-first feasibility package based on current production code paths:
  - `frontend/components/commerce/catalog-workspace.tsx`
  - `frontend/components/commerce/inventory-workspace.tsx`
  - `easy_ecom/api/routers/catalog.py`
  - `easy_ecom/api/routers/inventory.py`
  - `easy_ecom/api/schemas/commerce.py`
  - `easy_ecom/domain/services/commerce_service.py`

## Current Contract Baseline (Must Not Regress)
- Tenant isolation is enforced through `client_id`-scoped reads/writes in service layer and DB constraints.
- Saleable stock identity is `variant_id` only.
- Inventory truth is ledger-derived (`InventoryLedgerModel`), not manual mutable counters.
- Receive stock writes auditable purchase + ledger records.
- Catalog product save requires at least one variant (`At least one variant is required`).
- Stock adjustments and receipt posting enforce non-negative availability invariants.

## Feasibility Matrix (Mapped To Typical TEA-40 UX Change Classes)

| Proposed UX class | Feasibility | Backend/API impact | Guardrail notes |
|---|---|---|---|
| 1. Reorder catalog screen sections, labels, helper text, visual hierarchy | Go | No backend change | Safe if semantics remain product=parent, variant=saleable SKU |
| 2. Convert add product + variant flow to stepper/wizard UX | Go with conditions | Optional API shape helper only | Keep final save atomic through existing `POST/PUT /catalog/products`; do not split stock semantics into product-level inventory |
| 3. Stronger match-first search (SKU/barcode/variant exact-first) | Go | No backend change (already supported by workspace search behavior) | Preserve deterministic exact-first staging behavior |
| 4. Auto-generate variants from option matrix with preview | Go | No backend change | Existing generator + server duplicate-signature validation is aligned |
| 5. Save-draft UI cues before commit | Go | No backend change required | Must remain client-side draft only until explicit save |
| 6. Inline editing of supplier / reorder level from inventory tables | Go | Already supported by `PATCH /inventory/inline-update` | Keep reorder level non-negative validation |
| 7. Unify “receive stock” into guided intake flow | Go | Already supported by `POST /inventory/receipts` + `intake/lookup` | Must keep ledger event creation per line; no hidden stock mutation paths |
| 8. Product-level stock badges/summary prominently shown | Caution | No API change required for display, but copy constraints required | Any “stock” label must resolve from variant aggregates and not imply product owns stock |
| 9. Quick actions to archive/delete variants from grid | Risky / Approval needed | Potential backend policy update | Current policy blocks archiving variants with stock/reservations; destructive actions need explicit approval + migration strategy |
| 10. Bulk import/edit variants (CSV or mass editor) | Risky / Approval needed | New endpoint(s), stricter validation, rollback behavior | High risk for tenant leakage and duplicate SKU conflicts; requires staged design + tests before execution |
| 11. Auto-create stock while creating product in catalog flow | No-Go (without redesign) | Would violate current separation | Stock must remain inventory-ledger driven through receipts/adjustments, never implicit in catalog save |
| 12. Reduce required fields in first-time flow | Go with conditions | No API change if still satisfies schema | `product_name` and at least one variant remain required contract |

## API/Schema Constraints To Preserve
- `CatalogUpsertRequest`:
  - requires `identity.product_name`
  - requires `variants[]` non-empty
- `CatalogVariantInput` supports optional `variant_id`; duplicate option signatures are rejected server-side.
- `ReceiveStockRequest`:
  - posts stock only through explicit `action=receive_stock`
  - `save_template_only` exists but must not post ledger movement
- `InventoryAdjustmentRequest` requires `variant_id` and non-zero quantity delta.

## Minimal Safe Backend Adjustments (Only If TEA-40 Needs Them)
1. API compatibility aliasing for UI stepper payloads:
- Keep current canonical payloads.
- Add narrow compatibility parsing only when unavoidable.
- Do not fork business logic.

2. Read-model enrichment only:
- Add extra response metadata fields for UX chips/badges if needed.
- Keep write contracts unchanged unless business rule requires it.

3. Explicit copy-safe contract notes in frontend types:
- Enforce variant-first stock wording in UI text constants.

## Test Impact Notes (Required If Any Contract Touch Happens)
- `easy_ecom/tests/test_api_inventory.py`:
  - receipt posting still creates ledger and keeps variant-level identity.
  - inline update + low-stock paths remain valid.
- `easy_ecom/tests/test_api_auth.py` and module access checks:
  - no regression in Catalog/Inventory page authorization.
- Add contract tests if request/response shape changes are introduced.

## High-Risk Items Requiring Explicit User Approval Before Execution
1. Any UX proposal that implies product-level stock ownership.
2. Any bulk edit/import write path that bypasses existing per-line validation and auditability.
3. Any destructive variant/archive policy relaxation when stock/reservations exist.
4. Any split-save architecture that writes partial catalog/inventory state in separate implicit steps.

## PM Decision Package (Go/No-Go)
- Go now (safe, no backend change):
  - visual hierarchy redesign, guided copy, search clarity, variant generator UX polish, staged draft clarity.
- Go with bounded backend support:
  - optional read-model enrichment or compatibility parser, with tests.
- Hold for approval:
  - bulk mutation flows, destructive archive/delete behavior, semantics-changing stock shortcuts.

## Final Note
- This TEA-41 package is execution-ready for PM review now.
- Final per-item mapping should be refreshed once TEA-40 posts its concrete P0/P1/P2 recommendation list.
