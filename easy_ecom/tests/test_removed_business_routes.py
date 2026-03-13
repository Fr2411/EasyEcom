from fastapi.testclient import TestClient

from easy_ecom.api.main import app


def test_removed_business_routes_return_missing() -> None:
    client = TestClient(app)

    for path in [
        "/dashboard/overview",
        "/catalog/products",
        "/products/search",
        "/products-stock/snapshot",
        "/inventory",
        "/sales",
        "/finance/overview",
        "/returns",
        "/purchases",
        "/reports/summary",
        "/admin/users",
        "/integrations/channels",
        "/ai-review/drafts",
        "/automation/policies",
        "/settings",
    ]:
        response = client.get(path)
        assert response.status_code == 404
