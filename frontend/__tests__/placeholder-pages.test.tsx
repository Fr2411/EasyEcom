import { cleanup, render, screen } from '@testing-library/react';
import { afterEach, describe, expect, test } from 'vitest';
import AdminPage from '@/app/(app)/admin/page';
import AiReviewPage from '@/app/(app)/ai-review/page';
import AutomationPage from '@/app/(app)/automation/page';
import CatalogPage from '@/app/(app)/catalog/page';
import CustomersPage from '@/app/(app)/customers/page';
import DashboardPage from '@/app/(app)/dashboard/page';
import FinancePage from '@/app/(app)/finance/page';
import IntegrationsPage from '@/app/(app)/integrations/page';
import InventoryPage from '@/app/(app)/inventory/page';
import HomePage from '@/app/(app)/page';
import ProductsStockPage from '@/app/(app)/products-stock/page';
import PurchasesPage from '@/app/(app)/purchases/page';
import ReportsPage from '@/app/(app)/reports/page';
import ReturnsPage from '@/app/(app)/returns/page';
import SalesPage from '@/app/(app)/sales/page';
import SettingsPage from '@/app/(app)/settings/page';

const cases = [
  ['Home', HomePage],
  ['Dashboard', DashboardPage],
  ['Reports', ReportsPage],
  ['Catalog', CatalogPage],
  ['Customers', CustomersPage],
  ['Inventory', InventoryPage],
  ['Products & Stock', ProductsStockPage],
  ['Sales', SalesPage],
  ['Finance', FinancePage],
  ['Returns', ReturnsPage],
  ['Purchases', PurchasesPage],
  ['Admin & Roles', AdminPage],
  ['Integrations & Channels', IntegrationsPage],
  ['AI Review Inbox', AiReviewPage],
  ['Automation', AutomationPage],
  ['Settings', SettingsPage],
] as const;

describe('Placeholder business pages', () => {
  afterEach(() => {
    cleanup();
  });

  test.each(cases)('%s renders the reset placeholder', (_title, PageComponent) => {
    render(<PageComponent />);

    expect(screen.getAllByText('Reset In Progress').length).toBeGreaterThan(0);
    expect(screen.getByText(/intentionally blank right now/i)).toBeTruthy();
  });
});
