from __future__ import annotations

from dataclasses import dataclass

from fastapi.testclient import TestClient

from easy_ecom.api.dependencies import RequestUser, get_container, get_current_user
from easy_ecom.api.main import app, create_app


@dataclass
class DummyTenant:
    client_id: str
    business_name: str


class DummySettingsService:
    def __init__(self) -> None:
        self.business = {
            "tenant-a": {
                "client_id": "tenant-a",
                "business_name": "Tenant A",
                "display_name": "A Trade",
                "phone": "",
                "email": "",
                "address": "",
                "currency_code": "USD",
                "timezone": "UTC",
                "tax_registration_no": "",
                "logo_upload_supported": False,
                "logo_upload_deferred_reason": "Deferred",
            },
            "tenant-b": {
                "client_id": "tenant-b",
                "business_name": "Tenant B",
                "display_name": "B Trade",
                "phone": "",
                "email": "",
                "address": "",
                "currency_code": "EUR",
                "timezone": "UTC",
                "tax_registration_no": "",
                "logo_upload_supported": False,
                "logo_upload_deferred_reason": "Deferred",
            },
        }
        self.preferences = {
            "tenant-a": {
                "low_stock_threshold": 5,
                "default_sales_note": "",
                "default_inventory_adjustment_reasons": [],
                "default_payment_terms_days": 0,
                "active_usage": {
                    "low_stock_threshold": True,
                    "default_sales_note": False,
                    "default_inventory_adjustment_reasons": False,
                    "default_payment_terms_days": False,
                },
            }
        }
        self.sequences = {
            "tenant-a": {
                "sales_prefix": "SAL",
                "returns_prefix": "RET",
                "active_usage": {"sales_prefix": False, "returns_prefix": False},
            }
        }

    def get_business_profile(self, *, client_id: str):
        return self.business.get(client_id)

    def patch_business_profile(self, *, client_id: str, payload):
        if client_id not in self.business:
            return None
        for k, v in payload.__dict__.items():
            if v is not None:
                self.business[client_id][k] = v
        return self.business[client_id]

    def get_preferences(self, *, client_id: str):
        return self.preferences.get(client_id)

    def patch_preferences(self, *, client_id: str, payload):
        if client_id not in self.preferences:
            return None
        if payload.low_stock_threshold is not None and payload.low_stock_threshold > 999:
            raise ValueError("low_stock_threshold must be between 0 and 999")
        for k, v in payload.__dict__.items():
            if v is not None:
                self.preferences[client_id][k] = v
        return self.preferences[client_id]

    def get_sequences(self, *, client_id: str):
        return self.sequences.get(client_id)

    def patch_sequences(self, *, client_id: str, payload):
        if client_id not in self.sequences:
            return None
        for k, v in payload.__dict__.items():
            if v is not None:
                self.sequences[client_id][k] = v
        return self.sequences[client_id]

    def get_tenant_context(self, *, client_id: str):
        item = self.business.get(client_id)
        if not item:
            return None
        return {
            "client_id": client_id,
            "business_name": item["business_name"],
            "status": "active",
            "currency_code": item["currency_code"],
        }


class DummyContainer:
    def __init__(self) -> None:
        self.settings_mvp = DummySettingsService()


def test_settings_requires_auth() -> None:
    client = TestClient(create_app())
    assert client.get('/settings/business-profile').status_code == 401


def test_settings_fetch_and_tenant_isolation() -> None:
    container = DummyContainer()
    app.dependency_overrides[get_container] = lambda: container
    app.dependency_overrides[get_current_user] = lambda: RequestUser(user_id='u-a', client_id='tenant-a', roles=['CLIENT_EMPLOYEE'])
    client = TestClient(app)

    res = client.get('/settings/business-profile')
    assert res.status_code == 200
    assert res.json()['client_id'] == 'tenant-a'

    tenant = client.get('/settings/tenant-context')
    assert tenant.status_code == 200
    assert tenant.json()['business_name'] == 'Tenant A'

    app.dependency_overrides.clear()


def test_settings_non_admin_cannot_update() -> None:
    container = DummyContainer()
    app.dependency_overrides[get_container] = lambda: container
    app.dependency_overrides[get_current_user] = lambda: RequestUser(user_id='u-a', client_id='tenant-a', roles=['CLIENT_EMPLOYEE'])
    client = TestClient(app)

    forbidden = client.patch('/settings/business-profile', json={'business_name': 'New Name'})
    assert forbidden.status_code == 403

    app.dependency_overrides.clear()


def test_settings_admin_updates_and_validation() -> None:
    container = DummyContainer()
    app.dependency_overrides[get_container] = lambda: container
    app.dependency_overrides[get_current_user] = lambda: RequestUser(user_id='u-a', client_id='tenant-a', roles=['CLIENT_OWNER'])
    client = TestClient(app)

    updated = client.patch('/settings/business-profile', json={'business_name': 'Tenant A Prime'})
    assert updated.status_code == 200
    assert updated.json()['business_name'] == 'Tenant A Prime'

    partial = client.patch('/settings/preferences', json={'default_sales_note': 'Thank you'})
    assert partial.status_code == 200
    assert partial.json()['default_sales_note'] == 'Thank you'

    bad = client.patch('/settings/sequences', json={'sales_prefix': ''})
    assert bad.status_code == 422

    app.dependency_overrides.clear()
