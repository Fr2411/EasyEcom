import { apiClient } from '@/lib/api/client';
import type {
  SaleCreatePayload,
  SaleDetail,
  SaleListItem,
  SaleLookupCustomer,
  SaleLookupProduct,
} from '@/types/sales';

export async function getSales(query = ''): Promise<{ items: SaleListItem[] }> {
  const params = new URLSearchParams();
  if (query.trim()) params.set('q', query.trim());
  return apiClient<{ items: SaleListItem[] }>(`/sales${params.toString() ? `?${params.toString()}` : ''}`);
}

export async function getSalesFormOptions(query = ''): Promise<{ customers: SaleLookupCustomer[]; products: SaleLookupProduct[] }> {
  const params = new URLSearchParams();
  if (query.trim()) params.set('q', query.trim());
  return apiClient<{ customers: SaleLookupCustomer[]; products: SaleLookupProduct[] }>(`/sales/form-options${params.toString() ? `?${params.toString()}` : ''}`);
}

export async function createSale(payload: SaleCreatePayload): Promise<{ sale_id: string }> {
  return apiClient<{ sale_id: string }>('/sales', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export async function getSaleDetail(saleId: string): Promise<SaleDetail> {
  return apiClient<SaleDetail>(`/sales/${saleId}`);
}
