import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, describe, expect, test, vi } from 'vitest';
import { ReturnsWorkspace } from '@/components/commerce/returns-workspace';

const {
  mockGetReturns,
  mockSearchReturnOrders,
  mockGetEligibleReturnLines,
  mockCreateSalesReturn,
  mockRecordSalesReturnRefund,
} = vi.hoisted(() => ({
  mockGetReturns: vi.fn(),
  mockSearchReturnOrders: vi.fn(),
  mockGetEligibleReturnLines: vi.fn(),
  mockCreateSalesReturn: vi.fn(),
  mockRecordSalesReturnRefund: vi.fn(),
}));

vi.mock('next/navigation', () => ({
  useSearchParams: () => new URLSearchParams(),
}));

vi.mock('@/lib/api/commerce', () => ({
  getReturns: mockGetReturns,
  searchReturnOrders: mockSearchReturnOrders,
  getEligibleReturnLines: mockGetEligibleReturnLines,
  createSalesReturn: mockCreateSalesReturn,
  recordSalesReturnRefund: mockRecordSalesReturnRefund,
}));

describe('ReturnsWorkspace', () => {
  afterEach(() => {
    cleanup();
    vi.clearAllMocks();
  });

  test('loads a return and records refund payments explicitly', async () => {
    mockGetReturns.mockResolvedValue({
      items: [
        {
          sales_return_id: 'return-1',
          return_number: 'RT-1001',
          sales_order_id: 'sale-1',
          order_number: 'SO-1001',
          customer_name: 'Amina Buyer',
          customer_phone: '+971500000000',
          status: 'approved',
          refund_status: 'partial',
          notes: 'First return',
          subtotal_amount: '500',
          refund_amount: '150',
          requested_at: '2026-03-15T10:00:00+00:00',
          received_at: '2026-03-16T10:00:00+00:00',
          refund_paid_amount: '50',
          refund_outstanding_amount: '100',
          finance_status: 'posted',
          finance_posted_at: '2026-03-16T11:00:00+00:00',
          recent_refunds: [],
          lines: [
            {
              sales_return_item_id: 'rline-1',
              sales_order_item_id: 'line-1',
              variant_id: 'variant-1',
              product_name: 'Runner',
              label: 'Runner / Black / 42',
              quantity: '1',
              restock_quantity: '1',
              disposition: 'restock',
              unit_refund_amount: '150',
              line_total: '150',
            },
          ],
        },
      ],
    });
    mockSearchReturnOrders.mockResolvedValue({ items: [] });
    mockGetEligibleReturnLines.mockResolvedValue({
      sales_order_id: 'sale-1',
      order_number: 'SO-1001',
      customer_name: 'Amina Buyer',
      customer_phone: '+971500000000',
      lines: [],
    });
    mockCreateSalesReturn.mockResolvedValue({
      sales_return_id: 'return-1',
      return_number: 'RT-1001',
      sales_order_id: 'sale-1',
      order_number: 'SO-1001',
      customer_name: 'Amina Buyer',
      customer_phone: '+971500000000',
      status: 'approved',
      refund_status: 'partial',
      notes: 'First return',
      subtotal_amount: '500',
      refund_amount: '150',
      requested_at: '2026-03-15T10:00:00+00:00',
      received_at: '2026-03-16T10:00:00+00:00',
      refund_paid_amount: '50',
      refund_outstanding_amount: '100',
      finance_status: 'posted',
      finance_posted_at: '2026-03-16T11:00:00+00:00',
      recent_refunds: [],
      lines: [],
    });
    mockRecordSalesReturnRefund.mockResolvedValue({
      sales_return_id: 'return-1',
      return_number: 'RT-1001',
      sales_order_id: 'sale-1',
      order_number: 'SO-1001',
      customer_name: 'Amina Buyer',
      customer_phone: '+971500000000',
      status: 'approved',
      refund_status: 'paid',
      notes: 'First return',
      subtotal_amount: '500',
      refund_amount: '150',
      requested_at: '2026-03-15T10:00:00+00:00',
      received_at: '2026-03-16T10:00:00+00:00',
      refund_paid_amount: '150',
      refund_outstanding_amount: '0',
      finance_status: 'posted',
      finance_posted_at: '2026-03-16T11:00:00+00:00',
      recent_refunds: [
        {
          transaction_id: 'txn-refund-1',
          amount: '100',
          method: 'bank transfer',
          reference: 'RF-1001',
          note: 'Balance refund',
          posted_at: '2026-03-16T12:00:00+00:00',
        },
      ],
      lines: [],
    });

    render(<ReturnsWorkspace />);

    fireEvent.click(screen.getByRole('tab', { name: /history/i }));
    await waitFor(() => expect(screen.getByText('RT-1001')).toBeTruthy());
    fireEvent.click(screen.getByRole('button', { name: /open refund details/i }));

    await waitFor(() => expect(screen.getByText(/refund status: partial/i)).toBeTruthy());
    fireEvent.change(screen.getByLabelText(/amount/i), { target: { value: '100' } });
    fireEvent.change(screen.getByLabelText(/method/i), { target: { value: 'bank transfer' } });
    fireEvent.change(screen.getByLabelText(/reference/i), { target: { value: 'RF-1001' } });
    fireEvent.change(screen.getByLabelText(/note/i), { target: { value: 'Balance refund' } });
    fireEvent.click(screen.getByRole('button', { name: /record refund payment/i }));

    await waitFor(() =>
      expect(mockRecordSalesReturnRefund).toHaveBeenCalledWith(
        'return-1',
        expect.objectContaining({
          amount: '100',
          method: 'bank transfer',
          reference: 'RF-1001',
          note: 'Balance refund',
        })
      )
    );
  });
});
