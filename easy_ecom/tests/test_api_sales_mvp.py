from fastapi.testclient import TestClient

from easy_ecom.api.dependencies import RequestUser, get_container, get_current_user
from easy_ecom.api.main import app, create_app


class DummySalesService:
    def __init__(self) -> None:
        self.sales = [
            {
                "sale_id": "sale-1",
                "sale_no": "SAL-20260310-0001",
                "customer_id": "cust-a",
                "customer_name": "Alice",
                "timestamp": "2026-03-10T00:00:00Z",
                "subtotal": 100.0,
                "discount": 0.0,
                "tax": 5.0,
                "total": 105.0,
                "status": "confirmed",
                "note": "",
                "lines": [
                    {
                        "line_id": "line-1",
                        "product_id": "prd-1",
                        "product_name": "Product A",
                        "qty": 1,
                        "unit_price": 100.0,
                        "line_total": 100.0,
                    }
                ],
            }
        ]

    def list_sales(self, client_id: str, query: str = ""):
        rows = self.sales.copy()
        if query:
            rows = [r for r in rows if query.lower() in r["sale_no"].lower() or query.lower() in r["customer_name"].lower()]
        return [{k: v for k, v in row.items() if k not in {"lines", "note"}} for row in rows]

    def lookup_customers(self, client_id: str, query: str = ""):
        return [{"customer_id": "cust-a", "full_name": "Alice", "phone": "111", "email": "alice@x.com"}]

    def lookup_products(self, client_id: str, query: str = ""):
        return [{"variant_id": "var-1", "product_id": "prd-1", "sku": "SKU-1", "barcode": "", "product_name": "Product A", "variant_name": "Default", "label": "Product A / Default / SKU-1", "default_unit_price": 100.0, "available_qty": 9.0}]

    def get_sale_detail(self, client_id: str, sale_id: str):
        for row in self.sales:
            if row["sale_id"] == sale_id:
                return row
        return None

    def create_sale(self, **kwargs):
        if kwargs["customer_id"] == "cust-other":
            raise ValueError("Invalid customer for tenant")
        if kwargs["lines"][0].qty > 9:
            raise ValueError("Insufficient stock for prd-1")
        return {"sale_id": "sale-new", "sale_no": "SAL-20260310-0002", "total": 50.0, "status": "confirmed"}


class DummyContainer:
    def __init__(self) -> None:
        self.sales_mvp = DummySalesService()


def test_sales_requires_auth() -> None:
    client = TestClient(create_app())
    assert client.get('/sales').status_code == 401
    assert client.post('/sales', json={"customer_id": "x", "lines": [{"variant_id": "v", "qty": 1, "unit_price": 1}], "discount": 0, "tax": 0, "note": ""}).status_code == 401


def test_sales_list_create_detail_and_errors() -> None:
    app.dependency_overrides[get_container] = lambda: DummyContainer()
    app.dependency_overrides[get_current_user] = lambda: RequestUser(user_id='u1', client_id='tenant-a', roles=['SUPER_ADMIN'])
    client = TestClient(app)

    list_res = client.get('/sales?q=alice')
    assert list_res.status_code == 200
    assert len(list_res.json()["items"]) == 1

    options_res = client.get('/sales/form-options')
    assert options_res.status_code == 200
    assert options_res.json()["customers"][0]["customer_id"] == "cust-a"

    detail_res = client.get('/sales/sale-1')
    assert detail_res.status_code == 200
    assert detail_res.json()["lines"][0]["product_id"] == "prd-1"

    create_ok = client.post('/sales', json={"customer_id": "cust-a", "lines": [{"variant_id": "var-1", "qty": 1, "unit_price": 50}], "discount": 0, "tax": 0, "note": ""})
    assert create_ok.status_code == 201

    invalid_customer = client.post('/sales', json={"customer_id": "cust-other", "lines": [{"variant_id": "var-1", "qty": 1, "unit_price": 50}], "discount": 0, "tax": 0, "note": ""})
    assert invalid_customer.status_code == 400

    stock_fail = client.post('/sales', json={"customer_id": "cust-a", "lines": [{"variant_id": "var-1", "qty": 99, "unit_price": 50}], "discount": 0, "tax": 0, "note": ""})
    assert stock_fail.status_code == 400

    bad_payload = client.post('/sales', json={"customer_id": "cust-a", "lines": [], "discount": 0, "tax": 0, "note": ""})
    assert bad_payload.status_code == 422

    app.dependency_overrides.clear()
