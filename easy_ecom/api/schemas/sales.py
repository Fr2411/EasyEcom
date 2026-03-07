from pydantic import BaseModel, Field


class SaleItemRequest(BaseModel):
    product_id: str
    qty: float = Field(gt=0)
    unit_selling_price: float = Field(gt=0)


class SalesCreateRequest(BaseModel):
    customer_id: str
    items: list[SaleItemRequest]
    discount: float = 0
    tax: float = 0
    note: str = ""


class SalesCreateResponse(BaseModel):
    order_id: str
    invoice_id: str
    status: str
