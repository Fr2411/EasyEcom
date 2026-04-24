from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
import json
from typing import Any

import httpx
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.exc import IntegrityError
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from easy_ecom.core.config import settings
from easy_ecom.core.errors import ApiException
from easy_ecom.core.ids import new_uuid
from easy_ecom.core.rbac import default_page_names_for_roles
from easy_ecom.core.time_utils import now_utc
from easy_ecom.data.store.postgres_models import (
    AuditLogModel,
    BillingCustomerModel,
    BillingPlanModel,
    ClientModel,
    PaymentEventModel,
    SubscriptionModel,
)
from easy_ecom.data.store.schema import BILLING_PLANS_SEED
from easy_ecom.domain.models.auth import AuthenticatedUser

PAID_ONLY_PAGES: tuple[str, ...] = (
    "Purchases",
    "Customers",
    "Reports",
    "Automation",
)
FREE_ALLOWED_PAGES: tuple[str, ...] = (
    "Home",
    "Dashboard",
    "Catalog",
    "Inventory",
    "Sales",
    "Finance",
    "Returns",
    "Settings",
)
BILLING_SELF_SERVICE_PAGES: tuple[str, ...] = ("Billing",)
WRITE_ALLOWLIST_PREFIXES: tuple[str, ...] = (
    "/auth",
    "/session",
    "/health",
    "/billing",
    "/public/billing",
)
GRACE_PERIOD_DAYS = 7
PAYPAL_PROVIDER = "paypal"
PAYPAL_PLAN_CODES: tuple[str, ...] = ("growth", "scale")


@dataclass(frozen=True)
class BillingSnapshot:
    plan_code: str
    billing_status: str
    billing_access_state: str
    grace_until: datetime | None
    allowed_pages: list[str]


