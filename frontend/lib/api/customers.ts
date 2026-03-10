import { apiClient } from '@/lib/api/client';
import type {
  CustomerListResponse,
  CustomerMutationResponse,
  CustomerPayload,
} from '@/types/customers';

export async function getCustomers(query = ''): Promise<CustomerListResponse> {
  const params = new URLSearchParams();
  if (query.trim()) params.set('q', query.trim());
  return apiClient<CustomerListResponse>(`/customers${params.toString() ? `?${params.toString()}` : ''}`);
}

export async function createCustomer(payload: CustomerPayload): Promise<CustomerMutationResponse> {
  return apiClient<CustomerMutationResponse>('/customers', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export async function updateCustomer(
  customerId: string,
  payload: Partial<CustomerPayload>,
): Promise<CustomerMutationResponse> {
  return apiClient<CustomerMutationResponse>(`/customers/${customerId}`, {
    method: 'PATCH',
    body: JSON.stringify(payload),
  });
}
