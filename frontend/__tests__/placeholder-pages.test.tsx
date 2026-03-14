import { cleanup, render, screen, waitFor } from '@testing-library/react';
import { afterEach, describe, expect, test, vi } from 'vitest';
import AiReviewPage from '@/app/(app)/ai-review/page';
import AutomationPage from '@/app/(app)/automation/page';
import CatalogPage from '@/app/(app)/catalog/page';
import CustomersPage from '@/app/(app)/customers/page';
import DashboardPage from '@/app/(app)/dashboard/page';
import FinancePage from '@/app/(app)/finance/page';
import IntegrationsPage from '@/app/(app)/integrations/page';
import InventoryPage from '@/app/(app)/inventory/page';
import HomePage from '@/app/(app)/page';
import ReportsPage from '@/app/(app)/reports/page';
import ReturnsPage from '@/app/(app)/returns/page';
import SalesPage from '@/app/(app)/sales/page';
import SettingsPage from '@/app/(app)/settings/page';

vi.mock('next/navigation', () => ({
  useSearchParams: () => new URLSearchParams(),
  redirect: vi.fn(),
}));

vi.mock('@/lib/api/commerce', () => ({
  getCatalogWorkspace: vi.fn(async () => ({
    query: '',
    has_multiple_locations: false,
    active_location: { location_id: 'loc-1', name: 'Main', is_default: true },
    locations: [{ location_id: 'loc-1', name: 'Main', is_default: true }],
    categories: [],
    suppliers: [],
    items: [],
  })),
  saveCatalogProduct: vi.fn(),
  getInventoryWorkspace: vi.fn(async () => ({
    query: '',
    has_multiple_locations: false,
    active_location: { location_id: 'loc-1', name: 'Main', is_default: true },
    locations: [{ location_id: 'loc-1', name: 'Main', is_default: true }],
    stock_items: [],
    low_stock_items: [],
  })),
  receiveInventoryStock: vi.fn(),
  createInventoryAdjustment: vi.fn(),
  getSalesOrders: vi.fn(async () => ({ items: [] })),
  getSalesOrder: vi.fn(),
  searchSaleVariants: vi.fn(async () => ({ items: [] })),
  searchEmbeddedCustomers: vi.fn(async () => ({ items: [] })),
  saveSalesOrder: vi.fn(),
  confirmSalesOrder: vi.fn(),
  fulfillSalesOrder: vi.fn(),
  cancelSalesOrder: vi.fn(),
  getReturns: vi.fn(async () => ({ items: [] })),
  searchReturnOrders: vi.fn(async () => ({ items: [] })),
  getEligibleReturnLines: vi.fn(),
  createSalesReturn: vi.fn(),
}));

const cases = [
  ['Home', HomePage, /the product foundation is live again/i],
  ['Dashboard', DashboardPage, /pilot rebuild command center/i],
  ['Reports', ReportsPage, /reset in progress|rebuild foundation/i],
  ['Catalog', CatalogPage, /variant-first catalog/i],
  ['Customers', CustomersPage, /embedded customer records/i],
  ['Inventory', InventoryPage, /variant-level inventory control/i],
  ['Sales', SalesPage, /order-first sales workspace/i],
  ['Finance', FinancePage, /reset in progress|rebuild foundation/i],
  ['Returns', ReturnsPage, /return and restock control/i],
  ['Integrations & Channels', IntegrationsPage, /reset in progress|rebuild foundation/i],
  ['AI Review Inbox', AiReviewPage, /reset in progress|rebuild foundation/i],
  ['Automation', AutomationPage, /reset in progress|rebuild foundation/i],
  ['Settings', SettingsPage, /reset in progress|rebuild foundation/i],
] as const;

describe('Business pages', () => {
  afterEach(() => {
    cleanup();
  });

  test.each(cases)('%s renders its current workspace shell', async (_title, PageComponent, matcher) => {
    render(<PageComponent />);
    await waitFor(() => expect(screen.getByText(matcher)).toBeTruthy());
  });

  test('purchases route redirects into inventory receive stock', async () => {
    vi.resetModules();
    const redirectMock = vi.fn();
    vi.doMock('next/navigation', () => ({
      redirect: redirectMock,
    }));

    const module = await import('@/app/(app)/purchases/page');
    module.default();

    expect(redirectMock).toHaveBeenCalledWith('/inventory?tab=receive');
    vi.doUnmock('next/navigation');
    vi.resetModules();
  });

  test('legacy products-stock route redirects to catalog', async () => {
    vi.resetModules();
    const redirectMock = vi.fn();
    vi.doMock('next/navigation', () => ({
      redirect: redirectMock,
    }));

    const module = await import('@/app/(app)/products-stock/page');
    module.default();

    expect(redirectMock).toHaveBeenCalledWith('/catalog');
    vi.doUnmock('next/navigation');
    vi.resetModules();
  });
});
