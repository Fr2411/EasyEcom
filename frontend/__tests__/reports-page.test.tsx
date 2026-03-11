import { render, screen, waitFor } from '@testing-library/react';
import { describe, expect, test, vi } from 'vitest';

vi.mock('@/lib/api/reports', () => ({
  getReportsOverview: vi.fn(async () => ({ from_date: '2026-01-01', to_date: '2026-01-31', sales_revenue_total: 1200, sales_count: 8, expense_total: 300, returns_total: 50, purchases_total: 500 })),
  getSalesReport: vi.fn(async () => ({ from_date: '2026-01-01', to_date: '2026-01-31', sales_count: 8, revenue_total: 1200, sales_trend: [{ period: '2026-01-01', value: 200 }], top_products: [], top_customers: [], deferred_metrics: [] })),
  getInventoryReport: vi.fn(async () => ({ from_date: '2026-01-01', to_date: '2026-01-31', total_skus_with_stock: 5, total_stock_units: 40, low_stock_items: [], stock_movement_trend: [], inventory_value: null, deferred_metrics: [{ metric: 'inventory_value', reason: 'deferred' }] })),
  getProductsReport: vi.fn(async () => ({ from_date: '2026-01-01', to_date: '2026-01-31', highest_selling: [], low_or_zero_movement: [], deferred_metrics: [] })),
  getFinanceReport: vi.fn(async () => ({ from_date: '2026-01-01', to_date: '2026-01-31', expense_total: 300, expense_trend: [], receivables_total: 100, payables_total: 50, net_operating_snapshot: 900, deferred_metrics: [] })),
  getReturnsReport: vi.fn(async () => ({ from_date: '2026-01-01', to_date: '2026-01-31', returns_count: 1, return_qty_total: 1, return_amount_total: 50, deferred_metrics: [] })),
  getPurchasesReport: vi.fn(async () => ({ from_date: '2026-01-01', to_date: '2026-01-31', purchases_count: 2, purchases_subtotal: 500, purchases_trend: [], deferred_metrics: [] })),
}));

import ReportsPage from '@/app/(app)/reports/page';

describe('ReportsPage', () => {
  test('renders reporting workspace and deferred block', async () => {
    render(<ReportsPage />);
    expect(screen.getByRole('heading', { name: 'Reporting & Analytics' })).toBeTruthy();
    await waitFor(() => {
      expect(screen.getByText('Sales Revenue')).toBeTruthy();
      expect(screen.getByText('Deferred metrics')).toBeTruthy();
    });
  });
});
