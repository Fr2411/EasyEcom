from __future__ import annotations

import pandas as pd
from fastapi import APIRouter, Depends, HTTPException, Query

from easy_ecom.api.dependencies import (
    RequestUser,
    ServiceContainer,
    get_container,
    get_current_user,
    require_page_access,
)
from easy_ecom.api.schemas.inventory import (
    InventoryAddRequest,
    InventoryAddResponse,
    InventoryAdjustmentRequest,
    InventoryAdjustmentResponse,
    InventoryDetailResponse,
    InventoryItemSummary,
    InventoryListResponse,
    InventoryMovement,
    InventoryMovementsResponse,
)

router = APIRouter(prefix="/inventory", tags=["inventory"])


INBOUND_TYPES = {"IN", "ADJUST+", "ADJUST"}


def _safe_float(value: object, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _build_movement_rows(container: ServiceContainer, client_id: str) -> pd.DataFrame:
    movements = container.inventory.reconciliation.normalized_inventory_rows(client_id)
    if movements.empty:
        return movements

    d = movements.copy()
    d["timestamp"] = d.get("timestamp", "").astype(str)
    d["txn_type"] = d.get("txn_type", "").astype(str)
    d["qty"] = pd.to_numeric(d.get("qty", 0), errors="coerce").fillna(0.0)
    d["signed_qty"] = d.apply(
        lambda row: row["qty"] if row["txn_type"] in INBOUND_TYPES else -row["qty"], axis=1
    )
    d["item_id"] = d.get("inventory_product_id", "").astype(str)
    d["item_name"] = d.get("inventory_product_name", "").astype(str)
    d["parent_product_id"] = d.get("parent_product_id", "").astype(str)
    d["parent_product_name"] = d.get("parent_product_name", "").astype(str)

    d = d.sort_values(["item_id", "timestamp", "txn_id"]).reset_index(drop=True)
    d["resulting_balance"] = d.groupby("item_id")["signed_qty"].cumsum()
    return d


def _item_type(row: pd.Series) -> str:
    variant_id = str(row.get("variant_id", "")).strip()
    if str(row.get("is_unmapped", "")).lower() == "true":
        return "unmapped"
    return "variant" if variant_id else "product"


def _build_inventory_items(container: ServiceContainer, client_id: str) -> list[InventoryItemSummary]:
    stock_rows = container.inventory.stock_by_lot_with_issues(client_id)
    if stock_rows.empty:
        return []

    d = stock_rows.copy()
    d["qty"] = pd.to_numeric(d.get("qty", 0), errors="coerce").fillna(0.0)
    d["unit_cost"] = pd.to_numeric(d.get("unit_cost", 0), errors="coerce").fillna(0.0)
    d["stock_value"] = d["qty"] * d["unit_cost"]

    grouped = d.groupby(
        [
            "product_id",
            "product_name",
            "parent_product_id",
            "parent_product_name",
            "variant_id",
            "is_unmapped",
        ],
        as_index=False,
    ).agg(
        available_qty=("qty", "sum"),
        stock_value=("stock_value", "sum"),
        lot_count=("lot_id", "nunique"),
    )

    items: list[InventoryItemSummary] = []
    for _, row in grouped.iterrows():
        qty = float(row["available_qty"])
        value = float(row["stock_value"])
        avg_cost = value / qty if qty > 0 else 0.0
        items.append(
            InventoryItemSummary(
                item_id=str(row["product_id"]),
                item_name=str(row["product_name"]),
                parent_product_id=str(row.get("parent_product_id", "") or ""),
                parent_product_name=str(row.get("parent_product_name", "") or ""),
                item_type=_item_type(row),
                available_qty=qty,
                avg_unit_cost=avg_cost,
                stock_value=value,
                lot_count=int(row["lot_count"]),
                low_stock=qty <= 5,
            )
        )
    return sorted(items, key=lambda item: (item.low_stock is False, item.item_name.lower()))


def _validate_inventory_item(container: ServiceContainer, client_id: str, item_id: str) -> tuple[str, str]:
    item_id = item_id.strip()
    if not item_id:
        raise HTTPException(status_code=400, detail="item_id is required")

    variants = container.products.list_variants_by_client(client_id)
    if not variants.empty:
        scoped = variants[variants["variant_id"].astype(str) == item_id]
        if not scoped.empty:
            row = scoped.iloc[0]
            return str(row["variant_id"]), str(row.get("variant_name", row["variant_id"]))

    products = container.products.list_by_client(client_id)
    if not products.empty:
        scoped = products[products["product_id"].astype(str) == item_id]
        if not scoped.empty:
            row = scoped.iloc[0]
            return str(row["product_id"]), str(row.get("product_name", row["product_id"]))

    raise HTTPException(status_code=404, detail="Inventory item not found for tenant")


def _movements_response(d: pd.DataFrame) -> list[InventoryMovement]:
    items: list[InventoryMovement] = []
    if d.empty:
        return items
    for _, row in d.iterrows():
        items.append(
            InventoryMovement(
                txn_id=str(row.get("txn_id", "")),
                timestamp=str(row.get("timestamp", "")),
                item_id=str(row.get("item_id", "")),
                item_name=str(row.get("item_name", "")),
                parent_product_id=str(row.get("parent_product_id", "") or ""),
                parent_product_name=str(row.get("parent_product_name", "") or ""),
                movement_type=str(row.get("txn_type", "")),
                qty_delta=float(row.get("signed_qty", 0.0)),
                source_type=str(row.get("source_type", "") or ""),
                source_id=str(row.get("source_id", "") or ""),
                note=str(row.get("note", "") or ""),
                lot_id=str(row.get("lot_id", "") or ""),
                resulting_balance=_safe_float(row.get("resulting_balance"), 0.0),
            )
        )
    return items


@router.get("", response_model=InventoryListResponse)
def list_inventory(
    q: str = Query(default="", max_length=100),
    user: RequestUser = Depends(get_current_user),
    container: ServiceContainer = Depends(get_container),
) -> InventoryListResponse:
    require_page_access(user, "Catalog & Stock")
    items = _build_inventory_items(container, user.client_id)
    if q.strip():
        needle = q.strip().lower()
        items = [
            item
            for item in items
            if needle in item.item_name.lower()
            or needle in item.item_id.lower()
            or needle in item.parent_product_name.lower()
        ]
    return InventoryListResponse(items=items)


@router.get("/movements", response_model=InventoryMovementsResponse)
def list_movements(
    item_id: str = Query(default="", max_length=64),
    movement_type: str = Query(default="", max_length=20),
    start_date: str = Query(default="", max_length=30),
    end_date: str = Query(default="", max_length=30),
    limit: int = Query(default=100, ge=1, le=500),
    user: RequestUser = Depends(get_current_user),
    container: ServiceContainer = Depends(get_container),
) -> InventoryMovementsResponse:
    require_page_access(user, "Catalog & Stock")
    d = _build_movement_rows(container, user.client_id)
    if d.empty:
        return InventoryMovementsResponse(items=[])

    if item_id.strip():
        d = d[d["item_id"] == item_id.strip()]
    if movement_type.strip():
        d = d[d["txn_type"].str.upper() == movement_type.strip().upper()]
    if start_date.strip():
        d = d[d["timestamp"] >= start_date.strip()]
    if end_date.strip():
        d = d[d["timestamp"] <= end_date.strip()]

    d = d.sort_values(["timestamp", "txn_id"], ascending=False).head(limit)
    return InventoryMovementsResponse(items=_movements_response(d))


@router.get("/{item_id}", response_model=InventoryDetailResponse)
def inventory_detail(
    item_id: str,
    user: RequestUser = Depends(get_current_user),
    container: ServiceContainer = Depends(get_container),
) -> InventoryDetailResponse:
    require_page_access(user, "Catalog & Stock")
    items = _build_inventory_items(container, user.client_id)
    item = next((entry for entry in items if entry.item_id == item_id), None)
    if item is None:
        raise HTTPException(status_code=404, detail="Inventory item not found")

    d = _build_movement_rows(container, user.client_id)
    recent = d[d["item_id"] == item_id].sort_values(["timestamp", "txn_id"], ascending=False).head(20)
    return InventoryDetailResponse(item=item, recent_movements=_movements_response(recent))


@router.post("/adjustments", response_model=InventoryAdjustmentResponse, status_code=201)
def create_adjustment(
    payload: InventoryAdjustmentRequest,
    user: RequestUser = Depends(get_current_user),
    container: ServiceContainer = Depends(get_container),
) -> InventoryAdjustmentResponse:
    require_page_access(user, "Catalog & Stock")
    item_id, item_name = _validate_inventory_item(container, user.client_id, payload.item_id)

    stock_rows = container.inventory.stock_by_lot_with_issues(user.client_id)
    scoped = stock_rows[stock_rows["product_id"].astype(str) == item_id] if not stock_rows.empty else pd.DataFrame()
    avg_unit_cost = (
        float((pd.to_numeric(scoped["qty"], errors="coerce").fillna(0.0) * pd.to_numeric(scoped["unit_cost"], errors="coerce").fillna(0.0)).sum() / pd.to_numeric(scoped["qty"], errors="coerce").fillna(0.0).sum())
        if not scoped.empty and float(pd.to_numeric(scoped["qty"], errors="coerce").fillna(0.0).sum()) > 0
        else 0.0
    )

    note_parts = [part for part in [payload.reason.strip(), payload.note.strip()] if part]
    note = " | ".join(note_parts)
    source_id = payload.reference.strip()
    if not source_id:
        source_id = f"manual-{user.user_id}"

    lot_ids: list[str] = []
    before_ids = set(container.inventory.repo.all().get("txn_id", pd.Series(dtype=str)).astype(str).tolist())

    try:
        if payload.adjustment_type == "stock_in":
            unit_cost = payload.unit_cost if payload.unit_cost is not None else avg_unit_cost
            if unit_cost <= 0:
                raise HTTPException(status_code=400, detail="unit_cost is required for stock-in when no historical cost exists")
            qty = float(payload.quantity or 0)
            lot_ids.append(
                container.inventory.add_stock(
                    client_id=user.client_id,
                    product_id=item_id,
                    product_name=item_name,
                    qty=qty,
                    unit_cost=unit_cost,
                    supplier_snapshot="",
                    note=note,
                    source_type="manual_stock_in",
                    source_id=source_id,
                    user_id=user.user_id,
                )
            )
            applied_delta = qty
        elif payload.adjustment_type == "stock_out":
            qty = float(payload.quantity or 0)
            container.inventory.deduct_stock(
                client_id=user.client_id,
                product_id=item_id,
                qty=qty,
                source_type="manual_stock_out",
                source_id=source_id,
                note=note,
                user_id=user.user_id,
            )
            applied_delta = -qty
        else:
            delta = float(payload.quantity_delta or 0)
            if delta > 0:
                unit_cost = payload.unit_cost if payload.unit_cost is not None else avg_unit_cost
                if unit_cost <= 0:
                    raise HTTPException(status_code=400, detail="unit_cost is required for positive correction when no historical cost exists")
                lot_ids.append(
                    container.inventory.add_stock(
                        client_id=user.client_id,
                        product_id=item_id,
                        product_name=item_name,
                        qty=delta,
                        unit_cost=unit_cost,
                        supplier_snapshot="",
                        note=note,
                        source_type="manual_correction",
                        source_id=source_id,
                        user_id=user.user_id,
                    )
                )
            else:
                container.inventory.deduct_stock(
                    client_id=user.client_id,
                    product_id=item_id,
                    qty=abs(delta),
                    source_type="manual_correction",
                    source_id=source_id,
                    note=note,
                    user_id=user.user_id,
                )
            applied_delta = delta
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    after = container.inventory.repo.all()
    movement_ids = [
        str(txn_id)
        for txn_id in after.get("txn_id", pd.Series(dtype=str)).astype(str).tolist()
        if txn_id not in before_ids
    ]

    return InventoryAdjustmentResponse(
        success=True,
        item_id=item_id,
        adjustment_type=payload.adjustment_type,
        applied_qty_delta=applied_delta,
        lot_ids=lot_ids,
        movement_ids=movement_ids,
    )


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
