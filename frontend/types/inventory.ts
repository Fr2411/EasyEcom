import type {
  CatalogProduct,
  ProductMedia,
  CatalogVariant,
  CatalogVariantInput,
  ProductIdentityInput,
  WorkspaceLocation,
} from '@/types/catalog';

export type InventoryStockRow = {
  variant_id: string;
  product_id: string;
  product_name: string;
  image_url: string;
  image: ProductMedia | null;
  label: string;
  sku: string;
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

export type InventoryIntakeIdentityInput = ProductIdentityInput & {
  product_id?: string;
};

export type ReceiveStockLineInput = CatalogVariantInput & {
  quantity: string;
};

export type InventoryIntakeExactVariantMatch = {
  match_reason: string;
  product: CatalogProduct;
  variant: CatalogVariant;
};

export type InventoryIntakeLookup = {
  query: string;
  exact_variants: InventoryIntakeExactVariantMatch[];
  product_matches: CatalogProduct[];
  suggested_new_product: {
    product_name: string;
    sku_root: string;
  } | null;
};

export type ReceiveStockPayload = {
  action: 'receive_stock' | 'save_template_only';
  location_id?: string;
  source_purchase_order_id?: string;
  notes: string;
  update_matched_product_details: boolean;
  identity: InventoryIntakeIdentityInput;
  lines: ReceiveStockLineInput[];
};

export type ReceiveStockResponse = {
  action: 'receive_stock' | 'save_template_only';
  purchase_id: string | null;
  purchase_number: string | null;
  product: CatalogProduct;
  lines: Array<{
    quantity_received: string;
    variant: CatalogVariant;
  }>;
};

export type InventoryAdjustmentPayload = {
  location_id?: string;
  variant_id: string;
  quantity_delta: string;
  reason: string;
  notes: string;
};

export type InventoryInlineUpdatePayload = {
  variant_id: string;
  supplier?: string;
  reorder_level?: string;
};
