from decimal import Decimal
from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy import select

from easy_ecom.api import dependencies as deps
from easy_ecom.api.main import create_app
from easy_ecom.core.ids import new_uuid
from easy_ecom.core.security import hash_password
from easy_ecom.data.store.postgres_models import AuditLogModel, ClientModel, ClientSettingsModel
from easy_ecom.tests.support.sqlite_runtime import build_sqlite_runtime, seed_auth_user

CLIENT_ID = "22222222-2222-2222-2222-222222222222"
USER_ID = "11111111-1111-1111-1111-111111111111"


def _setup_runtime(tmp_path: Path, monkeypatch):
    runtime = build_sqlite_runtime(tmp_path, "settings.db")
    monkeypatch.setattr(deps, "settings", runtime.settings)
    seed_auth_user(
        runtime.session_factory,
        user_id=USER_ID,
        client_id=CLIENT_ID,
        email="owner@example.com",
        name="Owner",
        password_hash=hash_password("secret"),
        role_code="CLIENT_OWNER",
    )
    return runtime


def _login_client() -> TestClient:
    client = TestClient(create_app())
    response = client.post("/auth/login", json={"email": "owner@example.com", "password": "secret"})
    assert response.status_code == 200
    return client


def test_settings_workspace_returns_defaults_when_row_is_missing(monkeypatch, tmp_path: Path) -> None:
    runtime = _setup_runtime(tmp_path, monkeypatch)
    client = _login_client()

    response = client.get("/settings/workspace")

    assert response.status_code == 200
    payload = response.json()
    assert payload["tenant_context"]["client_id"] == CLIENT_ID
    assert payload["defaults"]["default_location_name"] == "Main Warehouse"
    assert payload["defaults"]["low_stock_threshold"] == 5
    assert payload["prefixes"]["sales_prefix"] == "SO"
    assert payload["prefixes"]["purchases_prefix"] == "PO"
    assert payload["prefixes"]["returns_prefix"] == "RT"

    settings_rows = runtime.store.read("client_settings.csv")
    assert len(settings_rows[settings_rows["client_id"] == CLIENT_ID]) == 1


def test_settings_workspace_updates_profile_defaults_and_prefixes(monkeypatch, tmp_path: Path) -> None:
    runtime = _setup_runtime(tmp_path, monkeypatch)
    with runtime.session_factory() as session:
        session.add(
            ClientSettingsModel(
                client_settings_id=new_uuid(),
                client_id=CLIENT_ID,
                low_stock_threshold=Decimal("2"),
                allow_backorder=False,
                default_location_name="Main Warehouse",
                require_discount_approval=False,
                order_prefix="SO",
                purchase_prefix="PO",
                return_prefix="RT",
            )
        )
        session.commit()

    client = _login_client()
    response = client.put(
        "/settings/workspace",
        json={
            "profile": {
                "business_name": "Tenant One",
                "contact_name": "Asha Contact",
                "owner_name": "Asha Owner",
                "email": "ops@tenant.test",
                "phone": "+9715000001",
                "address": "Dubai",
                "website_url": "https://tenant.test",
                "whatsapp_number": "+9715000001",
                "timezone": "Asia/Dubai",
                "currency_code": "aed",
                "currency_symbol": "AED",
                "notes": "Primary tenant profile",
            },
            "defaults": {
                "default_location_name": "Flagship Warehouse",
                "low_stock_threshold": "7",
                "allow_backorder": True,
                "require_discount_approval": True,
            },
            "prefixes": {
                "sales_prefix": "sal",
                "purchases_prefix": "buy",
                "returns_prefix": "ret",
            },
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["profile"]["business_name"] == "Tenant One"
    assert payload["profile"]["currency_code"] == "AED"
    assert payload["defaults"]["low_stock_threshold"] == 7
    assert payload["defaults"]["allow_backorder"] is True
    assert payload["prefixes"]["sales_prefix"] == "SAL"
    assert payload["prefixes"]["purchases_prefix"] == "BUY"
    assert payload["prefixes"]["returns_prefix"] == "RET"

    with runtime.session_factory() as session:
        client_row = session.execute(select(ClientModel).where(ClientModel.client_id == CLIENT_ID)).scalar_one()
        settings_row = session.execute(
            select(ClientSettingsModel).where(ClientSettingsModel.client_id == CLIENT_ID)
        ).scalar_one()
        audit_rows = session.execute(
            select(AuditLogModel).where(AuditLogModel.client_id == CLIENT_ID)
        ).scalars().all()

        assert client_row.business_name == "Tenant One"
        assert client_row.currency_code == "AED"
        assert settings_row.default_location_name == "Flagship Warehouse"
        assert settings_row.low_stock_threshold == Decimal("7")
        assert settings_row.allow_backorder is True
        assert settings_row.order_prefix == "SAL"
        assert settings_row.purchase_prefix == "BUY"
        assert settings_row.return_prefix == "RET"
        assert [row.action for row in audit_rows] == ["settings_updated"]
        assert "order_prefix" in (audit_rows[0].metadata_json or {}).get("changed_fields", [])
