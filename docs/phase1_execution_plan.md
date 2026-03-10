# Phase 1 — Domain / Module Execution Plan

This roadmap converts legacy Streamlit scope into incremental production delivery on Next.js + FastAPI + RDS Postgres.

## Delivery principles
- Preserve working auth/session and tenant isolation.
- Reuse existing domain services before adding new business logic.
- Ship read-first where possible, then controlled write operations.
- Keep each module behind explicit API contracts and RBAC checks.

## Module-by-module plan

| Module | Business Objective | Core Screens | MVP Scope | Advanced Scope | Required APIs | Required DB Entities | Dependencies | UI Complexity | Backend Complexity | Priority |
|---|---|---|---|---|---|---|---|---|---|---|
| Dashboard | Real-time business health for operators/admin | KPI cards, trend charts, product performance, inventory/receivables health, reconciliation panel | KPI snapshot + date-range trend + top product tables | Super-admin cross-client monitoring, anomaly drilldown, export views | `GET /dashboard/summary` + new trend/performance endpoints | `sales_orders`, `sales_order_items`, `invoices`, `payments`, `inventory_txn`, `ledger`, `products`, `product_variants`, `clients` | Auth, products, inventory, sales, finance | Medium | Medium | P0 |
| Products | Product catalog and variant master lifecycle | Product chooser/search, identity form, variant grid, pricing/discount controls | Keep existing products-stock workspace as canonical products MVP | Supplier/category entities, bulk import, variant image/media, archival/versioning | Existing `/products-stock/*`; later `/products/*` search/detail/upsert | `products`, `product_variants`, optional `suppliers`, `categories` | Auth | Medium | Medium | P0 |
| Inventory | Trustworthy stock movement and valuation | Stock-in form, lot explorer, stock adjustment history | Dedicated stock-in/out + lot-wise explorer | Multi-warehouse, transfer, cycle count, reservation policies | Existing `POST /inventory/add` (mount), new stock query endpoints | `inventory_txn`, `sequences`, `products`, `product_variants` | Products | Medium | High | P0 |
| Sales | End-to-end order-to-cash flow | Draft cart, order detail, pricing panel, payment panel, fulfillment timeline | Draft create/add/update, place/confirm order, payment record, shipment creation | Delivery failure handling, cancellation policies, customer snapshot and document generation | Extend beyond current `POST /sales/create` to full lifecycle endpoints | `sales_orders`, `sales_order_items`, `invoices`, `payments`, `shipments`, `inventory_txn`, `ledger`, `audit_log` | Customers, Products, Inventory | High | High | P0 |
| Customers | Customer master and lookup | Customer list/search, create/edit drawer | Create + search + list by client | Segmentation, tags, contact preferences, merge/dedupe | New `/customers` CRUD/search endpoints | `customers` | Auth | Low | Low | P1 |
| Purchases | Controlled procurement and inward stock traceability | Purchase order list/detail, create PO, receive stock | If no PO model yet: scoped MVP as manual stock-in with supplier metadata | Full procure-to-stock lifecycle (PO -> GRN -> invoice match) | New `/purchases` endpoints (phase-gated) | Existing `inventory_txn`; likely new `purchase_orders`, `purchase_order_items` | Products, Inventory, Suppliers | Medium | High | P2 |
| Finance | Cashflow/profit visibility and ledger control | Ledger entry form, ledger table, profit and pressure metrics | Manual ledger post + MTD profit + receivables KPI | P&L period views, category analytics, reconciliation with returns/refunds | New `/finance` ledger + metrics endpoints | `ledger`, `sales_*`, `payments`, `inventory_txn`, `returns/refunds` | Sales, Inventory, Returns | Medium | Medium | P1 |
| Returns | Returns/refunds with stock and finance consistency | Return request form, pending queue, approve/reject actions | Request + approve/reject + optional restock | Multi-step receive/inspect/refund workflow and reason analytics | New `/returns` endpoints aligned to `ReturnsService` | `returns`, `return_items`, `refunds`, `inventory_txn`, `ledger` | Sales, Finance, Inventory | Medium | High | P2 |
| Admin | Tenant operations and access control | Client management, user management, role assignment | Client/user CRUD with audit | Role policy matrix UI, activation workflows, admin alerts | New `/admin/clients`, `/admin/users`, `/admin/roles` | `clients`, `users`, `roles`, `user_roles`, `audit_log` | Auth | Medium | Medium | P2 |
| Settings | User/session/workspace preferences | Profile + session details + logout | Session visibility + logout + org currency read-only | Configurable preferences, notification controls | Existing `/auth/me`, `/auth/logout`; future `/settings` profile endpoints | `users`, `clients` | Auth/Admin | Low | Low | P3 |

## Recommended implementation sequence (Phase 2+)

1. **API surface hardening**
   - Mount existing routers (dashboard/sales/inventory/products) in canonical `api_router`.
   - Keep all routes cookie-session + RBAC guarded.
2. **Dashboard read module**
   - Ship dashboards first to validate data quality and confidence.
3. **Customers module**
   - Provide customer lookup foundation for sales UX.
4. **Sales module (MVP lifecycle)**
   - Draft -> place/confirm -> payment -> shipment path.
5. **Inventory dedicated module**
   - Explicit stock operations beyond products workspace.
6. **Finance module**
   - Ledger + metrics on top of real sales/inventory flows.
7. **Returns module**
   - Controlled stock+money reversals.
8. **Admin module**
   - Tenant/user operations migrated from legacy Streamlit.
9. **Settings module**
   - User operational preferences and session controls.
10. **Purchases advanced module**
   - Introduce PO entities only after validating operating model.

## Release safety checklist for each module
- Tenant filter enforced for every query/mutation.
- Role check mapped to `PAGE_PERMISSIONS` equivalent policy.
- API contract typed in FastAPI schemas + frontend types.
- DB migration reviewed (forward + rollback path).
- Observability: audit events for critical mutations.
- Regression tests for auth, tenant boundaries, and money/stock invariants.
