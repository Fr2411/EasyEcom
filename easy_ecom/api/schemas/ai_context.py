from __future__ import annotations

from pydantic import BaseModel, Field


class AiProductVariant(BaseModel):
    variant_id: str
    variant_name: str
    sku_code: str
    default_price: float
    is_active: bool


class AiProductContextItem(BaseModel):
    product_id: str
    product_name: str
    category: str
    default_price: float
    stock_qty: float
    variants: list[AiProductVariant] = Field(default_factory=list)


class AiProductsContextResponse(BaseModel):
    query: str
    count: int
    items: list[AiProductContextItem] = Field(default_factory=list)


class AiStockContextItem(BaseModel):
    product_id: str
    product_name: str
    variant_id: str
    variant_name: str
    available_qty: float


class AiStockProductRollupItem(BaseModel):
    product_id: str
    product_name: str
    available_qty: float


class AiStockContextResponse(BaseModel):
    product_id: str | None
    count: int
    items: list[AiStockContextItem] = Field(default_factory=list)
    product_rollup: list[AiStockProductRollupItem] = Field(default_factory=list)


class AiSalesTopProduct(BaseModel):
    product_id: str
    product_name: str
    qty_sold: float
    revenue: float


class AiSalesContextResponse(BaseModel):
    window_days: int
    confirmed_sales_count: int
    confirmed_sales_revenue: float
    top_products: list[AiSalesTopProduct] = Field(default_factory=list)


class AiCustomerContextItem(BaseModel):
    customer_id: str
    full_name: str
    phone: str
    email: str
    is_active: bool


class AiCustomersContextResponse(BaseModel):
    query: str
    count: int
    items: list[AiCustomerContextItem] = Field(default_factory=list)


class AiOverviewResponse(BaseModel):
    tenant_id: str
    generated_at: str
    products_count: int
    variants_count: int
    active_customers_count: int
    confirmed_sales_count: int
    confirmed_sales_revenue: float
    low_stock_items_count: int
    domains: list[str] = Field(default_factory=list)
    deferred_capabilities: list[str] = Field(default_factory=list)


class AiLookupResponse(BaseModel):
    query: str
    count: int
    items: list[dict[str, object]] = Field(default_factory=list)


class AiRecentActivityItem(BaseModel):
    type: str
    timestamp: str
    reference_id: str
    summary: str


class AiRecentActivityResponse(BaseModel):
    window_days: int
    count: int
    items: list[AiRecentActivityItem] = Field(default_factory=list)


class AiLowStockResponse(BaseModel):
    threshold: int
    count: int
    items: list[AiStockContextItem] = Field(default_factory=list)


class InboundInquiryRequest(BaseModel):
    message: str = Field(min_length=1, max_length=500)
    customer_ref: str | None = Field(default=None, max_length=120)


class InboundInquiryResponse(BaseModel):
    intent: str
    suggested_endpoint: str
    customer_ref: str | None
    context: dict[str, object]
    guardrails: dict[str, bool]
