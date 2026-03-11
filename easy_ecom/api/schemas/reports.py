from __future__ import annotations

from pydantic import BaseModel, Field


class ReportDeferredMetric(BaseModel):
    metric: str
    reason: str


class ReportTrendPoint(BaseModel):
    period: str
    value: float


class SalesTopProduct(BaseModel):
    product_id: str
    product_name: str
    qty_sold: float
    revenue: float


class SalesTopCustomer(BaseModel):
    customer_id: str
    customer_name: str
    sales_count: int
    revenue: float


class SalesReportResponse(BaseModel):
    from_date: str
    to_date: str
    sales_count: int
    revenue_total: float
    sales_trend: list[ReportTrendPoint]
    top_products: list[SalesTopProduct]
    top_customers: list[SalesTopCustomer]
    deferred_metrics: list[ReportDeferredMetric] = Field(default_factory=list)


class InventoryStockSummary(BaseModel):
    product_id: str
    product_name: str
    current_qty: float


class InventoryMovementPoint(BaseModel):
    period: str
    qty_in: float
    qty_out: float


class InventoryReportResponse(BaseModel):
    from_date: str
    to_date: str
    total_skus_with_stock: int
    total_stock_units: float
    low_stock_items: list[InventoryStockSummary]
    stock_movement_trend: list[InventoryMovementPoint]
    inventory_value: float | None
    deferred_metrics: list[ReportDeferredMetric] = Field(default_factory=list)


class ProductActivityRow(BaseModel):
    product_id: str
    product_name: str
    qty_sold: float
    revenue: float


class ProductsReportResponse(BaseModel):
    from_date: str
    to_date: str
    highest_selling: list[ProductActivityRow]
    low_or_zero_movement: list[ProductActivityRow]
    deferred_metrics: list[ReportDeferredMetric] = Field(default_factory=list)


class FinanceExpensePoint(BaseModel):
    period: str
    amount: float


class FinanceReportResponse(BaseModel):
    from_date: str
    to_date: str
    expense_total: float
    expense_trend: list[FinanceExpensePoint]
    receivables_total: float
    payables_total: float
    net_operating_snapshot: float | None
    deferred_metrics: list[ReportDeferredMetric] = Field(default_factory=list)


class ReturnsReportResponse(BaseModel):
    from_date: str
    to_date: str
    returns_count: int
    return_qty_total: float
    return_amount_total: float
    deferred_metrics: list[ReportDeferredMetric] = Field(default_factory=list)


class PurchasesTrendPoint(BaseModel):
    period: str
    subtotal: float
    quantity: float


class PurchasesReportResponse(BaseModel):
    from_date: str
    to_date: str
    purchases_count: int
    purchases_subtotal: float
    purchases_trend: list[PurchasesTrendPoint]
    deferred_metrics: list[ReportDeferredMetric] = Field(default_factory=list)


class ReportsOverviewResponse(BaseModel):
    from_date: str
    to_date: str
    sales_revenue_total: float
    sales_count: int
    expense_total: float
    returns_total: float
    purchases_total: float

