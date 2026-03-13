from pydantic import BaseModel, Field


class PurchaseLineRequest(BaseModel):
    variant_id: str = Field(min_length=1)
    qty: float = Field(gt=0)
    unit_cost: float = Field(gt=0)


class PurchaseCreateRequest(BaseModel):
    purchase_date: str = Field(min_length=1)
    supplier_id: str = ""
    reference_no: str = ""
    note: str = ""
    lines: list[PurchaseLineRequest] = Field(min_length=1)
    payment_status: str = Field(default="unpaid")


class PurchaseLineResponse(BaseModel):
    line_id: str
    product_id: str
    variant_id: str = ""
    product_name: str
    qty: float
    unit_cost: float
    line_total: float


class PurchaseSummary(BaseModel):
    purchase_id: str
    purchase_no: str
    purchase_date: str
    supplier_id: str = ""
    supplier_name: str = ""
    reference_no: str = ""
    subtotal: float
    status: str
    created_at: str


class PurchasesListResponse(BaseModel):
    items: list[PurchaseSummary]


class PurchaseDetailResponse(PurchaseSummary):
    note: str = ""
    created_by_user_id: str = ""
    lines: list[PurchaseLineResponse]


class PurchaseCreateResponse(BaseModel):
    purchase_id: str
    purchase_no: str
    subtotal: float
    status: str


class PurchaseLookupProduct(BaseModel):
    variant_id: str
    product_id: str
    label: str
    current_stock: float
    default_purchase_price: float = 0
    sku: str = ""
    barcode: str = ""


class PurchaseLookupSupplier(BaseModel):
    supplier_id: str
    name: str


class PurchaseFormOptionsResponse(BaseModel):
    products: list[PurchaseLookupProduct]
    suppliers: list[PurchaseLookupSupplier]
