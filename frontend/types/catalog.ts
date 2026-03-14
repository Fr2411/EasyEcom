export type WorkspaceLocation = {
  location_id: string;
  name: string;
  is_default: boolean;
};

export type WorkspaceOption = {
  category_id?: string;
  supplier_id?: string;
  name: string;
};

export type VariantOptions = {
  size: string;
  color: string;
  other: string;
};

export type CatalogVariant = {
  variant_id: string;
  product_id: string;
  product_name: string;
  title: string;
  label: string;
  sku: string;
  barcode: string;
  status: string;
  options: VariantOptions;
  unit_cost: string;
  unit_price: string;
  min_price: string;
  reorder_level: string;
  on_hand: string;
  reserved: string;
  available_to_sell: string;
};

export type CatalogProduct = {
  product_id: string;
  name: string;
  brand: string;
  status: string;
  supplier: string;
  category: string;
  description: string;
  sku_root: string;
  default_price: string;
  min_price: string;
  max_discount_percent: string;
  variants: CatalogVariant[];
};

export type CatalogWorkspace = {
  query: string;
  has_multiple_locations: boolean;
  active_location: WorkspaceLocation;
  locations: WorkspaceLocation[];
  categories: Array<WorkspaceOption & { category_id: string }>;
  suppliers: Array<WorkspaceOption & { supplier_id: string }>;
  items: CatalogProduct[];
};

export type ProductIdentityInput = {
  product_name: string;
  supplier: string;
  category: string;
  brand: string;
  description: string;
  image_url: string;
  sku_root: string;
  default_selling_price: string;
  min_selling_price: string;
  max_discount_percent: string;
  status: string;
};

export type CatalogVariantInput = {
  variant_id?: string | null;
  sku: string;
  barcode: string;
  size: string;
  color: string;
  other: string;
  default_purchase_price: string;
  default_selling_price: string;
  min_selling_price: string;
  reorder_level: string;
  status: string;
};

export type CatalogUpsertPayload = {
  product_id?: string;
  identity: ProductIdentityInput;
  variants: CatalogVariantInput[];
};
