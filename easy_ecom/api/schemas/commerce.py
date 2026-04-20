from __future__ import annotations

from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator


class LocationSummaryResponse(BaseModel):
    location_id: str
    name: str
    is_default: bool


class CategorySummaryResponse(BaseModel):
    category_id: str
    name: str


class SupplierSummaryResponse(BaseModel):
    supplier_id: str
    name: str


class VariantDescriptorResponse(BaseModel):
    size: str
    color: str
    other: str


class CatalogVariantResponse(BaseModel):
    variant_id: str
    product_id: str
    product_name: str
    title: str
    label: str
    sku: str
    barcode: str
    status: str
    options: VariantDescriptorResponse
    unit_cost: Decimal | None
    unit_price: Decimal | None
    min_price: Decimal | None
    effective_unit_price: Decimal | None
    effective_min_price: Decimal | None
    is_price_inherited: bool
    is_min_price_inherited: bool
    reorder_level: Decimal
    on_hand: Decimal
    reserved: Decimal
    available_to_sell: Decimal


class ProductImageResponse(BaseModel):
    media_id: str
    upload_id: str
    large_url: str
    thumbnail_url: str
    width: int
    height: int
    vector_status: str


class CatalogProductResponse(BaseModel):
    product_id: str
    name: str
    brand: str
    status: str
    supplier: str
    category: str
    description: str
    sku_root: str
    default_price: Decimal | None
    min_price: Decimal | None
    max_discount_percent: Decimal | None
    image_url: str = ""
    image: ProductImageResponse | None = None
    variants: list[CatalogVariantResponse]


class CatalogWorkspaceResponse(BaseModel):
    query: str = ""
    has_multiple_locations: bool
    active_location: LocationSummaryResponse
    locations: list[LocationSummaryResponse]
    categories: list[CategorySummaryResponse]
    suppliers: list[SupplierSummaryResponse]
    items: list[CatalogProductResponse]


class ProductIdentityInput(BaseModel):
    product_name: str = Field(min_length=2, max_length=255)
    supplier: str = ""
    category: str = ""
    brand: str = ""
    description: str = ""
    image_url: str = ""
    sku_root: str = ""
    default_selling_price: Decimal | None = None
    min_selling_price: Decimal | None = None
    max_discount_percent: Decimal | None = None
    status: str = "active"
    pending_primary_media_upload_id: str = ""
    remove_primary_image: bool = False

    @field_validator("default_selling_price", "min_selling_price", "max_discount_percent", mode="before")
    @classmethod
    def blank_decimal_to_none(cls, value: object) -> object:
        if isinstance(value, str) and not value.strip():
            return None
        return value


class InventoryIntakeIdentityInput(ProductIdentityInput):
    product_id: str | None = None


class CatalogVariantInput(BaseModel):
    variant_id: str | None = None
    sku: str | None = Field(default=None, max_length=128)
    barcode: str = ""
    size: str = ""
    color: str = ""
    other: str = ""
    default_purchase_price: Decimal | None = None
    default_selling_price: Decimal | None = None
    min_selling_price: Decimal | None = None
    reorder_level: Decimal = Decimal("0")
    status: str = "active"

    @field_validator("sku", mode="before")
    @classmethod
    def blank_sku_to_none(cls, value: object) -> object:
        if isinstance(value, str) and not value.strip():
            return None
        return value

    @field_validator("default_purchase_price", "default_selling_price", "min_selling_price", mode="before")
    @classmethod
    def blank_variant_decimal_to_none(cls, value: object) -> object:
        if isinstance(value, str) and not value.strip():
            return None
        return value

    @field_validator("reorder_level", mode="before")
    @classmethod
    def blank_reorder_level_to_zero(cls, value: object) -> object:
        if isinstance(value, str) and not value.strip():
            return Decimal("0")
        return value


class ReceiveStockLineInput(CatalogVariantInput):
    quantity: Decimal | None = None

    @field_validator("quantity", mode="before")
    @classmethod
    def blank_quantity_to_none(cls, value: object) -> object:
        if isinstance(value, str) and not value.strip():
            return None
        return value


