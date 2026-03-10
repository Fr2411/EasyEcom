from fastapi import APIRouter, Depends, HTTPException, Query

from easy_ecom.api.dependencies import RequestUser, ServiceContainer, get_container, get_current_user, require_page_access
from easy_ecom.api.schemas.returns import (
    ReturnCreateRequest,
    ReturnCreateResponse,
    ReturnDetailLineResponse,
    ReturnDetailResponse,
    ReturnableSaleDetailResponse,
    ReturnSaleLookupItem,
    ReturnSalesLookupResponse,
    ReturnsListResponse,
    ReturnSummary,
)
from easy_ecom.domain.services.returns_api_service import ReturnCreateInput, ReturnLineInput

router = APIRouter(prefix="/returns", tags=["returns"])


def _require_service(container: ServiceContainer):
    service = getattr(container, "returns_mvp", None)
    if service is None:
        raise HTTPException(status_code=501, detail="Returns MVP API requires postgres backend")
    return service


@router.get("", response_model=ReturnsListResponse)
def list_returns(
    q: str = Query(default="", max_length=100),
    user: RequestUser = Depends(get_current_user),
    container: ServiceContainer = Depends(get_container),
) -> ReturnsListResponse:
    require_page_access(user, "Returns")
    service = _require_service(container)
    return ReturnsListResponse(items=[ReturnSummary(**row) for row in service.list_returns(client_id=user.client_id, query=q)])


@router.get("/sales-lookup", response_model=ReturnSalesLookupResponse)
def sales_lookup(
    q: str = Query(default="", max_length=100),
    user: RequestUser = Depends(get_current_user),
    container: ServiceContainer = Depends(get_container),
) -> ReturnSalesLookupResponse:
    require_page_access(user, "Returns")
    service = _require_service(container)
    return ReturnSalesLookupResponse(items=[ReturnSaleLookupItem(**row) for row in service.list_sales_for_returns(client_id=user.client_id, query=q)])


@router.get("/sales/{sale_id}", response_model=ReturnableSaleDetailResponse)
def get_returnable_sale(
    sale_id: str,
    user: RequestUser = Depends(get_current_user),
    container: ServiceContainer = Depends(get_container),
) -> ReturnableSaleDetailResponse:
    require_page_access(user, "Returns")
    service = _require_service(container)
    detail = service.get_returnable_sale(client_id=user.client_id, sale_id=sale_id)
    if detail is None:
        raise HTTPException(status_code=404, detail="Sale not found")
    return ReturnableSaleDetailResponse(**detail)


@router.get("/{return_id}", response_model=ReturnDetailResponse)
def get_return_detail(
    return_id: str,
    user: RequestUser = Depends(get_current_user),
    container: ServiceContainer = Depends(get_container),
) -> ReturnDetailResponse:
    require_page_access(user, "Returns")
    service = _require_service(container)
    detail = service.get_return_detail(client_id=user.client_id, return_id=return_id)
    if detail is None:
        raise HTTPException(status_code=404, detail="Return not found")
    detail["lines"] = [ReturnDetailLineResponse(**line) for line in detail["lines"]]
    return ReturnDetailResponse(**detail)


@router.post("", response_model=ReturnCreateResponse, status_code=201)
def create_return(
    payload: ReturnCreateRequest,
    user: RequestUser = Depends(get_current_user),
    container: ServiceContainer = Depends(get_container),
) -> ReturnCreateResponse:
    require_page_access(user, "Returns")
    service = _require_service(container)
    try:
        created = service.create_return(
            client_id=user.client_id,
            user_id=user.user_id,
            payload=ReturnCreateInput(
                sale_id=payload.sale_id,
                reason=payload.reason,
                note=payload.note,
                lines=[
                    ReturnLineInput(
                        sale_item_id=line.sale_item_id,
                        qty=line.qty,
                        reason=line.reason,
                        condition_status=line.condition_status,
                    )
                    for line in payload.lines
                ],
            ),
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return ReturnCreateResponse(**created)
