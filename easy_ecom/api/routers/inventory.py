from fastapi import APIRouter, Depends

from easy_ecom.api.dependencies import (
    RequestUser,
    ServiceContainer,
    get_container,
    get_current_user,
    require_page_access,
)
from easy_ecom.api.schemas.inventory import InventoryAddRequest, InventoryAddResponse

router = APIRouter(prefix="/inventory", tags=["inventory"])


@router.post("/add", response_model=InventoryAddResponse)
def add_inventory(
    payload: InventoryAddRequest,
    user: RequestUser = Depends(get_current_user),
    container: ServiceContainer = Depends(get_container),
) -> InventoryAddResponse:
    require_page_access(user, "Catalog & Stock")
    lot_id = container.inventory.add_stock(
        client_id=user.client_id,
        product_id=payload.product_id,
        product_name=payload.product_name,
        qty=payload.qty,
        unit_cost=payload.unit_cost,
        supplier_snapshot=payload.supplier_snapshot,
        note=payload.note,
        source_type=payload.source_type,
        source_id=payload.source_id,
        user_id=user.user_id,
    )
    return InventoryAddResponse(lot_id=lot_id)
