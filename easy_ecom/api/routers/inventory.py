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
    InventoryInboundCreateRequest,
    InventoryInboundCreateResponse,
    InventoryInboundReceiveRequest,
    InventoryInboundReceiveResponse,
    InventoryItemSummary,
    InventoryListResponse,
    InventoryMovement,
    InventoryMovementsResponse,
)

from easy_ecom.domain.services.stock_policy import ON_HAND_INBOUND_TYPES, stock_deltas

router = APIRouter(prefix="/inventory", tags=["inventory"])


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
    d["txn_type"] = d.get("txn_type", "").astype(str).str.upper()
    d["qty"] = pd.to_numeric(d.get("qty", 0), errors="coerce").fillna(0.0)

    d["signed_qty"] = d.apply(
        lambda row: stock_deltas(str(row["txn_type"]), float(row["qty"])).on_hand,
        axis=1,
    )
    d["item_id"] = d.get("inventory_product_id", "").astype(str)
    d["item_name"] = d.get("inventory_product_name", "").astype(str)
    d["parent_product_id"] = d.get("parent_product_id", "").astype(str)
    d["parent_product_name"] = d.get("parent_product_name", "").astype(str)

    d = d.sort_values(["item_id", "timestamp", "txn_id"]).reset_index(drop=True)
    d["resulting_balance"] = d.groupby("item_id")["signed_qty"].cumsum()
    return d


def _catalog_inventory_base(container: ServiceContainer, client_id: str) -> pd.DataFrame:
    products = container.products.list_by_client(client_id)
    variants = container.products.list_variants_by_client(client_id)

    if products.empty and variants.empty:
        return pd.DataFrame(
            columns=[
                "item_id",
                "item_name",
                "parent_product_id",
                "parent_product_name",
                "variant_id",
                "is_unmapped",
                "item_type",
            ]
        )

    products = products.copy() if not products.empty else pd.DataFrame()
    variants = variants.copy() if not variants.empty else pd.DataFrame()
    if not products.empty:
        products["is_active"] = products.get("is_active", "true").astype(str).str.lower()
        products = products[products["is_active"] != "false"].copy()

    if variants.empty:
        simple = products.copy()
        if simple.empty:
            return pd.DataFrame()
        simple["item_id"] = simple["product_id"].astype(str)
        simple["item_name"] = simple["product_name"].astype(str)
        simple["parent_product_id"] = simple["product_id"].astype(str)
        simple["parent_product_name"] = simple["product_name"].astype(str)
        simple["variant_id"] = ""
        simple["is_unmapped"] = False
        simple["item_type"] = "product"
        return simple[
            [
                "item_id",
                "item_name",
                "parent_product_id",
                "parent_product_name",
                "variant_id",
                "is_unmapped",
                "item_type",
            ]
        ]

    variants["is_active"] = variants.get("is_active", "true").astype(str).str.lower()
    active_variants = variants[variants["is_active"] != "false"].copy()

    variant_items = active_variants.merge(
        products[["product_id", "product_name"]].rename(
            columns={"product_id": "parent_product_id", "product_name": "parent_product_name"}
        ),
        on="parent_product_id",
        how="left",
    )
    variant_items["item_id"] = variant_items["variant_id"].astype(str)
    variant_items["item_name"] = variant_items["variant_name"].astype(str)
    variant_items["item_type"] = "variant"
    variant_items["is_unmapped"] = False

    variant_parent_ids = set(active_variants.get("parent_product_id", pd.Series(dtype=str)).astype(str))
    simple_items = products[~products["product_id"].astype(str).isin(variant_parent_ids)].copy()
    if not simple_items.empty:
        simple_items["item_id"] = simple_items["product_id"].astype(str)
        simple_items["item_name"] = simple_items["product_name"].astype(str)
        simple_items["parent_product_id"] = simple_items["product_id"].astype(str)
        simple_items["parent_product_name"] = simple_items["product_name"].astype(str)
        simple_items["variant_id"] = ""
        simple_items["item_type"] = "product"
        simple_items["is_unmapped"] = False

    base = pd.concat(
        [
            variant_items[
                [
                    "item_id",
                    "item_name",
                    "parent_product_id",
                    "parent_product_name",
                    "variant_id",
                    "is_unmapped",
                    "item_type",
                ]
            ],
            simple_items[
                [
                    "item_id",
                    "item_name",
                    "parent_product_id",
                    "parent_product_name",
                    "variant_id",
                    "is_unmapped",
                    "item_type",
                ]
            ]
            if not simple_items.empty
            else pd.DataFrame(),
        ],
        ignore_index=True,
    )
    return base.drop_duplicates(subset=["item_id"], keep="first")


