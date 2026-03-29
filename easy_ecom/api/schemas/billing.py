from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


BillingAccessState = Literal["free_active", "paid_active", "read_only_grace", "blocked"]
BillingSubscriptionStatus = Literal[
    "free",
    "trialing",
    "active",
    "past_due",
    "canceled",
    "unpaid",
    "incomplete",
    "incomplete_expired",
]


class BillingPlan(BaseModel):
    plan_code: str
    display_name: str
    is_paid: bool
    currency_code: str
    interval: str
    sort_order: int
    public_description: str
    feature_flags_json: dict[str, Any] | None = None


class BillingPlansResponse(BaseModel):
    items: list[BillingPlan]


class BillingSubscriptionState(BaseModel):
    plan_code: str
    plan_name: str
    billing_status: str
    billing_access_state: BillingAccessState
    cancel_at_period_end: bool
    current_period_start: str | None
    current_period_end: str | None
    grace_until: str | None
    stripe_customer_id: str | None
    stripe_subscription_id: str | None
    portal_available: bool
    can_upgrade: bool
    can_manage_subscription: bool
    paid_modules_locked: list[str]


class BillingCheckoutSessionRequest(BaseModel):
    plan_code: Literal["growth", "scale"]


class BillingCheckoutSessionResponse(BaseModel):
    checkout_url: str


class BillingPortalSessionResponse(BaseModel):
    portal_url: str


class BillingChangePlanRequest(BaseModel):
    target_plan_code: Literal["growth", "scale"]


class BillingWebhookProcessResult(BaseModel):
    accepted: bool
    status: str
    event_id: str | None = None
