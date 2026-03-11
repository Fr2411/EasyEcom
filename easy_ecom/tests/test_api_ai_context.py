from fastapi.testclient import TestClient

from easy_ecom.api.dependencies import RequestUser, get_container, get_current_user
from easy_ecom.api.main import app, create_app


class DummyAiContextService:
    def overview(self, *, client_id: str):
        return {
            "tenant_id": client_id,
            "generated_at": "2026-03-15T10:00:00+00:00",
            "products_count": 2 if client_id == "tenant-a" else 0,
            "variants_count": 3 if client_id == "tenant-a" else 0,
            "active_customers_count": 1 if client_id == "tenant-a" else 0,
            "confirmed_sales_count": 4 if client_id == "tenant-a" else 0,
            "confirmed_sales_revenue": 450.0 if client_id == "tenant-a" else 0.0,
            "low_stock_items_count": 1 if client_id == "tenant-a" else 0,
            "domains": ["products", "stock"],
            "deferred_capabilities": ["No external channel delivery in this phase."],
        }

    def products_context(self, *, client_id: str, query: str, limit: int):
        items = []
        if client_id == "tenant-a":
            items = [
                {
                    "product_id": "prd-1",
                    "product_name": "Blue Tee",
                    "category": "Apparel",
                    "default_price": 199.0,
                    "stock_qty": 8.0,
                    "variants": [],
                }
            ]
        return {"query": query.strip().lower(), "count": len(items), "items": items[:limit]}

    def stock_context(self, *, client_id: str, product_id: str):
        if client_id != "tenant-a":
            return {"product_id": product_id or None, "count": 0, "items": []}
        return {
            "product_id": product_id or None,
            "count": 1,
            "items": [{"product_id": "prd-1", "product_name": "Blue Tee", "available_qty": 8.0}],
        }

    def low_stock_context(self, *, client_id: str, threshold: int | None):
        return {
            "threshold": 5 if threshold is None else threshold,
            "count": 0 if client_id != "tenant-a" else 1,
            "items": [] if client_id != "tenant-a" else [{"product_id": "prd-2", "product_name": "Cap", "available_qty": 2.0}],
        }

    def sales_context(self, *, client_id: str, days: int):
        return {
            "window_days": days,
            "confirmed_sales_count": 0 if client_id != "tenant-a" else 2,
            "confirmed_sales_revenue": 0.0 if client_id != "tenant-a" else 250.0,
            "top_products": [],
        }

    def customers_context(self, *, client_id: str, query: str):
        if client_id != "tenant-a":
            return {"query": query.strip().lower(), "count": 0, "items": []}
        return {
            "query": query.strip().lower(),
            "count": 1,
            "items": [{"customer_id": "cus-1", "full_name": "Alice", "phone": "111", "email": "a@x.com", "is_active": True}],
        }

    def lookup_context(self, *, client_id: str, kind: str, query: str):
        if client_id != "tenant-a":
            return {"query": query, "count": 0, "items": []}
        return {"query": query, "count": 1, "items": [{"kind": kind, "id": "x-1"}]}

    def recent_activity_context(self, *, client_id: str, days: int):
        if client_id != "tenant-a":
            return {"window_days": days, "count": 0, "items": []}
        return {
            "window_days": days,
            "count": 1,
            "items": [{"type": "sale", "timestamp": "2026-03-15T10:00:00+00:00", "reference_id": "ord-1", "summary": "sale"}],
        }

    def handle_inbound_inquiry(self, *, client_id: str, payload):
        if not payload.message.strip():
            raise ValueError("message is required")
        return {
            "intent": "stock_check",
            "suggested_endpoint": "/ai/context/stock",
            "customer_ref": payload.customer_ref,
            "context": self.stock_context(client_id=client_id, product_id=""),
            "guardrails": {"tenant_scoped": True, "read_only": True, "llm_direct_db_access": False},
        }


class DummyContainer:
    def __init__(self) -> None:
        self.ai_context = DummyAiContextService()


def test_ai_context_requires_authentication() -> None:
    client = TestClient(create_app())
    resp = client.get("/ai/context/overview")
    assert resp.status_code == 401


def test_ai_context_tenant_scope_lookup_and_empty_behavior() -> None:
    app.dependency_overrides[get_container] = lambda: DummyContainer()
    app.dependency_overrides[get_current_user] = lambda: RequestUser(user_id="u1", client_id="tenant-a", roles=["CLIENT_OWNER"])
    client = TestClient(app)

    overview = client.get("/ai/context/overview")
    assert overview.status_code == 200
    assert overview.json()["confirmed_sales_count"] == 4

    lookup = client.get("/ai/context/lookup?kind=product&query=tee")
    assert lookup.status_code == 200
    assert lookup.json()["count"] == 1

    low_stock = client.get("/ai/context/low-stock?threshold=3")
    assert low_stock.status_code == 200
    assert low_stock.json()["threshold"] == 3

    hook = client.post("/ai/hooks/inbound-inquiry", json={"message": "stock availability", "customer_ref": "cus-1"})
    assert hook.status_code == 200
    assert hook.json()["guardrails"]["tenant_scoped"] is True

    app.dependency_overrides[get_current_user] = lambda: RequestUser(user_id="u2", client_id="tenant-b", roles=["CLIENT_OWNER"])
    tenant_b = client.get("/ai/context/overview")
    assert tenant_b.status_code == 200
    assert tenant_b.json()["confirmed_sales_count"] == 0

    empty_products = client.get("/ai/context/products?query=tee")
    assert empty_products.status_code == 200
    assert empty_products.json()["items"] == []

    bad_lookup = client.get("/ai/context/lookup?kind=unknown&query=x")
    assert bad_lookup.status_code == 422

    app.dependency_overrides.clear()
