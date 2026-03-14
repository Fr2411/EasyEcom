export type EmbeddedCustomer = {
  customer_id: string;
  name: string;
  phone: string;
  email: string;
};

export type SaleLookupVariant = {
  variant_id: string;
  product_id: string;
  product_name: string;
  label: string;
  sku: string;
  barcode: string;
  available_to_sell: string;
  unit_price: string;
  min_price: string | null;
};

export type SalesOrderLine = {
  sales_order_item_id: string;
  variant_id: string;
  product_id: string;
  product_name: string;
  label: string;
  sku: string;
  quantity: string;
  quantity_fulfilled: string;
  quantity_cancelled: string;
  reserved_quantity: string;
  unit_price: string;
  discount_amount: string;
  line_total: string;
};

export type SalesOrder = {
  sales_order_id: string;
  order_number: string;
  customer_id: string | null;
  customer_name: string;
  customer_phone: string;
  customer_email: string;
  location_id: string;
  location_name: string;
  status: string;
  payment_status: string;
  shipment_status: string;
  ordered_at: string | null;
  confirmed_at: string | null;
  notes: string;
  subtotal_amount: string;
  discount_amount: string;
  total_amount: string;
  paid_amount: string;
  lines: SalesOrderLine[];
};

export type SalesOrderLineInput = {
  variant_id: string;
  quantity: string;
  unit_price: string;
  discount_amount: string;
};

export type SalesOrderPayload = {
  location_id?: string;
  customer_id?: string;
  customer?: {
    name: string;
    phone: string;
    email: string;
    address: string;
  };
  payment_status: string;
  shipment_status: string;
  notes: string;
  lines: SalesOrderLineInput[];
  action: 'save_draft' | 'confirm' | 'confirm_and_fulfill';
};
