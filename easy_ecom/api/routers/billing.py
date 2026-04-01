from __future__ import annotations

from fastapi import APIRouter, Depends, Header, Request

from easy_ecom.api.dependencies import ServiceContainer, get_authenticated_user, get_container, require_page_access
from easy_ecom.api.schemas.billing import (
    BillingActionResponse,
    BillingChangePlanRequest,
    BillingPublicConfig,
    BillingPlansResponse,
    BillingSubscriptionState,
    BillingWebhookProcessResult,
)
from easy_ecom.domain.models.auth import AuthenticatedUser

router = APIRouter(tags=["billing"])
public_router = APIRouter(prefix="/public/billing", tags=["public-billing"])
protected_router = APIRouter(prefix="/billing", tags=["billing"])


@public_router.get("/plans", response_model=BillingPlansResponse)
def list_public_billing_plans(
    container: ServiceContainer = Depends(get_container),
) -> BillingPlansResponse:
    return BillingPlansResponse(items=container.billing.public_plans())


@public_router.get("/config", response_model=BillingPublicConfig)
def get_public_billing_config(
    container: ServiceContainer = Depends(get_container),
) -> BillingPublicConfig:
    return BillingPublicConfig.model_validate(container.billing.public_config())


@protected_router.get("/subscription", response_model=BillingSubscriptionState)
def get_billing_subscription(
    user: AuthenticatedUser = Depends(get_authenticated_user),
    container: ServiceContainer = Depends(get_container),
) -> BillingSubscriptionState:
    require_page_access(user, "Billing")
    return BillingSubscriptionState.model_validate(container.billing.subscription_state(user))


@protected_router.post("/change-plan", response_model=BillingActionResponse)
def change_plan(
    payload: BillingChangePlanRequest,
    user: AuthenticatedUser = Depends(get_authenticated_user),
    container: ServiceContainer = Depends(get_container),
) -> BillingActionResponse:
    require_page_access(user, "Billing")
    return BillingActionResponse.model_validate(
        container.billing.change_plan(user, target_plan_code=payload.target_plan_code)
    )


@protected_router.post("/cancel-subscription", response_model=BillingActionResponse)
def cancel_subscription(
    user: AuthenticatedUser = Depends(get_authenticated_user),
    container: ServiceContainer = Depends(get_container),
) -> BillingActionResponse:
    require_page_access(user, "Billing")
    return BillingActionResponse.model_validate(container.billing.cancel_subscription(user))


@router.post("/billing/webhooks/paypal", response_model=BillingWebhookProcessResult)
async def receive_paypal_webhook(
    request: Request,
    paypal_auth_algo: str | None = Header(default=None, alias="PAYPAL-AUTH-ALGO"),
    paypal_cert_url: str | None = Header(default=None, alias="PAYPAL-CERT-URL"),
    paypal_transmission_id: str | None = Header(default=None, alias="PAYPAL-TRANSMISSION-ID"),
    paypal_transmission_sig: str | None = Header(default=None, alias="PAYPAL-TRANSMISSION-SIG"),
    paypal_transmission_time: str | None = Header(default=None, alias="PAYPAL-TRANSMISSION-TIME"),
    container: ServiceContainer = Depends(get_container),
) -> BillingWebhookProcessResult:
    raw_body = await request.body()
    result = container.billing.handle_paypal_webhook(
        raw_body=raw_body,
        headers={
            "paypal-auth-algo": paypal_auth_algo,
            "paypal-cert-url": paypal_cert_url,
            "paypal-transmission-id": paypal_transmission_id,
            "paypal-transmission-sig": paypal_transmission_sig,
            "paypal-transmission-time": paypal_transmission_time,
        },
    )
    return BillingWebhookProcessResult.model_validate(result)
