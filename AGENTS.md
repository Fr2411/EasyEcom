# AGENTS.md

## Mission

Easy_Ecom is a multi-tenant commerce operating system for small businesses that buy/import products, store them, sell them, and manage operations through a web application. The platform also uses tenant-specific business data to power AI sales agents that communicate with end customers through channels such as WhatsApp and Messenger.

This repository must be treated as a production system. All changes must prioritize correctness, tenant safety, stock accuracy, auditability, maintainability, and AWS cost efficiency.

---

## Business Context

Each client is a separate tenant. A tenant may have multiple users with different roles such as owner, warehouse staff, and general staff.

The platform serves two purposes:

1. Client-facing operational software:
   - product catalog management
   - inventory tracking
   - purchase entry
   - sales entry
   - returns
   - dashboards
   - finance visibility based on role

2. Easy_Ecom internal intelligence layer:
   - collect structured business data
   - power pricing analysis
   - power AI sales agents
   - improve tenant revenue
   - support upsell / cross-sell / pricing optimization

The system is expected to scale to hundreds of tenants. Multi-tenant isolation is mandatory.

---

## Non-Negotiable Business Rules

### Tenant Isolation
- Every tenant can access only its own data.
- Super admin can access cross-tenant data.
- All reads and writes must respect tenant boundaries.
- No code change may weaken tenant isolation.

### Product vs Variant
- Product is a catalog-level entity.
- Variant is the real saleable stock-holding SKU.
- Size, color, and other sale-affecting attributes belong to the variant.
- Availability queries for customer service and AI must resolve at the variant level, not only the product level.

### Stock Ownership
- Saleable stock exists at variant level only.
- Parent product must never be treated as the stock-holding identity.
- New inventory transactions must point to `variant_id`.
- Sales logic must read real saleable stock from variant-level ledger totals.

### Inventory Truth
- Inventory is ledger-driven.
- Transaction history is the source of truth for stock.
- Do not rely on manually maintained stock numbers when ledger-derived truth exists.
- If cached or denormalized stock fields exist, they must be treated as derived and reconciled from ledger truth.

### Auditability
- Purchases, sales, returns, adjustments, and other stock movements must be historically traceable.
- Do not introduce write paths that silently mutate stock without an auditable transaction record.

### Pricing
- A product or variant may have a default selling price and discount constraints.
- Future pricing intelligence will use sales velocity, stock aging, profitability, and conversion behavior.
- Do not hardcode simplistic pricing assumptions into permanent architecture.

---

## Engineering Priorities

When tradeoffs exist, prioritize in this order:

1. Data correctness
2. Tenant safety
3. Stock accuracy
4. Auditability
5. Backward-compatible production safety
6. Simplicity
7. AWS cost efficiency
8. Performance optimization
9. Developer convenience

---

## Required Engineering Behavior

Codex and contributors must:

- read related files before editing
- understand current business flow before changing schema or logic
- prefer the smallest permanent fix over broad speculative rewrites
- preserve production stability
- keep frontend, backend, and database semantics aligned
- avoid duplicate business logic across layers
- document any architecture-impacting changes
- ensure migrations are safe, idempotent where appropriate, and production-aware
- keep code readable and maintainable
- avoid unnecessary AWS resource consumption

---

## Forbidden Behaviors

Do not:

- treat `product_id` as the stock-holding identity when `variant_id` is required
- add inventory logic that bypasses the transaction ledger
- mix tenant data in queries, joins, caches, or summaries
- introduce frontend-only fixes for backend data problems
- introduce backend-only assumptions that the frontend cannot safely consume
- duplicate pricing logic in multiple places without a clear shared rule source
- add unnecessary polling, heavy queries, wasteful compute, or expensive background behavior without justification
- add dead code, speculative abstraction, or half-finished architecture
- make schema changes without a migration
- break existing production flows to achieve elegance

---

## Data Model Principles

Use these meanings consistently:

- `tenant/client`: business account boundary
- `product`: catalog parent
- `variant`: actual saleable SKU
- `inventory transaction`: auditable stock movement event
- `sales line`: customer sale at line-item level
- `purchase line`: inbound stock at line-item level

If a customer asks for a specific size/color/option, availability must be resolved using the variant, not just the parent product.

---

## Frontend / Backend Contract Rule

Frontend forms, API payloads, backend validation, persistence rules, and reporting queries must agree on the same business meaning.

A change is incomplete if it updates only one layer and leaves the others inconsistent.

Every change affecting business flow must consider:
- UI input shape
- API contract
- DB write logic
- read/query logic
- reporting impact
- AI consumption impact

---

## Cost Discipline

This system runs on AWS and must be cost-aware.

Prefer:
- simple and efficient queries
- indexed access patterns
- lean APIs
- minimal background work
- managed services only when justified
- reuse of existing infrastructure where sensible

Do not optimize prematurely with costly infrastructure. Do not underbuild critical correctness.

---

## AI Integration Direction

AI agents will use tenant-specific catalog, pricing, and stock data to communicate with customers. Therefore:
- stock availability must be trustworthy
- variant-level identity must be stable
- pricing data must be structured
- product metadata must be clean and searchable
- tenant separation must be strict

Do not implement AI-facing data shortcuts that weaken correctness.

---

## Definition of Done

A task is not done unless:
- business logic is correct
- tenant safety is preserved
- stock logic is correct at variant level
- code is clean and minimal
- affected layers are aligned
- migrations are included when required
- edge cases are considered
- docs are updated when architecture or rules change
