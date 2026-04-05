from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime, timedelta
import json
from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy import func, select

from easy_ecom.api import dependencies as deps
from easy_ecom.api.main import create_app
from easy_ecom.core.security import hash_password
from easy_ecom.data.store.postgres_models import ClientModel, PaymentEventModel, SubscriptionModel
from easy_ecom.domain.services import billing_service as billing_module
from easy_ecom.tests.support.sqlite_runtime import build_sqlite_runtime, seed_auth_user

CLIENT_ID = "22222222-2222-2222-2222-222222222222"
USER_ID = "11111111-1111-1111-1111-111111111111"


def _setup_runtime(tmp_path: Path, monkeypatch):
    runtime = build_sqlite_runtime(tmp_path, "billing.db")
    billing_settings = replace(
        runtime.settings,
        app_base_url="https://app.easy-ecom.test",
        paypal_env="sandbox",
        paypal_client_id="paypal_client_id",
        paypal_client_secret="paypal_client_secret",
        paypal_webhook_id="WH-123",
        paypal_price_growth_monthly_amount="79.00",
        paypal_price_scale_monthly_amount="149.00",
    )
    monkeypatch.setattr(deps, "settings", billing_settings)
    monkeypatch.setattr(billing_module, "settings", billing_settings)
    return runtime


def _seed_owner(runtime, *, role_code: str = "CLIENT_OWNER", email: str = "owner@example.com") -> None:
    seed_auth_user(
        runtime.session_factory,
        user_id=USER_ID if role_code == "CLIENT_OWNER" else "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
        client_id=CLIENT_ID,
        email=email,
        name="Owner" if role_code == "CLIENT_OWNER" else "Staff",
        password_hash=hash_password("secret"),
        role_code=role_code,
    )


def _login(email: str = "owner@example.com") -> TestClient:
    client = TestClient(create_app())
    response = client.post("/auth/login", json={"email": email, "password": "secret"})
    assert response.status_code == 200, response.text
    return client


def _paypal_event(event_id: str, event_type: str, resource: dict) -> bytes:
    return json.dumps({"id": event_id, "event_type": event_type, "resource": resource}).encode("utf-8")


def _mock_paypal_request(monkeypatch) -> None:
    created_products: dict[str, str] = {"growth": "PROD-growth", "scale": "PROD-scale"}
    created_plans: dict[str, str] = {"growth": "P-growth", "scale": "P-scale"}

    def fake_request(self, method: str, path: str, **kwargs):
        if path == "/v1/catalogs/products" and method.upper() == "POST":
            name = (kwargs.get("json_body") or {}).get("name", "")
            key = "scale" if "Scale" in name else "growth"
            return {"id": created_products[key]}
        if path == "/v1/billing/plans" and method.upper() == "POST":
            plan_name = (kwargs.get("json_body") or {}).get("name", "")
            key = "scale" if "Scale" in plan_name else "growth"
            return {"id": created_plans[key]}
        if path.endswith("/revise"):
            return {"links": [{"rel": "approve", "href": "https://paypal.test/revise"}]}
        if path.endswith("/cancel"):
            return {}
        if path == "/v1/notifications/verify-webhook-signature":
            return {"verification_status": "SUCCESS"}
        raise AssertionError(f"Unexpected PayPal call: {method} {path}")

    monkeypatch.setattr(billing_module.BillingService, "_paypal_request", fake_request)


def _mock_subscription_details(monkeypatch, *, plan_code: str = "growth", next_billing_time: str = "2026-05-01T00:00:00Z"):
    plan_id = "P-scale" if plan_code == "scale" else "P-growth"

    def fake_fetch(self, provider_subscription_id: str):
        return {
            "id": provider_subscription_id,
            "plan_id": plan_id,
            "status": "ACTIVE",
            "custom_id": CLIENT_ID,
            "start_time": "2026-04-01T00:00:00Z",
            "subscriber": {
                "payer_id": "PAYER-123",
                "email_address": "owner@example.com",
                "name": {"given_name": "Owner", "surname": "EasyEcom"},
            },
            "billing_info": {"next_billing_time": next_billing_time},
        }

    monkeypatch.setattr(billing_module.BillingService, "_fetch_subscription_details", fake_fetch)


def test_public_plans_backfill_existing_tenants_to_free(monkeypatch, tmp_path: Path) -> None:
    runtime = _setup_runtime(tmp_path, monkeypatch)
    _mock_paypal_request(monkeypatch)
    _seed_owner(runtime)

    client = TestClient(create_app())
    response = client.get("/public/billing/plans")

    assert response.status_code == 200
    items = response.json()["items"]
    assert [item["plan_code"] for item in items] == ["free", "growth", "scale"]
    assert items[1]["billing_provider"] == "paypal"
    assert items[1]["provider_plan_id"] == "P-growth"

    with runtime.session_factory() as session:
        tenant = session.execute(select(ClientModel).where(ClientModel.client_id == CLIENT_ID)).scalar_one()
        subscription = session.execute(
            select(SubscriptionModel).where(SubscriptionModel.client_id == CLIENT_ID)
        ).scalar_one()
        assert tenant.billing_plan_code == "free"
        assert subscription.plan_code == "free"
        assert subscription.billing_provider == "paypal"


