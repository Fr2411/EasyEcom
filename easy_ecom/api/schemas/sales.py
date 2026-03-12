from pydantic import BaseModel, Field


class SaleLineRequest(BaseModel):
    variant_id: str = Field(min_length=1)
    qty: float = Field(gt=0)
    unit_price: float = Field(ge=0)


class SaleCreateRequest(BaseModel):
    customer_id: str = Field(min_length=1)
    lines: list[SaleLineRequest] = Field(min_length=1)
    discount: float = Field(default=0, ge=0)
    tax: float = Field(default=0, ge=0)
    note: str = ""


class SaleLineResponse(BaseModel):
    line_id: str
    product_id: str
    variant_id: str = ""
    product_name: str
    qty: float
    unit_price: float
    line_total: float


class SaleSummary(BaseModel):
    sale_id: str
    sale_no: str
    customer_id: str
    customer_name: str
    timestamp: str
    subtotal: float
    discount: float
    tax: float
    total: float
    status: str


class SalesListResponse(BaseModel):
    items: list[SaleSummary]


class SaleDetailResponse(SaleSummary):
    note: str = ""
    lines: list[SaleLineResponse]


class SaleCreateResponse(BaseModel):
    sale_id: str
    sale_no: str
    total: float
    status: str


class SaleLookupProduct(BaseModel):
    variant_id: str
    product_id: str
    sku: str = ""
    barcode: str = ""
    product_name: str
    variant_name: str
    label: str
    default_unit_price: float
    available_qty: float


class SaleLookupCustomer(BaseModel):
    customer_id: str
    full_name: str
    phone: str
    email: str


class SaleFormOptionsResponse(BaseModel):
    customers: list[SaleLookupCustomer]
    products: list[SaleLookupProduct]


class LegacySaleItemRequest(BaseModel):
    variant_id: str
    qty: float = Field(gt=0)
    unit_selling_price: float = Field(gt=0)


class LegacySalesCreateRequest(BaseModel):
    customer_id: str
    items: list[LegacySaleItemRequest]
    discount: float = 0
    tax: float = 0
    note: str = ""


class LegacySalesCreateResponse(BaseModel):
    order_id: str
    invoice_id: str
    status: str
