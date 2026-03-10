from fastapi.testclient import TestClient

from easy_ecom.api.dependencies import RequestUser, get_container, get_current_user
from easy_ecom.api.main import app, create_app


class DummyReturnsService:
    def __init__(self) -> None:
        self.rows = [
            {
                "return_id": "ret-1",
                "return_no": "RET-20260312-0001",
                "sale_id": "sale-a",
                "sale_no": "SAL-20260310-0001",
                "customer_id": "cust-a",
                "customer_name": "Alice",
                "reason": "Damaged",
                "return_total": 50.0,
                "created_at": "2026-03-12T00:00:00Z",
                "lines": [
                    {
                        "return_item_id": "ri-1",
                        "sale_item_id": "si-1",
                        "product_id": "prd-1",
                        "product_name": "Product A",
                        "sold_qty": 2,
                        "return_qty": 1,
                        "unit_price": 50,
                        "line_total": 50,
                        "reason": "Damaged",
                        "condition_status": "opened",
                    }
                ],
                "note": "",
            }
        ]

    def list_returns(self, *, client_id: str, query: str = ""):
        if client_id != "tenant-a":
            return []
        return [{k: v for k, v in self.rows[0].items() if k not in {"lines", "note"}}]

    def list_sales_for_returns(self, *, client_id: str, query: str = ""):
        if client_id != "tenant-a":
            return []
        return [{"sale_id": "sale-a", "sale_no": "SAL-20260310-0001", "customer_id": "cust-a", "customer_name": "Alice", "sale_date": "2026-03-10", "total": 100, "status": "confirmed"}]

    def get_returnable_sale(self, *, client_id: str, sale_id: str):
        if client_id != "tenant-a" or sale_id != "sale-a":
            return None
        return {"sale_id": "sale-a", "sale_no": "SAL-20260310-0001", "customer_id": "cust-a", "customer_name": "Alice", "sale_date": "2026-03-10", "lines": [{"sale_item_id": "si-1", "product_id": "prd-1", "product_name": "Product A", "sold_qty": 2, "already_returned_qty": 1, "eligible_qty": 1, "unit_price": 50}]}

    def get_return_detail(self, *, client_id: str, return_id: str):
        if client_id != "tenant-a" or return_id != "ret-1":
            return None
        return self.rows[0]

    def create_return(self, *, client_id: str, user_id: str, payload):
        if client_id != "tenant-a":
            raise ValueError("Invalid sale for tenant")
        if payload.lines[0].qty > 1:
            raise ValueError("Return quantity exceeds eligible quantity for line si-1")
        return {"return_id": "ret-new", "return_no": "RET-20260312-0002", "sale_id": payload.sale_id, "sale_no": "SAL-20260310-0001", "return_total": 25.0}


class DummyContainer:
    def __init__(self) -> None:
        self.returns_mvp = DummyReturnsService()


def test_returns_requires_auth() -> None:
    client = TestClient(create_app())
    assert client.get('/returns').status_code == 401
    assert client.post('/returns', json={"sale_id": "sale-a", "reason": "x", "note": "", "lines": [{"sale_item_id": "si-1", "qty": 1, "reason": "x"}]}).status_code == 401


def test_returns_endpoints_tenant_scoped_and_validation() -> None:
    app.dependency_overrides[get_container] = lambda: DummyContainer()
    app.dependency_overrides[get_current_user] = lambda: RequestUser(user_id='u1', client_id='tenant-a', roles=['CLIENT_OWNER'])
    client = TestClient(app)

    assert client.get('/returns').status_code == 200
    assert client.get('/returns/sales-lookup').status_code == 200
    assert client.get('/returns/sales/sale-a').status_code == 200
    assert client.get('/returns/ret-1').status_code == 200

    ok = client.post('/returns', json={"sale_id": "sale-a", "reason": "Damaged", "note": "", "lines": [{"sale_item_id": "si-1", "qty": 1, "reason": "Damaged"}]})
    assert ok.status_code == 201

    over = client.post('/returns', json={"sale_id": "sale-a", "reason": "Damaged", "note": "", "lines": [{"sale_item_id": "si-1", "qty": 9, "reason": "Damaged"}]})
    assert over.status_code == 400

    app.dependency_overrides[get_current_user] = lambda: RequestUser(user_id='u2', client_id='tenant-b', roles=['CLIENT_OWNER'])
    assert client.get('/returns').json()['items'] == []
    assert client.get('/returns/sales/sale-a').status_code == 404

    app.dependency_overrides.clear()
