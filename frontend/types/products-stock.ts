import type {
  CatalogProduct,
  CatalogUpsertPayload,
  CatalogVariant,
  CatalogVariantInput,
  CatalogWorkspace,
  ProductIdentityInput,
} from '@/types/catalog';

export type VariantMode = 'new_product' | 'existing_product_new_variant' | 'existing_variant';
export type ProductRecord = CatalogProduct;
export type ProductsStockSnapshot = CatalogWorkspace;
export type Variant = CatalogVariant;
export type ProductIdentity = ProductIdentityInput;
export type ProductLookupOption = { id: string; name: string };
export type SaveProductApiPayload = CatalogUpsertPayload;
export type SaveProductPayload = CatalogUpsertPayload;
export type SaveVariant = CatalogVariantInput;
export type VariantGenerationInput = { size: string; color: string; other: string };
