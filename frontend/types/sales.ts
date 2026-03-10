export type SaleListItem = {
  sale_id: string;
  sale_no: string;
  customer_id: string;
  customer_name: string;
  timestamp: string;
  subtotal: number;
  discount: number;
  tax: number;
  total: number;
  status: string;
};

export type SaleLine = {
  line_id: string;
  product_id: string;
  product_name: string;
  qty: number;
  unit_price: number;
  line_total: number;
};

export type SaleDetail = SaleListItem & {
  note: string;
  lines: SaleLine[];
};

export type SaleLookupCustomer = {
  customer_id: string;
  full_name: string;
  phone: string;
  email: string;
};

export type SaleLookupProduct = {
  product_id: string;
  label: string;
  default_unit_price: number;
  available_qty: number;
};

export type SaleCreateLinePayload = {
  product_id: string;
  qty: number;
  unit_price: number;
};

export type SaleCreatePayload = {
  customer_id: string;
  lines: SaleCreateLinePayload[];
  discount: number;
  tax: number;
  note: string;
};
