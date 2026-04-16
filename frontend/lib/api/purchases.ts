import { apiClient } from '@/lib/api/client';
import type { PurchaseDetail, PurchaseOrdersResponse } from '@/types/purchases';

function buildQuery(params: { status?: string; q?: string }) {
  const search = new URLSearchParams();
  if (params.status?.trim()) {
    search.set('status', params.status.trim());
  }
  if (params.q?.trim()) {
    search.set('q', params.q.trim());
  }
  const text = search.toString();
  return text ? `?${text}` : '';
}

export async function listPurchaseOrders(params: { status?: string; q?: string } = {}) {
  return apiClient<PurchaseOrdersResponse>(`/purchases/orders${buildQuery(params)}`);
}

export async function getPurchaseOrder(purchaseOrderId: string) {
  return apiClient<PurchaseDetail>(`/purchases/orders/${purchaseOrderId}`);
}
