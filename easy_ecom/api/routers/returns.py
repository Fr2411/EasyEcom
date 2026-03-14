from fastapi import APIRouter, Depends, Query

from easy_ecom.api.dependencies import ServiceContainer, get_authenticated_user, get_container, require_page_access
from easy_ecom.api.schemas.commerce import (
    ReturnCreateRequest,
    ReturnEligibleLinesResponse,
    ReturnLookupOrdersResponse,
    ReturnResponse,
    ReturnsResponse,
)
from easy_ecom.api.schemas.common import ModuleOverviewResponse
from easy_ecom.domain.models.auth import AuthenticatedUser

router = APIRouter(prefix="/returns", tags=["returns"])


@router.get("/overview", response_model=ModuleOverviewResponse)
def returns_overview(
    user: AuthenticatedUser = Depends(get_authenticated_user),
    container: ServiceContainer = Depends(get_container),
) -> ModuleOverviewResponse:
    require_page_access(user, "Returns")
    return container.overview.returns(user)


@router.get("", response_model=ReturnsResponse)
def list_returns(
    q: str = Query(default=""),
    user: AuthenticatedUser = Depends(get_authenticated_user),
    container: ServiceContainer = Depends(get_container),
) -> ReturnsResponse:
    return ReturnsResponse(items=container.returns.list_returns(user, query=q))


@router.get("/orders/search", response_model=ReturnLookupOrdersResponse)
def search_return_orders(
    q: str = Query(default=""),
    user: AuthenticatedUser = Depends(get_authenticated_user),
    container: ServiceContainer = Depends(get_container),
) -> ReturnLookupOrdersResponse:
    return ReturnLookupOrdersResponse(items=container.returns.eligible_orders(user, query=q))


@router.get("/orders/{sales_order_id}/eligible-lines", response_model=ReturnEligibleLinesResponse)
def eligible_return_lines(
    sales_order_id: str,
    user: AuthenticatedUser = Depends(get_authenticated_user),
    container: ServiceContainer = Depends(get_container),
) -> ReturnEligibleLinesResponse:
    return ReturnEligibleLinesResponse.model_validate(
        container.returns.eligible_lines(user, sales_order_id)
    )


@router.post("", response_model=ReturnResponse)
def create_return(
    payload: ReturnCreateRequest,
    user: AuthenticatedUser = Depends(get_authenticated_user),
    container: ServiceContainer = Depends(get_container),
) -> ReturnResponse:
    return ReturnResponse.model_validate(
        container.returns.create_return(
            user,
            sales_order_id=payload.sales_order_id,
            notes=payload.notes,
            refund_status=payload.refund_status,
            lines=[item.model_dump() for item in payload.lines],
        )
    )
