# TEA-70 / TEA-49.1 Backend Pricing Path Analysis and Rule Matrix (Product vs Variant)

Date: 2026-04-17
Owner: python-dev
Scope: Current backend behavior analysis only (no pricing-policy mutation in this task)

## 1) Objective

Map the real backend pricing flow for catalog, sales, inventory views, and AI-agent queries, then define a rule matrix for product-level vs variant-level pricing responsibilities.

This analysis is grounded in current code paths and DB constraints so follow-up implementation can be split safely.

## 2) Current Backend Pricing Flow (Observed)

### A. Source fields and fallback logic

- Product-level pricing fields:
  - `products.default_price_amount`
  - `products.min_price_amount`
  - `products.max_discount_percent` (derived in service)
- Variant-level pricing fields:
  - `product_variants.price_amount`
  - `product_variants.min_price_amount`
- Effective price resolution:
  - Effective unit price = `variant.price_amount` else `product.default_price_amount`
  - Effective minimum price = `variant.min_price_amount` else `product.min_price_amount`
  - Implemented in `CommerceBaseService` helper methods.

References:
- `easy_ecom/domain/services/commerce_service.py` (`_effective_variant_price`, `_effective_variant_min_price`, pricing normalizers)

### B. Write-time normalization and validation

- Product write path validates non-negative and `min <= default`.
- Product `max_discount_percent` is treated as legacy input and translated/validated against min/default.
- Variant write path validates non-negative and `variant_min <= variant_price` when both provided.

References:
- `easy_ecom/domain/services/commerce_service.py` (`_normalize_product_pricing`, `_normalize_variant_pricing`)
- `easy_ecom/domain/services/commerce_service.py` (`upsert_product`)

### C. Read-time payload behavior

Catalog payload exposes both explicit and effective variant values:
- Explicit variant values: `unit_price`, `min_price`
- Effective inherited values: `effective_unit_price`, `effective_min_price`
- Flags: `is_price_inherited`, `is_min_price_inherited`

References:
- `easy_ecom/domain/services/commerce_service.py` (`_variant_payload`)
- `easy_ecom/api/schemas/commerce.py` (`CatalogVariantResponse`)

### D. Sales order pricing enforcement

- Sales line input can include explicit `unit_price`; otherwise service uses effective variant price fallback.
- Order creation blocks if resolved price is missing/non-positive (`PRICE_REQUIRED`).
- Revalidation enforces minimum threshold using **effective min price** and rejects with `MIN_PRICE_VIOLATION`.
- Minimum check is based on `line_total >= quantity * min_price`.

References:
- `easy_ecom/domain/services/commerce_service.py` (`_upsert_order` line assembly + `_validate_order_pricing`)
- `easy_ecom/api/schemas/commerce.py` (`SalesOrderLineInput`)

### E. AI sales-agent pricing behavior

- Agent candidate selection uses effective variant price fallback and ignores variants with missing/non-positive effective price.
- Agent includes effective min price in matched variant payloads.

References:
- `easy_ecom/domain/services/sales_agent_service.py` (catalog summary/search/upsell paths using `_effective_variant_price` and `_effective_variant_min_price`)

### F. DB-level hard guards

- Product and variant pricing non-negative check constraints.
- `min <= default` (product) and `min <= price` (variant) constraints.
- Sales line `unit_price_amount >= 0`, `discount_amount >= 0`, `line_total_amount >= 0` constraints.

References:
- `easy_ecom/data/store/postgres_models.py` (`ProductModel`, `ProductVariantModel`, `SalesOrderItemModel` check constraints)
- Migration hardening: `easy_ecom/migrations/versions/20260416_0013_inventory_pricing_check_constraints.sql`

## 3) Product vs Variant Rule Matrix (Current vs Target)

