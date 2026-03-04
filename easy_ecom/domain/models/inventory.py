from pydantic import BaseModel, Field


class InventoryIn(BaseModel):
    client_id: str
    product_id: str
    qty: float = Field(gt=0)
    unit_cost: float = Field(gt=0)
    supplier_snapshot: str = ""
    note: str = ""
