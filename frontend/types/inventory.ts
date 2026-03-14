import type {
  CatalogVariant,
  CatalogVariantInput,
  ProductIdentityInput,
  WorkspaceLocation,
} from '@/types/catalog';

export type InventoryStockRow = {
  variant_id: string;
  product_id: string;
  product_name: string;
  label: string;
  sku: string;
  barcode: string;
  supplier: string;
  category: string;
  location_id: string;
  location_name: string;
  unit_cost: string | null;
  unit_price: string | null;
  reorder_level: string;
  on_hand: string;
  reserved: string;
  available_to_sell: string;
  low_stock: boolean;
};

export type InventoryWorkspace = {
  query: string;
  has_multiple_locations: boolean;
  active_location: WorkspaceLocation;
  locations: WorkspaceLocation[];
  stock_items: InventoryStockRow[];
  low_stock_items: InventoryStockRow[];
};

export type ReceiveStockPayload = {
  mode: 'existing_variant' | 'existing_product_new_variant' | 'new_product';
  location_id?: string;
  quantity: string;
  notes: string;
  identity: ProductIdentityInput;
  variant: CatalogVariantInput;
};

export type ReceiveStockResponse = {
  purchase_id: string;
  purchase_number: string;
  variant: CatalogVariant;
};

export type InventoryAdjustmentPayload = {
  location_id?: string;
  variant_id: string;
  quantity_delta: string;
  reason: string;
  notes: string;
};