| Rule Area | Current Backend Behavior | Risk / Ambiguity | Target Rule Direction |
|---|---|---|---|
| Saleable price identity | Variant effective price supports fallback to product default | Product-level defaults can silently drive sale price when variant price omitted | Keep fallback for bootstrap, but require explicit variant pricing before "sellable/active for channels" status |
| Minimum price enforcement | Enforced at order validation with effective min fallback | If both variant + product min missing, no floor guard exists | Define mandatory floor for sellable variants (variant min preferred; policy fallback allowed only by explicit tenant setting) |
| Discount policy field | `product.max_discount_percent` derived from product default/min | Derived field can be interpreted as authoritative policy but not variant-specific | Convert to presentation/derived metric only; move policy to explicit rule config (future table) |
| Catalog API semantics | Explicit + effective values both returned with inheritance flags | Consumers may still read `unit_price` and miss effective fallback | Standardize API consumer rule: use effective fields for selling decisions; explicit fields for edit forms only |
| Sales order price override | Line-level `unit_price` accepted, then floor checked by line total | Can undercut list price if min floor allows, no explicit reason/audit code | Require override reason code + actor metadata for below-list-but-above-floor lines |
| AI channel price output | Uses effective variant pricing, excludes unpriced variants | No explicit "price source" exposed to AI (variant vs inherited) | Include source marker (`variant`/`product_fallback`) in AI fact pack for explainability and QA |
| Tenant safety in pricing joins | Service queries filter by `client_id`; tenant-safe FK migration exists | If future code path skips filter, cross-tenant leakage risk | Keep mandatory `client_id` filters + preserve composite tenant-safe FK posture |

## 4) Key Gaps to Address in Follow-up Issues

1. Sellability gate gap:
- A variant can be active with inherited product price and no explicit variant price.
- Business impact: makes variant-level pricing governance weak for scaling and AI explainability.

2. Pricing-policy source-of-truth gap:
- Discount/price policy is implicit across product/variant fields rather than explicit rule entities.
- Business impact: difficult to roll out tenant-specific policy engines without side effects.

3. Auditability gap for manual price overrides:
- Sales line override is possible but no structured reason taxonomy currently attached in pricing validation.
- Business impact: limited commercial audit and coaching analytics.

4. API contract gap for downstream consumers:
- Both explicit/effective are present; not all consumers may consistently use effective values.
- Business impact: drift between UI, reports, and AI responses.

## 5) Recommended Execution Split (Sub-issues)

For this issue scope size, split follow-up implementation into sequenced sub-issues:

1. P0: Sellable variant pricing gate
- Require explicit variant `price_amount` (and policy-compliant floor) before variant is considered sellable in sales/AI lookup.
- Keep product fallback only for draft/template workflows.

2. P0: Pricing policy contract unification
- Define one shared backend policy resolver used by catalog payload, sales validation, and AI search.
- Output standardized fields: `effective_price`, `effective_min_price`, `price_source`, `policy_version`.

3. P1: Sales override audit hardening
- Add structured override reason + actor capture when line `unit_price` differs from resolved effective list price.
- Add reporting-friendly fields/events.

4. P1: API consumer alignment
- Enforce effective-price usage in all read endpoints used for selling and AI facts.
- Document explicit vs effective contract in API docs.

5. P2: Derived field cleanup
- Deprecate long-term dependence on `max_discount_percent` as business policy input.
- Keep only as computed compatibility field during migration window.

## 6) Existing Test Coverage Noted

- Existing regression demonstrates:
  - sales search uses effective fallback pricing,
  - below-minimum pricing is rejected with `MIN_PRICE_VIOLATION`.

Reference:
- `easy_ecom/tests/test_api_commerce.py` (`test_sales_search_uses_effective_price_and_rejects_below_minimum`)

## 7) Outcome of TEA-49.1 Analysis Task

Completed deliverable:
- Backend pricing path mapped end-to-end for catalog/sales/AI.
- Product-vs-variant rule matrix prepared with risks and target rules.
- Priority-ordered sub-issue sequence proposed for safe rollout.

No runtime code or schema mutations were applied in this analysis task.
