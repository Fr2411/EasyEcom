from fastapi.testclient import TestClient

from easy_ecom.api.dependencies import RequestUser, get_container, get_current_user
from easy_ecom.api.main import app, create_app


class DummyFinanceService:
    def __init__(self) -> None:
        self.expenses = {
            "tenant-a": [
                {
                    "expense_id": "exp-1",
                    "expense_date": "2026-03-11",
                    "category": "Logistics",
                    "amount": 55.0,
                    "payment_status": "paid",
                    "note": "Courier",
                    "created_at": "",
                    "updated_at": "",
                }
            ],
            "tenant-b": [],
        }

    def finance_overview(self, *, client_id: str):
        if client_id == "tenant-a":
            return {
                "sales_revenue": 300,
                "expense_total": 55,
                "receivables": 75,
                "payables": 10,
                "cash_in": 300,
                "cash_out": 55,
                "net_operating": 245,
            }
        return {"sales_revenue": 0, "expense_total": 0, "receivables": 0, "payables": 0, "cash_in": 0, "cash_out": 0, "net_operating": 0}

    def list_expenses(self, *, client_id: str, query: str = "", payment_status: str = ""):
        rows = self.expenses.get(client_id, []).copy()
        if payment_status:
            if payment_status not in {"paid", "unpaid", "partial"}:
                raise ValueError("payment_status must be one of: paid, unpaid, partial")
            rows = [r for r in rows if r["payment_status"] == payment_status]
        if query:
            rows = [r for r in rows if query.lower() in r["category"].lower()]
        return rows

    def create_expense(self, *, client_id: str, user_id: str, payload):
        if payload.amount <= 0:
            raise ValueError("amount must be > 0")
        row = {
            "expense_id": "exp-new",
            "expense_date": payload.expense_date,
            "category": payload.category,
            "amount": payload.amount,
            "payment_status": payload.payment_status,
            "note": payload.note,
            "created_at": "",
            "updated_at": "",
        }
        self.expenses.setdefault(client_id, []).append(row)
        return row

    def update_expense(self, *, client_id: str, expense_id: str, payload):
        for row in self.expenses.get(client_id, []):
            if row["expense_id"] == expense_id:
                row.update({
                    "expense_date": payload.expense_date,
                    "category": payload.category,
                    "amount": payload.amount,
                    "payment_status": payload.payment_status,
                    "note": payload.note,
                })
                return row
        return None

    def list_receivables(self, *, client_id: str):
        if client_id == "tenant-a":
            return [{"sale_id": "s1", "sale_no": "SAL-1", "customer_id": "c1", "customer_name": "Alice", "sale_date": "2026-03-10", "grand_total": 100, "amount_paid": 20, "outstanding_balance": 80, "payment_status": "partial"}]
        return []

    def list_payables(self, *, client_id: str):
        return {"supported": True, "deferred_reason": "", "unpaid_count": 0, "rows": []}

    def list_transactions(self, *, client_id: str):
        return [{"entry_id": "exp-1", "entry_date": "2026-03-11", "entry_type": "expense", "category": "Logistics", "amount": 55, "direction": "out", "reference": "exp-1", "note": "Courier"}]


class DummyContainer:
    def __init__(self) -> None:
        self.finance_mvp = DummyFinanceService()


def test_finance_requires_auth() -> None:
    client = TestClient(create_app())
    assert client.get('/finance/overview').status_code == 401
    assert client.post('/finance/expenses', json={"expense_date": "2026-03-11", "category": "Ops", "amount": 1, "payment_status": "paid", "note": "x"}).status_code == 401


def test_finance_mvp_endpoints_and_tenant_scope() -> None:
    container = DummyContainer()
    app.dependency_overrides[get_container] = lambda: container
    app.dependency_overrides[get_current_user] = lambda: RequestUser(user_id='u1', client_id='tenant-a', roles=['CLIENT_OWNER'])
    client = TestClient(app)

    assert client.get('/finance/overview').status_code == 200
    assert len(client.get('/finance/expenses').json()['items']) == 1
    assert client.get('/finance/expenses?payment_status=bad').status_code == 400

    created = client.post('/finance/expenses', json={"expense_date": "2026-03-11", "category": "Rent", "amount": 200, "payment_status": "unpaid", "note": "March"})
    assert created.status_code == 201

    patched = client.patch('/finance/expenses/exp-1', json={"expense_date": "2026-03-12", "category": "Logistics", "amount": 60, "payment_status": "paid", "note": "Courier 2"})
    assert patched.status_code == 200

    assert client.get('/finance/receivables').status_code == 200
    assert client.get('/finance/payables').status_code == 200
    assert client.get('/finance/transactions').status_code == 200

    app.dependency_overrides[get_current_user] = lambda: RequestUser(user_id='u2', client_id='tenant-b', roles=['CLIENT_OWNER'])
    tenant_b_expenses = client.get('/finance/expenses').json()['items']
    assert tenant_b_expenses == []

    app.dependency_overrides.clear()
