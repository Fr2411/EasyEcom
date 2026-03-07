from fastapi import APIRouter, Depends

from easy_ecom.api.dependencies import (
    RequestUser,
    ServiceContainer,
    get_container,
    get_current_user,
    require_page_access,
)
from easy_ecom.api.schemas.sales import SalesCreateRequest, SalesCreateResponse
from easy_ecom.domain.models.sales import SaleConfirm, SaleItem

router = APIRouter(prefix="/sales", tags=["sales"])


@router.post("/create", response_model=SalesCreateResponse)
def create_sale(
    payload: SalesCreateRequest,
    user: RequestUser = Depends(get_current_user),
    container: ServiceContainer = Depends(get_container),
) -> SalesCreateResponse:
    require_page_access(user, "Sales")
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
    return SalesCreateResponse(
        order_id=result.get("order_id", ""),
        invoice_id=result.get("invoice_id", ""),
        status=result.get("order_status", "confirmed"),
    )
