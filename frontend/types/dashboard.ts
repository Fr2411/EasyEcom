export type DashboardRangeKey = 'mtd' | 'last_7_days' | 'last_30_days' | 'last_90_days' | 'custom';

export type DashboardMetricUnit = 'money' | 'count' | 'quantity' | 'percent' | 'days';

export type DashboardLocationOption = {
  location_id: string;
  name: string;
  is_default: boolean;
};

export type DashboardAppliedRange = {
  range_key: DashboardRangeKey;
  label: string;
  timezone: string;
  from_date: string;
  to_date: string;
  previous_from_date: string;
  previous_to_date: string;
  bucket: 'day' | 'week';
  days: number;
};

export type DashboardVisibility = {
  can_view_financial_metrics: boolean;
};

export type DashboardMetric = {
  id: string;
  label: string;
  value: string | number | null;
  unit: DashboardMetricUnit;
  delta_value: string | number | null;
  delta_direction: 'up' | 'down' | 'flat' | null;
  help_text: string | null;
  is_estimated: boolean;
  unavailable_reason: string | null;
};

export type DashboardInsightCard = {
  id: string;
  title: string;
  summary: string;
  metric_label: string;
  metric_value: string;
  tone: 'positive' | 'neutral' | 'warning' | 'critical' | 'info';
  entity_name: string | null;
  path: string | null;
  unavailable_reason: string | null;
};

export type DashboardRevenueProfitPoint = {
  period: string;
  revenue: string | number;
  estimated_gross_profit: string | number | null;
};

export type DashboardRevenueProfitTrend = {
  items: DashboardRevenueProfitPoint[];
  unavailable_reason: string | null;
};

export type DashboardStockMovementPoint = {
  period: string;
  stock_received: string | number;
  sale_fulfilled: string | number;
  sales_return_restock: string | number;
  adjustment: string | number;
};

export type DashboardReturnsTrendPoint = {
  period: string;
  returns_count: number;
  refund_amount: string | number | null;
};

export type DashboardReturnsTrend = {
  items: DashboardReturnsTrendPoint[];
};

export type DashboardProductOpportunityPoint = {
  product_id: string;
  product_name: string;
  units_sold: string | number;
  sales_qty_per_day: string | number;
  estimated_margin_percent: string | number | null;
  inventory_cost_value: string | number | null;
  revenue: string | number;
  estimated_gross_profit: string | number | null;
  available_qty: string | number;
  days_cover: string | number | null;
};

export type DashboardProductOpportunity = {
  items: DashboardProductOpportunityPoint[];
  unavailable_reason: string | null;
};

export type DashboardRevenueOrdersAovPoint = {
  period: string;
  revenue: string | number;
  orders: number;
  aov: string | number;
  anomaly_flag: boolean;
};

export type DashboardRevenueOrdersAovTrend = {
  items: DashboardRevenueOrdersAovPoint[];
};

export type DashboardGrossProfitMarginPoint = {
  period: string;
  revenue: string | number;
  estimated_gross_profit: string | number | null;
  margin_percent: string | number | null;
};

export type DashboardGrossProfitMarginTrend = {
  items: DashboardGrossProfitMarginPoint[];
  unavailable_reason: string | null;
};

export type DashboardConversionFunnelStage = {
  stage: string;
  label: string;
  count: number;
  conversion_percent_from_previous: string | number | null;
  drop_off_from_previous: number | null;
};

export type DashboardConversionDropOffReason = {
  reason: string;
  count: number;
};

export type DashboardConversionFunnel = {
  stages: DashboardConversionFunnelStage[];
  drop_off_reasons: DashboardConversionDropOffReason[];
};

export type DashboardProductPerformancePoint = {
  product_id: string;
  product_name: string;
  sales_velocity: string | number;
  estimated_margin_percent: string | number | null;
  revenue: string | number;
  days_cover: string | number | null;
  quadrant: string;
};

export type DashboardProductPerformanceQuadrant = {
  items: DashboardProductPerformancePoint[];
  unavailable_reason: string | null;
};

export type DashboardBrandProfitMixNode = {
  brand: string;
  revenue: string | number;
  estimated_gross_profit: string | number | null;
  margin_percent: string | number | null;
  product_count: number;
};

export type DashboardCategoryProfitMixNode = {
  category: string;
  revenue: string | number;
  estimated_gross_profit: string | number | null;
  margin_percent: string | number | null;
  brands: DashboardBrandProfitMixNode[];
};

export type DashboardCategoryBrandProfitMix = {
  categories: DashboardCategoryProfitMixNode[];
  unavailable_reason: string | null;
};

export type DashboardReturnsReasonCell = {
  product_id: string;
  product_name: string;
  reason: string;
  returns_qty: string | number;
  refund_amount: string | number | null;
};

export type DashboardReturnsReasonSummary = {
  reason: string;
  returns_qty: string | number;
};

export type DashboardReturnsIntelligenceTrendPoint = {
  period: string;
  returns_count: number;
  return_rate_percent: string | number;
  refund_amount: string | number | null;
};

