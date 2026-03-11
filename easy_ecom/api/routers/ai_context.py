from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query

from easy_ecom.api.dependencies import (
    RequestUser,
    ServiceContainer,
    get_container,
    get_current_user,
    require_page_access,
)
from easy_ecom.api.schemas.ai_context import (
    AiCustomersContextResponse,
    AiLookupResponse,
    AiLowStockResponse,
    AiOverviewResponse,
    AiProductsContextResponse,
    AiRecentActivityResponse,
    AiSalesContextResponse,
    AiStockContextResponse,
    InboundInquiryRequest,
    InboundInquiryResponse,
)
from easy_ecom.domain.services.ai_context_service import InquiryPayload

router = APIRouter(prefix="/ai", tags=["ai"])


def _require_service(container: ServiceContainer):
    service = getattr(container, "ai_context", None)
    if service is None:
        raise HTTPException(status_code=501, detail="AI context API requires postgres backend")
    return service


@router.get("/context/overview", response_model=AiOverviewResponse)
def get_overview(
    user: RequestUser = Depends(get_current_user),
    container: ServiceContainer = Depends(get_container),
) -> AiOverviewResponse:
    require_page_access(user, "Reports")
    service = _require_service(container)
    return AiOverviewResponse(**service.overview(client_id=user.client_id))


@router.get("/context/products", response_model=AiProductsContextResponse)
def get_products(
    query: str = Query(default="", max_length=120),
    limit: int = Query(default=20, ge=1, le=100),
    user: RequestUser = Depends(get_current_user),
    container: ServiceContainer = Depends(get_container),
) -> AiProductsContextResponse:
    require_page_access(user, "Reports")
    service = _require_service(container)
    return AiProductsContextResponse(**service.products_context(client_id=user.client_id, query=query, limit=limit))


@router.get("/context/stock", response_model=AiStockContextResponse)
def get_stock(
    product_id: str = Query(default="", max_length=64),
    user: RequestUser = Depends(get_current_user),
    container: ServiceContainer = Depends(get_container),
) -> AiStockContextResponse:
    require_page_access(user, "Reports")
    service = _require_service(container)
    return AiStockContextResponse(**service.stock_context(client_id=user.client_id, product_id=product_id))


@router.get("/context/low-stock", response_model=AiLowStockResponse)
def get_low_stock(
    threshold: int | None = Query(default=None, ge=0, le=999),
    user: RequestUser = Depends(get_current_user),
    container: ServiceContainer = Depends(get_container),
) -> AiLowStockResponse:
    require_page_access(user, "Reports")
    service = _require_service(container)
    return AiLowStockResponse(**service.low_stock_context(client_id=user.client_id, threshold=threshold))


@router.get("/context/sales", response_model=AiSalesContextResponse)
def get_sales(
    days: int = Query(default=7, ge=1, le=90),
    user: RequestUser = Depends(get_current_user),
    container: ServiceContainer = Depends(get_container),
) -> AiSalesContextResponse:
    require_page_access(user, "Reports")
    service = _require_service(container)
    return AiSalesContextResponse(**service.sales_context(client_id=user.client_id, days=days))


@router.get("/context/customers", response_model=AiCustomersContextResponse)
def get_customers(
    query: str = Query(default="", max_length=120),
    user: RequestUser = Depends(get_current_user),
    container: ServiceContainer = Depends(get_container),
) -> AiCustomersContextResponse:
    require_page_access(user, "Reports")
    service = _require_service(container)
    return AiCustomersContextResponse(**service.customers_context(client_id=user.client_id, query=query))


@router.get("/context/lookup", response_model=AiLookupResponse)
def get_lookup(
    kind: str = Query(pattern="^(product|customer|sale)$"),
    query: str = Query(min_length=1, max_length=120),
    user: RequestUser = Depends(get_current_user),
    container: ServiceContainer = Depends(get_container),
) -> AiLookupResponse:
    require_page_access(user, "Reports")
    service = _require_service(container)
    try:
        return AiLookupResponse(**service.lookup_context(client_id=user.client_id, kind=kind, query=query))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/context/recent-activity", response_model=AiRecentActivityResponse)
def get_recent_activity(
    days: int = Query(default=7, ge=1, le=30),
    user: RequestUser = Depends(get_current_user),
    container: ServiceContainer = Depends(get_container),
) -> AiRecentActivityResponse:
    require_page_access(user, "Reports")
    service = _require_service(container)
    return AiRecentActivityResponse(**service.recent_activity_context(client_id=user.client_id, days=days))


@router.post("/hooks/inbound-inquiry", response_model=InboundInquiryResponse)
def inbound_inquiry(
    payload: InboundInquiryRequest,
    user: RequestUser = Depends(get_current_user),
    container: ServiceContainer = Depends(get_container),
) -> InboundInquiryResponse:
    require_page_access(user, "Reports")
    service = _require_service(container)
    try:
        result = service.handle_inbound_inquiry(
            client_id=user.client_id,
            payload=InquiryPayload(message=payload.message, customer_ref=payload.customer_ref),
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return InboundInquiryResponse(**result)
