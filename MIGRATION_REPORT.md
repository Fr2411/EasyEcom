# Streamlit to Next.js Migration Report (Phase 1-5 kickoff)

## 1) Streamlit page inventory and migration map

| Streamlit page | Purpose | Next.js route | API endpoints (current/required) | State/RBAC blockers |
|---|---|---|---|---|
| `01_Login.py` | Email/password auth and session bootstrap | `/login` | `POST /auth/login` | Streamlit session state replaced by browser storage + auth headers |
| `02_Dashboard.py` | KPI health dashboard, trend controls, scope switch for super admin | `/dashboard` | `GET /dashboard/summary` (+ future trend/performance endpoints) | Streamlit global session state stores user/client scope and refresh controls |
| `03_Catalog_&_Stock.py` | Product search/add, variant grid editing, stock posting | `/products-stock` | `GET /products/search`, `GET /products/{id}`, `POST /products/upsert`, `GET /stock/explorer`, `POST /inventory/add` | Streamlit `data_editor` state and multi-step tokenized workspace need client-managed state |
| `05_Sales.py` | Draft/order workspace, pricing, payment, fulfillment actions | `/sales` | `POST /sales/create` (+ future order lifecycle endpoints) | Streamlit keeps many selected order/customer keys in session; split into API resources |
| `06_Customers.py` | Customer CRUD/search | (future) `/customers` | (future) `/customers/*` | Pending |
| `07_Finance.py` | Ledger, receivables, finance controls | (future) `/finance` | (future) `/finance/*` | Pending |
| `08_Admin.py` | Admin-only controls | (future) `/admin` | (future) `/admin/*` | Pending |
| `09_Settings.py` | Client/user settings | (future) `/settings` | (future) `/settings/*` | Pending |
| `10_Returns.py` | Returns/refund workflow | (future) `/returns` | (future) `/returns/*` | Pending |

## 2) What was implemented now

- Added `easy_ecom/api` FastAPI layer with thin routers and schema contracts.
- Reused existing Python services (`UserService`, `DashboardService`, `CatalogStockService`, `InventoryService`, `SalesService`) as business logic source of truth.
- Added initial endpoints requested for login, dashboard summary, products search/detail/upsert, stock explorer, inventory add, and sales create.
- Added Next.js TypeScript app (`frontend`) with App Router and first mirrored routes:
  - `/login`
  - `/dashboard`
  - `/products-stock`
  - `/sales`
- Added Amplify-oriented config (`frontend/amplify.yml`) and API env variable usage (`NEXT_PUBLIC_API_BASE_URL`).
- Added backend API contract test and a frontend render smoke test.

## 3) Remaining parity gaps (documented)

- Dashboard currently mirrors KPI summary first; full trend/product/financial chart parity still pending.
- Products & Stock route mirrors core search/upsert flow but not full Streamlit variant editor behavior.
- Sales route mirrors confirm-sale path but not full draft/payment/fulfillment lifecycle controls yet.
- Auth currently uses header-based API auth context after login; token/session hardening is pending.

## 4) Streamlit status

- Streamlit app is retained and still runnable.
- No Streamlit pages were removed yet (deprecation should happen after route-by-route parity sign-off).
