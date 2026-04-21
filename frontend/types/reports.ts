export type ReportDeferredMetric = {
  metric: string;
  reason: string;
};

export type ReportTrendPoint = {
  period: string;
  value: number;
};

export type SalesReport = {
  from_date: string;
  to_date: string;
  sales_count: number;
  revenue_total: number;
  sales_trend: ReportTrendPoint[];
  top_products: Array<{ product_id: string; product_name: string; qty_sold: number; revenue: number }>;
  top_customers: Array<{ customer_id: string; customer_name: string; sales_count: number; revenue: number }>;
  deferred_metrics: ReportDeferredMetric[];
};

export type InventoryReport = {
  from_date: string;
  to_date: string;
  total_skus_with_stock: number;
  total_stock_units: number;
  low_stock_items: Array<{ product_id: string; product_name: string; current_qty: number }>;
  stock_movement_trend: Array<{ period: string; qty_in: number; qty_out: number }>;
  inventory_value: number | null;
  deferred_metrics: ReportDeferredMetric[];
};

export type ProductsReport = {
  from_date: string;
  to_date: string;
  highest_selling: Array<{ product_id: string; product_name: string; qty_sold: number; revenue: number }>;
  low_or_zero_movement: Array<{ product_id: string; product_name: string; qty_sold: number; revenue: number }>;
  deferred_metrics: ReportDeferredMetric[];
};

export type FinanceReport = {
  from_date: string;
  to_date: string;
  expense_total: number;
  expense_trend: Array<{ period: string; amount: number }>;
  receivables_total: number;
  payables_total: number | null;
  net_operating_snapshot: number | null;
  deferred_metrics: ReportDeferredMetric[];
};

export type ReturnsReport = {
  from_date: string;
  to_date: string;
  returns_count: number;
  return_qty_total: number;
  return_amount_total: number;
  deferred_metrics: ReportDeferredMetric[];
};

export type ReportsOverview = {
  from_date: string;
  to_date: string;
  sales_revenue_total: number;
  sales_count: number;
  expense_total: number;
  returns_total: number;
};
