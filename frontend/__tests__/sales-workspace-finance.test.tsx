import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, describe, expect, test, vi } from 'vitest';
import { SalesWorkspace } from '@/components/commerce/sales-workspace';

const {
  mockGetSalesOrders,
  mockGetSalesOrder,
  mockSearchSaleVariants,
  mockSearchEmbeddedCustomers,
  mockConfirmSalesOrder,
  mockFulfillSalesOrder,
  mockCancelSalesOrder,
  mockSaveSalesOrder,
} = vi.hoisted(() => ({
  mockGetSalesOrders: vi.fn(),
  mockGetSalesOrder: vi.fn(),
  mockSearchSaleVariants: vi.fn(),
  mockSearchEmbeddedCustomers: vi.fn(),
  mockConfirmSalesOrder: vi.fn(),
  mockFulfillSalesOrder: vi.fn(),
  mockCancelSalesOrder: vi.fn(),
  mockSaveSalesOrder: vi.fn(),
}));

vi.mock('next/navigation', () => ({
  useSearchParams: () => new URLSearchParams(),
}));

vi.mock('@/lib/api/commerce', () => ({
  getSalesOrders: mockGetSalesOrders,
  getSalesOrder: mockGetSalesOrder,
  searchSaleVariants: mockSearchSaleVariants,
  searchEmbeddedCustomers: mockSearchEmbeddedCustomers,
  saveSalesOrder: mockSaveSalesOrder,
  confirmSalesOrder: mockConfirmSalesOrder,
  fulfillSalesOrder: mockFulfillSalesOrder,
  cancelSalesOrder: mockCancelSalesOrder,
}));

describe('SalesWorkspace finance status', () => {
  afterEach(() => {
    cleanup();
    vi.clearAllMocks();
  });

  test('shows posted-to-finance status after fulfillment', async () => {
    const confirmedOrder = {
      sales_order_id: 'sale-1',
      order_number: 'SO-1001',
      customer_name: 'Amina Buyer',
      customer_phone: '+971500000000',
      customer_email: 'amina@example.com',
      status: 'confirmed',
      shipment_status: 'pending',
      payment_status: 'unpaid',
      total_amount: '500',
      ordered_at: '2026-03-15T10:00:00+00:00',
      finance_status: 'not_posted',
      finance_summary: null,
      lines: [
        {
          sales_order_item_id: 'line-1',
          variant_id: 'variant-1',
          label: 'Runner / Black / 42',
          quantity: '1',
          quantity_fulfilled: '0',
          reserved_quantity: '1',
          line_total: '500',
        },
      ],
    };

    const fulfilledOrder = {
      ...confirmedOrder,
      status: 'completed',
      shipment_status: 'fulfilled',
      finance_status: 'posted',
      finance_summary: {
        transaction_id: 'txn-sale-1',
        amount: '500',
        posted_at: '2026-03-15T11:00:00+00:00',
      },
    };

    mockGetSalesOrders.mockResolvedValueOnce({ items: [confirmedOrder] }).mockResolvedValueOnce({ items: [fulfilledOrder] });
    mockGetSalesOrder.mockResolvedValue(confirmedOrder);
    mockSearchSaleVariants.mockResolvedValue({ items: [] });
    mockSearchEmbeddedCustomers.mockResolvedValue({ items: [] });
    mockSaveSalesOrder.mockResolvedValue({ order: confirmedOrder });
    mockConfirmSalesOrder.mockResolvedValue({ order: confirmedOrder });
    mockFulfillSalesOrder.mockResolvedValue({ order: fulfilledOrder });
    mockCancelSalesOrder.mockResolvedValue({ order: confirmedOrder });

    render(<SalesWorkspace />);

    fireEvent.click(screen.getByRole('tab', { name: /open orders/i }));
    await waitFor(() => expect(screen.getByText('SO-1001')).toBeTruthy());
    fireEvent.click(screen.getByRole('button', { name: /so-1001/i }));
    await waitFor(() => expect(screen.getByRole('button', { name: /fulfill order/i })).toBeTruthy());
    fireEvent.click(screen.getByRole('button', { name: /fulfill order/i }));

    await waitFor(() => expect(screen.getByText(/order fulfilled and stock deducted/i)).toBeTruthy());
    expect(screen.getByText('Posted to finance')).toBeTruthy();
    expect(screen.getByText(/500\.00 at/i)).toBeTruthy();
  });
});
