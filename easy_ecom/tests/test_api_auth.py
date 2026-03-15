from pathlib import Path

from fastapi import HTTPException
from fastapi.testclient import TestClient
import pytest

from easy_ecom.api.main import create_app
from easy_ecom.api import dependencies as deps
from easy_ecom.core.security import hash_password
from easy_ecom.tests.support.sqlite_runtime import build_sqlite_runtime, seed_auth_user

USER_ID = "11111111-1111-1111-1111-111111111111"
CLIENT_ID = "22222222-2222-2222-2222-222222222222"


def _setup_runtime(tmp_path: Path):
    return build_sqlite_runtime(tmp_path, "api_auth.db")


def _append_user(
    runtime,
    *,
    password: str = "",
    password_hash: str = "",
    is_active: bool = True,
    role_code: str = "SUPER_ADMIN",
) -> None:
    seed_auth_user(
        runtime.session_factory,
        password=password,
        password_hash=password_hash,
        is_active=is_active,
        role_code=role_code,
    )


def test_valid_login(monkeypatch, tmp_path: Path):
    runtime = _setup_runtime(tmp_path)
    monkeypatch.setattr(deps, "settings", runtime.settings)
    _append_user(runtime, password_hash=hash_password("secret"))

    client = TestClient(create_app())
    response = client.post("/auth/login", json={"email": "u1@example.com", "password": "secret"})

    assert response.status_code == 200
    assert response.cookies.get("easy_ecom_session")
    assert "Dashboard" in response.json()["allowed_pages"]


def test_invalid_password(monkeypatch, tmp_path: Path):
    runtime = _setup_runtime(tmp_path)
    monkeypatch.setattr(deps, "settings", runtime.settings)
    _append_user(runtime, password_hash=hash_password("secret"))

    client = TestClient(create_app())
    response = client.post("/auth/login", json={"email": "u1@example.com", "password": "bad"})
    assert response.status_code == 401


def test_inactive_user_blocked(monkeypatch, tmp_path: Path):
    runtime = _setup_runtime(tmp_path)
    monkeypatch.setattr(deps, "settings", runtime.settings)
    _append_user(runtime, password_hash=hash_password("secret"), is_active=False)

    client = TestClient(create_app())
    response = client.post("/auth/login", json={"email": "u1@example.com", "password": "secret"})
    assert response.status_code == 401


def test_legacy_plaintext_migrates(monkeypatch, tmp_path: Path):
    runtime = _setup_runtime(tmp_path)
    monkeypatch.setattr(deps, "settings", runtime.settings)
    _append_user(runtime, password="legacy-secret", password_hash="")

    client = TestClient(create_app())
    response = client.post("/auth/login", json={"email": "u1@example.com", "password": "legacy-secret"})

    assert response.status_code == 200
    users = runtime.store.read("users.csv")
    row = users[users["user_id"] == USER_ID].iloc[0]
    assert row["password"] == ""
    assert str(row["password_hash"]).startswith("$2")


def test_logout(monkeypatch, tmp_path: Path):
    runtime = _setup_runtime(tmp_path)
    monkeypatch.setattr(deps, "settings", runtime.settings)
    _append_user(runtime, password_hash=hash_password("secret"))

    client = TestClient(create_app())
    client.post("/auth/login", json={"email": "u1@example.com", "password": "secret"})
    response = client.post("/auth/logout")

    assert response.status_code == 200


def test_session_endpoint_rejects_anonymous(monkeypatch, tmp_path: Path):
    runtime = _setup_runtime(tmp_path)
    monkeypatch.setattr(deps, "settings", runtime.settings)

    client = TestClient(create_app())
    response = client.get("/session/me")

    assert response.status_code == 401


def test_login_then_me_returns_authenticated_user(monkeypatch, tmp_path: Path):
    runtime = _setup_runtime(tmp_path)
    monkeypatch.setattr(deps, "settings", runtime.settings)
    _append_user(runtime, password_hash=hash_password("secret"))

    client = TestClient(create_app())
    login_response = client.post("/auth/login", json={"email": "u1@example.com", "password": "secret"})
    assert login_response.status_code == 200

    me_response = client.get("/auth/me")
    assert me_response.status_code == 200
    assert me_response.json() == {
        "user_id": USER_ID,
        "email": "u1@example.com",
        "name": "User One",
        "business_name": "Client One",
        "role": "SUPER_ADMIN",
        "client_id": CLIENT_ID,
        "roles": ["SUPER_ADMIN"],
        "allowed_pages": [
            "Home",
            "Dashboard",
            "Catalog",
            "Inventory",
            "Purchases",
            "Sales",
            "Customers",
            "Finance",
            "Returns",
            "Reports",
            "Sales Agent",
            "Admin",
            "Settings",
        ],
        "is_authenticated": True,
    }


