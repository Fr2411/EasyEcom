from pydantic import BaseModel


class DashboardSummaryResponse(BaseModel):
    Revenue: float
    Gross_Profit: float
    Net_Operating_Profit: float
    Gross_Margin_Pct: float
    Inventory_Value: float
    Outstanding_Receivables: float
    Data_Health_Score: float


class DashboardKpis(BaseModel):
    total_products: int
    total_variants: int
    current_stock_units: float
    low_stock_items: int


class DashboardBusinessHealth(BaseModel):
    inventory_value: float
    recent_stock_movements_count: int
    sales_count_last_30_days: int | None
    revenue_last_30_days: float | None


class DashboardActivityItem(BaseModel):
    timestamp: str
    txn_type: str
    product_name: str
    qty: float
    note: str | None


class DashboardTopProductItem(BaseModel):
    product_id: str
    product_name: str
    current_qty: float
    stock_value: float


class DashboardOverviewResponse(BaseModel):
    generated_at: str
    kpis: DashboardKpis
    business_health: DashboardBusinessHealth
    recent_activity: list[DashboardActivityItem]
    top_products: list[DashboardTopProductItem]
