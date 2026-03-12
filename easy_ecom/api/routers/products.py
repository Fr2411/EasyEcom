from fastapi import APIRouter, Depends, HTTPException

from easy_ecom.api.dependencies import (
    RequestUser,
    ServiceContainer,
    get_container,
    get_current_user,
    require_page_access,
)
from easy_ecom.api.schemas.products import (
    ProductDetailResponse,
    ProductSearchItem,
    ProductUpsertRequest,
    ProductUpsertResponse,
    StockExplorerResponse,
)
from easy_ecom.domain.services.catalog_stock_service import VariantWorkspaceEntry

router = APIRouter(tags=["products"])


@router.get("/products/search", response_model=list[ProductSearchItem])
def search_products(
    q: str = "",
    user: RequestUser = Depends(get_current_user),
    container: ServiceContainer = Depends(get_container),
) -> list[ProductSearchItem]:
    require_page_access(user, "Catalog & Stock")
    rows = container.catalog_stock.suggest_products(user.client_id, q)
    return [ProductSearchItem(**row) for row in rows]


@router.get("/products/{product_id}", response_model=ProductDetailResponse)
def get_product(
    product_id: str,
    user: RequestUser = Depends(get_current_user),
    container: ServiceContainer = Depends(get_container),
) -> ProductDetailResponse:
    require_page_access(user, "Catalog & Stock")
    product = container.products.get_by_id(user.client_id, product_id)
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    variants = container.products.list_variants(user.client_id, product_id)
    return ProductDetailResponse(product=product, variants=variants)


@router.post("/products/upsert", response_model=ProductUpsertResponse)
def upsert_product(
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
        variant_entries=entries,
        selected_product_id=payload.selected_product_id,
    )
    return ProductUpsertResponse(
        product_id=product_id,
        lot_ids=lot_ids,
        variant_upserts=variant_upserts,
    )


@router.get("/stock/explorer", response_model=StockExplorerResponse)
def stock_explorer(
    user: RequestUser = Depends(get_current_user),
    container: ServiceContainer = Depends(get_container),
) -> StockExplorerResponse:
    require_page_access(user, "Catalog & Stock")
    summary, detail = container.catalog_stock.stock_explorer(user.client_id)
    return StockExplorerResponse(
        summary=summary.to_dict(orient="records"),
        detail={k: v.to_dict(orient="records") for k, v in detail.items()},
    )
