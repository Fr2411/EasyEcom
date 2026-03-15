from fastapi import APIRouter, Depends, Query

from easy_ecom.api.dependencies import ServiceContainer, get_authenticated_user, get_container, require_page_access
from easy_ecom.api.schemas.commerce import (
    InventoryAdjustmentRequest,
    InventoryIntakeLookupResponse,
    InventoryStockRowResponse,
    InventoryWorkspaceResponse,
    PurchaseReceiptResponse,
    ReceiveStockRequest,
)
from easy_ecom.api.schemas.common import ModuleOverviewResponse
from easy_ecom.domain.models.auth import AuthenticatedUser

router = APIRouter(prefix="/inventory", tags=["inventory"])


@router.get("/overview", response_model=ModuleOverviewResponse)
def inventory_overview(
    user: AuthenticatedUser = Depends(get_authenticated_user),
    container: ServiceContainer = Depends(get_container),
) -> ModuleOverviewResponse:
    require_page_access(user, "Inventory")
    return container.overview.inventory(user)


@router.get("/workspace", response_model=InventoryWorkspaceResponse)
def inventory_workspace(
    q: str = Query(default=""),
    location_id: str | None = Query(default=None),
    user: AuthenticatedUser = Depends(get_authenticated_user),
    container: ServiceContainer = Depends(get_container),
) -> InventoryWorkspaceResponse:
    return InventoryWorkspaceResponse.model_validate(
        container.inventory.workspace(user, query=q, location_id=location_id)
    )


@router.get("/intake/lookup", response_model=InventoryIntakeLookupResponse)
def inventory_intake_lookup(
    q: str = Query(default=""),
    location_id: str | None = Query(default=None),
    user: AuthenticatedUser = Depends(get_authenticated_user),
    container: ServiceContainer = Depends(get_container),
) -> InventoryIntakeLookupResponse:
    return InventoryIntakeLookupResponse.model_validate(
        container.inventory.intake_lookup(user, query=q, location_id=location_id)
    )


@router.get("/low-stock", response_model=list[InventoryStockRowResponse])
def low_stock(
    location_id: str | None = Query(default=None),
    user: AuthenticatedUser = Depends(get_authenticated_user),
    container: ServiceContainer = Depends(get_container),
) -> list[InventoryStockRowResponse]:
    workspace = container.inventory.workspace(user, query="", location_id=location_id)
    return [InventoryStockRowResponse.model_validate(item) for item in workspace["low_stock_items"]]


@router.post("/receipts", response_model=PurchaseReceiptResponse)
def receive_stock(
    payload: ReceiveStockRequest,
    user: AuthenticatedUser = Depends(get_authenticated_user),
    container: ServiceContainer = Depends(get_container),
) -> PurchaseReceiptResponse:
    return PurchaseReceiptResponse.model_validate(
        container.inventory.receive_stock(
            user,
            action=payload.action,
            location_id=payload.location_id,
            notes=payload.notes,
            update_matched_product_details=payload.update_matched_product_details,
            identity=payload.identity.model_dump(),
            lines=[item.model_dump() for item in payload.lines],
        )
    )


@router.post("/adjustments", response_model=InventoryStockRowResponse)
def adjust_stock(
    payload: InventoryAdjustmentRequest,
    user: AuthenticatedUser = Depends(get_authenticated_user),
    container: ServiceContainer = Depends(get_container),
) -> InventoryStockRowResponse:
    return InventoryStockRowResponse.model_validate(
        container.inventory.adjust_stock(
            user,
            location_id=payload.location_id,
            variant_id=payload.variant_id,
            quantity_delta=payload.quantity_delta,
            reason=payload.reason,
            notes=payload.notes,
        )
    )
