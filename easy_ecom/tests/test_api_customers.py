from fastapi.testclient import TestClient

from easy_ecom.api.main import app, create_app
from easy_ecom.api.dependencies import RequestUser, get_container, get_current_user


class DummyCustomers:
    def __init__(self) -> None:
        self.items = [
            {
                "customer_id": "cust-a",
                "client_id": "tenant-a",
                "created_at": "2026-03-10T00:00:00Z",
                "updated_at": "2026-03-10T00:00:00Z",
                "full_name": "Alice",
                "phone": "111",
                "email": "alice@example.com",
                "address_line1": "Road 1",
                "city": "Austin",
                "notes": "VIP",
                "is_active": "true",
            }
        ]

    def list_for_client(self, client_id: str, query: str = ""):
        import pandas as pd

        rows = [r for r in self.items if r["client_id"] == client_id]
        if query:
            q = query.lower()
            rows = [r for r in rows if q in r["full_name"].lower() or q in r["phone"].lower() or q in r["email"].lower()]
        return pd.DataFrame(rows)

    def get_for_client(self, client_id: str, customer_id: str):
        for row in self.items:
            if row["client_id"] == client_id and row["customer_id"] == customer_id:
                return row
        return None

    def create(self, **kwargs):
        row = {
            "customer_id": "cust-new",
            "created_at": "2026-03-10T00:00:00Z",
            "updated_at": "2026-03-10T00:00:00Z",
            "is_active": "true",
            **kwargs,
        }
        self.items.append(row)
        return row

    def update_for_client(self, *, client_id: str, customer_id: str, patch: dict[str, str]):
        for row in self.items:
            if row["client_id"] == client_id and row["customer_id"] == customer_id:
                row.update(patch)
                return row
        return None


class DummyContainer:
    def __init__(self) -> None:
        self.customers = DummyCustomers()


def test_customers_require_auth() -> None:
    client = TestClient(create_app())
    assert client.get('/customers').status_code == 401
    assert client.post('/customers', json={"full_name": "X"}).status_code == 401


def test_customers_crud_and_tenant_isolation() -> None:
    container = DummyContainer()
    app.dependency_overrides[get_container] = lambda: container
    app.dependency_overrides[get_current_user] = lambda: RequestUser(user_id='u1', client_id='tenant-a', roles=['SUPER_ADMIN'])
    client = TestClient(app)

    assert client.get('/customers').status_code == 200
    assert client.get('/customers/cust-a').status_code == 200
    assert client.get('/customers?q=alice').status_code == 200

    create_res = client.post('/customers', json={"full_name": "Bob", "phone": "222", "email": "", "address_line1": "", "city": "", "notes": ""})
    assert create_res.status_code == 201

    patch_res = client.patch('/customers/cust-a', json={"city": "Dallas"})
    assert patch_res.status_code == 200
    assert patch_res.json()['customer']['city'] == 'Dallas'

    not_found = client.patch('/customers/cust-other', json={"city": "X"})
    assert not_found.status_code == 404

    app.dependency_overrides.clear()
