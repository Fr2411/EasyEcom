from __future__ import annotations

from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field, field_validator


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

    @field_validator("default_selling_price", "min_selling_price", "max_discount_percent", mode="before")
    @classmethod
    def blank_decimal_to_none(cls, value: object) -> object:
        if isinstance(value, str) and not value.strip():
            return None
        return value


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


class CatalogUpsertRequest(BaseModel):
    product_id: str | None = None
    identity: ProductIdentityInput
    variants: list[CatalogVariantInput] = Field(default_factory=list)


class CatalogUpsertResponse(BaseModel):
    product: CatalogProductResponse


class InventoryStockRowResponse(BaseModel):
    variant_id: str
    product_id: str
    product_name: str
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


class ReceiveStockRequest(BaseModel):
    mode: Literal["existing_variant", "existing_product_new_variant", "new_product"]
    location_id: str | None = None
    quantity: Decimal = Field(gt=Decimal("0"))
    notes: str = ""
    identity: ProductIdentityInput
    variant: CatalogVariantInput


class PurchaseReceiptResponse(BaseModel):
    purchase_id: str
    purchase_number: str
    variant: CatalogVariantResponse


class InventoryAdjustmentRequest(BaseModel):
    location_id: str | None = None
    variant_id: str
    quantity_delta: Decimal
    reason: str = Field(min_length=2, max_length=255)
    notes: str = ""


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
    requested_at: str | None
    received_at: str | None
    lines: list[ReturnLineResponse]


class ReturnsResponse(BaseModel):
    items: list[ReturnResponse]
