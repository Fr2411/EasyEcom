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
    billing_provider: str
    provider_plan_id: str | None = None
    currency_code: str
    interval: str
    sort_order: int
    public_description: str
    feature_flags_json: dict[str, Any] | None = None


class BillingPublicConfig(BaseModel):
    billing_provider: str
    paypal_client_id: str | None = None
    paypal_enabled: bool


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
    billing_provider: str
    provider_customer_id: str | None
    provider_subscription_id: str | None
    cancel_effective_at: str | None = None
    pending_plan_code: str | None = None
    can_upgrade: bool
    can_manage_subscription: bool
    paid_modules_locked: list[str]


class BillingChangePlanRequest(BaseModel):
    target_plan_code: Literal["growth", "scale"]


class BillingActionResponse(BaseModel):
    action_url: str | None = None
    status: str


class BillingWebhookProcessResult(BaseModel):
    accepted: bool
    status: str
    event_id: str | None = None
    provider: str
