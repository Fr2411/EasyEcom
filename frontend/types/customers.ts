export type CustomerWorkspaceRecentOrder = {
  sales_order_id: string;
  order_number: string;
  status: string;
  payment_status: string;
  total_amount: string;
  ordered_at: string | null;
};

export type CustomerWorkspaceRecentReturn = {
  sales_return_id: string;
  return_number: string;
  order_number: string;
  refund_status: string;
  refund_amount: string;
  requested_at: string | null;
};

export type CustomerWorkspaceItem = {
  customer_id: string;
  name: string;
  phone: string;
  email: string;
  address: string;
  total_orders: number;
  completed_orders: number;
  open_orders: number;
  total_returns: number;
  lifetime_revenue: string;
  outstanding_balance: string;
  last_order_at: string | null;
  last_return_at: string | null;
  recent_orders: CustomerWorkspaceRecentOrder[];
  recent_returns: CustomerWorkspaceRecentReturn[];
};

export type CustomerWorkspace = {
  query: string;
  items: CustomerWorkspaceItem[];
};
