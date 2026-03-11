from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query

from easy_ecom.api.dependencies import (
    RequestUser,
    ServiceContainer,
    get_container,
    get_current_user,
    require_page_access,
)
from easy_ecom.api.schemas.reports import (
    FinanceReportResponse,
    InventoryReportResponse,
    ProductsReportResponse,
    PurchasesReportResponse,
    ReportsOverviewResponse,
    ReturnsReportResponse,
    SalesReportResponse,
)

router = APIRouter(prefix="/reports", tags=["reports"])


def _require_service(container: ServiceContainer):
    service = getattr(container, "reports_mvp", None)
    if service is None:
        raise HTTPException(status_code=501, detail="Reports API requires postgres backend")
    return service


def _filters(
    service,
    *,
    from_date: date | None,
    to_date: date | None,
    product_id: str,
    category: str,
    customer_id: str,
):
    try:
        return service.build_filters(
            from_date=from_date,
            to_date=to_date,
            product_id=product_id,
            category=category,
            customer_id=customer_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/sales", response_model=SalesReportResponse)
def sales_report(
    from_date: date | None = Query(default=None),
    to_date: date | None = Query(default=None),
    product_id: str = Query(default="", max_length=64),
    customer_id: str = Query(default="", max_length=64),
    user: RequestUser = Depends(get_current_user),
    container: ServiceContainer = Depends(get_container),
) -> SalesReportResponse:
    require_page_access(user, "Reports")
    service = _require_service(container)
    filters = _filters(service, from_date=from_date, to_date=to_date, product_id=product_id, category="", customer_id=customer_id)
    return SalesReportResponse(**service.sales_report(client_id=user.client_id, filters=filters))


@router.get("/inventory", response_model=InventoryReportResponse)
def inventory_report(
    from_date: date | None = Query(default=None),
    to_date: date | None = Query(default=None),
    category: str = Query(default="", max_length=120),
    user: RequestUser = Depends(get_current_user),
    container: ServiceContainer = Depends(get_container),
) -> InventoryReportResponse:
    require_page_access(user, "Reports")
    service = _require_service(container)
    filters = _filters(service, from_date=from_date, to_date=to_date, product_id="", category=category, customer_id="")
    return InventoryReportResponse(**service.inventory_report(client_id=user.client_id, filters=filters))


@router.get("/products", response_model=ProductsReportResponse)
def products_report(
    from_date: date | None = Query(default=None),
    to_date: date | None = Query(default=None),
    category: str = Query(default="", max_length=120),
    user: RequestUser = Depends(get_current_user),
    container: ServiceContainer = Depends(get_container),
) -> ProductsReportResponse:
    require_page_access(user, "Reports")
    service = _require_service(container)
    filters = _filters(service, from_date=from_date, to_date=to_date, product_id="", category=category, customer_id="")
    return ProductsReportResponse(**service.products_report(client_id=user.client_id, filters=filters))


@router.get("/finance", response_model=FinanceReportResponse)
def finance_report(
    from_date: date | None = Query(default=None),
    to_date: date | None = Query(default=None),
    user: RequestUser = Depends(get_current_user),
    container: ServiceContainer = Depends(get_container),
) -> FinanceReportResponse:
    require_page_access(user, "Reports")
    service = _require_service(container)
    filters = _filters(service, from_date=from_date, to_date=to_date, product_id="", category="", customer_id="")
    return FinanceReportResponse(**service.finance_report(client_id=user.client_id, filters=filters))


@router.get("/returns", response_model=ReturnsReportResponse)
def returns_report(
    from_date: date | None = Query(default=None),
    to_date: date | None = Query(default=None),
    user: RequestUser = Depends(get_current_user),
    container: ServiceContainer = Depends(get_container),
) -> ReturnsReportResponse:
    require_page_access(user, "Reports")
    service = _require_service(container)
    filters = _filters(service, from_date=from_date, to_date=to_date, product_id="", category="", customer_id="")
    return ReturnsReportResponse(**service.returns_report(client_id=user.client_id, filters=filters))


@router.get("/purchases", response_model=PurchasesReportResponse)
def purchases_report(
    from_date: date | None = Query(default=None),
    to_date: date | None = Query(default=None),
    user: RequestUser = Depends(get_current_user),
    container: ServiceContainer = Depends(get_container),
) -> PurchasesReportResponse:
    require_page_access(user, "Reports")
    service = _require_service(container)
    filters = _filters(service, from_date=from_date, to_date=to_date, product_id="", category="", customer_id="")
    return PurchasesReportResponse(**service.purchases_report(client_id=user.client_id, filters=filters))


@router.get("/overview", response_model=ReportsOverviewResponse)
def overview_report(
    from_date: date | None = Query(default=None),
    to_date: date | None = Query(default=None),
    user: RequestUser = Depends(get_current_user),
    container: ServiceContainer = Depends(get_container),
) -> ReportsOverviewResponse:
    require_page_access(user, "Reports")
    service = _require_service(container)
    filters = _filters(service, from_date=from_date, to_date=to_date, product_id="", category="", customer_id="")
    return ReportsOverviewResponse(**service.overview_report(client_id=user.client_id, filters=filters))

