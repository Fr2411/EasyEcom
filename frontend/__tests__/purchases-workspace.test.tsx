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

    await waitFor(() => expect(screen.getByText('Purchase orders could not be loaded')).toBeTruthy());
    const retryButton = screen.getByRole('button', { name: 'Retry' });
    fireEvent.click(retryButton);

    await waitFor(() => expect(mockListPurchaseOrders).toHaveBeenCalledTimes(2));
    await waitFor(() => expect(screen.queryByText('Purchase orders could not be loaded')).toBeNull());
  });
});
