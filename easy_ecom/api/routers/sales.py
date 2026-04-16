from fastapi import APIRouter, Depends, Query

from easy_ecom.api.dependencies import ServiceContainer, get_authenticated_user, get_container, require_module_access
from easy_ecom.api.schemas.commerce import (
    CustomerLookupResponse,
    SaleVariantLookupResponse,
    SalesOrderActionRequest,
    SalesOrderActionResponse,
    SalesOrderPaymentRequest,
    SalesOrderResponse,
    SalesOrderUpsertRequest,
    SalesOrdersResponse,
)
from easy_ecom.api.schemas.common import ModuleOverviewResponse
from easy_ecom.domain.models.auth import AuthenticatedUser

router = APIRouter(
    prefix="/sales",
    tags=["sales"],
    dependencies=[Depends(require_module_access("Sales"))],
)


@router.get("/overview", response_model=ModuleOverviewResponse)
def sales_overview(
    user: AuthenticatedUser = Depends(get_authenticated_user),
    container: ServiceContainer = Depends(get_container),
) -> ModuleOverviewResponse:
    return container.overview.sales(user)


@router.get("/orders", response_model=SalesOrdersResponse)
def list_orders(
    status: str | None = Query(default=None),
    q: str = Query(default=""),
    user: AuthenticatedUser = Depends(get_authenticated_user),
    container: ServiceContainer = Depends(get_container),
) -> SalesOrdersResponse:
    return SalesOrdersResponse(
        items=container.sales.list_orders(user, status=status, query=q)
    )


@router.get("/orders/{sales_order_id}", response_model=SalesOrderResponse)
def get_order(
    sales_order_id: str,
    user: AuthenticatedUser = Depends(get_authenticated_user),
    container: ServiceContainer = Depends(get_container),
) -> SalesOrderResponse:
    return SalesOrderResponse.model_validate(container.sales.get_order(user, sales_order_id))


@router.get("/variants/search", response_model=SaleVariantLookupResponse)
def search_variants(
    q: str = Query(default=""),
    location_id: str | None = Query(default=None),
    user: AuthenticatedUser = Depends(get_authenticated_user),
    container: ServiceContainer = Depends(get_container),
) -> SaleVariantLookupResponse:
    return SaleVariantLookupResponse(
        items=container.sales.lookup_variants(user, query=q, location_id=location_id)
    )


@router.get("/customers/search", response_model=CustomerLookupResponse)
def search_customers(
    phone: str = Query(default=""),
    email: str = Query(default=""),
    user: AuthenticatedUser = Depends(get_authenticated_user),
    container: ServiceContainer = Depends(get_container),
) -> CustomerLookupResponse:
    return CustomerLookupResponse(items=container.sales.lookup_customers(user, phone=phone, email=email))


@router.post("/orders", response_model=SalesOrderActionResponse)
def create_order(
    payload: SalesOrderUpsertRequest,
    user: AuthenticatedUser = Depends(get_authenticated_user),
    container: ServiceContainer = Depends(get_container),
) -> SalesOrderActionResponse:
    return SalesOrderActionResponse(
        order=container.sales.create_order(
            user,
            location_id=payload.location_id,
            customer_id=payload.customer_id,
            customer_payload=payload.customer.model_dump() if payload.customer else None,
            payment_status=payload.payment_status,
            shipment_status=payload.shipment_status,
            notes=payload.notes,
            lines=[item.model_dump() for item in payload.lines],
            action=payload.action,
        )
    )


@router.put("/orders/{sales_order_id}", response_model=SalesOrderActionResponse)
def update_order(
    sales_order_id: str,
    payload: SalesOrderUpsertRequest,
    user: AuthenticatedUser = Depends(get_authenticated_user),
    container: ServiceContainer = Depends(get_container),
) -> SalesOrderActionResponse:
    return SalesOrderActionResponse(
        order=container.sales.update_order(
            user,
            sales_order_id=sales_order_id,
            location_id=payload.location_id,
            customer_id=payload.customer_id,
            customer_payload=payload.customer.model_dump() if payload.customer else None,
            payment_status=payload.payment_status,
            shipment_status=payload.shipment_status,
            notes=payload.notes,
            lines=[item.model_dump() for item in payload.lines],
            action=payload.action,
        )
    )


@router.post("/orders/{sales_order_id}/confirm", response_model=SalesOrderActionResponse)
def confirm_order(
    sales_order_id: str,
    _payload: SalesOrderActionRequest,
    user: AuthenticatedUser = Depends(get_authenticated_user),
    container: ServiceContainer = Depends(get_container),
) -> SalesOrderActionResponse:
    return SalesOrderActionResponse(order=container.sales.confirm_order(user, sales_order_id))


@router.post("/orders/{sales_order_id}/fulfill", response_model=SalesOrderActionResponse)
def fulfill_order(
    sales_order_id: str,
    _payload: SalesOrderActionRequest,
    user: AuthenticatedUser = Depends(get_authenticated_user),
    container: ServiceContainer = Depends(get_container),
) -> SalesOrderActionResponse:
    return SalesOrderActionResponse(order=container.sales.fulfill_order(user, sales_order_id))


@router.post("/orders/{sales_order_id}/cancel", response_model=SalesOrderActionResponse)
def cancel_order(
    sales_order_id: str,
    payload: SalesOrderActionRequest,
    user: AuthenticatedUser = Depends(get_authenticated_user),
    container: ServiceContainer = Depends(get_container),
) -> SalesOrderActionResponse:
    return SalesOrderActionResponse(
        order=container.sales.cancel_order(user, sales_order_id, notes=payload.notes)
    )


@router.post("/orders/{sales_order_id}/record-payment", response_model=SalesOrderActionResponse)
def record_order_payment(
    sales_order_id: str,
    payload: SalesOrderPaymentRequest,
    user: AuthenticatedUser = Depends(get_authenticated_user),
    container: ServiceContainer = Depends(get_container),
) -> SalesOrderActionResponse:
    return SalesOrderActionResponse(
        order=container.sales.record_order_payment(
            user,
            sales_order_id=sales_order_id,
            payment_date=payload.payment_date,
            amount=payload.amount,
            method=payload.method,
            reference=payload.reference,
            note=payload.note,
        )
    )