def _item_type(row: pd.Series) -> str:
    variant_id = str(row.get("variant_id", "")).strip()
    if str(row.get("is_unmapped", "")).lower() == "true":
        return "unmapped"
    return "variant" if variant_id else "product"


def _build_inventory_items(container: ServiceContainer, client_id: str) -> list[InventoryItemSummary]:
    catalog_base = _catalog_inventory_base(container, client_id)
    movements = _build_movement_rows(container, client_id)

    if catalog_base.empty and movements.empty:
        return []

    base = catalog_base.copy()
    if not movements.empty:
        unresolved = movements[
            ~movements["item_id"].astype(str).isin(base["item_id"].astype(str))
            & movements["item_id"].astype(str).str.strip().ne("")
        ].copy()
        if not unresolved.empty:
            unresolved["item_type"] = "unmapped"
            unresolved["is_unmapped"] = True
            base = pd.concat(
                [
                    base,
                    unresolved[
                        [
                            "item_id",
                            "item_name",
                            "parent_product_id",
                            "parent_product_name",
                            "variant_id",
                            "is_unmapped",
                            "item_type",
                        ]
                    ],
                ],
                ignore_index=True,
            ).drop_duplicates(subset=["item_id"], keep="first")

    qty_summary = pd.DataFrame(columns=["item_id", "on_hand_qty", "incoming_qty", "reserved_qty"])
    fallback_costs: dict[str, float] = {}
    if not movements.empty:
        d = movements.copy()
        d["txn_type"] = d["txn_type"].astype(str).str.upper()

        d["incoming_signed_qty"] = d.apply(
            lambda row: stock_deltas(str(row["txn_type"]), float(row["qty"])).incoming,
            axis=1,
        )

        qty_summary = d.groupby("item_id", as_index=False).agg(
            on_hand_qty=("signed_qty", "sum"),
            incoming_qty=("incoming_signed_qty", "sum"),
        )
        qty_summary["reserved_qty"] = 0.0

        inbound = d[d["txn_type"].isin(ON_HAND_INBOUND_TYPES)].copy()
        if not inbound.empty:
            inbound = inbound.sort_values(["item_id", "timestamp", "txn_id"])
            inbound["unit_cost"] = pd.to_numeric(inbound.get("unit_cost", 0), errors="coerce").fillna(0.0)
            latest = inbound.groupby("item_id", as_index=False).tail(1)
            fallback_costs = {
                str(row["item_id"]): float(row["unit_cost"])
                for _, row in latest.iterrows()
                if float(row.get("unit_cost", 0)) > 0
            }

    stock_rows = container.inventory.stock_by_lot_with_issues(client_id)
    on_hand_value = pd.DataFrame(columns=["item_id", "stock_value", "lot_count"])
    if not stock_rows.empty:
        lots = stock_rows.copy()
        lots["qty"] = pd.to_numeric(lots.get("qty", 0), errors="coerce").fillna(0.0)
        lots["unit_cost"] = pd.to_numeric(lots.get("unit_cost", 0), errors="coerce").fillna(0.0)
        lots["stock_value"] = lots["qty"] * lots["unit_cost"]
        on_hand_value = lots.groupby("product_id", as_index=False).agg(
            stock_value=("stock_value", "sum"),
            lot_count=("lot_id", "nunique"),
        ).rename(columns={"product_id": "item_id"})

    merged = base.merge(qty_summary, on="item_id", how="left").merge(on_hand_value, on="item_id", how="left")
    merged["on_hand_qty"] = pd.to_numeric(merged.get("on_hand_qty", 0), errors="coerce").fillna(0.0)
    merged["incoming_qty"] = pd.to_numeric(merged.get("incoming_qty", 0), errors="coerce").fillna(0.0)
    merged["reserved_qty"] = pd.to_numeric(merged.get("reserved_qty", 0), errors="coerce").fillna(0.0)
    merged["stock_value"] = pd.to_numeric(merged.get("stock_value", 0), errors="coerce").fillna(0.0)
    merged["lot_count"] = pd.to_numeric(merged.get("lot_count", 0), errors="coerce").fillna(0).astype(int)

    items: list[InventoryItemSummary] = []
    for _, row in merged.iterrows():
        on_hand_qty = float(row.get("on_hand_qty", 0.0))
        incoming_qty = float(row.get("incoming_qty", 0.0))
        reserved_qty = float(row.get("reserved_qty", 0.0))
        safety_stock_qty = 0.0
        sellable_qty = max(0.0, on_hand_qty - reserved_qty - safety_stock_qty)
        value = float(row.get("stock_value", 0.0))
        avg_cost = value / on_hand_qty if on_hand_qty > 0 else fallback_costs.get(str(row["item_id"]), 0.0)
        item_name = str(row.get("item_name", "") or row["item_id"])
        items.append(
            InventoryItemSummary(
                item_id=str(row["item_id"]),
                item_name=item_name,
                parent_product_id=str(row.get("parent_product_id", "") or ""),
                parent_product_name=str(row.get("parent_product_name", "") or ""),
                item_type=str(row.get("item_type") or _item_type(row)),
                on_hand_qty=on_hand_qty,
                incoming_qty=incoming_qty,
                reserved_qty=reserved_qty,
                sellable_qty=sellable_qty,
                avg_unit_cost=avg_cost,
                stock_value=value,
                lot_count=int(row.get("lot_count", 0)),
                low_stock=sellable_qty <= 5,
            )
        )
    return sorted(items, key=lambda item: (item.low_stock is False, item.item_name.lower()))


