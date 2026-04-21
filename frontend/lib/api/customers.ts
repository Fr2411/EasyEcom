import { apiClient } from '@/lib/api/client';
import type { CustomerWorkspace } from '@/types/customers';

function buildQuery(q: string) {
  const trimmed = q.trim();
  if (!trimmed) return '';
  return `?q=${encodeURIComponent(trimmed)}`;
}

export async function getCustomersWorkspace(q = '') {
  return apiClient<CustomerWorkspace>(`/customers/workspace${buildQuery(q)}`);
}
