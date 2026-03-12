import { apiClient } from '@/lib/api';
import type { ProductRecord, ProductsStockSnapshot, SaveProductPayload } from '@/types/products-stock';

type SnapshotApiResponse = {
  products: ProductRecord[];
  suppliers: string[];
  categories: string[];
};

type SaveApiPayload = {
  mode: SaveProductPayload['mode'];
  identity: SaveProductPayload['identity'];
  variants: SaveProductPayload['variants'];
  selectedProductId?: string;
};

export async function getProductsStockSnapshot(): Promise<ProductsStockSnapshot> {
  const response = await apiClient<SnapshotApiResponse>('/products-stock/snapshot');

  return {
    products: response.products,
    suppliers: response.suppliers,
    categories: response.categories
  };
}

export async function saveProductStock(payload: SaveProductPayload): Promise<{ success: true }> {
  const body: SaveApiPayload = {
    mode: payload.mode,
    identity: payload.identity,
    variants: payload.variants,
    selectedProductId: payload.selectedProductId,
  };

  return apiClient<{ success: true }>('/products-stock/save', {
    method: 'POST',
    body: JSON.stringify(body),
  });
}