def _validate_inventory_item(container: ServiceContainer, client_id: str, item_id: str) -> tuple[str, str, str]:
    item_id = item_id.strip()
    if not item_id:
        raise HTTPException(status_code=400, detail="item_id is required")

    variants = container.products.list_variants_by_client(client_id)
    if not variants.empty:
        scoped = variants[variants["variant_id"].astype(str) == item_id]
        if not scoped.empty:
            row = scoped.iloc[0]
            parent_product_id = str(row.get("parent_product_id", "")).strip()
            if not parent_product_id:
                raise HTTPException(status_code=400, detail="Variant is missing parent product context")
            return str(row["variant_id"]), str(row.get("variant_name", row["variant_id"])), parent_product_id

    products = container.products.list_by_client(client_id)
    if not products.empty:
        scoped = products[products["product_id"].astype(str) == item_id]
        if not scoped.empty:
            sibling_variants = container.products.list_variants_by_client(client_id)
            if not sibling_variants.empty:
                has_variants = sibling_variants[
                    sibling_variants["parent_product_id"].astype(str) == item_id
                ]
                if not has_variants.empty:
                    raise HTTPException(
                        status_code=400,
                        detail="This product has variants. Use a variant item_id for inventory adjustments.",
                    )
            raise HTTPException(
                status_code=400,
                detail="Variant item_id is required for stock-affecting writes. Parent product ids are not accepted.",
            )

    raise HTTPException(status_code=404, detail="Inventory item not found for tenant")


