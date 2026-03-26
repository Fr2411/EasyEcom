from fastapi import APIRouter, Depends, Query, Body, Path, status
from fastapi.responses import JSONResponse
from typing import Optional, List

from easy_ecom.api.dependencies import ServiceContainer, get_authenticated_user, get_container, require_page_access
from easy_ecom.api.schemas.common import ModuleOverviewResponse
from easy_ecom.api.schemas.commerce import (
    PurchaseListItemResponse,
    PurchaseDetailResponse,
    PurchaseCreateRequest,
    PurchaseUpdateRequest,
    PurchaseLookupProductResponse,
    PurchaseLookupSupplierResponse,
    PurchaseOrdersResponse,
)
from easy_ecom.domain.models.auth import AuthenticatedUser

router = APIRouter(prefix="/purchases", tags=["purchases"])


@router.get("/overview", response_model=ModuleOverviewResponse)
def purchases_overview(
    user: AuthenticatedUser = Depends(get_authenticated_user),
    container: ServiceContainer = Depends(get_container),
) -> ModuleOverviewResponse:
    require_page_access(user, "Purchases")
    return container.overview.purchases(user)


@router.get("/orders", response_model=PurchaseOrdersResponse)
def list_purchase_orders(
    status: Optional[str] = Query(default=None),
    q: str = Query(default=""),
    user: AuthenticatedUser = Depends(get_authenticated_user),
    container: ServiceContainer = Depends(get_container),
) -> PurchaseOrdersResponse:
    return PurchaseOrdersResponse(
        items=container.inventory.list_purchase_orders(user, status=status, query=q)
    )


@router.get("/orders/{purchase_order_id}", response_model=PurchaseDetailResponse)
def get_purchase_order(
    purchase_order_id: str = Path(..., description="The ID of the purchase order"),
    user: AuthenticatedUser = Depends(get_authenticated_user),
    container: ServiceContainer = Depends(get_container),
) -> PurchaseDetailResponse:
    return PurchaseDetailResponse.model_validate(container.inventory.get_purchase_order(user, purchase_order_id))


@router.get("/variants/search", response_model=List[PurchaseLookupProductResponse])
def search_purchase_variants(
    q: str = Query(default=""),
    location_id: Optional[str] = Query(default=None),
    user: AuthenticatedUser = Depends(get_authenticated_user),
    container: ServiceContainer = Depends(get_container),
) -> List[PurchaseLookupProductResponse]:
    return container.inventory.lookup_purchase_variants(user, query=q, location_id=location_id)


@router.get("/vendors/search", response_model=List[PurchaseLookupSupplierResponse])
def search_purchase_vendors(
    q: str = Query(default=""),
    user: AuthenticatedUser = Depends(get_authenticated_user),
    container: ServiceContainer = Depends(get_container),
) -> List[PurchaseLookupSupplierResponse]:
    return container.inventory.lookup_purchase_suppliers(user, query=q)


@router.post("/orders", response_model=PurchaseDetailResponse, status_code=status.HTTP_201_CREATED)
def create_purchase_order(
    payload: PurchaseCreateRequest = Body(...),
    user: AuthenticatedUser = Depends(get_authenticated_user),
    container: ServiceContainer = Depends(get_container),
) -> PurchaseDetailResponse:
    return PurchaseDetailResponse.model_validate(
        container.inventory.create_purchase_order(
            user,
            purchase_date=payload.purchase_date,
            supplier_id=payload.supplier_id,
            reference_no=payload.reference_no,
            note=payload.note,
            payment_status=payload.payment_status,
            lines=payload.lines,
        )
    )


@router.put("/orders/{purchase_order_id}", response_model=PurchaseDetailResponse)
def update_purchase_order(
    purchase_order_id: str = Path(..., description="The ID of the purchase order"),
    payload: PurchaseUpdateRequest = Body(...),
    user: AuthenticatedUser = Depends(get_authenticated_user),
    container: ServiceContainer = Depends(get_container),
) -> PurchaseDetailResponse:
    return PurchaseDetailResponse.model_validate(
        container.inventory.update_purchase_order(
            user,
            purchase_order_id=purchase_order_id,
            purchase_date=payload.purchase_date,
            supplier_id=payload.supplier_id,
            reference_no=payload.reference_no,
            note=payload.note,
            payment_status=payload.payment_status,
            lines=payload.lines,
        )
    )


@router.post("/orders/{purchase_order_id}/receive", response_model=PurchaseDetailResponse)
def receive_purchase_order(
    purchase_order_id: str = Path(..., description="The ID of the purchase order to receive"),
    user: AuthenticatedUser = Depends(get_authenticated_user),
    container: ServiceContainer = Depends(get_container),
) -> PurchaseDetailResponse:
    return PurchaseDetailResponse.model_validate(
        container.inventory.receive_purchase_order(user, purchase_order_id=purchase_order_id)
    )


@router.post("/orders/{purchase_order_id}/cancel", response_model=PurchaseDetailResponse)
def cancel_purchase_order(
    purchase_order_id: str = Path(..., description="The ID of the purchase order to cancel"),
    payload: dict = Body(default={}),  # We can use a simple dict for notes if needed
    user: AuthenticatedUser = Depends(get_authenticated_user),
    container: ServiceContainer = Depends(get_container),
) -> PurchaseDetailResponse:
    notes = payload.get("notes", "") if isinstance(payload, dict) else ""
    return PurchaseDetailResponse.model_validate(
        container.inventory.cancel_purchase_order(user, purchase_order_id=purchase_order_id, notes=notes)
    )