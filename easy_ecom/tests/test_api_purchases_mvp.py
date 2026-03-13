from fastapi.testclient import TestClient

from easy_ecom.api.dependencies import RequestUser, get_container, get_current_user
from easy_ecom.api.main import app, create_app


class DummyPurchasesService:
    def __init__(self) -> None:
        self.rows = {
            "tenant-a": [
                {
                    "purchase_id": "pur-1",
                    "purchase_no": "PUR-20260314-0001",
                    "purchase_date": "2026-03-14",
                    "supplier_id": "sup-1",
                    "supplier_name": "Nova Supplies",
                    "reference_no": "INV-1",
                    "subtotal": 120.0,
                    "status": "received",
                    "created_at": "2026-03-14T00:00:00Z",
                    "created_by_user_id": "u1",
                    "note": "",
                    "lines": [
                        {
                            "line_id": "line-1",
                            "product_id": "prd-1",
                            "variant_id": "var-1",
                            "product_name": "Product A",
                            "qty": 2,
                            "unit_cost": 60,
                            "line_total": 120,
                        }
                    ],
                }
            ],
            "tenant-b": [],
        }

    def list_purchases(self, *, client_id: str, query: str = ""):
        rows = self.rows.get(client_id, []).copy()
        if query:
            rows = [r for r in rows if query.lower() in r["purchase_no"].lower()]
        return [{k: v for k, v in row.items() if k not in {"lines", "note", "created_by_user_id"}} for row in rows]

    def lookup_options(self, *, client_id: str, query: str = ""):
        if client_id != "tenant-a":
            return {"products": [], "suppliers": []}
        return {
            "products": [{"variant_id": "var-1", "product_id": "prd-1", "label": "Product A", "current_stock": 6, "sku": "", "barcode": ""}],
            "suppliers": [{"supplier_id": "sup-1", "name": "Nova Supplies"}],
        }

    def get_purchase_detail(self, *, client_id: str, purchase_id: str):
        for row in self.rows.get(client_id, []):
            if row["purchase_id"] == purchase_id:
                return row
        return None

    def create_purchase(self, *, client_id: str, user_id: str, payload):
        if payload.lines[0].variant_id == "other-tenant":
            raise ValueError("Invalid product reference: other-tenant")
        if payload.lines[0].qty <= 0:
            raise ValueError("Purchase quantity must be > 0")
        return {"purchase_id": "pur-new", "purchase_no": "PUR-20260314-0002", "subtotal": 50.0, "status": "received"}


class DummyContainer:
    def __init__(self) -> None:
        self.purchases_mvp = DummyPurchasesService()


def test_purchases_requires_auth() -> None:
    client = TestClient(create_app())
    assert client.get('/purchases').status_code == 401
    assert client.post('/purchases', json={"purchase_date": "2026-03-14", "supplier_id": "", "reference_no": "", "note": "", "payment_status": "unpaid", "lines": [{"variant_id": "var-1", "qty": 1, "unit_cost": 1}]}).status_code == 401


def test_purchases_endpoints_tenant_scoped_and_validation() -> None:
    app.dependency_overrides[get_container] = lambda: DummyContainer()
    app.dependency_overrides[get_current_user] = lambda: RequestUser(user_id='u1', client_id='tenant-a', roles=['CLIENT_OWNER'])
    client = TestClient(app)

    listed = client.get('/purchases?q=PUR')
    assert listed.status_code == 200
    assert len(listed.json()['items']) == 1

    options = client.get('/purchases/form-options')
    assert options.status_code == 200
    assert options.json()['products'][0]['product_id'] == 'prd-1'
    assert options.json()['products'][0]['variant_id'] == 'var-1'

    detail = client.get('/purchases/pur-1')
    assert detail.status_code == 200
    assert detail.json()['lines'][0]['product_id'] == 'prd-1'
    assert detail.json()['lines'][0]['variant_id'] == 'var-1'

    created = client.post('/purchases', json={"purchase_date": "2026-03-14", "supplier_id": "sup-1", "reference_no": "INV-2", "note": "", "payment_status": "unpaid", "lines": [{"variant_id": "var-1", "qty": 1, "unit_cost": 50}]})
    assert created.status_code == 201

    bad_product = client.post('/purchases', json={"purchase_date": "2026-03-14", "supplier_id": "", "reference_no": "", "note": "", "payment_status": "unpaid", "lines": [{"variant_id": "other-tenant", "qty": 1, "unit_cost": 50}]})
    assert bad_product.status_code == 400

    app.dependency_overrides[get_current_user] = lambda: RequestUser(user_id='u2', client_id='tenant-b', roles=['CLIENT_OWNER'])
    assert client.get('/purchases').json()['items'] == []
    assert client.get('/purchases/pur-1').status_code == 404

    app.dependency_overrides.clear()
