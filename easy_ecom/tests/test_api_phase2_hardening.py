from fastapi.testclient import TestClient

from easy_ecom.api.dependencies import RequestUser, get_container, get_current_user
from easy_ecom.api.main import app, create_app


class DashboardProbe:
    def __init__(self) -> None:
        self.seen_client_id = ""

    def business_health_snapshot(self, client_id: str):
        self.seen_client_id = client_id
        return {
            "Revenue": 0.0,
            "Gross Profit": 0.0,
            "Net Operating Profit": 0.0,
            "Gross Margin %": 0.0,
            "Inventory Value": 0.0,
            "Outstanding Receivables": 0.0,
            "Data Health Score": 100.0,
        }

    def overview_snapshot(self, client_id: str):
        self.seen_client_id = client_id
        return {
            "generated_at": "2026-01-01T00:00:00Z",
            "kpis": {
                "total_products": 0,
                "total_variants": 0,
                "current_stock_units": 0.0,
                "low_stock_items": 0,
            },
            "business_health": {
                "inventory_value": 0.0,
                "recent_stock_movements_count": 0,
                "sales_count_last_30_days": 0,
                "revenue_last_30_days": 0.0,
            },
            "recent_activity": [],
            "top_products": [],
        }


class ProbeContainer:
    def __init__(self) -> None:
        self.dashboard = DashboardProbe()


def test_protected_business_endpoints_reject_anonymous() -> None:
    client = TestClient(create_app())

    assert client.get("/dashboard/summary").status_code == 401
    assert client.get("/dashboard/overview").status_code == 401
    assert client.get("/products/search", params={"q": "shirt"}).status_code == 401
    assert client.get("/products/p-1").status_code == 401
    assert client.get("/stock/explorer").status_code == 401
    assert client.get("/products-stock/snapshot").status_code == 401
    assert (
        client.post(
            "/inventory/add",
            json={"product_id": "p-1", "product_name": "Demo", "qty": 1, "unit_cost": 1},
        ).status_code
        == 401
    )
    assert (
        client.post(
            "/sales/create",
            json={"customer_id": "cust-1", "items": [{"product_id": "p-1", "qty": 1, "unit_selling_price": 10}]},
        ).status_code
        == 401
    )


def test_dashboard_client_scope_is_locked_to_session_user() -> None:
    probe = ProbeContainer()
    app.dependency_overrides[get_container] = lambda: probe
    app.dependency_overrides[get_current_user] = lambda: RequestUser(
        user_id="u-1", client_id="tenant-session", roles=["SUPER_ADMIN"]
    )
    client = TestClient(app)

    response = client.get("/dashboard/summary", params={"client_id": "tenant-other"})

    assert response.status_code == 200
    assert probe.dashboard.seen_client_id == "tenant-session"

    response = client.get("/dashboard/overview", params={"client_id": "tenant-other"})

    assert response.status_code == 200
    assert probe.dashboard.seen_client_id == "tenant-session"

    app.dependency_overrides.clear()