class BillingService:
    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self._session_factory = session_factory

    def _paypal_enabled(self) -> bool:
        return bool(settings.paypal_client_id and settings.paypal_client_secret)

    def _paypal_base_url(self) -> str:
        if settings.paypal_env == "live":
            return "https://api-m.paypal.com"
        return "https://api-m.sandbox.paypal.com"

    def _paypal_access_token(self) -> str:
        if not self._paypal_enabled():
            raise ApiException(status_code=500, code="PAYPAL_NOT_CONFIGURED", message="PayPal credentials are not configured")
        response = httpx.post(
            f"{self._paypal_base_url()}/v1/oauth2/token",
            auth=(settings.paypal_client_id, settings.paypal_client_secret),
            data={"grant_type": "client_credentials"},
            headers={"Accept": "application/json", "Accept-Language": "en_US"},
            timeout=20.0,
        )
        response.raise_for_status()
        payload = response.json()
        token = str(payload.get("access_token") or "").strip()
        if not token:
            raise ApiException(status_code=502, code="PAYPAL_TOKEN_MISSING", message="PayPal did not return an access token")
        return token

    def _paypal_request(
        self,
        method: str,
        path: str,
        *,
        json_body: dict[str, Any] | None = None,
        form_body: dict[str, Any] | None = None,
        expected_statuses: tuple[int, ...] = (200, 201, 204),
    ) -> dict[str, Any]:
        token = self._paypal_access_token()
        headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/json",
            "Prefer": "return=representation",
        }
        response = httpx.request(
            method=method.upper(),
            url=f"{self._paypal_base_url()}{path}",
            headers=headers,
            json=json_body,
            data=form_body,
            timeout=30.0,
        )
        if response.status_code not in expected_statuses:
            detail = response.text[:500]
            raise ApiException(status_code=502, code="PAYPAL_REQUEST_FAILED", message=f"PayPal request failed: {detail}")
        if response.status_code == 204 or not response.content:
            return {}
        return response.json()

    def _verify_paypal_webhook(self, *, event: dict[str, Any], headers: dict[str, str | None]) -> None:
        if not settings.paypal_webhook_id:
            raise ApiException(status_code=500, code="PAYPAL_WEBHOOK_NOT_CONFIGURED", message="PayPal webhook ID is not configured")
        payload = {
            "transmission_id": headers.get("paypal-transmission-id"),
            "transmission_time": headers.get("paypal-transmission-time"),
            "cert_url": headers.get("paypal-cert-url"),
            "auth_algo": headers.get("paypal-auth-algo"),
            "transmission_sig": headers.get("paypal-transmission-sig"),
            "webhook_id": settings.paypal_webhook_id,
            "webhook_event": event,
        }
        result = self._paypal_request(
            "POST",
            "/v1/notifications/verify-webhook-signature",
            json_body=payload,
            expected_statuses=(200,),
        )
        if str(result.get("verification_status") or "").upper() != "SUCCESS":
            raise ApiException(status_code=401, code="INVALID_PAYPAL_SIGNATURE", message="Invalid PayPal webhook signature")

    def _log_audit(
        self,
        session: Session,
        *,
        client_id: str | None,
        actor_user_id: str | None,
        entity_type: str,
        entity_id: str,
        action: str,
        metadata_json: dict[str, Any] | None,
    ) -> None:
        session.add(
            AuditLogModel(
                audit_log_id=new_uuid(),
                client_id=client_id,
                actor_user_id=actor_user_id,
                entity_type=entity_type,
                entity_id=entity_id,
                action=action,
                request_id=None,
                metadata_json=metadata_json,
                created_at=now_utc(),
            )
        )

    def _plan_override_ids(self, plan_code: str) -> tuple[str | None, str | None]:
        if plan_code == "growth":
            return settings.paypal_product_growth_id or None, settings.paypal_plan_growth_monthly or None
        if plan_code == "scale":
            return settings.paypal_product_scale_id or None, settings.paypal_plan_scale_monthly or None
        return None, None

    def _plan_amount(self, plan_code: str) -> str | None:
        if plan_code == "growth":
            return settings.paypal_price_growth_monthly_amount or None
        if plan_code == "scale":
            return settings.paypal_price_scale_monthly_amount or None
        return None

    def _plan_payload(self, plan: BillingPlanModel) -> dict[str, Any]:
        return {
            "plan_code": plan.plan_code,
            "display_name": plan.display_name,
            "is_paid": plan.is_paid,
            "billing_provider": plan.billing_provider,
            "provider_plan_id": plan.provider_plan_id,
            "currency_code": plan.currency_code,
            "interval": plan.interval,
            "sort_order": plan.sort_order,
            "public_description": plan.public_description,
            "feature_flags_json": plan.feature_flags_json,
        }

    def _create_paypal_product(self, *, plan: BillingPlanModel) -> str:
        payload = {
            "name": f"EasyEcom {plan.display_name}",
            "description": plan.public_description,
            "type": "SERVICE",
            "category": "SOFTWARE",
        }
        created = self._paypal_request("POST", "/v1/catalogs/products", json_body=payload)
        product_id = str(created.get("id") or "").strip()
        if not product_id:
            raise ApiException(status_code=502, code="PAYPAL_PRODUCT_CREATE_FAILED", message=f"Unable to create PayPal product for {plan.plan_code}")
        return product_id

    def _create_paypal_plan(self, *, plan: BillingPlanModel, product_id: str) -> str:
        amount = self._plan_amount(plan.plan_code)
        if not amount:
            raise ApiException(
                status_code=500,
                code="PAYPAL_PLAN_PRICE_MISSING",
                message=f"Missing PayPal monthly amount for {plan.plan_code}. Configure PAYPAL_PRICE_{plan.plan_code.upper()}_MONTHLY_AMOUNT.",
            )
        payload = {
            "product_id": product_id,
            "name": f"EasyEcom {plan.display_name} Monthly",
            "description": plan.public_description,
            "status": "ACTIVE",
            "billing_cycles": [
                {
                    "frequency": {"interval_unit": "MONTH", "interval_count": 1},
                    "tenure_type": "REGULAR",
                    "sequence": 1,
                    "total_cycles": 0,
                    "pricing_scheme": {
                        "fixed_price": {
                            "value": amount,
                            "currency_code": plan.currency_code,
                        }
                    },
                }
            ],
            "payment_preferences": {
                "auto_bill_outstanding": True,
                "setup_fee_failure_action": "CONTINUE",
                "payment_failure_threshold": 1,
            },
        }
        created = self._paypal_request("POST", "/v1/billing/plans", json_body=payload)
        provider_plan_id = str(created.get("id") or "").strip()
        if not provider_plan_id:
            raise ApiException(status_code=502, code="PAYPAL_PLAN_CREATE_FAILED", message=f"Unable to create PayPal plan for {plan.plan_code}")
        return provider_plan_id

    def ensure_plan_catalog(self, session: Session) -> None:
        for seed in BILLING_PLANS_SEED:
            record = session.execute(
                select(BillingPlanModel).where(BillingPlanModel.plan_code == seed["plan_code"])
            ).scalar_one_or_none()
            override_product_id, override_plan_id = self._plan_override_ids(seed["plan_code"])
            if record is None:
                record = BillingPlanModel(
                    plan_code=seed["plan_code"],
                    display_name=seed["display_name"],
                    is_paid=seed["is_paid"],
                    billing_provider=seed["billing_provider"],
                    provider_product_id=override_product_id or seed.get("provider_product_id"),
                    provider_plan_id=override_plan_id or seed.get("provider_plan_id"),
                    currency_code=seed["currency_code"],
                    interval=seed["interval"],
                    sort_order=seed["sort_order"],
                    public_description=seed["public_description"],
                    feature_flags_json=dict(seed["feature_flags_json"] or {}),
                )
                session.add(record)
            else:
                record.display_name = seed["display_name"]
                record.is_paid = seed["is_paid"]
                record.billing_provider = seed["billing_provider"]
                record.provider_product_id = override_product_id or record.provider_product_id or seed.get("provider_product_id")
                record.provider_plan_id = override_plan_id or record.provider_plan_id or seed.get("provider_plan_id")
                record.currency_code = seed["currency_code"]
                record.interval = seed["interval"]
                record.sort_order = seed["sort_order"]
                record.public_description = seed["public_description"]
                record.feature_flags_json = dict(seed["feature_flags_json"] or {})

            if record.is_paid and self._paypal_enabled():
                if not record.provider_product_id:
                    record.provider_product_id = self._create_paypal_product(plan=record)
                if not record.provider_plan_id and self._plan_amount(record.plan_code):
                    record.provider_plan_id = self._create_paypal_plan(plan=record, product_id=record.provider_product_id)

    def _pending_subscription_row(self, session: Session, client_id: str) -> SubscriptionModel | None:
        for pending in session.new:
            if isinstance(pending, SubscriptionModel) and str(pending.client_id) == str(client_id):
                return pending
        return None

    def _ensure_free_subscription_exists(self, session: Session, client_id: str) -> None:
        values = {
            "subscription_id": new_uuid(),
            "client_id": client_id,
            "plan_code": "free",
            "billing_provider": PAYPAL_PROVIDER,
            "status": "free",
            "cancel_at_period_end": False,
        }
        bind = session.get_bind()
        if bind is not None and bind.dialect.name == "postgresql":
            session.execute(
                pg_insert(SubscriptionModel.__table__)
                .values(**values)
                .on_conflict_do_nothing(index_elements=["client_id"])
            )
            return
        try:
            with session.begin_nested():
                session.add(SubscriptionModel(**values))
                session.flush()
        except IntegrityError:
            pass

    def seed_existing_clients_to_free(self, session: Session) -> None:
        self.ensure_plan_catalog(session)
        clients = session.execute(select(ClientModel)).scalars().all()
        existing_subscription_client_ids = {
            str(client_id)
            for client_id in session.execute(select(SubscriptionModel.client_id)).scalars().all()
            if client_id is not None
        }
        for client in clients:
            changed = False
            if not client.billing_plan_code:
                client.billing_plan_code = "free"
                changed = True
            if not client.billing_status:
                client.billing_status = "free"
                changed = True
            if not client.billing_access_state:
                client.billing_access_state = "free_active"
                changed = True
            if changed:
                client.billing_updated_at = now_utc()
            if str(client.client_id) not in existing_subscription_client_ids and self._pending_subscription_row(session, str(client.client_id)) is None:
                self._ensure_free_subscription_exists(session, str(client.client_id))
                existing_subscription_client_ids.add(str(client.client_id))
        session.flush()

    def public_plans(self) -> list[dict[str, Any]]:
        with self._session_factory() as session:
            self.seed_existing_clients_to_free(session)
            session.commit()
            plans = session.execute(
                select(BillingPlanModel).order_by(BillingPlanModel.sort_order.asc(), BillingPlanModel.plan_code.asc())
            ).scalars().all()
            return [self._plan_payload(plan) for plan in plans]

    def public_config(self) -> dict[str, Any]:
        return {
            "billing_provider": PAYPAL_PROVIDER,
            "paypal_client_id": settings.paypal_client_id or None,
            "paypal_enabled": self._paypal_enabled(),
        }

    def _require_owner_or_admin(self, user: AuthenticatedUser) -> None:
        if "SUPER_ADMIN" in user.roles or "CLIENT_OWNER" in user.roles:
            return
        raise ApiException(status_code=403, code="BILLING_ACCESS_DENIED", message="Only tenant owners can manage billing")

    def _plan_pages(self, plan_code: str) -> set[str]:
        if plan_code == "free":
            return set(FREE_ALLOWED_PAGES)
        return set(default_page_names_for_roles(["CLIENT_OWNER", "CLIENT_STAFF", "FINANCE_STAFF", "SUPER_ADMIN"]))

    def _entitled_pages(self, roles: list[str], role_allowed_pages: list[str], plan_code: str) -> list[str]:
        if "SUPER_ADMIN" in roles:
            return role_allowed_pages
        entitled = self._plan_pages(plan_code)
        allowed = {page for page in role_allowed_pages if page in entitled}
        if "CLIENT_OWNER" in roles:
            allowed.update(BILLING_SELF_SERVICE_PAGES)
        return [page for page in role_allowed_pages if page in allowed]

    def _to_dt(self, value: Any) -> datetime | None:
        if value in (None, "", 0):
            return None
        if isinstance(value, datetime):
            return value if value.tzinfo else value.replace(tzinfo=UTC)
        if isinstance(value, (int, float)):
            return datetime.fromtimestamp(value, tz=UTC)
        text = str(value).strip()
        if not text:
            return None
        if text.endswith("Z"):
            text = text[:-1] + "+00:00"
        parsed = datetime.fromisoformat(text)
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)

    def _lookup_plan_by_provider_plan_id(self, session: Session, provider_plan_id: str | None) -> BillingPlanModel | None:
        if not provider_plan_id:
            return None
        return session.execute(
            select(BillingPlanModel).where(BillingPlanModel.provider_plan_id == provider_plan_id)
        ).scalar_one_or_none()

    def _subscription_row(self, session: Session, client_id: str) -> SubscriptionModel:
        pending = self._pending_subscription_row(session, client_id)
        if pending is not None:
            return pending
        row = session.execute(
            select(SubscriptionModel).where(SubscriptionModel.client_id == client_id)
        ).scalar_one_or_none()
        if row is None:
            self._ensure_free_subscription_exists(session, client_id)
            pending = self._pending_subscription_row(session, client_id)
            if pending is not None:
                return pending
            row = session.execute(
                select(SubscriptionModel).where(SubscriptionModel.client_id == client_id)
            ).scalar_one_or_none()
            if row is None:
                raise ApiException(status_code=500, code="SUBSCRIPTION_BOOTSTRAP_FAILED", message="Unable to initialize subscription state")
        return row

    def _sync_client_snapshot(
        self,
        session: Session,
        *,
        client: ClientModel,
        subscription: SubscriptionModel,
        plan_code: str,
        billing_status: str,
        access_state: str,
        grace_until: datetime | None,
    ) -> None:
        client.billing_plan_code = plan_code
        client.billing_status = billing_status
        client.billing_access_state = access_state
        client.billing_grace_until = grace_until
        client.billing_updated_at = now_utc()
        subscription.plan_code = plan_code
        subscription.status = billing_status
        subscription.grace_until = grace_until

    def _degrade_to_free_if_grace_expired(self, session: Session, client: ClientModel, subscription: SubscriptionModel) -> None:
        if client.billing_access_state != "read_only_grace":
            return
        if client.billing_grace_until is None or client.billing_grace_until > now_utc():
            return
        self._downgrade_to_free(session, client_id=str(client.client_id), subscription=subscription, event_id="grace_expired")

    def _finalize_period_end_cancellation_if_due(self, session: Session, client: ClientModel, subscription: SubscriptionModel) -> None:
        if not subscription.cancel_at_period_end:
            return
        effective_at = subscription.cancel_effective_at or subscription.current_period_end
        if effective_at is None or effective_at > now_utc():
            return
        self._downgrade_to_free(session, client_id=str(client.client_id), subscription=subscription, event_id="cancel_period_end")

    def snapshot_for_request(self, session: Session, *, client_id: str, roles: list[str]) -> BillingSnapshot:
        self.seed_existing_clients_to_free(session)
        client = session.execute(select(ClientModel).where(ClientModel.client_id == client_id)).scalar_one()
        subscription = self._subscription_row(session, client_id)
        self._degrade_to_free_if_grace_expired(session, client, subscription)
        self._finalize_period_end_cancellation_if_due(session, client, subscription)
        role_pages = list(default_page_names_for_roles(roles))
        entitled = self._entitled_pages(roles, role_pages, client.billing_plan_code or "free")
        return BillingSnapshot(
            plan_code=client.billing_plan_code or "free",
            billing_status=client.billing_status or "free",
            billing_access_state=client.billing_access_state or "free_active",
            grace_until=client.billing_grace_until,
            allowed_pages=entitled,
        )

    def enforce_request_access(self, *, user: AuthenticatedUser, request_method: str, request_path: str) -> None:
        if "SUPER_ADMIN" in user.roles:
            return
        if user.billing_access_state == "read_only_grace" and request_method.upper() not in {"GET", "HEAD", "OPTIONS"}:
            if not request_path.startswith(WRITE_ALLOWLIST_PREFIXES):
                raise ApiException(
                    status_code=403,
                    code="BILLING_READ_ONLY",
                    message="Subscription payment is overdue. Writes are blocked until payment is recovered.",
                )

    def subscription_state(self, user: AuthenticatedUser) -> dict[str, Any]:
        with self._session_factory() as session:
            self.seed_existing_clients_to_free(session)
            client = session.execute(select(ClientModel).where(ClientModel.client_id == user.client_id)).scalar_one()
            subscription = self._subscription_row(session, user.client_id)
            self._degrade_to_free_if_grace_expired(session, client, subscription)
            self._finalize_period_end_cancellation_if_due(session, client, subscription)
            plan = session.execute(
                select(BillingPlanModel).where(BillingPlanModel.plan_code == (client.billing_plan_code or "free"))
            ).scalar_one()
            session.commit()
            return {
                "plan_code": plan.plan_code,
                "plan_name": plan.display_name,
                "billing_status": client.billing_status or "free",
                "billing_access_state": client.billing_access_state or "free_active",
                "cancel_at_period_end": subscription.cancel_at_period_end,
                "current_period_start": subscription.current_period_start.isoformat() if subscription.current_period_start else None,
                "current_period_end": subscription.current_period_end.isoformat() if subscription.current_period_end else None,
                "grace_until": client.billing_grace_until.isoformat() if client.billing_grace_until else None,
                "billing_provider": PAYPAL_PROVIDER,
                "provider_customer_id": subscription.provider_customer_id,
                "provider_subscription_id": subscription.provider_subscription_id,
                "cancel_effective_at": subscription.cancel_effective_at.isoformat() if subscription.cancel_effective_at else None,
                "pending_plan_code": subscription.pending_plan_code,
                "can_upgrade": plan.plan_code == "free",
                "can_manage_subscription": plan.is_paid and bool(subscription.provider_subscription_id),
                "paid_modules_locked": list(PAID_ONLY_PAGES) if plan.plan_code == "free" or client.billing_access_state == "read_only_grace" else [],
            }

    def _provider_subscription_id_from_resource(self, resource: dict[str, Any]) -> str | None:
        for key in ("billing_agreement_id", "subscription_id", "id"):
            value = str(resource.get(key) or "").strip()
            if value and value.startswith("I-"):
                return value
        return None

    def _provider_customer_id_from_resource(self, resource: dict[str, Any]) -> str | None:
        subscriber = resource.get("subscriber") or {}
        payer = subscriber.get("payer_id") or (subscriber.get("payer") or {}).get("payer_id")
        value = str(payer or "").strip()
        return value or None

    def _fetch_subscription_details(self, provider_subscription_id: str) -> dict[str, Any]:
        return self._paypal_request("GET", f"/v1/billing/subscriptions/{provider_subscription_id}", expected_statuses=(200,))

    def _event_row(self, session: Session, *, provider_event_id: str) -> PaymentEventModel | None:
        return session.execute(
            select(PaymentEventModel).where(PaymentEventModel.provider_event_id == provider_event_id)
        ).scalar_one_or_none()

    def _upsert_billing_customer(
        self,
        session: Session,
        *,
        client_id: str,
        provider_customer_id: str | None,
        email: str = "",
        name: str = "",
    ) -> BillingCustomerModel:
        row = session.execute(
            select(BillingCustomerModel).where(BillingCustomerModel.client_id == client_id)
        ).scalar_one_or_none()
        if row is None:
            row = BillingCustomerModel(
                billing_customer_id=new_uuid(),
                client_id=client_id,
                billing_provider=PAYPAL_PROVIDER,
                provider_customer_id=provider_customer_id,
                stripe_customer_id=None,
                email=email,
                name=name,
            )
            session.add(row)
            session.flush()
            return row
        row.billing_provider = PAYPAL_PROVIDER
        if provider_customer_id:
            row.provider_customer_id = provider_customer_id
        if email:
            row.email = email
        if name:
            row.name = name
        return row

    def _mark_event(self, event: PaymentEventModel, *, status: str, error_message: str = "") -> None:
        event.status = status
        event.error_message = error_message
        event.processed_at = now_utc()

    def _sync_subscription_from_paypal_details(
        self,
        session: Session,
        *,
        client_id: str,
        details: dict[str, Any],
        event_id: str,
    ) -> SubscriptionModel:
        subscription = self._subscription_row(session, client_id)
        provider_plan_id = str(details.get("plan_id") or "").strip() or subscription.provider_plan_id
        plan = self._lookup_plan_by_provider_plan_id(session, provider_plan_id)
        subscriber = details.get("subscriber") or {}
        payer_id = str(subscriber.get("payer_id") or "").strip() or subscription.provider_customer_id
        next_billing_time = self._to_dt((details.get("billing_info") or {}).get("next_billing_time"))
        start_time = self._to_dt(details.get("start_time")) or subscription.current_period_start
        subscription.billing_provider = PAYPAL_PROVIDER
        subscription.provider_subscription_id = str(details.get("id") or subscription.provider_subscription_id or "")
        subscription.provider_customer_id = payer_id or subscription.provider_customer_id
        subscription.provider_plan_id = provider_plan_id
        subscription.current_period_start = start_time
        subscription.current_period_end = next_billing_time or subscription.current_period_end
        subscription.updated_from_event_id = event_id
        if plan is not None:
            subscription.plan_code = plan.plan_code
            if subscription.pending_plan_code == plan.plan_code:
                subscription.pending_plan_code = None
        if subscription.cancel_at_period_end and subscription.current_period_end:
            subscription.cancel_effective_at = subscription.current_period_end
        email = str(subscriber.get("email_address") or "").strip()
        name_parts = [
            str(((subscriber.get("name") or {}).get("given_name")) or "").strip(),
            str(((subscriber.get("name") or {}).get("surname")) or "").strip(),
        ]
        name = " ".join([part for part in name_parts if part]).strip()
        self._upsert_billing_customer(
            session,
            client_id=client_id,
            provider_customer_id=payer_id,
            email=email,
            name=name,
        )
        return subscription

    def _event_client_id(self, session: Session, *, resource: dict[str, Any]) -> str | None:
        custom_id = str(resource.get("custom_id") or "").strip()
        if custom_id:
            return custom_id
        provider_subscription_id = self._provider_subscription_id_from_resource(resource)
        if provider_subscription_id:
            subscription = session.execute(
                select(SubscriptionModel).where(SubscriptionModel.provider_subscription_id == provider_subscription_id)
            ).scalar_one_or_none()
            if subscription is not None:
                return str(subscription.client_id)
        provider_customer_id = self._provider_customer_id_from_resource(resource)
        if provider_customer_id:
            customer = session.execute(
                select(BillingCustomerModel).where(BillingCustomerModel.provider_customer_id == provider_customer_id)
            ).scalar_one_or_none()
            if customer is not None:
                return str(customer.client_id)
        return None

    def _set_paid_active(
        self,
        session: Session,
        *,
        client_id: str,
        subscription: SubscriptionModel,
        plan_code: str,
        event_id: str,
    ) -> None:
        client = session.execute(select(ClientModel).where(ClientModel.client_id == client_id)).scalar_one()
        subscription.plan_code = plan_code
        subscription.status = "active"
        subscription.grace_until = None
        subscription.updated_from_event_id = event_id
        self._sync_client_snapshot(
            session,
            client=client,
            subscription=subscription,
            plan_code=plan_code,
            billing_status="active",
            access_state="paid_active",
            grace_until=None,
        )

    def _set_read_only_grace(self, session: Session, *, client_id: str, subscription: SubscriptionModel, event_id: str) -> None:
        client = session.execute(select(ClientModel).where(ClientModel.client_id == client_id)).scalar_one()
        grace_until = now_utc() + timedelta(days=GRACE_PERIOD_DAYS)
        subscription.updated_from_event_id = event_id
        self._sync_client_snapshot(
            session,
            client=client,
            subscription=subscription,
            plan_code=client.billing_plan_code or subscription.plan_code or "free",
            billing_status="past_due",
            access_state="read_only_grace",
            grace_until=grace_until,
        )

    def _downgrade_to_free(self, session: Session, *, client_id: str, subscription: SubscriptionModel, event_id: str) -> None:
        client = session.execute(select(ClientModel).where(ClientModel.client_id == client_id)).scalar_one()
        subscription.updated_from_event_id = event_id
        subscription.cancel_at_period_end = False
        subscription.cancel_effective_at = None
        subscription.pending_plan_code = None
        self._sync_client_snapshot(
            session,
            client=client,
            subscription=subscription,
            plan_code="free",
            billing_status="free",
            access_state="free_active",
            grace_until=None,
        )

    def change_plan(self, user: AuthenticatedUser, *, target_plan_code: str) -> dict[str, Any]:
        self._require_owner_or_admin(user)
        with self._session_factory() as session:
            self.seed_existing_clients_to_free(session)
            client = session.execute(select(ClientModel).where(ClientModel.client_id == user.client_id)).scalar_one()
            current_subscription = self._subscription_row(session, user.client_id)
            target_plan = session.execute(
                select(BillingPlanModel).where(BillingPlanModel.plan_code == target_plan_code)
            ).scalar_one_or_none()
            if target_plan is None or not target_plan.is_paid:
                raise ApiException(status_code=400, code="INVALID_BILLING_PLAN", message="Plan change target must be a paid plan")
            if client.billing_plan_code == "free":
                raise ApiException(status_code=400, code="PAYPAL_BUTTON_REQUIRED", message="Start a new paid plan from the PayPal checkout button.")
            if not current_subscription.provider_subscription_id:
                raise ApiException(status_code=400, code="SUBSCRIPTION_NOT_FOUND", message="No paid subscription is available to change")
            if not target_plan.provider_plan_id:
                raise ApiException(status_code=500, code="PAYPAL_PLAN_NOT_READY", message=f"PayPal plan is not configured for {target_plan_code}")
            response = self._paypal_request(
                "POST",
                f"/v1/billing/subscriptions/{current_subscription.provider_subscription_id}/revise",
                json_body={
                    "plan_id": target_plan.provider_plan_id,
                    "application_context": {
                        "brand_name": "EasyEcom",
                        "return_url": f"{settings.app_base_url}/billing/success",
                        "cancel_url": f"{settings.app_base_url}/billing/cancel",
                    },
                },
                expected_statuses=(200, 201),
            )
            current_subscription.pending_plan_code = target_plan_code
            current_subscription.updated_from_event_id = f"manual_change_{now_utc().isoformat()}"
            self._log_audit(
                session,
                client_id=str(client.client_id),
                actor_user_id=user.user_id,
                entity_type="subscription",
                entity_id=current_subscription.subscription_id,
                action="subscription_plan_change_requested",
                metadata_json={"target_plan_code": target_plan_code},
            )
            session.commit()
            action_url = None
            for link in response.get("links") or []:
                if str(link.get("rel") or "").lower() in {"approve", "payer-action"}:
                    action_url = str(link.get("href") or "").strip() or None
                    break
            return {"status": "plan_change_requested", "action_url": action_url}

    def cancel_subscription(self, user: AuthenticatedUser) -> dict[str, Any]:
        self._require_owner_or_admin(user)
        with self._session_factory() as session:
            client = session.execute(select(ClientModel).where(ClientModel.client_id == user.client_id)).scalar_one()
            subscription = self._subscription_row(session, user.client_id)
            if not subscription.provider_subscription_id:
                raise ApiException(status_code=400, code="SUBSCRIPTION_NOT_FOUND", message="No paid subscription is available to cancel")
            self._paypal_request(
                "POST",
                f"/v1/billing/subscriptions/{subscription.provider_subscription_id}/cancel",
                json_body={"reason": "Canceled from EasyEcom billing workspace"},
                expected_statuses=(204,),
            )
            subscription.cancel_at_period_end = True
            subscription.cancel_effective_at = subscription.current_period_end
            subscription.updated_from_event_id = f"manual_cancel_{now_utc().isoformat()}"
            self._log_audit(
                session,
                client_id=str(client.client_id),
                actor_user_id=user.user_id,
                entity_type="subscription",
                entity_id=subscription.subscription_id,
                action="subscription_cancellation_scheduled",
                metadata_json={"cancel_effective_at": subscription.cancel_effective_at.isoformat() if subscription.cancel_effective_at else None},
            )
            session.commit()
            return {"status": "cancellation_scheduled", "action_url": None}

    def handle_paypal_webhook(self, *, raw_body: bytes, headers: dict[str, str | None]) -> dict[str, Any]:
        if not self._paypal_enabled():
            raise ApiException(status_code=500, code="PAYPAL_NOT_CONFIGURED", message="PayPal credentials are not configured")
        event = json.loads(raw_body.decode("utf-8"))
        self._verify_paypal_webhook(event=event, headers=headers)

        event_id = str(event.get("id") or "").strip()
        event_type = str(event.get("event_type") or "").strip()
        resource = dict(event.get("resource") or {})
        provider_object_id = self._provider_subscription_id_from_resource(resource) or str(resource.get("id") or "").strip()

        with self._session_factory() as session:
            self.seed_existing_clients_to_free(session)
            existing = self._event_row(session, provider_event_id=event_id)
            if existing is not None:
                session.commit()
                return {"accepted": True, "status": existing.status, "event_id": event_id, "provider": PAYPAL_PROVIDER}

            client_id = self._event_client_id(session, resource=resource)
            payment_event = PaymentEventModel(
                payment_event_id=new_uuid(),
                client_id=client_id,
                billing_provider=PAYPAL_PROVIDER,
                provider_event_id=event_id,
                stripe_event_id=None,
                event_type=event_type,
                provider_object_id=provider_object_id or "",
                stripe_object_id=None,
                status="received",
                payload_json=event,
            )
            session.add(payment_event)

            try:
                provider_subscription_id = self._provider_subscription_id_from_resource(resource)
                details = None
                if provider_subscription_id:
                    details = self._fetch_subscription_details(provider_subscription_id)
                    client_id = client_id or str(details.get("custom_id") or "").strip() or client_id

                if event_type in {"BILLING.SUBSCRIPTION.ACTIVATED", "BILLING.SUBSCRIPTION.UPDATED"}:
                    if client_id and details:
                        subscription = self._sync_subscription_from_paypal_details(session, client_id=client_id, details=details, event_id=event_id)
                        client = session.execute(select(ClientModel).where(ClientModel.client_id == client_id)).scalar_one()
                        if client.billing_status == "active":
                            self._sync_client_snapshot(
                                session,
                                client=client,
                                subscription=subscription,
                                plan_code=subscription.plan_code or client.billing_plan_code or "free",
                                billing_status=client.billing_status,
                                access_state=client.billing_access_state or "paid_active",
                                grace_until=client.billing_grace_until,
                            )
                    self._mark_event(payment_event, status="synced")
                elif event_type == "PAYMENT.SALE.COMPLETED":
                    if client_id and details:
                        subscription = self._sync_subscription_from_paypal_details(session, client_id=client_id, details=details, event_id=event_id)
                        plan = self._lookup_plan_by_provider_plan_id(session, subscription.provider_plan_id) or session.execute(
                            select(BillingPlanModel).where(BillingPlanModel.plan_code == (subscription.pending_plan_code or subscription.plan_code or "growth"))
                        ).scalar_one()
                        self._set_paid_active(
                            session,
                            client_id=client_id,
                            subscription=subscription,
                            plan_code=plan.plan_code,
                            event_id=event_id,
                        )
                    self._mark_event(payment_event, status="paid")
                elif event_type == "BILLING.SUBSCRIPTION.PAYMENT.FAILED":
                    if client_id:
                        subscription = self._subscription_row(session, client_id)
                        if details:
                            subscription = self._sync_subscription_from_paypal_details(session, client_id=client_id, details=details, event_id=event_id)
                        self._set_read_only_grace(session, client_id=client_id, subscription=subscription, event_id=event_id)
                    self._mark_event(payment_event, status="past_due")
                elif event_type in {"BILLING.SUBSCRIPTION.CANCELLED", "BILLING.SUBSCRIPTION.SUSPENDED", "BILLING.SUBSCRIPTION.EXPIRED"}:
                    if client_id:
                        subscription = self._subscription_row(session, client_id)
                        if details:
                            subscription = self._sync_subscription_from_paypal_details(session, client_id=client_id, details=details, event_id=event_id)
                        effective_at = subscription.cancel_effective_at or subscription.current_period_end
                        if subscription.cancel_at_period_end and effective_at and effective_at > now_utc():
                            subscription.status = "active"
                        else:
                            self._downgrade_to_free(session, client_id=client_id, subscription=subscription, event_id=event_id)
                    self._mark_event(payment_event, status="downgraded")
                else:
                    self._mark_event(payment_event, status="ignored")

                session.commit()
                return {"accepted": True, "status": payment_event.status, "event_id": event_id, "provider": PAYPAL_PROVIDER}
            except Exception as exc:
                self._mark_event(payment_event, status="failed", error_message=str(exc))
                session.commit()
                raise
