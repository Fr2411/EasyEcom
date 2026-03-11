from pydantic import BaseModel, Field


class ReturnSummary(BaseModel):
    return_id: str
    return_no: str
    sale_id: str
    sale_no: str
    customer_id: str
    customer_name: str
    reason: str
    return_total: float
    created_at: str


class ReturnsListResponse(BaseModel):
    items: list[ReturnSummary]


class ReturnSaleLookupItem(BaseModel):
    sale_id: str
    sale_no: str
    customer_id: str
    customer_name: str
    sale_date: str
    total: float
    status: str


class ReturnSalesLookupResponse(BaseModel):
    items: list[ReturnSaleLookupItem]


class ReturnableSaleLine(BaseModel):
    sale_item_id: str
    product_id: str
    variant_id: str = ""
    product_name: str
    sold_qty: float
    already_returned_qty: float
    eligible_qty: float
    unit_price: float


class ReturnableSaleDetailResponse(BaseModel):
    sale_id: str
    sale_no: str
    customer_id: str
    customer_name: str
    sale_date: str
    lines: list[ReturnableSaleLine]


class ReturnCreateLineRequest(BaseModel):
    sale_item_id: str = Field(min_length=1)
    qty: float = Field(gt=0)
    reason: str = Field(min_length=1, max_length=255)
    condition_status: str = Field(default="", max_length=64)


class ReturnCreateRequest(BaseModel):
    sale_id: str = Field(min_length=1)
    reason: str = Field(min_length=1, max_length=255)
    note: str = ""
    lines: list[ReturnCreateLineRequest] = Field(min_length=1)


class ReturnCreateResponse(BaseModel):
    return_id: str
    return_no: str
    sale_id: str
    sale_no: str
    return_total: float


class ReturnDetailLineResponse(BaseModel):
    return_item_id: str
    sale_item_id: str
    product_id: str
    variant_id: str = ""
    product_name: str
    sold_qty: float
    return_qty: float
    unit_price: float
    line_total: float
    reason: str
    condition_status: str


class ReturnDetailResponse(BaseModel):
    return_id: str
    return_no: str
    sale_id: str
    sale_no: str
    customer_id: str
    customer_name: str
    reason: str
    note: str
    return_total: float
    created_at: str
    lines: list[ReturnDetailLineResponse]