class CatalogUpsertRequest(BaseModel):
    product_id: str | None = None
    identity: ProductIdentityInput
    variants: list[CatalogVariantInput] = Field(default_factory=list)


class CatalogUpsertResponse(BaseModel):
    product: CatalogProductResponse


CatalogCreationStep = Literal["product", "first_variant", "confirm"]


class CatalogStepValidationRequest(BaseModel):
    step: CatalogCreationStep
    identity: ProductIdentityInput
    variants: list[CatalogVariantInput] = Field(default_factory=list)


class CatalogStepValidationResponse(BaseModel):
    step: CatalogCreationStep
    valid: bool = True


class StagedProductMediaUploadResponse(ProductImageResponse):
    pass


class AttachProductMediaRequest(BaseModel):
    upload_id: str


class InventoryStockRowResponse(BaseModel):
    variant_id: str
    product_id: str
    product_name: str
    image_url: str = ""
    image: ProductImageResponse | None = None
    label: str
    sku: str
    barcode: str
    supplier: str
    category: str
    location_id: str
    location_name: str
    unit_cost: Decimal | None
    unit_price: Decimal | None
    reorder_level: Decimal
    on_hand: Decimal
    reserved: Decimal
    available_to_sell: Decimal
    low_stock: bool


class InventoryWorkspaceResponse(BaseModel):
    query: str = ""
    has_multiple_locations: bool
    active_location: LocationSummaryResponse
    locations: list[LocationSummaryResponse]
    stock_items: list[InventoryStockRowResponse]
    low_stock_items: list[InventoryStockRowResponse]


class InventoryIntakeSuggestedProductResponse(BaseModel):
    product_name: str
    sku_root: str


class InventoryIntakeExactVariantMatchResponse(BaseModel):
    match_reason: str
    product: CatalogProductResponse
    variant: CatalogVariantResponse


class InventoryIntakeLookupResponse(BaseModel):
    query: str = ""
    exact_variants: list[InventoryIntakeExactVariantMatchResponse]
    product_matches: list[CatalogProductResponse]
    suggested_new_product: InventoryIntakeSuggestedProductResponse | None = None


class ReceiveStockRequest(BaseModel):
    action: Literal["receive_stock", "save_template_only"] = "receive_stock"
    location_id: str | None = None
    source_purchase_order_id: str | None = None
    notes: str = ""
    update_matched_product_details: bool = False
    identity: InventoryIntakeIdentityInput
    lines: list[ReceiveStockLineInput] = Field(default_factory=list)
    mode: Literal["existing_variant", "existing_product_new_variant", "new_product"] | None = None
    quantity: Decimal | None = None
    variant: CatalogVariantInput | None = None

    @field_validator("quantity", mode="before")
    @classmethod
    def blank_receive_quantity_to_none(cls, value: object) -> object:
        if isinstance(value, str) and not value.strip():
            return None
        return value

    @model_validator(mode="before")
    @classmethod
    def normalize_legacy_single_line_payload(cls, value: object) -> object:
        if not isinstance(value, dict) or value.get("lines"):
            return value
        variant = value.get("variant")
        if variant is None:
            return value
        line = dict(variant)
        line["quantity"] = value.get("quantity")
        normalized = dict(value)
        normalized["action"] = normalized.get("action") or "receive_stock"
        normalized["lines"] = [line]
        return normalized

    @model_validator(mode="after")
    def validate_lines(self) -> "ReceiveStockRequest":
        if not self.lines:
            raise ValueError("At least one line is required")
        if self.action == "receive_stock":
            for line in self.lines:
                if line.quantity is None or line.quantity <= Decimal("0"):
                    raise ValueError("Quantity is required for each received line")
        return self


class PurchaseReceiptLineResponse(BaseModel):
    quantity_received: Decimal
    variant: CatalogVariantResponse


class PurchaseReceiptResponse(BaseModel):
    action: Literal["receive_stock", "save_template_only"]
    purchase_id: str | None = None
    purchase_number: str | None = None
    product: CatalogProductResponse
    lines: list[PurchaseReceiptLineResponse]


class InventoryAdjustmentRequest(BaseModel):
    location_id: str | None = None
    variant_id: str
    quantity_delta: Decimal
    reason: str = Field(min_length=2, max_length=255)
    notes: str = ""


