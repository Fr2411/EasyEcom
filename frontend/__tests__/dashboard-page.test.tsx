import { render, screen, waitFor } from '@testing-library/react';
import { describe, expect, test, vi } from 'vitest';

vi.mock('@/lib/api/dashboard', () => ({
  getDashboardOverview: vi.fn(async () => ({
    generated_at: '2026-01-01T00:00:00Z',
    kpis: {
      total_products: 4,
      total_variants: 12,
      current_stock_units: 240,
      low_stock_items: 2,
    },
    business_health: {
      inventory_value: 5000,
      recent_stock_movements_count: 7,
      sales_count_last_30_days: 5,
      revenue_last_30_days: 2500,
    },
    recent_activity: [],
    top_products: [],
  })),
}));

import DashboardPage from '@/app/(app)/dashboard/page';

describe('DashboardPage', () => {
  test('renders operational dashboard content', async () => {
    render(<DashboardPage />);

    expect(screen.getByRole('heading', { name: 'Dashboard' })).toBeTruthy();
    await waitFor(() => {
      expect(screen.getByText('Total Products')).toBeTruthy();
      expect(screen.getByText('Top Products by Stock Value')).toBeTruthy();
    });
  });
});