def test_non_owner_cannot_manage_billing(monkeypatch, tmp_path: Path) -> None:
    runtime = _setup_runtime(tmp_path, monkeypatch)
    _mock_paypal_request(monkeypatch)
    _seed_owner(runtime, role_code="CLIENT_STAFF", email="staff@example.com")

    client = _login("staff@example.com")
    response = client.post("/billing/change-plan", json={"target_plan_code": "scale"})

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "ACCESS_DENIED"


def test_verified_paypal_webhook_activates_and_graces_subscription(monkeypatch, tmp_path: Path) -> None:
    runtime = _setup_runtime(tmp_path, monkeypatch)
    _mock_paypal_request(monkeypatch)
    _mock_subscription_details(monkeypatch, plan_code="growth", next_billing_time="2026-05-01T00:00:00Z")
    _seed_owner(runtime)

    client = _login()

    activated = client.post(
        "/billing/webhooks/paypal",
        content=_paypal_event("WH-EVT-1", "BILLING.SUBSCRIPTION.ACTIVATED", {"id": "I-123", "custom_id": CLIENT_ID}),
        headers={
            "PAYPAL-AUTH-ALGO": "algo",
            "PAYPAL-CERT-URL": "https://paypal.test/cert",
            "PAYPAL-TRANSMISSION-ID": "tx-1",
            "PAYPAL-TRANSMISSION-SIG": "sig",
            "PAYPAL-TRANSMISSION-TIME": "2026-04-02T00:00:00Z",
        },
    )
    assert activated.status_code == 200
    assert activated.json()["status"] == "synced"

    paid = client.post(
        "/billing/webhooks/paypal",
        content=_paypal_event("WH-EVT-2", "PAYMENT.SALE.COMPLETED", {"id": "SALE-1", "billing_agreement_id": "I-123"}),
        headers={
            "PAYPAL-AUTH-ALGO": "algo",
            "PAYPAL-CERT-URL": "https://paypal.test/cert",
            "PAYPAL-TRANSMISSION-ID": "tx-2",
            "PAYPAL-TRANSMISSION-SIG": "sig",
            "PAYPAL-TRANSMISSION-TIME": "2026-04-02T00:01:00Z",
        },
    )
    assert paid.status_code == 200
    assert paid.json()["status"] == "paid"

    state = client.get("/billing/subscription")
    assert state.status_code == 200
    assert state.json()["plan_code"] == "growth"
    assert state.json()["billing_access_state"] == "paid_active"
    assert state.json()["provider_subscription_id"] == "I-123"

    failed = client.post(
        "/billing/webhooks/paypal",
        content=_paypal_event("WH-EVT-3", "BILLING.SUBSCRIPTION.PAYMENT.FAILED", {"id": "I-123", "custom_id": CLIENT_ID}),
        headers={
            "PAYPAL-AUTH-ALGO": "algo",
            "PAYPAL-CERT-URL": "https://paypal.test/cert",
            "PAYPAL-TRANSMISSION-ID": "tx-3",
            "PAYPAL-TRANSMISSION-SIG": "sig",
            "PAYPAL-TRANSMISSION-TIME": "2026-04-02T00:02:00Z",
        },
    )
    assert failed.status_code == 200
    assert failed.json()["status"] == "past_due"

    grace_state = client.get("/billing/subscription")
    assert grace_state.status_code == 200
    assert grace_state.json()["billing_status"] == "past_due"
    assert grace_state.json()["billing_access_state"] == "read_only_grace"


