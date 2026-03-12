from fastapi.testclient import TestClient
import pandas as pd

from easy_ecom.api.app import app
from easy_ecom.api.dependencies import RequestUser, get_container, get_current_user
from easy_ecom.domain.models.auth import AuthenticatedUser


class DummyAuth:
    def authenticate(self, email: str, password: str) -> AuthenticatedUser | None:
        if email != "admin@example.com" or password != "secret":
            return None
        return AuthenticatedUser(
            user_id="u1",
            client_id="c1",
            roles=["SUPER_ADMIN"],
            name="Admin",
            email=email,
        )


class DummyDashboard:
    def business_health_snapshot(self, client_id: str):
        return {
            "Revenue": 10.0,
            "Gross Profit": 5.0,
            "Net Operating Profit": 3.0,
            "Gross Margin %": 50.0,
            "Inventory Value": 100.0,
            "Outstanding Receivables": 4.0,
            "Data Health Score": 95.0,
        }

    def overview_snapshot(self, client_id: str):
        return {
            "generated_at": "2026-01-01T00:00:00Z",
            "kpis": {
                "total_products": 1,
                "total_variants": 1,
                "current_stock_units": 1.0,
                "low_stock_items": 1,
            },
            "business_health": {
                "inventory_value": 2.0,
                "recent_stock_movements_count": 1,
                "sales_count_last_30_days": 1,
                "revenue_last_30_days": 10.0,
            },
            "recent_activity": [],
            "top_products": [
                {
                    "product_id": "p1",
                    "product_name": "Widget",
                    "current_qty": 1.0,
                    "stock_value": 2.0,
                }
            ],
        }


class DummyCatalogStock:
    def suggest_products(self, client_id: str, q: str):
        return [{"product_id": "p1", "product_name": "Widget"}]

    def save_workspace(self, **kwargs):
        return "p1", ["lot1"], 1

    def stock_explorer(self, client_id: str):
        return pd.DataFrame([{"product_id": "p1", "product_name": "Widget", "total_available_qty": 1, "variant_count": 1, "default_selling_price": 10, "avg_unit_cost": 2, "stock_value": 2}]), {"p1": pd.DataFrame([{"variant_id": "v1", "variant_name": "Default", "qty": 1, "unit_cost": 2, "stock_value": 2, "lot_id": "lot1"}])}

    def list_supplier_options(self, client_id: str):
        return ["Demo Supplier"]

    def list_category_options(self, client_id: str):
        return ["General"]


class DummyProducts:
    def get_by_id(self, client_id: str, product_id: str):
        return {"product_id": "p1", "product_name": "Widget"}

    def list_variants(self, client_id: str, product_id: str):
        return [{"variant_id": "v1", "variant_name": "Default"}]

    def list_by_client(self, client_id: str):
        return pd.DataFrame([
            {
                "product_id": "p1",
                "product_name": "Widget",
                "supplier": "Demo Supplier",
                "category": "General",
                "prd_description": "",
                "prd_features_json": '{"features": []}',
            }
        ])

    def list_variants_by_client(self, client_id: str):
        return pd.DataFrame([
            {
                "variant_id": "v1",
                "parent_product_id": "p1",
                "variant_name": "Default",
                "size": "",
                "color": "",
                "other": "",
                "default_selling_price": "10",
                "max_discount_pct": "10",
            }
        ])


class DummyInventory:
    def add_stock(self, **kwargs):
        return "lot1"

    def stock_by_lot_with_issues(self, client_id: str):
        return pd.DataFrame([{"variant_id": "v1", "qty": 1, "unit_cost": 2}])


class DummySales:
    def confirm_sale(self, payload, customer_snapshot, user_id: str = ""):
        return {"order_id": "o1", "invoice_id": "i1", "order_status": "confirmed"}


class DummyContainer:
    auth = DummyAuth()
    dashboard = DummyDashboard()
    catalog_stock = DummyCatalogStock()
    products = DummyProducts()
    inventory = DummyInventory()
    sales = DummySales()


def test_core_api_endpoints() -> None:
    app.dependency_overrides[get_container] = lambda: DummyContainer()
    app.dependency_overrides[get_current_user] = lambda: RequestUser(
        user_id="u1", client_id="c1", roles=["SUPER_ADMIN"]
    )

    client = TestClient(app)

    assert client.post("/auth/login", json={"email": "admin@example.com", "password": "secret"}).status_code == 200
    assert client.get("/session/me").status_code == 200
    assert client.get("/dashboard/summary").status_code == 200
    assert client.get("/dashboard/overview").status_code == 200
    assert client.get("/products/search", params={"q": "wid"}).status_code == 200
    assert client.get("/products/p1").status_code == 200
    assert client.post(
        "/products/upsert",
        json={
            "typed_product_name": "Widget",
            "variant_entries": [
                {
                    "variant_id": "",
                    "variant_label": "Default",
                    "size": "M",
                    "color": "Red",
                    "other": "",
                    "qty": 1,
                    "unit_cost": 2,
                    "default_selling_price": 10,
                    "max_discount_pct": 10,
                }
            ],
        },
    ).status_code == 200
    assert client.get("/stock/explorer").status_code == 200
    assert client.get("/products-stock/snapshot").status_code == 200
    assert client.post(
        "/products-stock/save",
        json={
            "mode": "new",
            "identity": {
                "productName": "Widget",
                "supplier": "Demo Supplier",
                "category": "General",
                "description": "",
                "features": [],
            },
            "variants": [
                {
                    "id": "",
                    "label": "Default",
                    "size": "M",
                    "color": "Red",
                    "other": "",
                    "qty": 1,
                    "cost": 2,
                    "defaultSellingPrice": 10,
                    "maxDiscountPct": 10,
                }
            ],
        },
    ).status_code == 200
    assert client.post(
        "/inventory/add",
        json={"product_id": "p1", "variant_id": "v1", "product_name": "Widget", "qty": 1, "unit_cost": 1},
    ).status_code == 200
    assert client.post(
        "/sales/create",
        json={
            "customer_id": "cust1",
            "items": [{"variant_id": "v1", "qty": 1, "unit_price": 10}],
        },
    ).status_code == 422

    app.dependency_overrides.clear()
