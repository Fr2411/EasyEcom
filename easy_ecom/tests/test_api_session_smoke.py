from pathlib import Path

from fastapi.testclient import TestClient

from easy_ecom.api.main import create_app
from easy_ecom.core.config import Settings
from easy_ecom.api import dependencies as deps
from easy_ecom.core.security import hash_password
from easy_ecom.data.store.csv_store import CsvStore
from easy_ecom.data.store.schema import TABLE_SCHEMAS


def test_session_me_smoke(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(deps, "settings", Settings(data_dir=tmp_path, storage_backend="csv"))
    store = CsvStore(tmp_path)
    for table_name, columns in TABLE_SCHEMAS.items():
        store.ensure_table(table_name, columns)

    store.append(
        "users.csv",
        {
            "user_id": "u1",
            "client_id": "c1",
            "name": "User One",
            "email": "u1@example.com",
            "password": "",
            "password_hash": hash_password("secret"),
            "is_active": "true",
            "created_at": "",
        },
    )
    store.append("user_roles.csv", {"user_id": "u1", "role_code": "SUPER_ADMIN"})

    client = TestClient(create_app())
    client.post("/auth/login", json={"email": "u1@example.com", "password": "secret"})
    response = client.get("/session/me")

    assert response.status_code == 200
    assert response.json()["user_id"] == "u1"
