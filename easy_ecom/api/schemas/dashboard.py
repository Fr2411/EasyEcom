from __future__ import annotations

from decimal import Decimal
from typing import Literal

from pydantic import BaseModel


DashboardMetricUnit = Literal["money", "count", "quantity", "percent", "days"]
DashboardTone = Literal["positive", "neutral", "warning", "critical", "info"]


class DashboardLocationOptionResponse(BaseModel):
    location_id: str
    name: str
    is_default: bool


class DashboardAppliedRangeResponse(BaseModel):
    range_key: str
    label: str
    timezone: str
    from_date: str
    to_date: str
    previous_from_date: str
    previous_to_date: str
    bucket: Literal["day", "week"]
    days: int


class DashboardVisibilityResponse(BaseModel):
    can_view_financial_metrics: bool


class DashboardMetricResponse(BaseModel):
    id: str
    label: str
    value: Decimal | int | None
    unit: DashboardMetricUnit
    delta_value: Decimal | int | None = None
    delta_direction: Literal["up", "down", "flat"] | None = None
    help_text: str | None = None
    is_estimated: bool = False
    unavailable_reason: str | None = None


class DashboardInsightCardResponse(BaseModel):
    id: str
    title: str
    summary: str
    metric_label: str
    metric_value: str
    tone: DashboardTone = "neutral"
    entity_name: str | None = None
    path: str | None = None
    unavailable_reason: str | None = None


class DashboardRevenueProfitPointResponse(BaseModel):
    period: str
    revenue: Decimal
    estimated_gross_profit: Decimal | None = None


class DashboardRevenueProfitTrendResponse(BaseModel):
    items: list[DashboardRevenueProfitPointResponse]
    unavailable_reason: str | None = None


class DashboardStockMovementPointResponse(BaseModel):
    period: str
    stock_received: Decimal
    sale_fulfilled: Decimal
    sales_return_restock: Decimal
    adjustment: Decimal


class DashboardReturnsTrendPointResponse(BaseModel):
    period: str
    returns_count: int
    refund_amount: Decimal | None = None


class DashboardReturnsTrendResponse(BaseModel):
    items: list[DashboardReturnsTrendPointResponse]


class DashboardProductOpportunityPointResponse(BaseModel):
    product_id: str
    product_name: str
    units_sold: Decimal
    sales_qty_per_day: Decimal
    estimated_margin_percent: Decimal | None = None
    inventory_cost_value: Decimal | None = None
    revenue: Decimal
    estimated_gross_profit: Decimal | None = None
    available_qty: Decimal
    days_cover: Decimal | None = None


class DashboardProductOpportunityResponse(BaseModel):
    items: list[DashboardProductOpportunityPointResponse]
    unavailable_reason: str | None = None


class DashboardChartsResponse(BaseModel):
    revenue_profit_trend: DashboardRevenueProfitTrendResponse
    stock_movement_trend: list[DashboardStockMovementPointResponse]
    returns_trend: DashboardReturnsTrendResponse
    product_opportunity_matrix: DashboardProductOpportunityResponse


class DashboardStockInvestmentRowResponse(BaseModel):
    product_id: str
    product_name: str
    on_hand_qty: Decimal
    available_qty: Decimal
    inventory_cost_value: Decimal | None = None
    active_variants: int


class DashboardLowStockVariantRowResponse(BaseModel):
    variant_id: str
    product_id: str
    product_name: str
    label: str
    on_hand_qty: Decimal
    reserved_qty: Decimal
    available_qty: Decimal
    reorder_level: Decimal
    inventory_cost_value: Decimal | None = None


class DashboardProductLeaderboardRowResponse(BaseModel):
    product_id: str
    product_name: str
    units_sold: Decimal
    revenue: Decimal
    estimated_gross_profit: Decimal | None = None
    estimated_margin_percent: Decimal | None = None


class DashboardLeaderboardSectionResponse(BaseModel):
    items: list[DashboardProductLeaderboardRowResponse]
    unavailable_reason: str | None = None


class DashboardSlowMoverRowResponse(BaseModel):
    product_id: str
    product_name: str
    available_qty: Decimal
    inventory_cost_value: Decimal | None = None
    units_sold_in_range: Decimal


class DashboardRecentActivityItemResponse(BaseModel):
    timestamp: str
    event_type: str
    product_name: str
    label: str
    quantity: Decimal
    note: str | None = None


class DashboardTablesResponse(BaseModel):
    stock_investment_by_product: list[DashboardStockInvestmentRowResponse]
    low_stock_variants: list[DashboardLowStockVariantRowResponse]
    top_products_by_units_sold: list[DashboardProductLeaderboardRowResponse]
    top_products_by_revenue: DashboardLeaderboardSectionResponse
    top_products_by_estimated_gross_profit: DashboardLeaderboardSectionResponse
    slow_movers: list[DashboardSlowMoverRowResponse]
    recent_activity: list[DashboardRecentActivityItemResponse]


class DashboardAnalyticsResponse(BaseModel):
    generated_at: str
    has_multiple_locations: bool
    selected_location_id: str | None = None
    locations: list[DashboardLocationOptionResponse]
    applied_range: DashboardAppliedRangeResponse
    visibility: DashboardVisibilityResponse
    kpis: list[DashboardMetricResponse]
    insight_cards: list[DashboardInsightCardResponse]
    charts: DashboardChartsResponse
    tables: DashboardTablesResponse
