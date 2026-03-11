import { apiClient } from '@/lib/api/client';
import type {
  FinanceReport,
  InventoryReport,
  ProductsReport,
  PurchasesReport,
  ReportsOverview,
  ReturnsReport,
  SalesReport,
} from '@/types/reports';

type ReportFilters = {
  fromDate: string;
  toDate: string;
};

function q(filters: ReportFilters): string {
  return `from_date=${encodeURIComponent(filters.fromDate)}&to_date=${encodeURIComponent(filters.toDate)}`;
}

export function getReportsOverview(filters: ReportFilters) {
  return apiClient<ReportsOverview>(`/reports/overview?${q(filters)}`);
}

export function getSalesReport(filters: ReportFilters) {
  return apiClient<SalesReport>(`/reports/sales?${q(filters)}`);
}

export function getInventoryReport(filters: ReportFilters) {
  return apiClient<InventoryReport>(`/reports/inventory?${q(filters)}`);
}

export function getProductsReport(filters: ReportFilters) {
  return apiClient<ProductsReport>(`/reports/products?${q(filters)}`);
}

export function getFinanceReport(filters: ReportFilters) {
  return apiClient<FinanceReport>(`/reports/finance?${q(filters)}`);
}

export function getReturnsReport(filters: ReportFilters) {
  return apiClient<ReturnsReport>(`/reports/returns?${q(filters)}`);
}

export function getPurchasesReport(filters: ReportFilters) {
  return apiClient<PurchasesReport>(`/reports/purchases?${q(filters)}`);
}

