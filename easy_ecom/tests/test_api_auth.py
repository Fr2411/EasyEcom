from pathlib import Path

from fastapi import HTTPException
from fastapi.testclient import TestClient
import pytest

from easy_ecom.api.main import create_app
from easy_ecom.core.config import Settings
from easy_ecom.api import dependencies as deps
from easy_ecom.core.security import hash_password
from easy_ecom.data.store.csv_store import CsvStore
from easy_ecom.data.store.schema import TABLE_SCHEMAS


def _setup_store(tmp_path: Path) -> CsvStore:
    store = CsvStore(tmp_path)
    for table_name, columns in TABLE_SCHEMAS.items():
        store.ensure_table(table_name, columns)
    return store


def _append_user(store: CsvStore, *, password: str = "", password_hash: str = "", is_active: str = "true") -> None:
    store.append(
        "users.csv",
        {
            "user_id": "u1",
            "client_id": "c1",
            "name": "User One",
            "email": "u1@example.com",
            "password": password,
            "password_hash": password_hash,
            "is_active": is_active,
            "created_at": "",
        },
    )
    store.append("user_roles.csv", {"user_id": "u1", "role_code": "SUPER_ADMIN"})


def test_valid_login(monkeypatch, tmp_path: Path):
    monkeypatch.setattr(deps, "settings", Settings(data_dir=tmp_path, storage_backend="csv"))
    store = _setup_store(tmp_path)
    _append_user(store, password_hash=hash_password("secret"))

    client = TestClient(create_app())
    response = client.post("/auth/login", json={"email": "u1@example.com", "password": "secret"})

    assert response.status_code == 200
    assert response.cookies.get("easy_ecom_session")


def test_invalid_password(monkeypatch, tmp_path: Path):
    monkeypatch.setattr(deps, "settings", Settings(data_dir=tmp_path, storage_backend="csv"))
    store = _setup_store(tmp_path)
    _append_user(store, password_hash=hash_password("secret"))

    client = TestClient(create_app())
    response = client.post("/auth/login", json={"email": "u1@example.com", "password": "bad"})
    assert response.status_code == 401


def test_inactive_user_blocked(monkeypatch, tmp_path: Path):
    monkeypatch.setattr(deps, "settings", Settings(data_dir=tmp_path, storage_backend="csv"))
    store = _setup_store(tmp_path)
    _append_user(store, password_hash=hash_password("secret"), is_active="false")

    client = TestClient(create_app())
    response = client.post("/auth/login", json={"email": "u1@example.com", "password": "secret"})
    assert response.status_code == 401


def test_legacy_plaintext_migrates(monkeypatch, tmp_path: Path):
    monkeypatch.setattr(deps, "settings", Settings(data_dir=tmp_path, storage_backend="csv"))
    store = _setup_store(tmp_path)
    _append_user(store, password="legacy-secret", password_hash="")

    client = TestClient(create_app())
    response = client.post("/auth/login", json={"email": "u1@example.com", "password": "legacy-secret"})

    assert response.status_code == 200
    users = store.read("users.csv")
    row = users[users["user_id"] == "u1"].iloc[0]
    assert row["password"] == ""
    assert str(row["password_hash"]).startswith("$2")


def test_logout(monkeypatch, tmp_path: Path):
    monkeypatch.setattr(deps, "settings", Settings(data_dir=tmp_path, storage_backend="csv"))
    store = _setup_store(tmp_path)
    _append_user(store, password_hash=hash_password("secret"))

    client = TestClient(create_app())
    client.post("/auth/login", json={"email": "u1@example.com", "password": "secret"})
    response = client.post("/auth/logout")

    assert response.status_code == 200


def test_protected_endpoint_rejects_anonymous(monkeypatch, tmp_path: Path):
    monkeypatch.setattr(deps, "settings", Settings(data_dir=tmp_path, storage_backend="csv"))
    _setup_store(tmp_path)

    client = TestClient(create_app())
    response = client.get("/products-stock/snapshot")

    assert response.status_code == 401


def test_login_then_me_returns_authenticated_user(monkeypatch, tmp_path: Path):
    monkeypatch.setattr(deps, "settings", Settings(data_dir=tmp_path, storage_backend="csv"))
    store = _setup_store(tmp_path)
    _append_user(store, password_hash=hash_password("secret"))

    client = TestClient(create_app())
    login_response = client.post("/auth/login", json={"email": "u1@example.com", "password": "secret"})
    assert login_response.status_code == 200

    me_response = client.get("/auth/me")
    assert me_response.status_code == 200
    assert me_response.json() == {
        "user_id": "u1",
        "email": "u1@example.com",
        "name": "User One",
        "role": "SUPER_ADMIN",
        "client_id": "c1",
        "roles": ["SUPER_ADMIN"],
        "is_authenticated": True,
    }


def test_me_requires_cookie(monkeypatch, tmp_path: Path):
    monkeypatch.setattr(deps, "settings", Settings(data_dir=tmp_path, storage_backend="csv"))
    _setup_store(tmp_path)

    client = TestClient(create_app())
    response = client.get("/auth/me")

    assert response.status_code == 401


def test_me_rejects_corrupted_cookie(monkeypatch, tmp_path: Path):
    monkeypatch.setattr(deps, "settings", Settings(data_dir=tmp_path, storage_backend="csv"))
    _setup_store(tmp_path)

    client = TestClient(create_app())
    client.cookies.set("easy_ecom_session", "not-a-valid-token")
    response = client.get("/auth/me")

    assert response.status_code == 401


def test_logout_then_me_is_unauthorized(monkeypatch, tmp_path: Path):
    monkeypatch.setattr(deps, "settings", Settings(data_dir=tmp_path, storage_backend="csv"))
    store = _setup_store(tmp_path)
    _append_user(store, password_hash=hash_password("secret"))

    client = TestClient(create_app())
    login_response = client.post("/auth/login", json={"email": "u1@example.com", "password": "secret"})
    assert login_response.status_code == 200

    logout_response = client.post("/auth/logout")
    assert logout_response.status_code == 200

    me_response = client.get("/auth/me")
    assert me_response.status_code == 401


def test_roles_round_trip_and_id_normalization(monkeypatch, tmp_path: Path):
    from easy_ecom.api.dependencies import get_authenticated_user

    monkeypatch.setattr(deps, "settings", Settings(data_dir=tmp_path, storage_backend="csv"))
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

    monkeypatch.setattr(deps, "settings", Settings(data_dir=tmp_path, storage_backend="csv"))
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

    monkeypatch.setattr(deps, "settings", Settings(data_dir=tmp_path, storage_backend="csv"))
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
