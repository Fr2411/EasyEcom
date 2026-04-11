import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, test, vi } from 'vitest';
import DashboardPage from '@/app/(app)/dashboard/page';


const { getDashboardAnalytics } = vi.hoisted(() => ({
  getDashboardAnalytics: vi.fn(),
}));

vi.mock('@/lib/api/dashboard', () => ({
  getDashboardAnalytics,
}));


function buildPayload(canViewFinancialMetrics = true) {
  return {
    generated_at: '2026-03-15T10:00:00+00:00',
    has_multiple_locations: true,
    selected_location_id: null,
    locations: [
      { location_id: 'loc-1', name: 'Main Warehouse', is_default: true },
      { location_id: 'loc-2', name: 'Outlet', is_default: false },
    ],
    applied_range: {
      range_key: 'mtd',
      label: 'Month to date',
      timezone: 'UTC',
      from_date: '2026-03-01',
      to_date: '2026-03-15',
      previous_from_date: '2026-02-14',
      previous_to_date: '2026-02-28',
      bucket: 'day',
      days: 15,
    },
    visibility: { can_view_financial_metrics: canViewFinancialMetrics },
    kpis: [
      {
        id: 'completed_sales_revenue',
        label: 'Completed Sales',
        value: '205.00',
        unit: 'money',
        delta_value: '20.00',
        delta_direction: 'up',
        help_text: null,
        is_estimated: false,
        unavailable_reason: null,
      },
      {
        id: 'units_sold',
        label: 'Units Sold',
        value: '3.000',
        unit: 'quantity',
        delta_value: '1.000',
        delta_direction: 'up',
        help_text: null,
        is_estimated: false,
        unavailable_reason: null,
      },
    ],
    insight_cards: [
      {
        id: 'replenish_winners',
        title: 'Replenish Winners',
        summary: 'Products moving quickly with limited days of cover.',
        metric_label: 'Products under 14 days cover',
        metric_value: '2',
        tone: 'warning',
        entity_name: 'Trail Runner',
        path: '/inventory?tab=low-stock',
        unavailable_reason: null,
      },
    ],
    charts: {
      revenue_profit_trend: {
        items: [
          { period: 'Mar 01', revenue: '75.00', estimated_gross_profit: '35.00' },
          { period: 'Mar 02', revenue: '130.00', estimated_gross_profit: '60.00' },
        ],
        unavailable_reason: canViewFinancialMetrics ? null : 'Financial metrics are hidden for your role.',
      },
      stock_movement_trend: [
        { period: 'Mar 01', stock_received: '10.000', sale_fulfilled: '2.000', sales_return_restock: '0.000', adjustment: '0.000' },
        { period: 'Mar 02', stock_received: '0.000', sale_fulfilled: '1.000', sales_return_restock: '1.000', adjustment: '0.000' },
      ],
      returns_trend: {
        items: [
          { period: 'Mar 01', returns_count: 0, refund_amount: canViewFinancialMetrics ? '0.00' : null },
          { period: 'Mar 02', returns_count: 1, refund_amount: canViewFinancialMetrics ? '75.00' : null },
        ],
      },
      product_opportunity_matrix: {
        items: canViewFinancialMetrics ? [
          {
            product_id: 'prod-1',
            product_name: 'Trail Runner',
            units_sold: '3.000',
            sales_qty_per_day: '0.20',
            estimated_margin_percent: '46.34',
            inventory_cost_value: '360.00',
            revenue: '205.00',
            estimated_gross_profit: '95.00',
            available_qty: '9.000',
            days_cover: '45.00',
          },
        ] : [],
        unavailable_reason: canViewFinancialMetrics ? null : 'Financial metrics are hidden for your role.',
      },
    },
    tables: {
      stock_investment_by_product: [
        {
          product_id: 'prod-1',
          product_name: 'Trail Runner',
          on_hand_qty: '9.000',
          available_qty: '9.000',
          inventory_cost_value: canViewFinancialMetrics ? '360.00' : null,
          active_variants: 2,
        },
      ],
      low_stock_variants: [
        {
          variant_id: 'var-1',
          product_id: 'prod-1',
          product_name: 'Trail Runner',
          label: 'Trail Runner / 42 / Black',
          on_hand_qty: '2.000',
          reserved_qty: '0.000',
          available_qty: '2.000',
          reorder_level: '2.000',
          inventory_cost_value: canViewFinancialMetrics ? '80.00' : null,
        },
      ],
      top_products_by_units_sold: [
        {
          product_id: 'prod-1',
          product_name: 'Trail Runner',
          units_sold: '3.000',
          revenue: '205.00',
          estimated_gross_profit: canViewFinancialMetrics ? '95.00' : null,
          estimated_margin_percent: canViewFinancialMetrics ? '46.34' : null,
        },
      ],
      top_products_by_revenue: {
        items: canViewFinancialMetrics ? [
          {
            product_id: 'prod-1',
            product_name: 'Trail Runner',
            units_sold: '3.000',
            revenue: '205.00',
            estimated_gross_profit: '95.00',
            estimated_margin_percent: '46.34',
          },
        ] : [],
        unavailable_reason: canViewFinancialMetrics ? null : 'Financial metrics are hidden for your role.',
      },
      top_products_by_estimated_gross_profit: {
        items: canViewFinancialMetrics ? [
          {
            product_id: 'prod-1',
            product_name: 'Trail Runner',
            units_sold: '3.000',
            revenue: '205.00',
            estimated_gross_profit: '95.00',
            estimated_margin_percent: '46.34',
          },
        ] : [],
        unavailable_reason: canViewFinancialMetrics ? null : 'Financial metrics are hidden for your role.',
      },
      slow_movers: [],
      recent_activity: [
        {
          timestamp: '2026-03-15T10:00:00+00:00',
          event_type: 'Stock received',
          product_name: 'Trail Runner',
          label: 'Trail Runner / 42 / Black',
          quantity: '5.000',
          note: 'Seed stock',
        },
      ],
    },
  };
}