class InventoryInlineUpdateRequest(BaseModel):
    variant_id: str
    supplier: str | None = None
    reorder_level: Decimal | None = None

    @field_validator("supplier", mode="before")
    @classmethod
    def normalize_supplier(cls, value: object) -> object:
        if value is None:
            return None
        if isinstance(value, str):
            return value.strip()
        return value


class EmbeddedCustomerResponse(BaseModel):
    customer_id: str
    name: str
    phone: str
    email: str


class CustomerLookupResponse(BaseModel):
    items: list[EmbeddedCustomerResponse]


class CustomerInput(BaseModel):
    name: str = Field(min_length=2, max_length=255)
    phone: str = Field(min_length=3, max_length=64)
    email: str = ""
    address: str = ""


class SaleLookupVariantResponse(BaseModel):
    variant_id: str
    product_id: str
    product_name: str
    label: str
    sku: str
    barcode: str
    available_to_sell: Decimal
    unit_price: Decimal
    min_price: Decimal | None


class SaleVariantLookupResponse(BaseModel):
    items: list[SaleLookupVariantResponse]


class SalesOrderLineInput(BaseModel):
    variant_id: str
    quantity: Decimal = Field(gt=Decimal("0"))
    unit_price: Decimal | None = None
    discount_amount: Decimal = Decimal("0")

    @field_validator("unit_price", mode="before")
    @classmethod
    def blank_unit_price_to_none(cls, value: object) -> object:
        if isinstance(value, str) and not value.strip():
            return None
        return value


class SalesOrderLineResponse(BaseModel):
    sales_order_item_id: str
    variant_id: str
    product_id: str
    product_name: str
    label: str
    sku: str
    quantity: Decimal
    quantity_fulfilled: Decimal
    quantity_cancelled: Decimal
    reserved_quantity: Decimal
    unit_price: Decimal
    discount_amount: Decimal
    line_total: Decimal


class SalesOrderResponse(BaseModel):
    sales_order_id: str
    order_number: str
    customer_id: str | None
    customer_name: str
    customer_phone: str
    customer_email: str
    location_id: str
    location_name: str
    status: str
    payment_status: str
    shipment_status: str
    ordered_at: str | None
    confirmed_at: str | None
    notes: str
    subtotal_amount: Decimal
    discount_amount: Decimal
    total_amount: Decimal
    paid_amount: Decimal
    source_type: str
    finance_status: Literal["not_posted", "posted", "reversed"]
    finance_summary: dict | None = None
    lines: list[SalesOrderLineResponse]


class SalesOrdersResponse(BaseModel):
    items: list[SalesOrderResponse]


class SalesOrderUpsertRequest(BaseModel):
    location_id: str | None = None
    customer_id: str | None = None
    customer: CustomerInput | None = None
    payment_status: str = "unpaid"
    shipment_status: str = "pending"
    notes: str = ""
    lines: list[SalesOrderLineInput] = Field(default_factory=list)
    action: Literal["save_draft", "confirm", "confirm_and_fulfill"] = "save_draft"


class SalesOrderActionResponse(BaseModel):
    order: SalesOrderResponse


class SalesOrderActionRequest(BaseModel):
    payment_status: str | None = None
    shipment_status: str | None = None
    notes: str | None = None


class SalesOrderPaymentRequest(BaseModel):
    payment_date: str
    amount: Decimal = Field(gt=Decimal("0"))
    method: str = "manual"
    reference: str = ""
    note: str = ""


class ReturnLookupOrderResponse(BaseModel):
    sales_order_id: str
    order_number: str
    customer_name: str
    customer_phone: str
    customer_email: str
    ordered_at: str | None
    total_amount: Decimal
    status: str
    shipment_status: str


class ReturnLookupOrdersResponse(BaseModel):
    items: list[ReturnLookupOrderResponse]


class ReturnEligibleLineResponse(BaseModel):
    sales_order_item_id: str
    variant_id: str
    product_name: str
    label: str
    quantity: Decimal
    quantity_fulfilled: Decimal
    quantity_returned: Decimal
    eligible_quantity: Decimal
    unit_price: Decimal


