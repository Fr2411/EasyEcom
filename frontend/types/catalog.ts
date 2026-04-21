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
  status: string;
  options: VariantOptions;
  unit_cost: string | null;
  unit_price: string | null;
  min_price: string | null;
  effective_unit_price: string | null;
  effective_min_price: string | null;
  is_price_inherited: boolean;
  is_min_price_inherited: boolean;
  reorder_level: string;
  on_hand: string;
  reserved: string;
  available_to_sell: string;
};

export type ProductMedia = {
  media_id: string;
  upload_id: string;
  large_url: string;
  thumbnail_url: string;
  width: number;
  height: number;
  vector_status: string;
};

export type StagedProductMediaUpload = ProductMedia;

export type CatalogProduct = {
  product_id: string;
  name: string;
  brand: string;
  status: string;
  supplier: string;
  category: string;
  description: string;
  sku_root: string;
  default_price: string | null;
  min_price: string | null;
  max_discount_percent: string | null;
  image_url: string;
  image: ProductMedia | null;
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
  pending_primary_media_upload_id?: string;
  remove_primary_image?: boolean;
  sku_root: string;
  default_selling_price: string;
  min_selling_price: string;
  max_discount_percent?: string;
  status: string;
};

export type CatalogVariantInput = {
  variant_id?: string | null;
  sku: string;
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

export type CatalogCreationStep = 'product' | 'first_variant' | 'confirm';
