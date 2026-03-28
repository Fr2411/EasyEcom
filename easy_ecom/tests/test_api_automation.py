from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from easy_ecom.api import dependencies as deps
from easy_ecom.api.main import create_app
from easy_ecom.core.security import hash_password
from easy_ecom.tests.support.sqlite_runtime import build_sqlite_runtime, seed_auth_user


def _login_client(tmp_path: Path, monkeypatch) -> TestClient:
    runtime = build_sqlite_runtime(tmp_path, "automation.db")
    monkeypatch.setattr(deps, "settings", runtime.settings)
    seed_auth_user(
        runtime.session_factory,
        password_hash=hash_password("secret"),
        role_code="CLIENT_OWNER",
    )

    client = TestClient(create_app())
    login_response = client.post("/auth/login", json={"email": "u1@example.com", "password": "secret"})
    assert login_response.status_code == 200
    return client


def test_automation_overview_and_empty_lists_are_available_with_auth(monkeypatch, tmp_path: Path) -> None:
    client = _login_client(tmp_path, monkeypatch)

    overview_response = client.get("/automation/overview")
    rules_response = client.get("/automation/rules")
    runs_response = client.get("/automation/runs")
    rule_runs_response = client.get("/automation/rules/sample-rule/runs")

    assert overview_response.status_code == 200
    assert rules_response.status_code == 200
    assert runs_response.status_code == 200
    assert rule_runs_response.status_code == 200

    overview = overview_response.json()
    assert overview["module"] == "automation"
    assert overview["status"] == "skeleton"
    assert [metric["value"] for metric in overview["metrics"]] == ["0", "0", "0"]

    assert rules_response.json() == {"items": []}
    assert runs_response.json() == {"items": []}
    assert rule_runs_response.json() == {"items": []}


def test_automation_rule_detail_returns_not_found(monkeypatch, tmp_path: Path) -> None:
    client = _login_client(tmp_path, monkeypatch)

    response = client.get("/automation/rules/sample-rule")

    assert response.status_code == 404
    assert response.json()["detail"] == "Automation rules are not yet configured"


def test_automation_routes_require_authentication(tmp_path: Path, monkeypatch) -> None:
    runtime = build_sqlite_runtime(tmp_path, "automation-unauth.db")
    monkeypatch.setattr(deps, "settings", runtime.settings)

    client = TestClient(create_app())
    response = client.get("/automation/overview")

    assert response.status_code == 401


def test_automation_routes_require_page_access(monkeypatch, tmp_path: Path) -> None:
    client = _login_client(tmp_path, monkeypatch)
    session = client.cookies.get(deps.settings.session_cookie_name)
    assert session

    payload = deps._signer().loads(session)
    payload["allowed_pages"] = ["Dashboard", "Settings"]
    client.cookies.set(deps.settings.session_cookie_name, deps._signer().dumps(payload))

    response = client.get("/automation/overview")

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "ACCESS_DENIED"
