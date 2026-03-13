export type InventoryItem = {
  item_id: string;
  item_name: string;
  parent_product_id: string;
  parent_product_name: string;
  item_type: 'product' | 'variant' | 'unmapped';
  availability_status: 'in_stock' | 'incoming' | 'low_stock' | 'out_of_stock' | 'unmapped';
  on_hand_qty: number;
  incoming_qty: number;
  reserved_qty: number;
  sellable_qty: number;
  avg_unit_cost: number;
  stock_value: number;
  lot_count: number;
  low_stock: boolean;
  actionable: boolean;
};

export type InventoryMovement = {
  txn_id: string;
  timestamp: string;
  item_id: string;
  item_name: string;
  parent_product_id: string;
  parent_product_name: string;
  movement_type: string;
  qty_delta: number;
  source_type: string;
  source_id: string;
  note: string;
  lot_id: string;
  resulting_balance: number | null;
};

export type InventoryDetail = {
  item: InventoryItem;
  recent_movements: InventoryMovement[];
};

export type InventoryAdjustmentPayload = {
  item_id: string;
  adjustment_type: 'stock_in' | 'stock_out' | 'correction';
  quantity?: number;
  quantity_delta?: number;
  unit_cost?: number;
  reason: string;
  note: string;
  reference: string;
};
