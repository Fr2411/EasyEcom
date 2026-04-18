import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, describe, expect, test, vi } from 'vitest';
import { ApiNetworkError } from '@/lib/api/client';
import { PurchasesWorkspace } from '@/components/purchases/purchases-workspace';

const { mockListPurchaseOrders } = vi.hoisted(() => ({
  mockListPurchaseOrders: vi.fn(),
}));

vi.mock('@/lib/api/purchases', () => ({
  listPurchaseOrders: mockListPurchaseOrders,
}));

afterEach(() => {
  cleanup();
  mockListPurchaseOrders.mockReset();
});

describe('PurchasesWorkspace', () => {
  test('shows retry action for failure state and retries loading when pressed', async () => {
    mockListPurchaseOrders
      .mockRejectedValueOnce(new ApiNetworkError('fetch failed (https://api.easy-ecom.online/purchases/orders)'))
      .mockResolvedValueOnce({ items: [] });

    render(<PurchasesWorkspace />);

    await waitFor(() => expect(screen.getByText('We could not refresh purchase orders right now')).toBeTruthy());
    expect(screen.getByText('Existing purchase orders and received stock remain unchanged.')).toBeTruthy();
    const receiveStockLinks = screen.getAllByRole('link', { name: 'Open Receive Stock' });
    expect(receiveStockLinks.some((link) => link.getAttribute('href') === '/inventory?tab=receive')).toBe(true);
    const retryButton = screen.getByRole('button', { name: 'Retry purchase orders' });
    fireEvent.click(retryButton);

    await waitFor(() => expect(mockListPurchaseOrders).toHaveBeenCalledTimes(2));
    await waitFor(() => expect(screen.queryByText('We could not refresh purchase orders right now')).toBeNull());
  });

  test('shows repeated-failure guidance when retry does not recover', async () => {
    mockListPurchaseOrders
      .mockRejectedValueOnce(new ApiNetworkError('fetch failed (https://api.easy-ecom.online/purchases/orders)'))
      .mockRejectedValueOnce(new ApiNetworkError('fetch failed (https://api.easy-ecom.online/purchases/orders)'));

    render(<PurchasesWorkspace />);

    await waitFor(() => expect(screen.getByText('We could not refresh purchase orders right now')).toBeTruthy());
    expect(screen.queryByText('Repeated retries are still failing. Open Dashboard to refresh your session, wait a moment, then return to Purchases.')).toBeNull();

    fireEvent.click(screen.getByRole('button', { name: 'Retry purchase orders' }));

    await waitFor(() => expect(mockListPurchaseOrders).toHaveBeenCalledTimes(2));
    await waitFor(() =>
      expect(
        screen.getByText(
          'Repeated retries are still failing. Open Dashboard to refresh your session, wait a moment, then return to Purchases.'
        )
      ).toBeTruthy()
    );
  });
});
