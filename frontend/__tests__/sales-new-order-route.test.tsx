import { describe, expect, test, vi } from 'vitest';
import SalesNewOrderAliasPage from '@/app/(app)/sales/new-order/page';

const redirectMock = vi.fn();

vi.mock('next/navigation', () => ({
  redirect: (path: string) => redirectMock(path),
}));

describe('sales new-order alias route', () => {
  test('redirects /sales/new-order to /sales', () => {
    SalesNewOrderAliasPage();
    expect(redirectMock).toHaveBeenCalledWith('/sales');
  });
});
