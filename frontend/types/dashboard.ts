export type DashboardKpis = {
  total_products: number;
  total_variants: number;
  current_stock_units: number;
  low_stock_items: number;
};

export type DashboardBusinessHealth = {
  inventory_value: number;
  recent_stock_movements_count: number;
  sales_count_last_30_days: number | null;
  revenue_last_30_days: number | null;
};

export type DashboardActivityItem = {
  timestamp: string;
  txn_type: string;
  product_name: string;
  qty: number;
  note: string | null;
};

export type DashboardTopProduct = {
  product_id: string;
  product_name: string;
  current_qty: number;
  stock_value: number;
};

export type DashboardOverview = {
  generated_at: string;
  kpis: DashboardKpis;
  business_health: DashboardBusinessHealth;
  recent_activity: DashboardActivityItem[];
  top_products: DashboardTopProduct[];
};
