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


class DashboardRevenueOrdersAovPointResponse(BaseModel):
    period: str
    revenue: Decimal
    orders: int
    aov: Decimal
    anomaly_flag: bool = False


class DashboardRevenueOrdersAovTrendResponse(BaseModel):
    items: list[DashboardRevenueOrdersAovPointResponse]


class DashboardGrossProfitMarginPointResponse(BaseModel):
    period: str
    revenue: Decimal
    estimated_gross_profit: Decimal | None = None
    margin_percent: Decimal | None = None


class DashboardGrossProfitMarginTrendResponse(BaseModel):
    items: list[DashboardGrossProfitMarginPointResponse]
    unavailable_reason: str | None = None


class DashboardConversionFunnelStageResponse(BaseModel):
    stage: str
    label: str
    count: int
    conversion_percent_from_previous: Decimal | None = None
    drop_off_from_previous: int | None = None


class DashboardConversionDropOffReasonResponse(BaseModel):
    reason: str
    count: int


class DashboardConversionFunnelResponse(BaseModel):
    stages: list[DashboardConversionFunnelStageResponse]
    drop_off_reasons: list[DashboardConversionDropOffReasonResponse]


class DashboardProductPerformancePointResponse(BaseModel):
    product_id: str
    product_name: str
    sales_velocity: Decimal
    estimated_margin_percent: Decimal | None = None
    revenue: Decimal
    days_cover: Decimal | None = None
    quadrant: str


class DashboardProductPerformanceQuadrantResponse(BaseModel):
    items: list[DashboardProductPerformancePointResponse]
    unavailable_reason: str | None = None


class DashboardBrandProfitMixNodeResponse(BaseModel):
    brand: str
    revenue: Decimal
    estimated_gross_profit: Decimal | None = None
    margin_percent: Decimal | None = None
    product_count: int


class DashboardCategoryProfitMixNodeResponse(BaseModel):
    category: str
    revenue: Decimal
    estimated_gross_profit: Decimal | None = None
    margin_percent: Decimal | None = None
    brands: list[DashboardBrandProfitMixNodeResponse]


class DashboardCategoryBrandProfitMixResponse(BaseModel):
    categories: list[DashboardCategoryProfitMixNodeResponse]
    unavailable_reason: str | None = None


class DashboardReturnsReasonCellResponse(BaseModel):
    product_id: str
    product_name: str
    reason: str
    returns_qty: Decimal
    refund_amount: Decimal | None = None


class DashboardReturnsReasonSummaryResponse(BaseModel):
    reason: str
    returns_qty: Decimal


class DashboardReturnsIntelligenceTrendPointResponse(BaseModel):
    period: str
    returns_count: int
    return_rate_percent: Decimal
    refund_amount: Decimal | None = None


class DashboardReturnsIntelligenceResponse(BaseModel):
    heatmap: list[DashboardReturnsReasonCellResponse]
    top_reasons: list[DashboardReturnsReasonSummaryResponse]
    trend: list[DashboardReturnsIntelligenceTrendPointResponse]


class DashboardInventoryAgingBucketResponse(BaseModel):
    bucket: str
    on_hand_qty: Decimal
    inventory_value: Decimal | None = None
    net_qty_change: Decimal
    net_value_change: Decimal | None = None


class DashboardInventoryAgingWaterfallResponse(BaseModel):
    buckets: list[DashboardInventoryAgingBucketResponse]
    unavailable_reason: str | None = None


class DashboardSellThroughCoverPointResponse(BaseModel):
    product_id: str
    product_name: str
    sell_through_percent: Decimal
    days_cover: Decimal | None = None
    sales_velocity: Decimal
    zone: str
    revenue: Decimal


class DashboardSellThroughCoverMatrixResponse(BaseModel):
    items: list[DashboardSellThroughCoverPointResponse]


class DashboardReorderPriorityRowResponse(BaseModel):
    product_id: str
    product_name: str
    priority_score: Decimal
    sales_velocity: Decimal
    days_cover: Decimal | None = None
    estimated_margin_percent: Decimal | None = None
    revenue: Decimal
    recommended_action: str


class DashboardReorderPriorityScoreboardResponse(BaseModel):
    items: list[DashboardReorderPriorityRowResponse]


class DashboardPriceDiscountImpactPointResponse(BaseModel):
    product_id: str
    product_name: str
    discount_percent: Decimal
    unit_lift_percent: Decimal
    net_margin_percent: Decimal | None = None
    revenue: Decimal
    recommendation: Literal["raise", "keep", "discount"]


class DashboardPriceDiscountImpactResponse(BaseModel):
    items: list[DashboardPriceDiscountImpactPointResponse]
    unavailable_reason: str | None = None


class DashboardChartsResponse(BaseModel):
    revenue_profit_trend: DashboardRevenueProfitTrendResponse
    stock_movement_trend: list[DashboardStockMovementPointResponse]
    returns_trend: DashboardReturnsTrendResponse
    product_opportunity_matrix: DashboardProductOpportunityResponse
    revenue_orders_aov_trend: DashboardRevenueOrdersAovTrendResponse
    gross_profit_margin_trend: DashboardGrossProfitMarginTrendResponse
    conversion_funnel: DashboardConversionFunnelResponse
    product_performance_quadrant: DashboardProductPerformanceQuadrantResponse
    category_brand_profit_mix: DashboardCategoryBrandProfitMixResponse
    returns_intelligence: DashboardReturnsIntelligenceResponse
    inventory_aging_waterfall: DashboardInventoryAgingWaterfallResponse
    sell_through_cover_matrix: DashboardSellThroughCoverMatrixResponse
    reorder_priority_scoreboard: DashboardReorderPriorityScoreboardResponse
    price_discount_impact: DashboardPriceDiscountImpactResponse


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
