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
    defaultSellingPrice: variant.defaultSellingPrice,
    maxDiscountPct: variant.maxDiscountPct,
  };
}

function mapVariantForSave(variant: CatalogVariant): SaveCatalogVariant {
  return {
    variant_id: variant.variant_id,
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