export type DashboardReturnsIntelligence = {
  heatmap: DashboardReturnsReasonCell[];
  top_reasons: DashboardReturnsReasonSummary[];
  trend: DashboardReturnsIntelligenceTrendPoint[];
};

export type DashboardInventoryAgingBucket = {
  bucket: string;
  on_hand_qty: string | number;
  inventory_value: string | number | null;
  net_qty_change: string | number;
  net_value_change: string | number | null;
};

export type DashboardInventoryAgingWaterfall = {
  buckets: DashboardInventoryAgingBucket[];
  unavailable_reason: string | null;
};

export type DashboardSellThroughCoverPoint = {
  product_id: string;
  product_name: string;
  sell_through_percent: string | number;
  days_cover: string | number | null;
  sales_velocity: string | number;
  zone: string;
  revenue: string | number;
};

export type DashboardSellThroughCoverMatrix = {
  items: DashboardSellThroughCoverPoint[];
};

export type DashboardReorderPriorityRow = {
  product_id: string;
  product_name: string;
  priority_score: string | number;
  sales_velocity: string | number;
  days_cover: string | number | null;
  estimated_margin_percent: string | number | null;
  revenue: string | number;
  recommended_action: string;
};

export type DashboardReorderPriorityScoreboard = {
  items: DashboardReorderPriorityRow[];
};

export type DashboardPriceDiscountImpactPoint = {
  product_id: string;
  product_name: string;
  discount_percent: string | number;
  unit_lift_percent: string | number;
  net_margin_percent: string | number | null;
  revenue: string | number;
  recommendation: 'raise' | 'keep' | 'discount';
};

export type DashboardPriceDiscountImpact = {
  items: DashboardPriceDiscountImpactPoint[];
  unavailable_reason: string | null;
};

export type DashboardCharts = {
  revenue_profit_trend: DashboardRevenueProfitTrend;
  stock_movement_trend: DashboardStockMovementPoint[];
  returns_trend: DashboardReturnsTrend;
  product_opportunity_matrix: DashboardProductOpportunity;
  revenue_orders_aov_trend: DashboardRevenueOrdersAovTrend;
  gross_profit_margin_trend: DashboardGrossProfitMarginTrend;
  conversion_funnel: DashboardConversionFunnel;
  product_performance_quadrant: DashboardProductPerformanceQuadrant;
  category_brand_profit_mix: DashboardCategoryBrandProfitMix;
  returns_intelligence: DashboardReturnsIntelligence;
  inventory_aging_waterfall: DashboardInventoryAgingWaterfall;
  sell_through_cover_matrix: DashboardSellThroughCoverMatrix;
  reorder_priority_scoreboard: DashboardReorderPriorityScoreboard;
  price_discount_impact: DashboardPriceDiscountImpact;
};

export type DashboardStockInvestmentRow = {
  product_id: string;
  product_name: string;
  on_hand_qty: string | number;
  available_qty: string | number;
  inventory_cost_value: string | number | null;
  active_variants: number;
};

export type DashboardLowStockVariantRow = {
  variant_id: string;
  product_id: string;
  product_name: string;
  label: string;
  on_hand_qty: string | number;
  reserved_qty: string | number;
  available_qty: string | number;
  reorder_level: string | number;
  inventory_cost_value: string | number | null;
};

export type DashboardProductLeaderboardRow = {
  product_id: string;
  product_name: string;
  units_sold: string | number;
  revenue: string | number;
  estimated_gross_profit: string | number | null;
  estimated_margin_percent: string | number | null;
};

export type DashboardLeaderboardSection = {
  items: DashboardProductLeaderboardRow[];
  unavailable_reason: string | null;
};

export type DashboardSlowMoverRow = {
  product_id: string;
  product_name: string;
  available_qty: string | number;
  inventory_cost_value: string | number | null;
  units_sold_in_range: string | number;
};

export type DashboardRecentActivityItem = {
  timestamp: string;
  event_type: string;
  product_name: string;
  label: string;
  quantity: string | number;
  note: string | null;
};

export type DashboardTables = {
  stock_investment_by_product: DashboardStockInvestmentRow[];
  low_stock_variants: DashboardLowStockVariantRow[];
  top_products_by_units_sold: DashboardProductLeaderboardRow[];
  top_products_by_revenue: DashboardLeaderboardSection;
  top_products_by_estimated_gross_profit: DashboardLeaderboardSection;
  slow_movers: DashboardSlowMoverRow[];
  recent_activity: DashboardRecentActivityItem[];
};

export type DashboardAnalytics = {
  generated_at: string;
  has_multiple_locations: boolean;
  selected_location_id: string | null;
  locations: DashboardLocationOption[];
  applied_range: DashboardAppliedRange;
  visibility: DashboardVisibility;
  kpis: DashboardMetric[];
  insight_cards: DashboardInsightCard[];
  charts: DashboardCharts;
  tables: DashboardTables;
};
