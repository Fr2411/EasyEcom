from pydantic import BaseModel, Field


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
