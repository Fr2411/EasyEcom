import { apiClient } from '@/lib/api/client';
import type {
  FinanceReport,
  InventoryReport,
  ProductsReport,
  ReportsOverview,
  ReturnsReport,
  SalesReport,
} from '@/types/reports';

function buildDateQuery(params: { fromDate?: string; toDate?: string }) {
  const search = new URLSearchParams();
  if (params.fromDate?.trim()) {
    search.set('from_date', params.fromDate.trim());
  }
  if (params.toDate?.trim()) {
    search.set('to_date', params.toDate.trim());
  }
  const text = search.toString();
  return text ? `?${text}` : '';
}

export async function getReportsOverview(params: { fromDate?: string; toDate?: string } = {}) {
  return apiClient<ReportsOverview>(`/reports/overview${buildDateQuery(params)}`);
}

export async function getSalesReport(params: { fromDate?: string; toDate?: string } = {}) {
  return apiClient<SalesReport>(`/reports/sales${buildDateQuery(params)}`);
}

export async function getInventoryReport(params: { fromDate?: string; toDate?: string } = {}) {
  return apiClient<InventoryReport>(`/reports/inventory${buildDateQuery(params)}`);
}

export async function getFinanceReport(params: { fromDate?: string; toDate?: string } = {}) {
  return apiClient<FinanceReport>(`/reports/finance${buildDateQuery(params)}`);
}

export async function getReturnsReport(params: { fromDate?: string; toDate?: string } = {}) {
  return apiClient<ReturnsReport>(`/reports/returns${buildDateQuery(params)}`);
}

export async function getProductsReport(params: { fromDate?: string; toDate?: string } = {}) {
  return apiClient<ProductsReport>(`/reports/products${buildDateQuery(params)}`);
}
