from fastapi import APIRouter, Depends, HTTPException, Query

from easy_ecom.api.dependencies import (
    RequestUser,
    ServiceContainer,
    get_container,
    get_current_user,
    require_page_access,
)
from easy_ecom.api.schemas.sales import (
    SaleCreateRequest,
    SaleCreateResponse,
    SaleDetailResponse,
    SaleFormOptionsResponse,
    SaleLineResponse,
    SaleSummary,
    SalesListResponse,
    LegacySalesCreateRequest,
    LegacySalesCreateResponse,
)
from easy_ecom.domain.services.sales_api_service import SalesLineInput
from easy_ecom.domain.models.sales import SaleConfirm, SaleItem

router = APIRouter(prefix="/sales", tags=["sales"])


def _require_service(container: ServiceContainer):
    service = getattr(container, "sales_mvp", None)
    if service is None:
        raise HTTPException(status_code=501, detail="Sales MVP API requires postgres backend")
    return service


@router.get("", response_model=SalesListResponse)
def list_sales(
    q: str = Query(default="", max_length=100),
    user: RequestUser = Depends(get_current_user),
    container: ServiceContainer = Depends(get_container),
) -> SalesListResponse:
    require_page_access(user, "Sales")
    service = _require_service(container)
    items = [SaleSummary(**row) for row in service.list_sales(client_id=user.client_id, query=q)]
    return SalesListResponse(items=items)


@router.get("/form-options", response_model=SaleFormOptionsResponse)
def form_options(
    q: str = Query(default="", max_length=100),
    user: RequestUser = Depends(get_current_user),
    container: ServiceContainer = Depends(get_container),
) -> SaleFormOptionsResponse:
    require_page_access(user, "Sales")
    service = _require_service(container)
    return SaleFormOptionsResponse(
        customers=service.lookup_customers(client_id=user.client_id, query=q),
        products=service.lookup_products(client_id=user.client_id, query=q),
    )


@router.get("/{sale_id}", response_model=SaleDetailResponse)
def get_sale_detail(
    sale_id: str,
    user: RequestUser = Depends(get_current_user),
    container: ServiceContainer = Depends(get_container),
) -> SaleDetailResponse:
    require_page_access(user, "Sales")
    service = _require_service(container)
    detail = service.get_sale_detail(client_id=user.client_id, sale_id=sale_id)
    if detail is None:
        raise HTTPException(status_code=404, detail="Sale not found")
    detail["lines"] = [SaleLineResponse(**line) for line in detail["lines"]]
    return SaleDetailResponse(**detail)


@router.post("", response_model=SaleCreateResponse, status_code=201)
def create_sale(
    payload: SaleCreateRequest,
    user: RequestUser = Depends(get_current_user),
    container: ServiceContainer = Depends(get_container),
) -> SaleCreateResponse:
    require_page_access(user, "Sales")
    service = getattr(container, "sales_mvp", None)
    if service is None:
        raise HTTPException(status_code=501, detail="Sales MVP API requires postgres backend")
    try:
        result = service.create_sale(
            client_id=user.client_id,
            user_id=user.user_id,
            customer_id=payload.customer_id,
            lines=[SalesLineInput(variant_id=line.variant_id, qty=line.qty, unit_price=line.unit_price) for line in payload.lines],
            discount=payload.discount,
            tax=payload.tax,
            note=payload.note,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return SaleCreateResponse(**result)


@router.post("/create", response_model=LegacySalesCreateResponse)
def create_sale_legacy(
    payload: LegacySalesCreateRequest,
    user: RequestUser = Depends(get_current_user),
    container: ServiceContainer = Depends(get_container),
) -> LegacySalesCreateResponse:
    require_page_access(user, "Sales")

    service = getattr(container, "sales_mvp", None)
    if service is not None:
        try:
            result = service.create_sale(
                client_id=user.client_id,
                user_id=user.user_id,
                customer_id=payload.customer_id,
                lines=[SalesLineInput(variant_id=line.variant_id, qty=line.qty, unit_price=line.unit_selling_price) for line in payload.items],
                discount=payload.discount,
                tax=payload.tax,
                note=payload.note,
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return LegacySalesCreateResponse(order_id=result["sale_id"], invoice_id="", status=result["status"])

    # Backward compatibility for existing CSV-backed service/tests.
    result = container.sales.confirm_sale(
        SaleConfirm(
            client_id=user.client_id,
            customer_id=payload.customer_id,
            items=[
                SaleItem(
                    product_id=item.product_id,
                    qty=item.qty,
                    unit_selling_price=item.unit_selling_price,
                )
                for item in payload.items
            ],
            discount=payload.discount,
            tax=payload.tax,
            note=payload.note,
        ),
        customer_snapshot={},
        user_id=user.user_id,
    )
    return LegacySalesCreateResponse(
        order_id=str(result.get("order_id", "")),
        invoice_id=str(result.get("invoice_id", "")),
        status=str(result.get("order_status", "confirmed")),
    )
