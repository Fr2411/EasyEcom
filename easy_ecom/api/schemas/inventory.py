from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, model_validator


class InventoryAddRequest(BaseModel):
    product_id: str
    product_name: str
    qty: float = Field(gt=0)
    unit_cost: float = Field(gt=0)
    supplier_snapshot: str = ""
    note: str = ""
    source_type: str = "manual"
    source_id: str = ""


class InventoryAddResponse(BaseModel):
    lot_id: str


class InventoryItemSummary(BaseModel):
    item_id: str
    item_name: str
    parent_product_id: str = ""
    parent_product_name: str = ""
    item_type: Literal["product", "variant", "unmapped"]
    on_hand_qty: float
    incoming_qty: float
    reserved_qty: float
    sellable_qty: float
    avg_unit_cost: float
    stock_value: float
    lot_count: int
    low_stock: bool


class InventoryListResponse(BaseModel):
    items: list[InventoryItemSummary]


class InventoryMovement(BaseModel):
    txn_id: str
    timestamp: str
    item_id: str
    item_name: str
    parent_product_id: str = ""
    parent_product_name: str = ""
    movement_type: str
    qty_delta: float
    source_type: str = ""
    source_id: str = ""
    note: str = ""
    lot_id: str = ""
    resulting_balance: float | None = None


class InventoryMovementsResponse(BaseModel):
    items: list[InventoryMovement]


class InventoryAdjustmentRequest(BaseModel):
    item_id: str = Field(min_length=1)
    adjustment_type: Literal["stock_in", "stock_out", "correction"]
    quantity: float | None = Field(default=None, gt=0)
    quantity_delta: float | None = None
    unit_cost: float | None = Field(default=None, gt=0)
    reason: str = Field(default="", max_length=200)
    note: str = Field(default="", max_length=500)
    reference: str = Field(default="", max_length=120)

    @model_validator(mode="after")
    def validate_payload(self) -> "InventoryAdjustmentRequest":
        if self.adjustment_type in {"stock_in", "stock_out"} and self.quantity is None:
            raise ValueError("quantity is required for stock_in/stock_out")
        if self.adjustment_type == "correction":
            if self.quantity_delta is None:
                raise ValueError("quantity_delta is required for correction")
            if self.quantity_delta == 0:
                raise ValueError("quantity_delta must be non-zero for correction")
        return self


class InventoryAdjustmentResponse(BaseModel):
    success: bool
    item_id: str
    adjustment_type: str
    applied_qty_delta: float
    lot_ids: list[str] = []
    movement_ids: list[str] = []


class InventoryInboundCreateRequest(BaseModel):
    item_id: str = Field(min_length=1)
    quantity: float = Field(gt=0)
    expected_unit_cost: float = Field(gt=0)
    supplier_snapshot: str = Field(default="", max_length=255)
    note: str = Field(default="", max_length=500)
    reference: str = Field(default="", max_length=120)


class InventoryInboundCreateResponse(BaseModel):
    success: bool
    inbound_id: str
    item_id: str
    pending_incoming_qty: float


class InventoryInboundReceiveRequest(BaseModel):
    quantity: float | None = Field(default=None, gt=0)
    unit_cost: float | None = Field(default=None, gt=0)
    note: str = Field(default="", max_length=500)


class InventoryInboundReceiveResponse(BaseModel):
    success: bool
    inbound_id: str
    item_id: str
    received_qty: float
    lot_id: str


class InventoryDetailResponse(BaseModel):
    item: InventoryItemSummary
    recent_movements: list[InventoryMovement]