def test_change_plan_and_cancel_preserve_cycle_end_rules(monkeypatch, tmp_path: Path) -> None:
    runtime = _setup_runtime(tmp_path, monkeypatch)
    _mock_paypal_request(monkeypatch)
    _seed_owner(runtime)

    with runtime.session_factory() as session:
        tenant = session.execute(select(ClientModel).where(ClientModel.client_id == CLIENT_ID)).scalar_one()
        tenant.billing_plan_code = "growth"
        tenant.billing_status = "active"
        tenant.billing_access_state = "paid_active"
        subscription = session.execute(
            select(SubscriptionModel).where(SubscriptionModel.client_id == CLIENT_ID)
        ).scalar_one()
        subscription.plan_code = "growth"
        subscription.status = "active"
        subscription.provider_subscription_id = "I-123"
        subscription.provider_customer_id = "PAYER-123"
        subscription.provider_plan_id = "P-growth"
        subscription.current_period_start = datetime(2026, 4, 1, tzinfo=UTC)
        subscription.current_period_end = datetime(2026, 5, 1, tzinfo=UTC)
        session.commit()

    client = _login()

    change = client.post("/billing/change-plan", json={"target_plan_code": "scale"})
    assert change.status_code == 200
    assert change.json()["status"] == "plan_change_requested"
    assert change.json()["action_url"] == "https://paypal.test/revise"

    cancel = client.post("/billing/cancel-subscription")
    assert cancel.status_code == 200
    assert cancel.json()["status"] == "cancellation_scheduled"
    assert cancel.json()["action_url"] is None

    with runtime.session_factory() as session:
        subscription = session.execute(
            select(SubscriptionModel).where(SubscriptionModel.client_id == CLIENT_ID)
        ).scalar_one()
        assert subscription.pending_plan_code == "scale"
        assert subscription.cancel_at_period_end is True
        assert subscription.cancel_effective_at == datetime(2026, 5, 1, tzinfo=UTC)


def test_paypal_webhook_idempotency_and_period_end_downgrade(monkeypatch, tmp_path: Path) -> None:
    runtime = _setup_runtime(tmp_path, monkeypatch)
    _mock_paypal_request(monkeypatch)
    _mock_subscription_details(monkeypatch, plan_code="growth", next_billing_time="2026-04-01T00:00:00Z")
    _seed_owner(runtime)

    client = _login()
    payload = _paypal_event("WH-DUP", "PAYMENT.SALE.COMPLETED", {"id": "SALE-1", "billing_agreement_id": "I-123", "custom_id": CLIENT_ID})
    headers = {
        "PAYPAL-AUTH-ALGO": "algo",
        "PAYPAL-CERT-URL": "https://paypal.test/cert",
        "PAYPAL-TRANSMISSION-ID": "tx-dup",
        "PAYPAL-TRANSMISSION-SIG": "sig",
        "PAYPAL-TRANSMISSION-TIME": "2026-04-02T00:03:00Z",
    }

    first = client.post("/billing/webhooks/paypal", content=payload, headers=headers)
    second = client.post("/billing/webhooks/paypal", content=payload, headers=headers)
    assert first.status_code == 200
    assert second.status_code == 200

    with runtime.session_factory() as session:
        count = session.execute(select(func.count()).select_from(PaymentEventModel)).scalar_one()
        assert count == 1
        tenant = session.execute(select(ClientModel).where(ClientModel.client_id == CLIENT_ID)).scalar_one()
        subscription = session.execute(
            select(SubscriptionModel).where(SubscriptionModel.client_id == CLIENT_ID)
        ).scalar_one()
        tenant.billing_plan_code = "growth"
        tenant.billing_status = "active"
        tenant.billing_access_state = "paid_active"
        subscription.plan_code = "growth"
        subscription.status = "active"
        subscription.cancel_at_period_end = True
        subscription.cancel_effective_at = datetime.now(tz=UTC) - timedelta(days=1)
        subscription.current_period_end = datetime.now(tz=UTC) - timedelta(days=1)
        session.commit()

    me_response = client.get("/auth/me")
    assert me_response.status_code == 200
    assert me_response.json()["billing_plan_code"] == "free"
    assert me_response.json()["billing_access_state"] == "free_active"


def test_free_plan_owner_retains_finance_access(monkeypatch, tmp_path: Path) -> None:
    runtime = _setup_runtime(tmp_path, monkeypatch)
    _mock_paypal_request(monkeypatch)
    _seed_owner(runtime, role_code="CLIENT_OWNER", email="owner@example.com")

    client = _login("owner@example.com")
    me_response = client.get("/auth/me")

    assert me_response.status_code == 200
    assert me_response.json()["billing_plan_code"] == "free"
    assert "Finance" in me_response.json()["allowed_pages"]

    finance_response = client.get("/finance/overview")
    assert finance_response.status_code == 200


def test_free_plan_client_staff_still_blocked_from_finance(monkeypatch, tmp_path: Path) -> None:
    runtime = _setup_runtime(tmp_path, monkeypatch)
    _mock_paypal_request(monkeypatch)
    _seed_owner(runtime, role_code="CLIENT_STAFF", email="staff@example.com")

    client = _login("staff@example.com")
    me_response = client.get("/auth/me")

    assert me_response.status_code == 200
    assert me_response.json()["billing_plan_code"] == "free"
    assert "Finance" not in me_response.json()["allowed_pages"]

    finance_response = client.get("/finance/overview")
    assert finance_response.status_code == 403
