# Phase 3 — Dashboard v2

## Delivered dashboard features

- Replaced placeholder dashboard page with a read-first operational dashboard UI.
- Added tenant-scoped `GET /dashboard/overview` backend endpoint.
- Implemented dashboard KPI cards:
  - Total Products
  - Total Variants / SKUs
  - Current Stock Units
  - Low Stock Items
- Added business health summary with real metrics:
  - Inventory Value
  - Recent Stock Movements (7d)
  - Sales Count (30d)
  - Revenue Snapshot (30d)
- Added recent activity list sourced from real inventory transaction rows.
- Added top products table ranked by current stock value.
- Added loading, error, and empty states for dashboard rendering.

## Real metrics in MVP (truthful, tenant-scoped)

All values are derived from authenticated session tenant (`user.client_id`) and existing PostgreSQL/CSV-backed repositories through service layer metrics:

- Product and variant counts from `products` and `product_variants`
- Stock units and low-stock count from current inventory balances
- Inventory value from current lot-based stock valuation
- Recent stock movement count/activity from `inventory_txn`
- Sales count/revenue snapshot from confirmed `sales_orders`

## Deferred metrics

- Profit/cashflow trend widgets and advanced financial analytics were deferred from this endpoint response to keep the MVP focused on reliable operational data and avoid overreaching module scope.
- Date-range filter UI was deferred; dashboard currently represents current snapshot + fixed recent windows (7d and 30d).

## API contract changes

- Added `GET /dashboard/overview`
  - Response sections:
    - `generated_at`
    - `kpis`
    - `business_health`
    - `recent_activity`
    - `top_products`
- Existing `GET /dashboard/summary` remains unchanged for backward compatibility.

## Reusable dashboard UI elements introduced

- KPI card grid pattern
- Section card layout
- Activity list block
- Top-products tabular block
- Inline empty state and loading/error state blocks

These are implemented in modular frontend components so the same patterns can be reused in upcoming modules.
