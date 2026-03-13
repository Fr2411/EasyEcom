export type CatalogMode = 'existing' | 'new';

export type CatalogVariant = {
  tempId: string;
  variant_id?: string;
  defaultSellingPrice: number;
  maxDiscountPct: number;
  size: string;
  color: string;
  other: string;
};

export type VariantGenerationInput = {
  size: string;
  color: string;
  other: string;
};

export type ProductIdentity = {
  productName: string;
  supplier: string;
  category: string;
  description: string;
  features: string[];
};

export type CatalogProductRecord = {
  product_id: string;
  identity: ProductIdentity;
  variants: CatalogVariant[];
};

export type ProductLookupOption = {
  id: string;
  name: string;
};

export type CatalogSnapshot = {
  products: CatalogProductRecord[];
  suppliers: string[];
  categories: string[];
};

export type SaveCatalogPayload = {
  mode: CatalogMode;
  identity: ProductIdentity;
  variants: CatalogVariant[];
  selectedProductId?: string;
};

export type SaveCatalogVariant = {
  variant_id?: string;
  defaultSellingPrice: number;
  maxDiscountPct: number;
  size: string;
  color: string;
  other: string;
};

export type SaveCatalogApiPayload = {
  identity: ProductIdentity;
  variants: SaveCatalogVariant[];
};