describe('Dashboard page', () => {
  beforeEach(() => {
    getDashboardAnalytics.mockReset();
    getDashboardAnalytics.mockResolvedValue(buildPayload(true));
  });

  afterEach(() => {
    cleanup();
  });

  test('loads month-to-date analytics by default and renders key sections', async () => {
    render(<DashboardPage />);

    await waitFor(() => expect(getDashboardAnalytics).toHaveBeenCalled());
    expect(getDashboardAnalytics.mock.calls[0][0]?.rangeKey).toBe('mtd');
    expect(await screen.findByText(/business analytics dashboard/i)).toBeTruthy();
    expect(screen.getByText(/revenue vs estimated gross profit/i)).toBeTruthy();
    expect(screen.getByText(/sales qty\/day vs avg\. margin/i)).toBeTruthy();
    expect(screen.getAllByText(/trail runner/i).length).toBeGreaterThan(0);
  });

  test('changing duration refetches dashboard data', async () => {
    render(<DashboardPage />);

    await waitFor(() => expect(getDashboardAnalytics).toHaveBeenCalledTimes(1));
    fireEvent.change(screen.getByLabelText('Dashboard duration'), { target: { value: 'last_30_days' } });

    await waitFor(() => expect(getDashboardAnalytics).toHaveBeenCalledTimes(2));
    expect(getDashboardAnalytics.mock.calls[1][0]?.rangeKey).toBe('last_30_days');
  });

  test('staff view hides financial-only sections', async () => {
    getDashboardAnalytics.mockResolvedValue(buildPayload(false));
    render(<DashboardPage />);

    await screen.findByText(/stock movement trend/i);
    expect(screen.queryByText(/revenue vs estimated gross profit/i)).toBeNull();
    expect(screen.queryByText(/top products by revenue/i)).toBeNull();
  });

  test('removed dashboard labels do not render', async () => {
    render(<DashboardPage />);

    await screen.findByText(/business analytics dashboard/i);
    expect(screen.queryByText(/^today$/i)).toBeNull();
    expect(screen.queryByText(/^open reports$/i)).toBeNull();
    expect(screen.queryByText(/^workspace$/i)).toBeNull();
  });
});
