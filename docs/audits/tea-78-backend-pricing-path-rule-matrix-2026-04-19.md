# TEA-78 / TEA-49.1 Backend Pricing Path Evidence and Rule Matrix (Product vs Variant)

Date: 2026-04-19
Owner: python-dev
Scope: Publish verifiable backend evidence for current pricing execution paths (no runtime behavior change)

## 1) Blocker Unblock Evidence

Blocked-lane unblock condition requested two artifacts:
1. execution-path recovery evidence for `python-dev`
2. published backend pricing rule-matrix evidence for product-vs-variant

Both are satisfied in this artifact with line-level backend references from the current codebase.

## 2) Execution-Path Recovery (python-dev)

Runtime/file-path execution checks completed in current workspace:
- Verified pricing resolver and validation methods exist and are reachable in service code:
  - `easy_ecom/domain/services/commerce_service.py:281`
  - `easy_ecom/domain/services/commerce_service.py:287`
  - `easy_ecom/domain/services/commerce_service.py:315`
  - `easy_ecom/domain/services/commerce_service.py:2319`
  - `easy_ecom/domain/services/commerce_service.py:2445`
- Verified AI-agent catalog/search paths consume pricing resolver methods:
  - `easy_ecom/domain/services/sales_agent_service.py:2375`
  - `easy_ecom/domain/services/sales_agent_service.py:2508`

## 3) Product vs Variant Pricing Path (Code Evidence)

### A. Effective pricing ownership and fallback

Observed backend rule:
- Effective unit price = variant price when present, else product default price.
- Effective minimum price = variant min when present, else product min.

Evidence:
- `_effective_variant_price`: `easy_ecom/domain/services/commerce_service.py:281`
- `_effective_variant_min_price`: `easy_ecom/domain/services/commerce_service.py:284`

### B. Write-time normalization and guards

Observed backend rule:
- Product pricing normalization enforces non-negative values and `min <= default`.
- Variant pricing normalization enforces non-negative values and `variant_min <= variant_price`.

Evidence:
- `_normalize_product_pricing`: `easy_ecom/domain/services/commerce_service.py:287`
- `_normalize_variant_pricing`: `easy_ecom/domain/services/commerce_service.py:315`

### C. Catalog/read contract for explicit vs effective values

Observed backend rule:
- API payload publishes both explicit (`unit_price`, `min_price`) and effective (`effective_unit_price`, `effective_min_price`) values.
- Inheritance flags indicate fallback source.

Evidence:
- Payload assembly: `easy_ecom/domain/services/commerce_service.py:433`
- Response schema fields: `easy_ecom/api/schemas/commerce.py:31`

### D. Sales order pricing enforcement

Observed backend rule:
- `SalesOrderLineInput.unit_price` is optional; service resolves fallback when omitted.
- Order creation rejects missing/non-positive resolved price (`PRICE_REQUIRED`).
- Validation enforces floor via effective minimum price and rejects below-floor (`MIN_PRICE_VIOLATION`).

Evidence:
- Input contract: `easy_ecom/api/schemas/commerce.py:360`
- Line assembly and fallback: `easy_ecom/domain/services/commerce_service.py:2390`
- Price required check: `easy_ecom/domain/services/commerce_service.py:2408`
- Floor enforcement: `easy_ecom/domain/services/commerce_service.py:2445`

### E. AI sales-agent pricing behavior

Observed backend rule:
- AI catalog summary/search only considers active/in-stock variants with positive effective price.
- AI matched variant payload carries effective unit/min price values.

Evidence:
- Catalog summary gating: `easy_ecom/domain/services/sales_agent_service.py:2368`
- Search gating and matched payload pricing: `easy_ecom/domain/services/sales_agent_service.py:2497`

### F. DB-level hard constraints for pricing invariants

Observed backend rule:
- Products: non-negative default/min price and `min <= default`.
- Variants: non-negative price/min and `min <= price`.
- Sales order items: non-negative `unit_price_amount`, `discount_amount`, `line_total_amount`.

Evidence:
- ORM constraints: `easy_ecom/data/store/postgres_models.py:215`
- Sales order item constraints: `easy_ecom/data/store/postgres_models.py:642`
- Constraint migration: `easy_ecom/migrations/versions/20260416_0013_inventory_pricing_check_constraints.sql:49`

## 4) Rule Matrix (Current State vs Target Direction)

| Rule Area | Current Backend Behavior | Risk / Gap | Target Direction |
|---|---|---|---|
| Saleable price identity | Variant can inherit product default price via effective resolver | Variant-level commercial ownership can drift when explicit variant price is missing | Require explicit variant price before “sellable in channels/AI” status |
| Minimum floor | Effective min price fallback used in order validation | No floor when both variant + product min are null | Require mandatory min-floor policy for sellable variants |
| Explicit vs effective contract | Both are exposed with inheritance flags | Consumers may incorrectly read only explicit fields | Enforce effective fields for sell/AI flows; explicit fields for edit UX only |
| Sales line override | Optional `unit_price` accepted if floor check passes | No structured override reason for audit analytics | Add override-reason taxonomy and actor metadata |
| AI explainability | AI uses effective prices but does not emit explicit source marker | Harder to audit whether price was inherited or explicit | Include price source marker (`variant` vs `product_fallback`) |

## 5) Verification Evidence

Existing test confirms effective-price fallback and minimum-floor rejection behavior:
- `easy_ecom/tests/test_api_commerce.py:732`

## 6) Outcome

Published TEA-78 backend pricing path evidence with line-level proof for product-vs-variant rules and current risk matrix, without mutating runtime behavior.
