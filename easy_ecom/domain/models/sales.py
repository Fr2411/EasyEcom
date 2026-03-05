from pydantic import BaseModel, Field


class SaleItem(BaseModel):
    product_id: str
    qty: float = Field(gt=0)
    unit_selling_price: float = Field(gt=0)


class ReturnItem(BaseModel):
    product_id: str
    qty: float = Field(gt=0)
    unit_selling_price: float = Field(gt=0)
    note: str = ""


class ReturnRequestCreate(BaseModel):
    client_id: str
    invoice_id: str
    order_id: str
    customer_id: str
    requested_by_user_id: str
    reason: str
    note: str = ""
    restock: bool = False
    items: list[ReturnItem]


class SaleConfirm(BaseModel):
    client_id: str
    customer_id: str
    items: list[SaleItem]
    discount: float = 0
    tax: float = 0
    note: str = ""
