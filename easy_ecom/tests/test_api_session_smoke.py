from pathlib import Path

from fastapi.testclient import TestClient

from easy_ecom.api.main import create_app
from easy_ecom.api import dependencies as deps
from easy_ecom.core.security import hash_password
from easy_ecom.tests.support.sqlite_runtime import build_sqlite_runtime, seed_auth_user

USER_ID = "11111111-1111-1111-1111-111111111111"


def test_session_me_smoke(monkeypatch, tmp_path: Path) -> None:
    runtime = build_sqlite_runtime(tmp_path, "session_smoke.db")
    monkeypatch.setattr(deps, "settings", runtime.settings)
    seed_auth_user(runtime.session_factory, password_hash=hash_password("secret"))

    client = TestClient(create_app())
    client.post("/auth/login", json={"email": "u1@example.com", "password": "secret"})
    response = client.get("/session/me")

    assert response.status_code == 200
    assert response.json()["user_id"] == USER_ID
