from fastapi import APIRouter, Depends, HTTPException, Query

from easy_ecom.api.dependencies import (
    RequestUser,
    ServiceContainer,
    get_container,
    get_current_user,
    require_page_access,
)
from easy_ecom.api.schemas.purchases import (
    PurchaseCreateRequest,
    PurchaseCreateResponse,
    PurchaseDetailResponse,
    PurchaseFormOptionsResponse,
    PurchaseLineResponse,
    PurchaseSummary,
    PurchasesListResponse,
)
from easy_ecom.domain.services.purchases_api_service import PurchaseCreateInput, PurchaseLineInput

router = APIRouter(prefix="/purchases", tags=["purchases"])


def _require_service(container: ServiceContainer):
    service = getattr(container, "purchases_mvp", None)
    if service is None:
        raise HTTPException(status_code=501, detail="Purchases MVP API requires postgres backend")
    return service


@router.get("", response_model=PurchasesListResponse)
def list_purchases(
    q: str = Query(default="", max_length=120),
    user: RequestUser = Depends(get_current_user),
    container: ServiceContainer = Depends(get_container),
) -> PurchasesListResponse:
    require_page_access(user, "Purchases")
    service = _require_service(container)
    rows = service.list_purchases(client_id=user.client_id, query=q)
    items = [
        PurchaseSummary(
            purchase_id=row["purchase_id"],
            purchase_no=row["purchase_no"],
            purchase_date=row["purchase_date"],
            supplier_id=row["supplier_id"],
            supplier_name=row["supplier_name"],
            reference_no=row["reference_no"],
            subtotal=row["subtotal"],
            status=row["status"],
            created_at=row["created_at"],
        )
        for row in rows
    ]
    return PurchasesListResponse(items=items)


@router.get("/form-options", response_model=PurchaseFormOptionsResponse)
def purchases_form_options(
    q: str = Query(default="", max_length=120),
    user: RequestUser = Depends(get_current_user),
    container: ServiceContainer = Depends(get_container),
) -> PurchaseFormOptionsResponse:
    require_page_access(user, "Purchases")
    service = _require_service(container)
    rows = service.lookup_options(client_id=user.client_id, query=q)
    return PurchaseFormOptionsResponse(products=rows["products"], suppliers=rows["suppliers"])


@router.get("/{purchase_id}", response_model=PurchaseDetailResponse)
def get_purchase_detail(
    purchase_id: str,
    user: RequestUser = Depends(get_current_user),
    container: ServiceContainer = Depends(get_container),
) -> PurchaseDetailResponse:
    require_page_access(user, "Purchases")
    service = _require_service(container)
    row = service.get_purchase_detail(client_id=user.client_id, purchase_id=purchase_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Purchase not found")
    row["lines"] = [PurchaseLineResponse(**line) for line in row["lines"]]
    return PurchaseDetailResponse(**row)


@router.post("", response_model=PurchaseCreateResponse, status_code=201)
def create_purchase(
    payload: PurchaseCreateRequest,
    user: RequestUser = Depends(get_current_user),
    container: ServiceContainer = Depends(get_container),
) -> PurchaseCreateResponse:
    require_page_access(user, "Purchases")
    service = _require_service(container)
    try:
        row = service.create_purchase(
            client_id=user.client_id,
            user_id=user.user_id,
            payload=PurchaseCreateInput(
                purchase_date=payload.purchase_date,
                supplier_id=payload.supplier_id,
                reference_no=payload.reference_no,
                note=payload.note,
                lines=[PurchaseLineInput(product_id=line.product_id, qty=line.qty, unit_cost=line.unit_cost) for line in payload.lines],
                payment_status=payload.payment_status,
            ),
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return PurchaseCreateResponse(**row)
