import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, describe, expect, test, vi } from 'vitest';
import { FinanceWorkspace } from '@/components/finance/finance-workspace';

const {
  mockGetFinanceWorkspace,
  mockCreateFinanceTransaction,
  mockUpdateFinanceTransaction,
} = vi.hoisted(() => ({
  mockGetFinanceWorkspace: vi.fn(),
  mockCreateFinanceTransaction: vi.fn(),
  mockUpdateFinanceTransaction: vi.fn(),
}));

vi.mock('@/lib/api/finance', () => ({
  getFinanceWorkspace: mockGetFinanceWorkspace,
  createFinanceTransaction: mockCreateFinanceTransaction,
  updateFinanceTransaction: mockUpdateFinanceTransaction,
}));

function workspaceFixture() {
  return {
    overview: {
      revenue: 500,
      cash_collected: 380,
      refunds_paid: 50,
      expenses: 60,
      receivables: 150,
      payables: 20,
      cash_in: 380,
      cash_out: 110,
      net_operating: 270,
    },
    commerce_transactions: [
      {
        transaction_id: 'txn-sale-1',
        occurred_at: '2026-03-15T10:00:00+00:00',
        origin_type: 'sale_fulfillment',
        origin_id: 'sale-1',
        direction: 'in',
        status: 'posted',
        currency_code: 'AED',
        amount: 500,
        reference: 'SO-1001',
        note: 'Recognized sale',
        counterparty_type: 'customer',
        counterparty_id: 'cust-1',
        counterparty_name: 'Amina Buyer',
        source_label: 'From Sales',
        editable: false,
      },
    ],
    manual_transactions: [
      {
        transaction_id: 'txn-manual-1',
        occurred_at: '2026-03-16T09:00:00+00:00',
        origin_type: 'manual_expense',
        origin_id: null,
        direction: 'out',
        status: 'unpaid',
        currency_code: 'AED',
        amount: 60,
        reference: 'EXP-1001',
        note: 'Office rent',
        counterparty_type: 'vendor',
        counterparty_id: null,
        counterparty_name: 'Landlord',
        source_label: 'Manual expense',
        editable: true,
      },
    ],
    recent_refunds: [
      {
        transaction_id: 'txn-refund-1',
        occurred_at: '2026-03-16T11:00:00+00:00',
        origin_type: 'return_refund',
        origin_id: 'return-1',
        direction: 'out',
        status: 'posted',
        currency_code: 'AED',
        amount: 50,
        reference: 'RT-1001',
        note: 'Refund paid via bank transfer',
        counterparty_type: 'customer',
        counterparty_id: 'cust-1',
        counterparty_name: 'Amina Buyer',
        source_label: 'From Returns',
        editable: false,
      },
    ],
    receivables: [
      {
        sale_id: 'sale-1',
        sale_no: 'SO-1001',
        customer_id: 'cust-1',
        customer_name: 'Amina Buyer',
        sale_date: '2026-03-15T10:00:00+00:00',
        grand_total: 500,
        amount_paid: 350,
        outstanding_balance: 150,
        payment_status: 'partial',
      },
    ],
    payables: [
      {
        transaction_id: 'txn-manual-1',
        reference: 'EXP-1001',
        vendor_name: 'Landlord',
        origin_type: 'manual_expense',
        occurred_at: '2026-03-16T09:00:00+00:00',
        amount: 20,
        status: 'unpaid',
        note: 'Office rent',
      },
    ],
  };
}