def test_me_requires_cookie(monkeypatch, tmp_path: Path):
    runtime = _setup_runtime(tmp_path)
    monkeypatch.setattr(deps, "settings", runtime.settings)

    client = TestClient(create_app())
    response = client.get("/auth/me")

    assert response.status_code == 401


def test_me_backfills_business_name_for_older_session_cookie(monkeypatch, tmp_path: Path):
    runtime = _setup_runtime(tmp_path)
    monkeypatch.setattr(deps, "settings", runtime.settings)
    _append_user(runtime, password_hash=hash_password("secret"), role_code="CLIENT_OWNER")

    client = TestClient(create_app())
    signer = deps.SessionSigner(deps.settings.session_secret)
    legacy_token = signer.dumps(
        {
            "user_id": USER_ID,
            "client_id": CLIENT_ID,
            "roles": ["CLIENT_OWNER"],
            "allowed_pages": ["Dashboard", "Inventory", "Sales", "Settings"],
            "email": "u1@example.com",
            "name": "User One",
        }
    )
    client.cookies.set("easy_ecom_session", legacy_token)

    response = client.get("/auth/me")

    assert response.status_code == 200
    assert response.json()["business_name"] == "Client One"
    assert "Sales Agent" in response.json()["allowed_pages"]


def test_me_rejects_corrupted_cookie(monkeypatch, tmp_path: Path):
    runtime = _setup_runtime(tmp_path)
    monkeypatch.setattr(deps, "settings", runtime.settings)

    client = TestClient(create_app())
    client.cookies.set("easy_ecom_session", "not-a-valid-token")
    response = client.get("/auth/me")

    assert response.status_code == 401


def test_logout_then_me_is_unauthorized(monkeypatch, tmp_path: Path):
    runtime = _setup_runtime(tmp_path)
    monkeypatch.setattr(deps, "settings", runtime.settings)
    _append_user(runtime, password_hash=hash_password("secret"))

    client = TestClient(create_app())
    login_response = client.post("/auth/login", json={"email": "u1@example.com", "password": "secret"})
    assert login_response.status_code == 200

    logout_response = client.post("/auth/logout")
    assert logout_response.status_code == 200

    me_response = client.get("/auth/me")
    assert me_response.status_code == 401


def test_roles_round_trip_and_id_normalization(monkeypatch, tmp_path: Path):
    from easy_ecom.api.dependencies import get_authenticated_user

    runtime = _setup_runtime(tmp_path)
    monkeypatch.setattr(deps, "settings", runtime.settings)
    signer = deps.SessionSigner(deps.settings.session_secret)
    token = signer.dumps(
        {
            "user_id": 42,
            "client_id": 7,
            "roles": "ADMIN, MANAGER",
            "email": "user@example.com",
            "name": "Typed User",
        }
    )

    user = get_authenticated_user(session_token=token)

    assert user.user_id == "42"
    assert user.client_id == "7"
    assert user.roles == ["ADMIN", "MANAGER"]


def test_me_rejects_missing_roles(monkeypatch, tmp_path: Path):
    from easy_ecom.api.dependencies import get_authenticated_user

    runtime = _setup_runtime(tmp_path)
    monkeypatch.setattr(deps, "settings", runtime.settings)
    signer = deps.SessionSigner(deps.settings.session_secret)
    token = signer.dumps(
        {
            "user_id": "u1",
            "client_id": "c1",
            "email": "user@example.com",
            "name": "No Roles",
        }
    )

    with pytest.raises(HTTPException) as exc:
        get_authenticated_user(session_token=token)

    assert exc.value.status_code == 401


def test_me_rejects_missing_client_id(monkeypatch, tmp_path: Path):
    from easy_ecom.api.dependencies import get_authenticated_user

    runtime = _setup_runtime(tmp_path)
    monkeypatch.setattr(deps, "settings", runtime.settings)
    signer = deps.SessionSigner(deps.settings.session_secret)
    token = signer.dumps(
        {
            "user_id": "u1",
            "roles": ["SUPER_ADMIN"],
            "email": "user@example.com",
            "name": "No Client",
        }
    )

    with pytest.raises(HTTPException) as exc:
        get_authenticated_user(session_token=token)

    assert exc.value.status_code == 401
