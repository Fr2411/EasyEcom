from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

import easy_ecom.api.main as api_main
from easy_ecom.api import dependencies as deps
from easy_ecom.api.main import create_app
from easy_ecom.api.routers import health as health_router
from easy_ecom.core.security import hash_password
from easy_ecom.data.store.postgres_db import build_postgres_engine
from easy_ecom.tests.support.sqlite_runtime import build_sqlite_runtime
from easy_ecom.tests.test_api_commerce import _setup_runtime, _seed_variant


def test_app_builds_db_runtime_once_per_process_lifecycle(monkeypatch, tmp_path: Path):
    runtime = build_sqlite_runtime(tmp_path, "lifecycle.db")
    monkeypatch.setattr(deps, "settings", runtime.settings)
    monkeypatch.setattr(api_main, "settings", runtime.settings)

    build_calls = 0
    original_builder = api_main.build_runtime_engine

    def counting_builder(config):
        nonlocal build_calls
        build_calls += 1
        return original_builder(config)

    monkeypatch.setattr(api_main, "build_runtime_engine", counting_builder)

    app = create_app()
    with TestClient(app) as client:
        assert client.get("/health").status_code == 200
        assert client.get("/health/live").status_code == 200
        assert client.get("/health/ready").status_code == 200
        assert client.get("/health").status_code == 200

    assert build_calls == 1


def test_health_ready_fails_closed_when_database_check_fails(monkeypatch, tmp_path: Path):
    runtime = build_sqlite_runtime(tmp_path, "health-ready.db")
    monkeypatch.setattr(deps, "settings", runtime.settings)
    monkeypatch.setattr(api_main, "settings", runtime.settings)

    app = create_app()

    class BrokenEngine:
        def connect(self):
            raise RuntimeError("database unavailable")

    app.dependency_overrides[health_router.get_engine] = lambda: BrokenEngine()

    with TestClient(app) as client:
        response = client.get("/health/ready")

    assert response.status_code == 503
    assert response.json()["error"]["code"] == "READINESS_CHECK_FAILED"


def test_auth_and_dashboard_smoke_under_repeated_requests(monkeypatch, tmp_path: Path):
    runtime = _setup_runtime(tmp_path, monkeypatch, role_code="CLIENT_OWNER")
    monkeypatch.setattr(api_main, "settings", runtime.settings)
    _seed_variant(
        runtime,
        product_name="Trail Runner",
        sku="TRAIL-42-BLK",
        size="42",
        color="Black",
        stock_qty=1,
    )

    app = create_app()
    with TestClient(app) as client:
        login_response = client.post("/auth/login", json={"email": "owner@example.com", "password": "secret"})
        assert login_response.status_code == 200
        for _ in range(15):
            me_response = client.get("/auth/me")
            analytics_response = client.get("/dashboard/analytics", params={"range_key": "mtd"})
            assert me_response.status_code == 200
            assert analytics_response.status_code == 200


def test_postgres_engine_uses_rds_safe_pool_defaults(monkeypatch):
    captured: dict[str, object] = {}

    def fake_create_engine(dsn: str, **kwargs):
        captured["dsn"] = dsn
        captured["kwargs"] = kwargs
        return object()

    monkeypatch.setattr("easy_ecom.data.store.postgres_db.create_engine", fake_create_engine)
    config = deps.settings.__class__(
        database_url="postgresql+psycopg://user:pass@db.example.com:5432/easy_ecom",
        postgres_pool_size=8,
        postgres_max_overflow=16,
        postgres_pool_timeout_seconds=25,
        postgres_pool_recycle_seconds=900,
    )

    build_postgres_engine(config)

    assert captured["dsn"] == config.postgres_dsn
    assert captured["kwargs"] == {
        "echo": config.postgres_echo,
        "pool_pre_ping": True,
        "pool_recycle": 900,
        "pool_size": 8,
        "max_overflow": 16,
        "pool_timeout": 25,
    }
