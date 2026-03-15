import { apiClient } from '@/lib/api/client';
import type { DashboardAnalytics, DashboardRangeKey } from '@/types/dashboard';


function buildQuery(params: Record<string, string | undefined>) {
  const search = new URLSearchParams();
  Object.entries(params).forEach(([key, value]) => {
    if (!value) return;
    search.set(key, value);
  });
  const text = search.toString();
  return text ? `?${text}` : '';
}


export async function getDashboardAnalytics(params: {
  rangeKey?: DashboardRangeKey;
  fromDate?: string;
  toDate?: string;
  locationId?: string;
} = {}) {
  return apiClient<DashboardAnalytics>(
    `/dashboard/analytics${buildQuery({
      range_key: params.rangeKey,
      from_date: params.fromDate,
      to_date: params.toDate,
      location_id: params.locationId,
    })}`
  );
}
