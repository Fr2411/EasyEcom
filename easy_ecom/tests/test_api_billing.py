from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime, timedelta
import json
from pathlib import Path
from types import SimpleNamespace

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


class FakeStripe:
    def __init__(self) -> None:
        self.api_key = None
        self.created_customers: list[dict] = []
        self.created_checkouts: list[dict] = []
        self.created_portals: list[dict] = []
        self.Customer = SimpleNamespace(create=self.customer_create)
        self.checkout = SimpleNamespace(Session=SimpleNamespace(create=self.checkout_create))
        self.billing_portal = SimpleNamespace(Session=SimpleNamespace(create=self.portal_create))
        self.Webhook = SimpleNamespace(construct_event=self.construct_event)

    def customer_create(self, **payload):
        self.created_customers.append(payload)
        return {"id": "cus_test_123"}

    def checkout_create(self, **payload):
        self.created_checkouts.append(payload)
        return {"id": "cs_test_123", "url": "https://checkout.stripe.test/session"}

    def portal_create(self, **payload):
        self.created_portals.append(payload)
        return {"id": "bps_test_123", "url": "https://billing.stripe.test/portal"}

    def construct_event(self, raw_body, signature, secret):
        if signature != "valid-signature":
            raise ValueError("invalid signature")
        return json.loads(raw_body.decode("utf-8"))


