from pathlib import Path

from fastapi.testclient import TestClient

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
