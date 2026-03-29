from __future__ import annotations

from fastapi import APIRouter, Depends, Header, Request

from easy_ecom.api.dependencies import ServiceContainer, get_authenticated_user, get_container, require_page_access
from easy_ecom.api.schemas.billing import (
    BillingChangePlanRequest,
    BillingCheckoutSessionRequest,
    BillingCheckoutSessionResponse,
    BillingPlansResponse,
    BillingPortalSessionResponse,
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


@protected_router.post("/checkout-session", response_model=BillingCheckoutSessionResponse)
def create_checkout_session(
    payload: BillingCheckoutSessionRequest,
    user: AuthenticatedUser = Depends(get_authenticated_user),
    container: ServiceContainer = Depends(get_container),
) -> BillingCheckoutSessionResponse:
    require_page_access(user, "Billing")
    return BillingCheckoutSessionResponse(
        checkout_url=container.billing.create_checkout_session(user, plan_code=payload.plan_code)
    )


@protected_router.get("/subscription", response_model=BillingSubscriptionState)
def get_billing_subscription(
    user: AuthenticatedUser = Depends(get_authenticated_user),
    container: ServiceContainer = Depends(get_container),
) -> BillingSubscriptionState:
    require_page_access(user, "Billing")
    return BillingSubscriptionState.model_validate(container.billing.subscription_state(user))


@protected_router.post("/customer-portal-session", response_model=BillingPortalSessionResponse)
def create_customer_portal_session(
    user: AuthenticatedUser = Depends(get_authenticated_user),
    container: ServiceContainer = Depends(get_container),
) -> BillingPortalSessionResponse:
    require_page_access(user, "Billing")
    return BillingPortalSessionResponse(
        portal_url=container.billing.create_customer_portal_session(user)
    )


@protected_router.post("/change-plan", response_model=BillingPortalSessionResponse)
def change_plan(
    payload: BillingChangePlanRequest,
    user: AuthenticatedUser = Depends(get_authenticated_user),
    container: ServiceContainer = Depends(get_container),
) -> BillingPortalSessionResponse:
    require_page_access(user, "Billing")
    return BillingPortalSessionResponse(
        portal_url=container.billing.change_plan(user, target_plan_code=payload.target_plan_code)
    )


@protected_router.post("/cancel-subscription", response_model=BillingPortalSessionResponse)
def cancel_subscription(
    user: AuthenticatedUser = Depends(get_authenticated_user),
    container: ServiceContainer = Depends(get_container),
) -> BillingPortalSessionResponse:
    require_page_access(user, "Billing")
    return BillingPortalSessionResponse(
        portal_url=container.billing.cancel_subscription(user)
    )


@router.post("/billing/webhooks/stripe", response_model=BillingWebhookProcessResult)
async def receive_stripe_webhook(
    request: Request,
    stripe_signature: str | None = Header(default=None, alias="Stripe-Signature"),
    container: ServiceContainer = Depends(get_container),
) -> BillingWebhookProcessResult:
    raw_body = await request.body()
    result = container.billing.handle_stripe_webhook(raw_body=raw_body, signature=stripe_signature)
    return BillingWebhookProcessResult.model_validate(result)
