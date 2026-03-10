import { apiClient } from '@/lib/api/client';
import type { ReturnCreatePayload, ReturnDetail, ReturnSummary, ReturnableSale, ReturnableSaleDetail } from '@/types/returns';

export async function getReturns(query = ''): Promise<{ items: ReturnSummary[] }> {
  const params = new URLSearchParams();
  if (query.trim()) params.set('q', query.trim());
  return apiClient<{ items: ReturnSummary[] }>(`/returns${params.toString() ? `?${params.toString()}` : ''}`);
}

export async function getReturnSalesLookup(query = ''): Promise<{ items: ReturnableSale[] }> {
  const params = new URLSearchParams();
  if (query.trim()) params.set('q', query.trim());
  return apiClient<{ items: ReturnableSale[] }>(`/returns/sales-lookup${params.toString() ? `?${params.toString()}` : ''}`);
}

export async function getReturnableSale(saleId: string): Promise<ReturnableSaleDetail> {
  return apiClient<ReturnableSaleDetail>(`/returns/sales/${saleId}`);
}

export async function createReturn(payload: ReturnCreatePayload): Promise<{ return_id: string; return_no: string }> {
  return apiClient<{ return_id: string; return_no: string }>('/returns', { method: 'POST', body: JSON.stringify(payload) });
}

export async function getReturnDetail(returnId: string): Promise<ReturnDetail> {
  return apiClient<ReturnDetail>(`/returns/${returnId}`);
}