def _setup_runtime(tmp_path: Path, monkeypatch):
    runtime = build_sqlite_runtime(tmp_path, "billing.db")
    billing_settings = replace(
        runtime.settings,
        app_base_url="https://app.easy-ecom.test",
        stripe_secret_key="sk_test_123",
        stripe_webhook_secret="whsec_test_123",
        stripe_price_growth_monthly="price_growth_monthly",
        stripe_price_scale_monthly="price_scale_monthly",
        stripe_portal_configuration_id="bpc_test_123",
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


def _event(event_id: str, event_type: str, obj: dict) -> bytes:
    return json.dumps(
        {
            "id": event_id,
            "type": event_type,
            "data": {"object": obj},
        }
    ).encode("utf-8")


def test_public_plans_backfill_existing_tenants_to_free(monkeypatch, tmp_path: Path) -> None:
    runtime = _setup_runtime(tmp_path, monkeypatch)
    _seed_owner(runtime)

    client = TestClient(create_app())
    response = client.get("/public/billing/plans")

    assert response.status_code == 200
    assert [item["plan_code"] for item in response.json()["items"]] == ["free", "growth", "scale"]

    with runtime.session_factory() as session:
        tenant = session.execute(select(ClientModel).where(ClientModel.client_id == CLIENT_ID)).scalar_one()
        subscription = session.execute(
            select(SubscriptionModel).where(SubscriptionModel.client_id == CLIENT_ID)
        ).scalar_one()
        assert tenant.billing_plan_code == "free"
        assert tenant.billing_status == "free"
        assert tenant.billing_access_state == "free_active"
        assert subscription.plan_code == "free"
        assert subscription.status == "free"


def test_owner_checkout_session_uses_stripe_but_does_not_activate_paid_access(monkeypatch, tmp_path: Path) -> None:
    runtime = _setup_runtime(tmp_path, monkeypatch)
    fake_stripe = FakeStripe()
    monkeypatch.setattr(billing_module.BillingService, "_stripe", lambda self: fake_stripe)
    _seed_owner(runtime)

    client = _login()
    checkout_response = client.post("/billing/checkout-session", json={"plan_code": "growth"})

    assert checkout_response.status_code == 200
    assert checkout_response.json() == {"checkout_url": "https://checkout.stripe.test/session"}
    assert fake_stripe.created_checkouts[0]["mode"] == "subscription"

    subscription_response = client.get("/billing/subscription")
    assert subscription_response.status_code == 200
    assert subscription_response.json()["plan_code"] == "free"
    assert subscription_response.json()["billing_access_state"] == "free_active"


def test_non_owner_cannot_manage_billing(monkeypatch, tmp_path: Path) -> None:
    runtime = _setup_runtime(tmp_path, monkeypatch)
    fake_stripe = FakeStripe()
    monkeypatch.setattr(billing_module.BillingService, "_stripe", lambda self: fake_stripe)
    _seed_owner(runtime, role_code="CLIENT_STAFF", email="staff@example.com")

    client = _login("staff@example.com")
    response = client.post("/billing/checkout-session", json={"plan_code": "growth"})

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "ACCESS_DENIED"


def test_webhook_lifecycle_activates_graces_and_downgrades_subscription(monkeypatch, tmp_path: Path) -> None:
    runtime = _setup_runtime(tmp_path, monkeypatch)
    fake_stripe = FakeStripe()
    monkeypatch.setattr(billing_module.BillingService, "_stripe", lambda self: fake_stripe)
    _seed_owner(runtime)

    client = _login()

    completed = client.post(
        "/billing/webhooks/stripe",
        content=_event(
            "evt_checkout_complete",
            "checkout.session.completed",
            {
                "id": "cs_test_123",
                "customer": "cus_test_123",
                "subscription": "sub_test_123",
                "client_reference_id": CLIENT_ID,
                "metadata": {"client_id": CLIENT_ID, "plan_code": "growth"},
                "customer_details": {"email": "owner@example.com", "name": "Owner"},
            },
        ),
        headers={"Stripe-Signature": "valid-signature"},
    )
    assert completed.status_code == 200
    assert completed.json()["status"] == "linked"

    created = client.post(
        "/billing/webhooks/stripe",
        content=_event(
            "evt_subscription_created",
            "customer.subscription.created",
            {
                "id": "sub_test_123",
                "customer": "cus_test_123",
                "cancel_at_period_end": False,
                "current_period_start": 1772323200,
                "current_period_end": 1774915200,
                "items": {"data": [{"id": "si_test_123", "price": {"id": "price_growth_monthly"}, "quantity": 1}]},
                "metadata": {"client_id": CLIENT_ID, "plan_code": "growth"},
            },
        ),
        headers={"Stripe-Signature": "valid-signature"},
    )
    assert created.status_code == 200

    paid = client.post(
        "/billing/webhooks/stripe",
        content=_event(
            "evt_invoice_paid",
            "invoice.paid",
            {
                "id": "in_test_123",
                "customer": "cus_test_123",
                "subscription": "sub_test_123",
                "period_start": 1772323200,
                "period_end": 1774915200,
                "lines": {"data": [{"price": {"id": "price_growth_monthly"}}]},
                "metadata": {"client_id": CLIENT_ID},
            },
        ),
        headers={"Stripe-Signature": "valid-signature"},
    )
    assert paid.status_code == 200
    assert paid.json()["status"] == "paid"

    active_state = client.get("/billing/subscription")
    assert active_state.status_code == 200
    assert active_state.json()["plan_code"] == "growth"
    assert active_state.json()["billing_status"] == "active"
    assert active_state.json()["billing_access_state"] == "paid_active"

    failed = client.post(
        "/billing/webhooks/stripe",
        content=_event(
            "evt_invoice_failed",
            "invoice.payment_failed",
            {
                "id": "in_test_124",
                "customer": "cus_test_123",
                "subscription": "sub_test_123",
                "metadata": {"client_id": CLIENT_ID},
            },
        ),
        headers={"Stripe-Signature": "valid-signature"},
    )
    assert failed.status_code == 200
    assert failed.json()["status"] == "past_due"

    grace_state = client.get("/billing/subscription")
    assert grace_state.status_code == 200
    assert grace_state.json()["billing_status"] == "past_due"
    assert grace_state.json()["billing_access_state"] == "read_only_grace"
    assert grace_state.json()["grace_until"] is not None

    deleted = client.post(
        "/billing/webhooks/stripe",
        content=_event(
            "evt_subscription_deleted",
            "customer.subscription.deleted",
            {
                "id": "sub_test_123",
                "customer": "cus_test_123",
                "cancel_at_period_end": False,
                "items": {"data": [{"id": "si_test_123", "price": {"id": "price_growth_monthly"}, "quantity": 1}]},
                "metadata": {"client_id": CLIENT_ID},
            },
        ),
        headers={"Stripe-Signature": "valid-signature"},
    )
    assert deleted.status_code == 200
    assert deleted.json()["status"] == "downgraded"

    downgraded_state = client.get("/billing/subscription")
    assert downgraded_state.status_code == 200
    assert downgraded_state.json()["plan_code"] == "free"
    assert downgraded_state.json()["billing_status"] == "free"
    assert downgraded_state.json()["billing_access_state"] == "free_active"


def test_webhook_signature_and_idempotency_are_enforced(monkeypatch, tmp_path: Path) -> None:
    runtime = _setup_runtime(tmp_path, monkeypatch)
    fake_stripe = FakeStripe()
    monkeypatch.setattr(billing_module.BillingService, "_stripe", lambda self: fake_stripe)
    _seed_owner(runtime)

    client = TestClient(create_app())
    invalid = client.post(
        "/billing/webhooks/stripe",
        content=_event("evt_invalid", "invoice.paid", {"id": "in_invalid", "metadata": {"client_id": CLIENT_ID}}),
        headers={"Stripe-Signature": "bad-signature"},
    )
    assert invalid.status_code == 401

    payload = _event(
        "evt_duplicate",
        "checkout.session.completed",
        {
            "id": "cs_dup",
            "customer": "cus_test_123",
            "subscription": "sub_test_123",
            "client_reference_id": CLIENT_ID,
            "metadata": {"client_id": CLIENT_ID, "plan_code": "growth"},
            "customer_details": {"email": "owner@example.com", "name": "Owner"},
        },
    )
    first = client.post("/billing/webhooks/stripe", content=payload, headers={"Stripe-Signature": "valid-signature"})
    second = client.post("/billing/webhooks/stripe", content=payload, headers={"Stripe-Signature": "valid-signature"})

    assert first.status_code == 200
    assert second.status_code == 200
    assert second.json()["status"] == "linked"

    with runtime.session_factory() as session:
        count = session.execute(select(func.count()).select_from(PaymentEventModel)).scalar_one()
        assert count == 1


def test_free_and_expired_grace_states_limit_access(monkeypatch, tmp_path: Path) -> None:
    runtime = _setup_runtime(tmp_path, monkeypatch)
    _seed_owner(runtime)

    client = _login()
    finance_response = client.get("/finance/overview")
    assert finance_response.status_code == 403

    with runtime.session_factory() as session:
        tenant = session.execute(select(ClientModel).where(ClientModel.client_id == CLIENT_ID)).scalar_one()
        subscription = session.execute(
            select(SubscriptionModel).where(SubscriptionModel.client_id == CLIENT_ID)
        ).scalar_one()
        tenant.billing_plan_code = "growth"
        tenant.billing_status = "past_due"
        tenant.billing_access_state = "read_only_grace"
        tenant.billing_grace_until = datetime.now(tz=UTC) - timedelta(days=1)
        subscription.plan_code = "growth"
        subscription.status = "past_due"
        subscription.grace_until = tenant.billing_grace_until
        session.commit()

    me_response = client.get("/auth/me")
    assert me_response.status_code == 200
    assert me_response.json()["billing_plan_code"] == "free"
    assert me_response.json()["billing_access_state"] == "free_active"
    assert "Finance" not in me_response.json()["allowed_pages"]
