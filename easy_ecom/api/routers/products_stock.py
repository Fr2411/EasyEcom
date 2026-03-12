from __future__ import annotations

import json

import pandas as pd
from fastapi import APIRouter, Depends, HTTPException

from easy_ecom.api.dependencies import (
    RequestUser,
    ServiceContainer,
    get_container,
    get_current_user,
    require_page_access,
)
from easy_ecom.api.schemas.products_stock import (
    ProductRecord,
    ProductsStockSnapshotResponse,
    SaveProductResponse,
    SaveProductsStockRequest,
    VariantRecord,
)
from easy_ecom.domain.services.catalog_stock_service import VariantWorkspaceEntry

router = APIRouter(prefix="/products-stock", tags=["products-stock"])


def _parse_features(raw_features: object) -> list[str]:
    if raw_features is None:
        return []
    text = str(raw_features).strip()
    if not text or text == "{}":
        return []
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        return [text]
    if isinstance(parsed, dict):
        features = parsed.get("features", [])
        if isinstance(features, list):
            return [str(item).strip() for item in features if str(item).strip()]
    return []


def _variant_stock_rollup(stock_rows: pd.DataFrame) -> dict[str, tuple[float, float]]:
    if stock_rows.empty:
        return {}
    scoped = stock_rows.copy()
    scoped["variant_id"] = scoped["variant_id"].astype(str)
    scoped = scoped[scoped["variant_id"].str.strip() != ""]
    if scoped.empty:
        return {}
    scoped["qty"] = pd.to_numeric(scoped["qty"], errors="coerce").fillna(0.0)
    scoped["unit_cost"] = pd.to_numeric(scoped["unit_cost"], errors="coerce").fillna(0.0)
    scoped["stock_value"] = scoped["qty"] * scoped["unit_cost"]
    grouped = scoped.groupby("variant_id", as_index=False).agg(qty=("qty", "sum"), stock_value=("stock_value", "sum"))
    return {
        str(row["variant_id"]): (
            float(row["qty"]),
            float(row["stock_value"] / row["qty"]) if float(row["qty"]) > 0 else 0.0,
        )
        for _, row in grouped.iterrows()
    }


@router.get("/snapshot", response_model=ProductsStockSnapshotResponse)
def products_stock_snapshot(
    user: RequestUser = Depends(get_current_user),
    container: ServiceContainer = Depends(get_container),
) -> ProductsStockSnapshotResponse:
    require_page_access(user, "Catalog & Stock")

    products_df = container.products.list_by_client(user.client_id)
    variants_df = container.products.list_variants_by_client(user.client_id)
    stock_df = container.inventory.stock_by_lot_with_issues(user.client_id)
    stock_by_variant = _variant_stock_rollup(stock_df)

    records: list[ProductRecord] = []
    for _, product in products_df.iterrows():
        product_id = str(product.get("product_id", "")).strip()
        scoped_variants = variants_df[variants_df["parent_product_id"].astype(str) == product_id] if not variants_df.empty else pd.DataFrame()
        variant_rows: list[VariantRecord] = []
        for _, variant in scoped_variants.iterrows():
            variant_id = str(variant.get("variant_id", "")).strip()
            if not variant_id:
                continue
            qty, cost = stock_by_variant.get(variant_id, (0.0, 0.0))
            variant_rows.append(
                VariantRecord(
                    id=variant_id,
                    size=str(variant.get("size", "") or ""),
                    color=str(variant.get("color", "") or ""),
                    other=str(variant.get("other", "") or ""),
                    qty=qty,
                    cost=cost,
                    defaultSellingPrice=float(variant.get("default_selling_price", 0) or 0),
                    maxDiscountPct=float(variant.get("max_discount_pct", 0) or 0),
                )
            )
        records.append(
            ProductRecord(
                id=product_id,
                identity={
                    "productName": str(product.get("product_name", "")),
                    "supplier": str(product.get("supplier", "")),
                    "category": str(product.get("category", "")) or "General",
                    "description": str(product.get("prd_description", "")),
                    "features": _parse_features(product.get("prd_features_json", "")),
                },
                variants=variant_rows,
            )
        )

    return ProductsStockSnapshotResponse(
        products=records,
        suppliers=container.catalog_stock.list_supplier_options(user.client_id),
        categories=container.catalog_stock.list_category_options(user.client_id),
    )


@router.post("/save", response_model=SaveProductResponse)
def save_products_stock(
    payload: SaveProductsStockRequest,
    user: RequestUser = Depends(get_current_user),
    container: ServiceContainer = Depends(get_container),
) -> SaveProductResponse:
    require_page_access(user, "Catalog & Stock")
    try:
        entries = [
            VariantWorkspaceEntry(
                variant_id=variant.id,
                size=variant.size,
                color=variant.color,
                other=variant.other,
                qty=variant.qty,
                unit_cost=variant.cost,
                default_selling_price=variant.defaultSellingPrice,
                max_discount_pct=variant.maxDiscountPct,
                supplier=payload.identity.supplier,
            )
            for variant in payload.variants
        ]
        container.catalog_stock.save_workspace(
            client_id=user.client_id,
            user_id=user.user_id,
            typed_product_name=payload.identity.productName,
            supplier=payload.identity.supplier,
            category=payload.identity.category,
            description=payload.identity.description,
            features_text="\n".join(payload.identity.features),
            default_selling_price=0,
            max_discount_pct=0,
            variant_entries=entries,
            selected_product_id=payload.selectedProductId or "",
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return SaveProductResponse(success=True)
