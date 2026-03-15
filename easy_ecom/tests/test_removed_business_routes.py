from pathlib import Path

from fastapi.testclient import TestClient

from easy_ecom.api import dependencies as deps
from easy_ecom.api.main import create_app
from easy_ecom.core.security import hash_password
from easy_ecom.tests.support.sqlite_runtime import build_sqlite_runtime, seed_auth_user


def _client_with_auth(tmp_path: Path, monkeypatch) -> TestClient:
    runtime = build_sqlite_runtime(tmp_path, "overview.db")
    monkeypatch.setattr(deps, "settings", runtime.settings)
    seed_auth_user(runtime.session_factory, password_hash=hash_password("secret"))

    client = TestClient(create_app())
    login_response = client.post("/auth/login", json={"email": "u1@example.com", "password": "secret"})
    assert login_response.status_code == 200
    return client


def test_new_module_overview_routes_are_available(monkeypatch, tmp_path: Path) -> None:
    client = _client_with_auth(tmp_path, monkeypatch)

    for path in [
        "/dashboard/overview",
        "/catalog/overview",
        "/inventory/overview",
        "/purchases/overview",
        "/customers/overview",
        "/sales/overview",
        "/finance/overview",
        "/returns/overview",
        "/reports/overview",
        "/admin/overview",
        "/settings/overview",
    ]:
        response = client.get(path)
        assert response.status_code == 200, path


def test_removed_legacy_business_paths_still_return_missing(monkeypatch, tmp_path: Path) -> None:
    client = _client_with_auth(tmp_path, monkeypatch)

    for path in [
        "/catalog/archive",
        "/products/search",
        "/products-stock/snapshot",
        "/sales/create",
        "/returns/approve",
        "/purchases/receive",
        "/admin/users",
        "/ai-review/drafts",
        "/automation/policies",
    ]:
        response = client.get(path)
        assert response.status_code == 404, path


def test_new_sales_agent_routes_are_available_with_auth(monkeypatch, tmp_path: Path) -> None:
    client = _client_with_auth(tmp_path, monkeypatch)

    for path in [
        "/integrations/channels",
        "/sales-agent/conversations",
        "/sales-agent/orders",
    ]:
        response = client.get(path)
        assert response.status_code == 200, path
