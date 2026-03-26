from pydantic import BaseModel
from typing import List, Optional


class ReportDeferredMetric(BaseModel):
    metric: str
    reason: str


class ReportTrendPoint(BaseModel):
    period: str
    value: float


class SalesReport(BaseModel):
    from_date: str
    to_date: str
    sales_count: int
    revenue_total: float
    sales_trend: List[ReportTrendPoint]
    top_products: List[dict]  # { product_id: str, product_name: str, qty_sold: int, revenue: float }
    top_customers: List[dict]  # { customer_id: str, customer_name: str, sales_count: int, revenue: float }
    deferred_metrics: List[ReportDeferredMetric]


class InventoryReport(BaseModel):
    from_date: str
    to_date: str
    total_skus_with_stock: int
    total_stock_units: int
    low_stock_items: List[dict]  # { product_id: str, product_name: str, current_qty: int }
    stock_movement_trend: List[dict]  # { period: str, qty_in: int, qty_out: int }
    inventory_value: Optional[float]
    deferred_metrics: List[ReportDeferredMetric]


class ProductsReport(BaseModel):
    from_date: str
    to_date: str
    highest_selling: List[dict]  # { product_id: str, product_name: str, qty_sold: int, revenue: float }
    low_or_zero_movement: List[dict]  # { product_id: str, product_name: str, qty_sold: int, revenue: float }
    deferred_metrics: List[ReportDeferredMetric]


class FinanceReport(BaseModel):
    from_date: str
    to_date: str
    expense_total: float
    expense_trend: List[dict]  # { period: str, amount: float }
    receivables_total: float
    payables_total: float
    net_operating_snapshot: Optional[float]
    deferred_metrics: List[ReportDeferredMetric]


class ReturnsReport(BaseModel):
    from_date: str
    to_date: str
    returns_count: int
    return_qty_total: int
    return_amount_total: float
    deferred_metrics: List[ReportDeferredMetric]


class PurchasesReport(BaseModel):
    from_date: str
    to_date: str
    purchases_count: int
    purchases_subtotal: float
    purchases_trend: List[dict]  # { period: str, subtotal: float, quantity: int }
    deferred_metrics: List[ReportDeferredMetric]


class ReportsOverview(BaseModel):
    from_date: str
    to_date: str
    sales_revenue_total: float
    sales_count: int
    expense_total: float
    returns_total: int
    purchases_total: float