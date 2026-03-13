import { apiClient } from '@/lib/api';
import type { ProductRecord, ProductsStockSnapshot, SaveProductApiPayload, SaveProductPayload, SaveVariant, Variant } from '@/types/products-stock';

type ApiVariant = Omit<Variant, 'rowId' | 'variant_id'> & {
  id: string;
};

type ApiProductRecord = Omit<ProductRecord, 'variants'> & {
  variants: ApiVariant[];
};

type SnapshotApiResponse = {
  products: ApiProductRecord[];
  suppliers: string[];
  categories: string[];
};

function buildVariantName(variant: Pick<Variant, 'size' | 'color' | 'other'>): string {
  return [variant.size, variant.color, variant.other]
    .map((part) => part.trim())
    .filter(Boolean)
    .join(' / ');
}

function mapVariantForSave(variant: Variant): SaveVariant {
  return {
    variant_id: variant.variant_id,
    variant_name: buildVariantName(variant),
    qty: variant.qty,
    cost: variant.cost,
    defaultSellingPrice: variant.defaultSellingPrice,
    maxDiscountPct: variant.maxDiscountPct,
    size: variant.size,
    color: variant.color,
    other: variant.other,
  };
}

export async function getProductsStockSnapshot(): Promise<ProductsStockSnapshot> {
  const response = await apiClient<SnapshotApiResponse>('/products-stock/snapshot');

  return {
    products: response.products.map((product) => ({
      ...product,
      variants: product.variants.map((variant) => ({
        rowId: crypto.randomUUID(),
        variant_id: variant.id,
        qty: variant.qty,
        cost: variant.cost,
        defaultSellingPrice: variant.defaultSellingPrice,
        maxDiscountPct: variant.maxDiscountPct,
        size: variant.size,
        color: variant.color,
        other: variant.other,
      })),
    })),
    suppliers: response.suppliers,
    categories: response.categories
  };
}

export async function saveProductStock(payload: SaveProductPayload): Promise<{ success: true }> {
  const body: SaveProductApiPayload = {
    mode: payload.mode,
    identity: payload.identity,
    variants: payload.variants.map(mapVariantForSave),
    selectedProductId: payload.selectedProductId,
  };

  return apiClient<{ success: true }>('/products-stock/save', {
    method: 'POST',
    body: JSON.stringify(body),
  });
}
