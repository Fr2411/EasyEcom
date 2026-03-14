export type ReturnLookupOrder = {
  sales_order_id: string;
  order_number: string;
  customer_name: string;
  customer_phone: string;
  customer_email: string;
  ordered_at: string | null;
  total_amount: string;
  status: string;
  shipment_status: string;
};

export type ReturnEligibleLine = {
  sales_order_item_id: string;
  variant_id: string;
  product_name: string;
  label: string;
  quantity: string;
  quantity_fulfilled: string;
  quantity_returned: string;
  eligible_quantity: string;
  unit_price: string;
};

export type ReturnEligibleLines = {
  sales_order_id: string;
  order_number: string;
  customer_name: string;
  customer_phone: string;
  lines: ReturnEligibleLine[];
};

export type ReturnLine = {
  sales_return_item_id: string;
  sales_order_item_id: string | null;
  variant_id: string;
  product_name: string;
  label: string;
  quantity: string;
  restock_quantity: string;
  disposition: string;
  unit_refund_amount: string;
  line_total: string;
};

export type ReturnRecord = {
  sales_return_id: string;
  return_number: string;
  sales_order_id: string | null;
  order_number: string;
  customer_name: string;
  customer_phone: string;
  status: string;
  refund_status: string;
  notes: string;
  subtotal_amount: string;
  refund_amount: string;
  requested_at: string | null;
  received_at: string | null;
  lines: ReturnLine[];
};

export type ReturnCreatePayload = {
  sales_order_id: string;
  notes: string;
  refund_status: string;
  lines: Array<{
    sales_order_item_id: string;
    quantity: string;
    restock_quantity: string;
    disposition: string;
    unit_refund_amount: string;
    reason: string;
  }>;
};
