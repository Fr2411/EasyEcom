export type ReturnSummary = {
  return_id: string;
  return_no: string;
  sale_id: string;
  sale_no: string;
  customer_id: string;
  customer_name: string;
  reason: string;
  return_total: number;
  created_at: string;
};

export type ReturnableSale = {
  sale_id: string;
  sale_no: string;
  customer_id: string;
  customer_name: string;
  sale_date: string;
  total: number;
  status: string;
};

export type ReturnableSaleLine = {
  sale_item_id: string;
  product_id: string;
  product_name: string;
  sold_qty: number;
  already_returned_qty: number;
  eligible_qty: number;
  unit_price: number;
};

export type ReturnableSaleDetail = {
  sale_id: string;
  sale_no: string;
  customer_id: string;
  customer_name: string;
  sale_date: string;
  lines: ReturnableSaleLine[];
};

export type ReturnCreatePayload = {
  sale_id: string;
  reason: string;
  note: string;
  lines: { sale_item_id: string; qty: number; reason: string; condition_status?: string }[];
};

export type ReturnDetail = {
  return_id: string;
  return_no: string;
  sale_id: string;
  sale_no: string;
  customer_id: string;
  customer_name: string;
  reason: string;
  note: string;
  return_total: number;
  created_at: string;
  lines: {
    return_item_id: string;
    sale_item_id: string;
    product_id: string;
    product_name: string;
    sold_qty: number;
    return_qty: number;
    unit_price: number;
    line_total: number;
    reason: string;
    condition_status: string;
  }[];
};
