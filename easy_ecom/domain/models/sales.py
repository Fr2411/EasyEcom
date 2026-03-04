from pydantic import BaseModel, Field


class SaleItem(BaseModel):
    product_id: str
    qty: float = Field(gt=0)
    unit_selling_price: float = Field(gt=0)


class SaleConfirm(BaseModel):
    client_id: str
    customer_id: str
    items: list[SaleItem]
    discount: float = 0
    tax: float = 0
    note: str = ""
