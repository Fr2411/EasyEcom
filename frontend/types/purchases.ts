export type PurchaseListItem = {
  purchase_id: string;
  purchase_no: string;
  purchase_date: string;
  supplier_id: string;
  supplier_name: string;
  reference_no: string;
  subtotal: number;
  status: string;
  created_at: string;
};

export type PurchaseLine = {
  line_id: string;
  variant_id: string;
  product_id: string;
  product_name: string;
  qty: number;
  unit_cost: number;
  line_total: number;
};

export type PurchaseDetail = PurchaseListItem & {
  note: string;
  created_by_user_id: string;
  lines: PurchaseLine[];
};

export type PurchaseLookupProduct = {
  variant_id: string;
  product_id: string;
  label: string;
  current_stock: number;
  default_purchase_price: number;
  sku: string;
  barcode: string;
};

export type PurchaseLookupSupplier = {
  supplier_id: string;
  name: string;
};

export type PurchaseCreatePayload = {
  purchase_date: string;
  supplier_id: string;
  reference_no: string;
  note: string;
  payment_status: 'paid' | 'unpaid' | 'partial';
  lines: Array<{ variant_id: string; qty: number; unit_cost: number }>;
};
