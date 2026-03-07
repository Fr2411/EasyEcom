from fastapi import APIRouter, Depends

from easy_ecom.api.dependencies import (
    RequestUser,
    ServiceContainer,
    get_container,
    get_current_user,
    require_page_access,
)
from easy_ecom.api.schemas.products import ProductUpsertRequest, ProductUpsertResponse, StockExplorerResponse
from easy_ecom.domain.services.catalog_stock_service import VariantWorkspaceEntry

router = APIRouter(prefix="/products-stock", tags=["products-stock"])


@router.get("/snapshot", response_model=StockExplorerResponse)
def products_stock_snapshot(
    user: RequestUser = Depends(get_current_user),
    container: ServiceContainer = Depends(get_container),
) -> StockExplorerResponse:
    require_page_access(user, "Catalog & Stock")
    summary, detail = container.catalog_stock.stock_explorer(user.client_id)
    return StockExplorerResponse(
        summary=summary.to_dict(orient="records"),
        detail={k: v.to_dict(orient="records") for k, v in detail.items()},
    )


@router.post("/save", response_model=ProductUpsertResponse)
def save_products_stock(
    payload: ProductUpsertRequest,
    user: RequestUser = Depends(get_current_user),
    container: ServiceContainer = Depends(get_container),
) -> ProductUpsertResponse:
    require_page_access(user, "Catalog & Stock")
    entries = [
        VariantWorkspaceEntry(
            variant_id=row.variant_id,
            variant_label=row.variant_label,
            size=row.size,
            color=row.color,
            other=row.other,
            qty=row.qty,
            unit_cost=row.unit_cost,
            default_selling_price=row.default_selling_price,
            max_discount_pct=row.max_discount_pct,
        )
        for row in payload.variant_entries
    ]
    product_id, lot_ids, variant_upserts = container.catalog_stock.save_workspace(
        client_id=user.client_id,
        user_id=user.user_id,
        typed_product_name=payload.typed_product_name,
        supplier=payload.supplier,
        category=payload.category,
        description=payload.description,
        features_text=payload.features_text,
        default_selling_price=payload.default_selling_price,
        max_discount_pct=payload.max_discount_pct,
        variant_entries=entries,
        selected_product_id=payload.selected_product_id,
    )
    return ProductUpsertResponse(
        product_id=product_id,
        lot_ids=lot_ids,
        variant_upserts=variant_upserts,
    )
