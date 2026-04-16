from fastapi import APIRouter, Depends, Query, Path, status
from fastapi.exceptions import HTTPException

from easy_ecom.api.dependencies import ServiceContainer, get_authenticated_user, get_container, require_module_access
from easy_ecom.api.schemas.commerce import (
    ReturnCreateRequest,
    ReturnEligibleLinesResponse,
    ReturnLookupOrdersResponse,
    ReturnRefundPaymentRequest,
    ReturnResponse,
    ReturnsResponse,
    ReturnUpdateRequest,
)
from easy_ecom.api.schemas.common import ModuleOverviewResponse
from easy_ecom.domain.models.auth import AuthenticatedUser

router = APIRouter(
    prefix="/returns",
    tags=["returns"],
    dependencies=[Depends(require_module_access("Returns"))],
)


@router.get("/overview", response_model=ModuleOverviewResponse)
def returns_overview(
    user: AuthenticatedUser = Depends(get_authenticated_user),
    container: ServiceContainer = Depends(get_container),
) -> ModuleOverviewResponse:
    return container.overview.returns(user)


@router.get("", response_model=ReturnsResponse)
def list_returns(
    q: str = Query(default=""),
    user: AuthenticatedUser = Depends(get_authenticated_user),
    container: ServiceContainer = Depends(get_container),
) -> ReturnsResponse:
    return ReturnsResponse(items=container.returns.list_returns(user, query=q))


@router.get("/{return_id}", response_model=ReturnResponse)
def get_return(
    return_id: str = Path(..., description="The return ID"),
    user: AuthenticatedUser = Depends(get_authenticated_user),
    container: ServiceContainer = Depends(get_container),
) -> ReturnResponse:
    """Get a specific return by ID."""
    return_record = container.returns.get_return(user, return_id)
    if not return_record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Return not found"
        )
    return ReturnResponse.model_validate(return_record)


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
    """Create a new return."""
    return ReturnResponse.model_validate(
        container.returns.create_return(
            user,
            sales_order_id=payload.sales_order_id,
            notes=payload.notes,
            refund_status=payload.refund_status,
            lines=[item.model_dump() for item in payload.lines],
        )
    )


@router.put("/{return_id}", response_model=ReturnResponse)
def update_return(
    return_id: str = Path(..., description="The return ID"),
    payload: ReturnUpdateRequest = None,
    user: AuthenticatedUser = Depends(get_authenticated_user),
    container: ServiceContainer = Depends(get_container),
) -> ReturnResponse:
    """Update an existing return (e.g., refund status, notes)."""
    return_record = container.returns.update_return(user, return_id, payload)
    if not return_record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Return not found"
        )
    return ReturnResponse.model_validate(return_record)


@router.post("/{return_id}/record-refund", response_model=ReturnResponse)
def record_refund(
    return_id: str = Path(..., description="The return ID"),
    payload: ReturnRefundPaymentRequest = None,
    user: AuthenticatedUser = Depends(get_authenticated_user),
    container: ServiceContainer = Depends(get_container),
) -> ReturnResponse:
    return_record = container.returns.record_refund_payment(
        user,
        return_id=return_id,
        refund_date=payload.refund_date,
        amount=payload.amount,
        method=payload.method,
        reference=payload.reference,
        note=payload.note,
    )
    if not return_record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Return not found"
        )
    return ReturnResponse.model_validate(return_record)