class ReturnEligibleLinesResponse(BaseModel):
    sales_order_id: str
    order_number: str
    customer_name: str
    customer_phone: str
    lines: list[ReturnEligibleLineResponse]


class ReturnLineInput(BaseModel):
    sales_order_item_id: str
    quantity: Decimal = Field(gt=Decimal("0"))
    restock_quantity: Decimal = Decimal("0")
    disposition: str = "restock"
    unit_refund_amount: Decimal = Decimal("0")
    reason: str = ""


class ReturnCreateRequest(BaseModel):
    sales_order_id: str
    notes: str = ""
    refund_status: str = "pending"
    lines: list[ReturnLineInput] = Field(default_factory=list)


class ReturnLineResponse(BaseModel):
    sales_return_item_id: str
    sales_order_item_id: str | None
    variant_id: str
    product_name: str
    label: str
    quantity: Decimal
    restock_quantity: Decimal
    disposition: str
    unit_refund_amount: Decimal
    line_total: Decimal


class ReturnRefundEventResponse(BaseModel):
    transaction_id: str
    amount: Decimal
    reference: str
    note: str
    posted_at: str | None


class ReturnResponse(BaseModel):
    sales_return_id: str
    return_number: str
    sales_order_id: str | None
    order_number: str
    customer_name: str
    customer_phone: str
    status: str
    refund_status: str
    notes: str
    subtotal_amount: Decimal
    refund_amount: Decimal
    refund_paid_amount: Decimal
    refund_outstanding_amount: Decimal
    finance_status: Literal["not_posted", "posted", "reversed"]
    requested_at: str | None
    received_at: str | None
    recent_refunds: list[ReturnRefundEventResponse] = Field(default_factory=list)
    lines: list[ReturnLineResponse]


class ReturnsResponse(BaseModel):
    items: list[ReturnResponse]


class ReturnUpdateRequest(BaseModel):
    refund_status: str | None = None
    notes: str | None = None
    status: str | None = None


class ReturnRefundPaymentRequest(BaseModel):
    refund_date: str
    amount: Decimal = Field(gt=Decimal("0"))
    method: str = "manual"
    reference: str = ""
    note: str = ""


# Purchase Order Schemas
class PurchaseLineItemResponse(BaseModel):
    line_id: str
    variant_id: str
    product_id: str
    product_name: str
    qty: Decimal
    unit_cost: Decimal
    line_total: Decimal


class PurchaseListItemResponse(BaseModel):
    purchase_id: str
    purchase_no: str
    purchase_date: str  # ISO string
    supplier_id: str
    supplier_name: str
    reference_no: str
    subtotal: Decimal
    status: str
    created_at: str  # ISO string


class PurchaseDetailResponse(BaseModel):
    purchase_id: str
    purchase_no: str
    purchase_date: str
    supplier_id: str
    supplier_name: str
    reference_no: str
    note: str
    subtotal: Decimal
    status: str
    created_at: str
    created_by_user_id: str
    lines: list[PurchaseLineItemResponse]


class PurchaseOrdersResponse(BaseModel):
    items: list[PurchaseListItemResponse]


class PurchaseCreateRequest(BaseModel):
    purchase_date: str  # ISO string
    supplier_id: str
    reference_no: str
    note: str = ""
    payment_status: Literal['paid', 'unpaid', 'partial'] = 'unpaid'
    lines: list[dict]  # We'll accept raw lines for now, or define a specific line input

    @field_validator('lines')
    @classmethod
    def check_lines_not_empty(cls, v):
        if not v:
            raise ValueError('At least one line is required')
        return v


class PurchaseUpdateRequest(BaseModel):
    purchase_date: Optional[str] = None
    supplier_id: Optional[str] = None
    reference_no: Optional[str] = None
    note: Optional[str] = None
    payment_status: Optional[Literal['paid', 'unpaid', 'partial']] = None
    lines: Optional[list[dict]] = None

# Purchase lookup schemas
class PurchaseLookupProductResponse(BaseModel):
    variant_id: str
    product_id: str
    label: str
    current_stock: Decimal
    default_purchase_price: Decimal | None
    sku: str
    barcode: str


class PurchaseLookupSupplierResponse(BaseModel):
    supplier_id: str
    name: str