describe('FinanceWorkspace', () => {
  afterEach(() => {
    cleanup();
    vi.clearAllMocks();
  });

  test('renders split finance sections for commerce, manual entries, receivables, and refunds', async () => {
    mockGetFinanceWorkspace.mockResolvedValue(workspaceFixture());

    render(<FinanceWorkspace />);

    await waitFor(() => expect(screen.getByText('Record manual finance entry')).toBeTruthy());
    expect(screen.getByText('Finance first-run checklist')).toBeTruthy();
    expect(screen.getByText('Commerce-origin transactions (read-only)')).toBeTruthy();
    expect(screen.getByText('Manual finance transactions (editable)')).toBeTruthy();
    expect(screen.getByText('Receivables and recent refunds')).toBeTruthy();
    expect(screen.getAllByText('From Sales').length).toBeGreaterThan(0);
    expect(screen.getAllByText('From Returns').length).toBeGreaterThan(0);
    expect(screen.getAllByText('SO-1001').length).toBeGreaterThan(0);
    expect(screen.getByText('RT-1001')).toBeTruthy();
  });

  test('records manual finance entries using the manual-only entry types', async () => {
    mockGetFinanceWorkspace.mockResolvedValue({
      overview: workspaceFixture().overview,
      commerce_transactions: [],
      manual_transactions: [],
      recent_refunds: [],
      receivables: [],
      payables: [],
    });
    mockCreateFinanceTransaction.mockResolvedValue({
      transaction_id: 'txn-manual-2',
      origin_type: 'manual_expense',
      origin_id: null,
      occurred_at: '2026-03-16T10:00:00+00:00',
      direction: 'out',
      status: 'unpaid',
      currency_code: 'AED',
      amount: 75,
      reference: 'BILL-2001',
      note: 'Courier invoice',
      counterparty_type: 'vendor',
      counterparty_id: null,
      counterparty_name: 'FastShip',
      source_label: 'Manual expense',
      editable: true,
    });

    render(<FinanceWorkspace />);

    await waitFor(() => expect(screen.getByText('Record manual finance entry')).toBeTruthy());
    fireEvent.change(screen.getByLabelText(/entry type/i), { target: { value: 'manual_expense' } });
    fireEvent.change(screen.getByLabelText(/^amount$/i), { target: { value: '75' } });
    fireEvent.change(screen.getByLabelText(/reference/i), { target: { value: 'BILL-2001' } });
    fireEvent.change(screen.getByLabelText(/^counterparty \*/i), { target: { value: 'FastShip' } });
    fireEvent.change(screen.getByLabelText(/note/i), { target: { value: 'Courier invoice' } });
    fireEvent.change(screen.getByLabelText(/status/i), { target: { value: 'unpaid' } });
    fireEvent.click(screen.getByRole('button', { name: /record manual expense/i }));

    await waitFor(() =>
      expect(mockCreateFinanceTransaction).toHaveBeenCalledWith(
        expect.objectContaining({
          origin_type: 'manual_expense',
          direction: 'out',
          amount: 75,
          reference: 'BILL-2001',
          counterparty_name: 'FastShip',
          counterparty_type: 'vendor',
          note: 'Courier invoice',
          status: 'unpaid',
        })
      )
    );
  });

  test('allows editing existing manual payments while leaving commerce-origin rows read-only', async () => {
    mockGetFinanceWorkspace.mockResolvedValue({
      ...workspaceFixture(),
      manual_transactions: [
        {
          transaction_id: 'txn-manual-1',
          occurred_at: '2026-03-16T09:00:00+00:00',
          origin_type: 'manual_payment',
          origin_id: null,
          direction: 'in',
          status: 'completed',
          currency_code: 'AED',
          amount: 120,
          reference: 'PAY-1001',
          note: 'Updated receipt',
          counterparty_type: 'internal',
          counterparty_id: null,
          counterparty_name: 'Cash drawer',
          source_label: 'Manual payment',
          editable: true,
        },
      ],
    });
    mockUpdateFinanceTransaction.mockResolvedValue({
      transaction_id: 'txn-manual-1',
      origin_type: 'manual_payment',
      origin_id: null,
      occurred_at: '2026-03-16T09:00:00+00:00',
      direction: 'in',
      status: 'completed',
      currency_code: 'AED',
      amount: 150,
      reference: 'PAY-1001',
      note: 'Updated receipt',
      counterparty_type: 'internal',
      counterparty_id: null,
      counterparty_name: 'Cash drawer',
      source_label: 'Manual payment',
      editable: true,
    });

    render(<FinanceWorkspace />);

    await waitFor(() => expect(screen.getByText('Record manual finance entry')).toBeTruthy());
    fireEvent.click(screen.getByRole('button', { name: /edit/i }));
    expect(screen.getByDisplayValue('120')).toBeTruthy();
    expect(screen.getByDisplayValue('Cash drawer')).toBeTruthy();

    fireEvent.change(screen.getByLabelText(/^amount$/i), { target: { value: '150' } });
    fireEvent.change(screen.getByLabelText(/note/i), { target: { value: 'Updated receipt' } });
    fireEvent.click(screen.getByRole('button', { name: /update manual entry/i }));

    await waitFor(() =>
      expect(mockUpdateFinanceTransaction).toHaveBeenCalledWith(
        'txn-manual-1',
        expect.objectContaining({
          origin_type: 'manual_payment',
          direction: 'in',
          amount: 150,
          reference: 'PAY-1001',
          note: 'Updated receipt',
          status: 'completed',
        })
      )
    );
  });
});
