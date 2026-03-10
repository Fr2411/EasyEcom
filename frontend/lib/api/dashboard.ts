import { apiClient } from '@/lib/api/client';
import type { DashboardOverview } from '@/types/dashboard';

export async function getDashboardOverview(): Promise<DashboardOverview> {
  return apiClient<DashboardOverview>('/dashboard/overview');
}
