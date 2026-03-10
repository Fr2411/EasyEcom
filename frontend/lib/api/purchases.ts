import { apiClient } from '@/lib/api/client';
import type {
  PurchaseCreatePayload,
  PurchaseDetail,
  PurchaseListItem,
  PurchaseLookupProduct,
  PurchaseLookupSupplier,
} from '@/types/purchases';

export async function getPurchases(query = ''): Promise<{ items: PurchaseListItem[] }> {
  const params = new URLSearchParams();
  if (query.trim()) params.set('q', query.trim());
  return apiClient<{ items: PurchaseListItem[] }>(`/purchases${params.toString() ? `?${params.toString()}` : ''}`);
}

export async function getPurchaseFormOptions(query = ''): Promise<{ products: PurchaseLookupProduct[]; suppliers: PurchaseLookupSupplier[] }> {
  const params = new URLSearchParams();
  if (query.trim()) params.set('q', query.trim());
  return apiClient<{ products: PurchaseLookupProduct[]; suppliers: PurchaseLookupSupplier[] }>(`/purchases/form-options${params.toString() ? `?${params.toString()}` : ''}`);
}

export async function createPurchase(payload: PurchaseCreatePayload): Promise<{ purchase_id: string }> {
  return apiClient<{ purchase_id: string }>('/purchases', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export async function getPurchaseDetail(purchaseId: string): Promise<PurchaseDetail> {
  return apiClient<PurchaseDetail>(`/purchases/${purchaseId}`);
}
