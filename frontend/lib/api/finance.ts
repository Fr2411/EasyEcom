import { apiClient } from '@/lib/api/client';
import type { FinanceOverview } from '@/types/finance';

export async function getFinanceOverview() {
  return apiClient<FinanceOverview>('/finance/overview');
}
