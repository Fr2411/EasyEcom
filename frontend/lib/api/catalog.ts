import { apiClient } from '@/lib/api';
import type {
  CatalogProductRecord,
  CatalogSnapshot,
  CatalogVariant,
  SaveCatalogApiPayload,
  SaveCatalogPayload,
  SaveCatalogVariant,
} from '@/types/catalog';

type ApiCatalogVariant = Omit<CatalogVariant, 'tempId'>;

type ApiCatalogProductRecord = Omit<CatalogProductRecord, 'variants'> & {
  variants: ApiCatalogVariant[];
};

type CatalogProductsResponse = {
  products: ApiCatalogProductRecord[];
  suppliers: string[];
  categories: string[];
};

function mapApiVariant(variant: ApiCatalogVariant): CatalogVariant {
  return {
    tempId: crypto.randomUUID(),
    variant_id: variant.variant_id,
    size: variant.size,
    color: variant.color,
    other: variant.other,
    defaultPurchasePrice: variant.defaultPurchasePrice,
    defaultSellingPrice: variant.defaultSellingPrice,
    maxDiscountPct: variant.maxDiscountPct,
    isArchived: false,
  };
}

function mapVariantForSave(variant: CatalogVariant): SaveCatalogVariant {
  return {
    variant_id: variant.variant_id,
    defaultPurchasePrice: variant.defaultPurchasePrice,
    defaultSellingPrice: variant.defaultSellingPrice,
    maxDiscountPct: variant.maxDiscountPct,
    size: variant.size,
    color: variant.color,
    other: variant.other,
  };
}

function toApiPayload(payload: SaveCatalogPayload): SaveCatalogApiPayload {
  return {
    identity: payload.identity,
    variants: payload.variants.map(mapVariantForSave),
    archiveVariantIds: payload.archiveVariantIds ?? [],
  };
}

export async function getCatalogProducts(): Promise<CatalogSnapshot> {
  const response = await apiClient<CatalogProductsResponse>('/catalog/products');
  return {
    products: response.products.map((product) => ({
      ...product,
      variants: product.variants.map(mapApiVariant),
    })),
    suppliers: response.suppliers,
    categories: response.categories,
  };
}

export async function getCatalogProduct(productId: string): Promise<CatalogProductRecord> {
  const response = await apiClient<ApiCatalogProductRecord>(`/catalog/products/${productId}`);
  return {
    ...response,
    variants: response.variants.map(mapApiVariant),
  };
}

export async function saveCatalogProduct(payload: SaveCatalogPayload): Promise<{ product_id: string; variant_count: number }> {
  const body = JSON.stringify(toApiPayload(payload));
  if (payload.mode === 'existing') {
    if (!payload.selectedProductId) {
      throw new Error('Select an existing product before saving updates.');
    }
    return apiClient<{ product_id: string; variant_count: number }>(`/catalog/products/${payload.selectedProductId}`, {
      method: 'PATCH',
      body,
    });
  }
  return apiClient<{ product_id: string; variant_count: number }>('/catalog/products', {
    method: 'POST',
    body,
  });
}
