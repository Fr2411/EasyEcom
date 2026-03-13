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
from easy_ecom.api.schemas.catalog import (
    CatalogProductRecord,
    CatalogProductRequest,
    CatalogProductsResponse,
    CatalogSaveResponse,
    CatalogVariantRecord,
)
from easy_ecom.domain.services.catalog_stock_service import VariantWorkspaceEntry

router = APIRouter(prefix="/catalog", tags=["catalog"])


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


def _catalog_product_record(
    product: pd.Series,
    variants_df: pd.DataFrame,
) -> CatalogProductRecord:
    product_id = str(product.get("product_id", "")).strip()
    scoped_variants = (
        variants_df[variants_df["parent_product_id"].astype(str) == product_id]
        if not variants_df.empty
        else pd.DataFrame()
    )
    variants = [
        CatalogVariantRecord(
            variant_id=str(variant.get("variant_id", "") or ""),
            size=str(variant.get("size", "") or ""),
            color=str(variant.get("color", "") or ""),
            other=str(variant.get("other", "") or ""),
            defaultSellingPrice=float(variant.get("default_selling_price", 0) or 0),
            maxDiscountPct=float(variant.get("max_discount_pct", 0) or 0),
        )
        for _, variant in scoped_variants.iterrows()
        if str(variant.get("variant_id", "")).strip()
    ]
    return CatalogProductRecord(
        product_id=product_id,
        identity={
            "productName": str(product.get("product_name", "")),
            "supplier": str(product.get("supplier", "")),
            "category": str(product.get("category", "")) or "General",
            "description": str(product.get("prd_description", "")),
            "features": _parse_features(product.get("prd_features_json", "")),
        },
        variants=variants,
    )


def _to_workspace_entry(variant: CatalogVariantRecord) -> VariantWorkspaceEntry:
    return VariantWorkspaceEntry(
        variant_id=str(variant.variant_id or "").strip(),
        size=str(variant.size or "").strip(),
        color=str(variant.color or "").strip(),
        other=str(variant.other or "").strip(),
        qty=0.0,
        unit_cost=0.0,
        default_selling_price=float(variant.defaultSellingPrice),
        max_discount_pct=float(variant.maxDiscountPct),
    )


@router.get("/products", response_model=CatalogProductsResponse)
def list_catalog_products(
    user: RequestUser = Depends(get_current_user),
    container: ServiceContainer = Depends(get_container),
) -> CatalogProductsResponse:
    require_page_access(user, "Catalog & Stock")
    products_df = container.products.list_by_client(user.client_id)
    variants_df = container.products.list_variants_by_client(user.client_id)
    records = [_catalog_product_record(product, variants_df) for _, product in products_df.iterrows()]
    return CatalogProductsResponse(
        products=records,
        suppliers=container.catalog_stock.list_supplier_options(user.client_id),
        categories=container.catalog_stock.list_category_options(user.client_id),
    )


@router.get("/products/{product_id}", response_model=CatalogProductRecord)
def get_catalog_product(
    product_id: str,
    user: RequestUser = Depends(get_current_user),
    container: ServiceContainer = Depends(get_container),
) -> CatalogProductRecord:
    require_page_access(user, "Catalog & Stock")
    products_df = container.products.list_by_client(user.client_id)
    scoped = products_df[products_df["product_id"].astype(str) == product_id]
    if scoped.empty:
        raise HTTPException(status_code=404, detail="Product not found")
    variants_df = container.products.list_variants_by_client(user.client_id)
    return _catalog_product_record(scoped.iloc[0], variants_df)


@router.post("/products", response_model=CatalogSaveResponse, status_code=201)
def create_catalog_product(
    payload: CatalogProductRequest,
    user: RequestUser = Depends(get_current_user),
    container: ServiceContainer = Depends(get_container),
) -> CatalogSaveResponse:
    require_page_access(user, "Catalog & Stock")
    try:
        product_id, _, variant_count = container.catalog_stock.save_workspace(
            client_id=user.client_id,
            user_id=user.user_id,
            typed_product_name=payload.identity.productName,
            supplier=payload.identity.supplier,
            category=payload.identity.category,
            description=payload.identity.description,
            features_text="\n".join(payload.identity.features),
            variant_entries=[_to_workspace_entry(variant) for variant in payload.variants],
            operation="create",
            post_stock=False,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return CatalogSaveResponse(product_id=product_id, variant_count=variant_count)


@router.patch("/products/{product_id}", response_model=CatalogSaveResponse)
def update_catalog_product(
    product_id: str,
    payload: CatalogProductRequest,
    user: RequestUser = Depends(get_current_user),
    container: ServiceContainer = Depends(get_container),
) -> CatalogSaveResponse:
    require_page_access(user, "Catalog & Stock")
    try:
        saved_product_id, _, variant_count = container.catalog_stock.save_workspace(
            client_id=user.client_id,
            user_id=user.user_id,
            typed_product_name=payload.identity.productName,
            supplier=payload.identity.supplier,
            category=payload.identity.category,
            description=payload.identity.description,
            features_text="\n".join(payload.identity.features),
            variant_entries=[_to_workspace_entry(variant) for variant in payload.variants],
            selected_product_id=product_id,
            operation="update",
            post_stock=False,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return CatalogSaveResponse(product_id=saved_product_id, variant_count=variant_count)