def _resolve_inventory_variant(
    container: ServiceContainer,
    client_id: str,
    *,
    item_id: str | None = None,
    variant_id: str | None = None,
) -> tuple[str, str, str]:
    candidate = (item_id or variant_id or "").strip()
    if not candidate:
        raise HTTPException(status_code=400, detail="variant_id is required for stock-affecting writes")
    return _validate_inventory_item(container, client_id, candidate)


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
    item_id, item_name, parent_product_id = _validate_inventory_item(container, user.client_id, payload.item_id)

    stock_rows = container.inventory.stock_by_lot_with_issues(user.client_id)
    scoped = stock_rows[stock_rows.get("variant_id", "").astype(str) == item_id] if not stock_rows.empty else pd.DataFrame()
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
                    product_id=parent_product_id,
                    variant_id=item_id,
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
                product_id=parent_product_id,
                variant_id=item_id,
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
                        product_id=parent_product_id,
                        variant_id=item_id,
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
                    product_id=parent_product_id,
                    variant_id=item_id,
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


@router.post("/inbound", response_model=InventoryInboundCreateResponse, status_code=201)
def create_inbound(
    payload: InventoryInboundCreateRequest,
    user: RequestUser = Depends(get_current_user),
    container: ServiceContainer = Depends(get_container),
) -> InventoryInboundCreateResponse:
    require_page_access(user, "Catalog & Stock")
    item_id, item_name, parent_product_id = _validate_inventory_item(container, user.client_id, payload.item_id)

    source_id = payload.reference.strip() or f"manual-{user.user_id}"
    inbound_id = container.inventory.create_incoming_stock(
        client_id=user.client_id,
        product_id=parent_product_id,
        variant_id=item_id,
        product_name=item_name,
        qty=payload.quantity,
        unit_cost=payload.expected_unit_cost,
        supplier_snapshot=payload.supplier_snapshot,
        note=payload.note,
        source_id=source_id,
        user_id=user.user_id,
    )

    item = next((entry for entry in _build_inventory_items(container, user.client_id) if entry.item_id == item_id), None)
    pending_qty = item.incoming_qty if item else payload.quantity
    return InventoryInboundCreateResponse(
        success=True,
        inbound_id=inbound_id,
        item_id=item_id,
        pending_incoming_qty=pending_qty,
    )


@router.post("/inbound/{inbound_id}/receive", response_model=InventoryInboundReceiveResponse)
def receive_inbound(
    inbound_id: str,
    payload: InventoryInboundReceiveRequest,
    user: RequestUser = Depends(get_current_user),
    container: ServiceContainer = Depends(get_container),
) -> InventoryInboundReceiveResponse:
    require_page_access(user, "Catalog & Stock")
    try:
        item_id, lot_id, received_qty = container.inventory.receive_incoming_stock(
            client_id=user.client_id,
            inbound_id=inbound_id,
            qty=payload.quantity,
            unit_cost=payload.unit_cost,
            note=payload.note,
            user_id=user.user_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return InventoryInboundReceiveResponse(
        success=True,
        inbound_id=inbound_id,
        item_id=item_id,
        received_qty=received_qty,
        lot_id=lot_id,
    )


@router.post("/add", response_model=InventoryAddResponse)
def add_inventory(
    payload: InventoryAddRequest,
    user: RequestUser = Depends(get_current_user),
    container: ServiceContainer = Depends(get_container),
) -> InventoryAddResponse:
    require_page_access(user, "Catalog & Stock")
    variant_id, variant_name, parent_product_id = _resolve_inventory_variant(
        container,
        user.client_id,
        variant_id=payload.variant_id,
    )
    lot_id = container.inventory.add_stock(
        client_id=user.client_id,
        product_id=parent_product_id,
        variant_id=variant_id,
        product_name=variant_name,
        qty=payload.qty,
        unit_cost=payload.unit_cost,
        supplier_snapshot=payload.supplier_snapshot,
        note=payload.note,
        source_type=payload.source_type,
        source_id=payload.source_id,
        user_id=user.user_id,
    )
    return InventoryAddResponse(lot_id=lot_id)
