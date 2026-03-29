from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from importlib import import_module
import json
from typing import Any

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
    "Finance",
    "Reports",
    "Integrations",
    "Sales Agent",
    "AI Review",
    "Automation",
)
FREE_ALLOWED_PAGES: tuple[str, ...] = (
    "Home",
    "Dashboard",
    "Catalog",
    "Inventory",
    "Sales",
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

    def _stripe(self):
        if not settings.stripe_secret_key:
            raise ApiException(status_code=500, code="STRIPE_NOT_CONFIGURED", message="Stripe secret key is not configured")
        stripe = import_module("stripe")
        stripe.api_key = settings.stripe_secret_key
        return stripe

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

    def ensure_plan_catalog(self, session: Session) -> None:
        overrides = {
            "growth": settings.stripe_price_growth_monthly or None,
            "scale": settings.stripe_price_scale_monthly or None,
        }
        for seed in BILLING_PLANS_SEED:
            record = session.execute(
                select(BillingPlanModel).where(BillingPlanModel.plan_code == seed["plan_code"])
            ).scalar_one_or_none()
            stripe_price_id = overrides.get(seed["plan_code"], seed["stripe_price_id"])
            feature_flags = dict(seed["feature_flags_json"] or {})
            if record is None:
                session.add(
                    BillingPlanModel(
                        plan_code=seed["plan_code"],
                        display_name=seed["display_name"],
                        is_paid=seed["is_paid"],
                        stripe_price_id=stripe_price_id,
                        currency_code=seed["currency_code"],
                        interval=seed["interval"],
                        sort_order=seed["sort_order"],
                        public_description=seed["public_description"],
                        feature_flags_json=feature_flags,
                    )
                )
                continue
            record.display_name = seed["display_name"]
            record.is_paid = seed["is_paid"]
            record.stripe_price_id = stripe_price_id
            record.currency_code = seed["currency_code"]
            record.interval = seed["interval"]
            record.sort_order = seed["sort_order"]
            record.public_description = seed["public_description"]
            record.feature_flags_json = feature_flags

    def seed_existing_clients_to_free(self, session: Session) -> None:
        self.ensure_plan_catalog(session)
        clients = session.execute(select(ClientModel)).scalars().all()
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
            subscription = session.execute(
                select(SubscriptionModel).where(SubscriptionModel.client_id == client.client_id)
            ).scalar_one_or_none()
            if subscription is None:
                session.add(
                    SubscriptionModel(
                        subscription_id=new_uuid(),
                        client_id=client.client_id,
                        plan_code="free",
                        status="free",
                        cancel_at_period_end=False,
                    )
                )

    def public_plans(self) -> list[dict[str, Any]]:
        with self._session_factory() as session:
            self.seed_existing_clients_to_free(session)
            session.commit()
            plans = session.execute(
                select(BillingPlanModel).order_by(BillingPlanModel.sort_order.asc(), BillingPlanModel.plan_code.asc())
            ).scalars().all()
            return [self._plan_payload(plan) for plan in plans]

    def _plan_payload(self, plan: BillingPlanModel) -> dict[str, Any]:
        return {
            "plan_code": plan.plan_code,
            "display_name": plan.display_name,
            "is_paid": plan.is_paid,
            "currency_code": plan.currency_code,
            "interval": plan.interval,
            "sort_order": plan.sort_order,
            "public_description": plan.public_description,
            "feature_flags_json": plan.feature_flags_json,
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

    def _lookup_plan_by_price_id(self, session: Session, price_id: str | None) -> BillingPlanModel | None:
        if not price_id:
            return None
        self.ensure_plan_catalog(session)
        return session.execute(
            select(BillingPlanModel).where(BillingPlanModel.stripe_price_id == price_id)
        ).scalar_one_or_none()

    def _get_or_create_billing_customer(
        self,
        session: Session,
        *,
        client: ClientModel,
        actor: AuthenticatedUser | None,
    ) -> BillingCustomerModel:
        record = session.execute(
            select(BillingCustomerModel).where(BillingCustomerModel.client_id == client.client_id)
        ).scalar_one_or_none()
        if record is not None:
            return record
        stripe = self._stripe()
        customer = stripe.Customer.create(
            email=client.email,
            name=client.business_name,
            metadata={"client_id": str(client.client_id), "client_slug": client.slug},
        )
        record = BillingCustomerModel(
            billing_customer_id=new_uuid(),
            client_id=client.client_id,
            stripe_customer_id=customer["id"],
            email=client.email,
            name=client.business_name,
        )
        session.add(record)
        self._log_audit(
            session,
            client_id=str(client.client_id),
            actor_user_id=actor.user_id if actor else None,
            entity_type="billing_customer",
            entity_id=record.billing_customer_id,
            action="billing_customer_created",
            metadata_json={"stripe_customer_id": record.stripe_customer_id},
        )
        return record

    def _subscription_row(self, session: Session, client_id: str) -> SubscriptionModel:
        row = session.execute(
            select(SubscriptionModel).where(SubscriptionModel.client_id == client_id)
        ).scalar_one_or_none()
        if row is None:
            row = SubscriptionModel(
                subscription_id=new_uuid(),
                client_id=client_id,
                plan_code="free",
                status="free",
            )
            session.add(row)
            session.flush()
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
        if client.billing_grace_until is None:
            return
        if client.billing_grace_until > now_utc():
            return
        self._sync_client_snapshot(
            session,
            client=client,
            subscription=subscription,
            plan_code="free",
            billing_status="free",
            access_state="free_active",
            grace_until=None,
        )

    def snapshot_for_request(self, session: Session, *, client_id: str, roles: list[str]) -> BillingSnapshot:
        self.seed_existing_clients_to_free(session)
        client = session.execute(select(ClientModel).where(ClientModel.client_id == client_id)).scalar_one()
        subscription = self._subscription_row(session, client_id)
        self._degrade_to_free_if_grace_expired(session, client, subscription)
        role_pages = list(default_page_names_for_roles(roles))
        entitled = self._entitled_pages(roles, role_pages, client.billing_plan_code or "free")
        return BillingSnapshot(
            plan_code=client.billing_plan_code or "free",
            billing_status=client.billing_status or "free",
            billing_access_state=client.billing_access_state or "free_active",
            grace_until=client.billing_grace_until,
            allowed_pages=entitled,
        )

    def enforce_request_access(
        self,
        *,
        user: AuthenticatedUser,
        request_method: str,
        request_path: str,
    ) -> None:
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
            session.commit()
            client = session.execute(select(ClientModel).where(ClientModel.client_id == user.client_id)).scalar_one()
            subscription = self._subscription_row(session, user.client_id)
            self._degrade_to_free_if_grace_expired(session, client, subscription)
            plan = session.execute(
                select(BillingPlanModel).where(BillingPlanModel.plan_code == (client.billing_plan_code or "free"))
            ).scalar_one()
            customer = session.execute(
                select(BillingCustomerModel).where(BillingCustomerModel.client_id == user.client_id)
            ).scalar_one_or_none()
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
                "stripe_customer_id": customer.stripe_customer_id if customer else None,
                "stripe_subscription_id": subscription.stripe_subscription_id,
                "portal_available": bool(customer and settings.stripe_portal_configuration_id),
                "can_upgrade": plan.plan_code == "free",
                "can_manage_subscription": plan.is_paid and bool(subscription.stripe_subscription_id),
                "paid_modules_locked": list(PAID_ONLY_PAGES) if plan.plan_code == "free" or client.billing_access_state == "read_only_grace" else [],
            }

    def create_checkout_session(self, user: AuthenticatedUser, *, plan_code: str) -> str:
        self._require_owner_or_admin(user)
        with self._session_factory() as session:
            self.seed_existing_clients_to_free(session)
            client = session.execute(select(ClientModel).where(ClientModel.client_id == user.client_id)).scalar_one()
            plan = session.execute(select(BillingPlanModel).where(BillingPlanModel.plan_code == plan_code)).scalar_one_or_none()
            if plan is None or not plan.is_paid:
                raise ApiException(status_code=400, code="INVALID_BILLING_PLAN", message="Only paid plans can be checked out")
            if not plan.stripe_price_id:
                raise ApiException(status_code=500, code="MISSING_STRIPE_PRICE", message=f"Stripe price is not configured for {plan_code}")
            customer = self._get_or_create_billing_customer(session, client=client, actor=user)
            stripe = self._stripe()
            checkout = stripe.checkout.Session.create(
                mode="subscription",
                customer=customer.stripe_customer_id,
                client_reference_id=str(client.client_id),
                success_url=f"{settings.app_base_url}/billing/success?session_id={{CHECKOUT_SESSION_ID}}",
                cancel_url=f"{settings.app_base_url}/billing/cancel",
                line_items=[{"price": plan.stripe_price_id, "quantity": 1}],
                metadata={"client_id": str(client.client_id), "plan_code": plan.plan_code},
                subscription_data={"metadata": {"client_id": str(client.client_id), "plan_code": plan.plan_code}},
            )
            subscription = self._subscription_row(session, str(client.client_id))
            subscription.last_checkout_session_id = checkout["id"]
            session.commit()
            return checkout["url"]

    def _customer_portal_session(
        self,
        *,
        stripe_customer_id: str,
        flow_data: dict[str, Any] | None = None,
    ) -> str:
        stripe = self._stripe()
        payload: dict[str, Any] = {
            "customer": stripe_customer_id,
            "return_url": f"{settings.app_base_url}/billing",
        }
        if settings.stripe_portal_configuration_id:
            payload["configuration"] = settings.stripe_portal_configuration_id
        if flow_data:
            payload["flow_data"] = flow_data
        portal = stripe.billing_portal.Session.create(**payload)
        return portal["url"]

    def create_customer_portal_session(self, user: AuthenticatedUser) -> str:
        self._require_owner_or_admin(user)
        with self._session_factory() as session:
            customer = session.execute(
                select(BillingCustomerModel).where(BillingCustomerModel.client_id == user.client_id)
            ).scalar_one_or_none()
            if customer is None:
                raise ApiException(status_code=400, code="BILLING_CUSTOMER_MISSING", message="No Stripe billing customer exists for this tenant")
            return self._customer_portal_session(stripe_customer_id=customer.stripe_customer_id)

    def change_plan(self, user: AuthenticatedUser, *, target_plan_code: str) -> str:
        self._require_owner_or_admin(user)
        with self._session_factory() as session:
            self.ensure_plan_catalog(session)
            client = session.execute(select(ClientModel).where(ClientModel.client_id == user.client_id)).scalar_one()
            target_plan = session.execute(
                select(BillingPlanModel).where(BillingPlanModel.plan_code == target_plan_code)
            ).scalar_one_or_none()
            if target_plan is None or not target_plan.is_paid:
                raise ApiException(status_code=400, code="INVALID_BILLING_PLAN", message="Plan change target must be a paid plan")
            if client.billing_plan_code == "free":
                session.commit()
                return self.create_checkout_session(user, plan_code=target_plan_code)
            customer = session.execute(
                select(BillingCustomerModel).where(BillingCustomerModel.client_id == user.client_id)
            ).scalar_one_or_none()
            subscription = session.execute(
                select(SubscriptionModel).where(SubscriptionModel.client_id == user.client_id)
            ).scalar_one_or_none()
            if customer is None or subscription is None or not subscription.stripe_subscription_id:
                raise ApiException(status_code=400, code="SUBSCRIPTION_NOT_FOUND", message="No paid subscription is available to change")
            if not target_plan.stripe_price_id:
                raise ApiException(status_code=500, code="MISSING_STRIPE_PRICE", message=f"Stripe price is not configured for {target_plan_code}")
            stripe = self._stripe()
            live_subscription = stripe.Subscription.retrieve(subscription.stripe_subscription_id)
            first_item = (((live_subscription or {}).get("items") or {}).get("data") or [None])[0]
            if not first_item:
                raise ApiException(status_code=400, code="SUBSCRIPTION_ITEM_MISSING", message="Stripe subscription item is missing")
            flow_data = {
                "type": "subscription_update_confirm",
                "after_completion": {
                    "type": "redirect",
                    "redirect": {"return_url": f"{settings.app_base_url}/billing"},
                },
                "subscription_update_confirm": {
                    "subscription": subscription.stripe_subscription_id,
                    "items": [
                        {
                            "id": first_item["id"],
                            "price": target_plan.stripe_price_id,
                            "quantity": first_item.get("quantity", 1),
                        }
                    ],
                },
            }
            session.commit()
            return self._customer_portal_session(stripe_customer_id=customer.stripe_customer_id, flow_data=flow_data)

    def cancel_subscription(self, user: AuthenticatedUser) -> str:
        self._require_owner_or_admin(user)
        with self._session_factory() as session:
            customer = session.execute(
                select(BillingCustomerModel).where(BillingCustomerModel.client_id == user.client_id)
            ).scalar_one_or_none()
            subscription = session.execute(
                select(SubscriptionModel).where(SubscriptionModel.client_id == user.client_id)
            ).scalar_one_or_none()
            if customer is None or subscription is None or not subscription.stripe_subscription_id:
                raise ApiException(status_code=400, code="SUBSCRIPTION_NOT_FOUND", message="No paid subscription is available to cancel")
            flow_data = {
                "type": "subscription_cancel",
                "after_completion": {
                    "type": "redirect",
                    "redirect": {"return_url": f"{settings.app_base_url}/billing/cancel"},
                },
                "subscription_cancel": {
                    "subscription": subscription.stripe_subscription_id,
                },
            }
            session.commit()
            return self._customer_portal_session(stripe_customer_id=customer.stripe_customer_id, flow_data=flow_data)

    def _event_client_id(self, session: Session, event_type: str, obj: dict[str, Any]) -> str | None:
        metadata = obj.get("metadata") or {}
        if metadata.get("client_id"):
            return str(metadata["client_id"])
        if obj.get("client_reference_id"):
            return str(obj["client_reference_id"])
        if obj.get("customer"):
            customer = session.execute(
                select(BillingCustomerModel).where(BillingCustomerModel.stripe_customer_id == str(obj["customer"]))
            ).scalar_one_or_none()
            if customer is not None:
                return str(customer.client_id)
        if obj.get("subscription") and event_type.startswith("invoice."):
            subscription = session.execute(
                select(SubscriptionModel).where(SubscriptionModel.stripe_subscription_id == str(obj["subscription"]))
            ).scalar_one_or_none()
            if subscription is not None:
                return str(subscription.client_id)
        if obj.get("id") and event_type.startswith("customer.subscription"):
            subscription = session.execute(
                select(SubscriptionModel).where(SubscriptionModel.stripe_subscription_id == str(obj["id"]))
            ).scalar_one_or_none()
            if subscription is not None:
                return str(subscription.client_id)
        return None

    def _event_row(self, session: Session, *, event_id: str) -> PaymentEventModel | None:
        return session.execute(
            select(PaymentEventModel).where(PaymentEventModel.stripe_event_id == event_id)
        ).scalar_one_or_none()

    def _upsert_billing_customer(self, session: Session, *, client_id: str, stripe_customer_id: str, email: str = "", name: str = "") -> BillingCustomerModel:
        row = session.execute(
            select(BillingCustomerModel).where(BillingCustomerModel.client_id == client_id)
        ).scalar_one_or_none()
        if row is None:
            row = BillingCustomerModel(
                billing_customer_id=new_uuid(),
                client_id=client_id,
                stripe_customer_id=stripe_customer_id,
                email=email,
                name=name,
            )
            session.add(row)
            session.flush()
            return row
        row.stripe_customer_id = stripe_customer_id
        if email:
            row.email = email
        if name:
            row.name = name
        return row

    def _mark_event(
        self,
        event: PaymentEventModel,
        *,
        status: str,
        error_message: str = "",
    ) -> None:
        event.status = status
        event.error_message = error_message
        event.processed_at = now_utc()

    def _sync_subscription_from_object(self, session: Session, *, client_id: str, obj: dict[str, Any], event_id: str) -> SubscriptionModel:
        subscription = self._subscription_row(session, client_id)
        price_id = ((((obj.get("items") or {}).get("data")) or [{}])[0].get("price") or {}).get("id")
        plan = self._lookup_plan_by_price_id(session, price_id)
        subscription.stripe_subscription_id = obj.get("id") or subscription.stripe_subscription_id
        subscription.stripe_customer_id = obj.get("customer") or subscription.stripe_customer_id
        subscription.stripe_price_id = price_id or subscription.stripe_price_id
        subscription.cancel_at_period_end = bool(obj.get("cancel_at_period_end"))
        subscription.current_period_start = self._to_dt(obj.get("current_period_start"))
        subscription.current_period_end = self._to_dt(obj.get("current_period_end"))
        subscription.updated_from_event_id = event_id
        if plan is not None:
            subscription.plan_code = plan.plan_code
        return subscription

    def _set_paid_active(self, session: Session, *, client_id: str, subscription: SubscriptionModel, plan_code: str, event_id: str, invoice_id: str | None) -> None:
        client = session.execute(select(ClientModel).where(ClientModel.client_id == client_id)).scalar_one()
        subscription.plan_code = plan_code
        subscription.status = "active"
        subscription.grace_until = None
        subscription.updated_from_event_id = event_id
        if invoice_id:
            subscription.last_invoice_id = invoice_id
        self._sync_client_snapshot(
            session,
            client=client,
            subscription=subscription,
            plan_code=plan_code,
            billing_status="active",
            access_state="paid_active",
            grace_until=None,
        )

    def _set_read_only_grace(self, session: Session, *, client_id: str, subscription: SubscriptionModel, event_id: str, invoice_id: str | None) -> None:
        client = session.execute(select(ClientModel).where(ClientModel.client_id == client_id)).scalar_one()
        grace_until = now_utc() + timedelta(days=GRACE_PERIOD_DAYS)
        subscription.updated_from_event_id = event_id
        if invoice_id:
            subscription.last_invoice_id = invoice_id
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
        self._sync_client_snapshot(
            session,
            client=client,
            subscription=subscription,
            plan_code="free",
            billing_status="free",
            access_state="free_active",
            grace_until=None,
        )

    def handle_stripe_webhook(self, *, raw_body: bytes, signature: str | None) -> dict[str, Any]:
        if not settings.stripe_webhook_secret:
            raise ApiException(status_code=500, code="STRIPE_WEBHOOK_NOT_CONFIGURED", message="Stripe webhook secret is not configured")
        stripe = self._stripe()
        try:
            event = stripe.Webhook.construct_event(raw_body, signature, settings.stripe_webhook_secret)
        except Exception as exc:
            raise ApiException(status_code=401, code="INVALID_STRIPE_SIGNATURE", message="Invalid Stripe webhook signature") from exc

        event_id = str(event["id"])
        event_type = str(event["type"])
        obj = dict((event.get("data") or {}).get("object") or {})
        stripe_object_id = str(obj.get("id") or obj.get("subscription") or "")

        with self._session_factory() as session:
            self.seed_existing_clients_to_free(session)
            existing = self._event_row(session, event_id=event_id)
            if existing is not None:
                session.commit()
                return {"accepted": True, "status": existing.status, "event_id": event_id}

            client_id = self._event_client_id(session, event_type, obj)
            payment_event = PaymentEventModel(
                payment_event_id=new_uuid(),
                client_id=client_id,
                stripe_event_id=event_id,
                event_type=event_type,
                stripe_object_id=stripe_object_id,
                status="received",
                payload_json=json.loads(raw_body.decode("utf-8")),
            )
            session.add(payment_event)

            try:
                if event_type == "checkout.session.completed":
                    client_id = client_id or self._event_client_id(session, event_type, obj)
                    if client_id and obj.get("customer"):
                        self._upsert_billing_customer(
                            session,
                            client_id=client_id,
                            stripe_customer_id=str(obj["customer"]),
                            email=str(obj.get("customer_details", {}).get("email") or ""),
                            name=str(obj.get("customer_details", {}).get("name") or ""),
                        )
                        subscription = self._subscription_row(session, client_id)
                        subscription.stripe_customer_id = str(obj["customer"])
                        subscription.stripe_subscription_id = str(obj.get("subscription") or subscription.stripe_subscription_id or "")
                        subscription.last_checkout_session_id = str(obj["id"])
                        subscription.updated_from_event_id = event_id
                    self._mark_event(payment_event, status="linked")
                elif event_type in {"customer.subscription.created", "customer.subscription.updated"}:
                    client_id = client_id or self._event_client_id(session, event_type, obj)
                    if client_id:
                        subscription = self._sync_subscription_from_object(session, client_id=client_id, obj=obj, event_id=event_id)
                        client = session.execute(select(ClientModel).where(ClientModel.client_id == client_id)).scalar_one()
                        if subscription.status in {"active", "trialing"} and client.billing_status == "active":
                            self._sync_client_snapshot(
                                session,
                                client=client,
                                subscription=subscription,
                                plan_code=subscription.plan_code or client.billing_plan_code or "free",
                                billing_status=client.billing_status or "active",
                                access_state=client.billing_access_state or "paid_active",
                                grace_until=client.billing_grace_until,
                            )
                    self._mark_event(payment_event, status="synced")
                elif event_type == "customer.subscription.deleted":
                    client_id = client_id or self._event_client_id(session, event_type, obj)
                    if client_id:
                        subscription = self._sync_subscription_from_object(session, client_id=client_id, obj=obj, event_id=event_id)
                        self._downgrade_to_free(session, client_id=client_id, subscription=subscription, event_id=event_id)
                    self._mark_event(payment_event, status="downgraded")
                elif event_type == "invoice.paid":
                    client_id = client_id or self._event_client_id(session, event_type, obj)
                    if client_id:
                        subscription = self._subscription_row(session, client_id)
                        subscription.stripe_subscription_id = str(obj.get("subscription") or subscription.stripe_subscription_id or "")
                        subscription.stripe_customer_id = str(obj.get("customer") or subscription.stripe_customer_id or "")
                        subscription.stripe_price_id = ((((obj.get("lines") or {}).get("data")) or [{}])[0].get("price") or {}).get("id") or subscription.stripe_price_id
                        plan = self._lookup_plan_by_price_id(session, subscription.stripe_price_id) or session.execute(
                            select(BillingPlanModel).where(BillingPlanModel.plan_code == (subscription.plan_code or "growth"))
                        ).scalar_one()
                        subscription.current_period_start = self._to_dt(obj.get("period_start")) or subscription.current_period_start
                        subscription.current_period_end = self._to_dt(obj.get("period_end")) or subscription.current_period_end
                        self._set_paid_active(
                            session,
                            client_id=client_id,
                            subscription=subscription,
                            plan_code=plan.plan_code,
                            event_id=event_id,
                            invoice_id=str(obj.get("id") or ""),
                        )
                    self._mark_event(payment_event, status="paid")
                elif event_type in {"invoice.payment_failed", "invoice.payment_action_required"}:
                    client_id = client_id or self._event_client_id(session, event_type, obj)
                    if client_id:
                        subscription = self._subscription_row(session, client_id)
                        subscription.stripe_subscription_id = str(obj.get("subscription") or subscription.stripe_subscription_id or "")
                        subscription.stripe_customer_id = str(obj.get("customer") or subscription.stripe_customer_id or "")
                        self._set_read_only_grace(
                            session,
                            client_id=client_id,
                            subscription=subscription,
                            event_id=event_id,
                            invoice_id=str(obj.get("id") or ""),
                        )
                    self._mark_event(payment_event, status="past_due")
                else:
                    self._mark_event(payment_event, status="ignored")

                session.commit()
                return {"accepted": True, "status": payment_event.status, "event_id": event_id}
            except Exception as exc:
                self._mark_event(payment_event, status="failed", error_message=str(exc))
                session.commit()
                raise
