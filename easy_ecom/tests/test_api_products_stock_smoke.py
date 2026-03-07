from fastapi.testclient import TestClient

from easy_ecom.api.main import app
from easy_ecom.api.dependencies import RequestUser, get_container, get_current_user


class DummyProducts:
    def list_by_client(self, client_id: str):
        import pandas as pd

        return pd.DataFrame(
            [
                {
                    "product_id": "p-100",
                    "product_name": "Urban Fit Tee",
                    "supplier": "Nova Textiles",
                    "category": "Apparel",
                    "prd_description": "Premium cotton crew-neck t-shirt.",
                    "prd_features_json": '{"features": ["180 GSM"]}',
                }
            ]
        )

    def list_variants_by_client(self, client_id: str):
        import pandas as pd

        return pd.DataFrame(
            [
                {
                    "variant_id": "v-1001",
                    "parent_product_id": "p-100",
                    "variant_name": "S / Black",
                    "size": "S",
                    "color": "Black",
                    "other": "",
                    "default_selling_price": "16.5",
                    "max_discount_pct": "10",
                }
            ]
        )


class DummyInventory:
    def stock_by_lot_with_issues(self, client_id: str):
        import pandas as pd

        return pd.DataFrame(
            [
                {
                    "variant_id": "v-1001",
                    "qty": 42,
                    "unit_cost": 8.75,
                }
            ]
        )


class DummyCatalogStock:
    def list_supplier_options(self, client_id: str):
        return ["Nova Textiles"]

    def list_category_options(self, client_id: str):
        return ["Apparel"]

    def save_workspace(self, **kwargs):
        return "p-100", [], 1


class DummyContainer:
    products = DummyProducts()
    inventory = DummyInventory()
    catalog_stock = DummyCatalogStock()


def test_products_stock_snapshot_smoke() -> None:
    app.dependency_overrides[get_container] = lambda: DummyContainer()
    app.dependency_overrides[get_current_user] = lambda: RequestUser(
        user_id="u-test", client_id="c-test", roles=["SUPER_ADMIN"]
    )
    client = TestClient(app)

    response = client.get("/products-stock/snapshot")

    assert response.status_code == 200
    body = response.json()
    assert "products" in body
    assert "suppliers" in body
    assert "categories" in body

    app.dependency_overrides.clear()


def test_products_stock_save_smoke() -> None:
    app.dependency_overrides[get_container] = lambda: DummyContainer()
    app.dependency_overrides[get_current_user] = lambda: RequestUser(
        user_id="u-test", client_id="c-test", roles=["SUPER_ADMIN"]
    )
    client = TestClient(app)

    response = client.post(
        "/products-stock/save",
        json={
            "mode": "new",
            "identity": {
                "productName": "Smoke Tee",
                "supplier": "Smoke Supplier",
                "category": "Apparel",
                "description": "",
                "features": ["Feature A"],
            },
            "variants": [
                {
                    "id": "",
                    "label": "Default",
                    "size": "",
                    "color": "",
                    "other": "",
                    "qty": 1,
                    "cost": 2,
                    "defaultSellingPrice": 10,
                    "maxDiscountPct": 10,
                }
            ],
        },
    )

    assert response.status_code == 200
    assert response.json() == {"success": True}

    app.dependency_overrides.clear()
