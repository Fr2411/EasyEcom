from fastapi.testclient import TestClient

from easy_ecom.api.app import app
from easy_ecom.api.dependencies import get_container, get_current_user
from easy_ecom.api.dependencies import RequestUser


class DummyUsers:
    def login(self, email: str, password: str):
        if email == "admin@example.com" and password == "secret":
            return {
                "user_id": "u1",
                "client_id": "c1",
                "roles": "SUPER_ADMIN",
                "name": "Admin",
                "email": email,
            }
        return None


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


class DummyCatalogStock:
    def suggest_products(self, client_id: str, q: str):
        return [{"product_id": "p1", "product_name": "Widget"}]

    def save_workspace(self, **kwargs):
        return "p1", ["lot1"], 1

    def stock_explorer(self, client_id: str):
        import pandas as pd

        return pd.DataFrame([{"product_id": "p1", "product_name": "Widget", "total_available_qty": 1, "variant_count": 1, "default_selling_price": 10, "avg_unit_cost": 2, "stock_value": 2}]), {"p1": pd.DataFrame([{"variant_id": "v1", "variant_name": "Default", "qty": 1, "unit_cost": 2, "stock_value": 2, "lot_id": "lot1"}])}


class DummyProducts:
    def get_by_id(self, client_id: str, product_id: str):
        return {"product_id": "p1", "product_name": "Widget"}

    def list_variants(self, client_id: str, product_id: str):
        return [{"variant_id": "v1", "variant_name": "Default"}]


class DummyInventory:
    def add_stock(self, **kwargs):
        return "lot1"


class DummySales:
    def confirm_sale(self, payload, customer_snapshot, user_id: str = ""):
        return {"order_id": "o1", "invoice_id": "i1", "order_status": "confirmed"}


class DummyContainer:
    users = DummyUsers()
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
    assert client.get("/dashboard/summary").status_code == 200
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
                    "size": "",
                    "color": "",
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
    assert client.post(
        "/inventory/add",
        json={"product_id": "p1", "product_name": "Widget", "qty": 1, "unit_cost": 1},
    ).status_code == 200
    assert client.post(
        "/sales/create",
        json={
            "customer_id": "cust1",
            "items": [{"product_id": "p1", "qty": 1, "unit_selling_price": 10}],
        },
    ).status_code == 200

    app.dependency_overrides.clear()
