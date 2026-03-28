import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, describe, expect, test, vi } from 'vitest';
import { FinanceWorkspace } from '@/components/finance/finance-workspace';

const {
  mockGetFinanceWorkspace,
  mockGetFinanceReport,
  mockCreateFinanceTransaction,
  mockUpdateFinanceTransaction,
} = vi.hoisted(() => ({
  mockGetFinanceWorkspace: vi.fn(),
  mockGetFinanceReport: vi.fn(),
  mockCreateFinanceTransaction: vi.fn(),
  mockUpdateFinanceTransaction: vi.fn(),
}));

vi.mock('@/lib/api/finance', () => ({
  getFinanceWorkspace: mockGetFinanceWorkspace,
  getFinanceReport: mockGetFinanceReport,
  createFinanceTransaction: mockCreateFinanceTransaction,
  updateFinanceTransaction: mockUpdateFinanceTransaction,
}));

describe('FinanceWorkspace', () => {
  afterEach(() => {
    cleanup();
    vi.clearAllMocks();
  });

  test('renders receivables, payables, and recent cash activity', async () => {
    mockGetFinanceWorkspace.mockResolvedValue({
      overview: {
        sales_revenue: 300,
        expense_total: 50,
        receivables: 50,
        payables: 20,
        cash_in: 250,
        cash_out: 90,
        net_operating: 160,
      },
      transactions: [
        {
          entry_id: 'txn-1',
          entry_date: '2026-03-15T10:00:00+00:00',
          entry_type: 'expense',
          direction: 'out',
          category: 'rent',
          amount: 30,
          reference: 'EXP-1001',
          note: 'Rent paid',
          payment_status: 'paid',
          vendor_name: 'Landlord',
        },
      ],
      receivables: [
        {
          sale_id: 'sale-1',
          sale_no: 'SO-1001',
          customer_id: 'cust-1',
          customer_name: 'Amina Buyer',
          sale_date: '2026-03-14T10:00:00+00:00',
          grand_total: 300,
          amount_paid: 250,
          outstanding_balance: 50,
          payment_status: 'partial',
        },
      ],
      payables: [
        {
          expense_id: 'exp-1',
          expense_number: 'EXP-1002',
          vendor_name: 'Utility',
          category: 'utilities',
          expense_date: '2026-03-15T11:00:00+00:00',
          amount: 20,
          payment_status: 'unpaid',
          note: 'Power bill accrued',
        },
      ],
    });
    mockGetFinanceReport.mockResolvedValue({
      from_date: '2026-03-01',
      to_date: '2026-03-15',
      expense_total: 50,
      expense_trend: [{ period: '2026-03-15', amount: 50 }],
      receivables_total: 50,
      payables_total: 20,
      net_operating_snapshot: 160,
      deferred_metrics: [],
    });

    render(<FinanceWorkspace />);

    await waitFor(() => expect(screen.getByText('Record money movement')).toBeTruthy());
    expect(screen.getByText('Receivables and payables')).toBeTruthy();
    expect(screen.getByText('SO-1001')).toBeTruthy();
    expect(screen.getByText('EXP-1002')).toBeTruthy();
    expect(screen.getByText('Money movement journal')).toBeTruthy();
  });

  test('records a new expense from the finance workspace', async () => {
    mockGetFinanceWorkspace.mockResolvedValue({
      overview: {
        sales_revenue: 300,
        expense_total: 50,
        receivables: 50,
        payables: 20,
        cash_in: 250,
        cash_out: 90,
        net_operating: 160,
      },
      transactions: [],
      receivables: [],
      payables: [],
    });
    mockGetFinanceReport.mockResolvedValue({
      from_date: '2026-03-01',
      to_date: '2026-03-15',
      expense_total: 50,
      expense_trend: [{ period: '2026-03-15', amount: 50 }],
      receivables_total: 50,
      payables_total: 20,
      net_operating_snapshot: 160,
      deferred_metrics: [],
    });
    mockCreateFinanceTransaction.mockResolvedValue({
      entry_id: 'txn-2',
      entry_date: '2026-03-16T10:00:00+00:00',
      entry_type: 'expense',
      direction: 'out',
      category: 'courier',
      amount: 75,
      reference: 'BILL-2001',
      note: 'Courier invoice',
      payment_status: 'unpaid',
      vendor_name: 'FastShip',
    });

    render(<FinanceWorkspace />);

    await waitFor(() => expect(screen.getByText('Record money movement')).toBeTruthy());
    fireEvent.change(screen.getByLabelText(/entry type/i), { target: { value: 'expense' } });
    fireEvent.change(screen.getByLabelText(/category or method/i), { target: { value: 'courier' } });
    fireEvent.change(screen.getByLabelText(/^amount$/i), { target: { value: '75' } });
    fireEvent.change(screen.getByLabelText(/reference/i), { target: { value: 'BILL-2001' } });
    fireEvent.change(screen.getByLabelText(/vendor/i), { target: { value: 'FastShip' } });
    fireEvent.change(screen.getByLabelText(/note/i), { target: { value: 'Courier invoice' } });
    fireEvent.change(screen.getByLabelText(/payment status/i), { target: { value: 'unpaid' } });
    fireEvent.click(screen.getByRole('button', { name: /post expense/i }));

    await waitFor(() =>
      expect(mockCreateFinanceTransaction).toHaveBeenCalledWith(
        expect.objectContaining({
          entry_type: 'expense',
          direction: 'out',
          category: 'courier',
          amount: 75,
          reference: 'BILL-2001',
          vendor_name: 'FastShip',
          note: 'Courier invoice',
          payment_status: 'unpaid',
        })
      )
    );
  });

  test('edits an existing payment transaction from the journal', async () => {
    mockGetFinanceWorkspace.mockResolvedValue({
      overview: {
        sales_revenue: 300,
        expense_total: 50,
        receivables: 50,
        payables: 20,
        cash_in: 250,
        cash_out: 90,
        net_operating: 160,
      },
      transactions: [
        {
          entry_id: 'txn-1',
          entry_date: '2026-03-15T10:00:00+00:00',
          entry_type: 'payment',
          direction: 'in',
          category: 'cash',
          amount: 120,
          reference: 'PAY-1001',
          note: 'Initial receipt',
          payment_status: 'completed',
        },
      ],
      receivables: [],
      payables: [],
    });
    mockGetFinanceReport.mockResolvedValue({
      from_date: '2026-03-01',
      to_date: '2026-03-15',
      expense_total: 50,
      expense_trend: [{ period: '2026-03-15', amount: 50 }],
      receivables_total: 50,
      payables_total: 20,
      net_operating_snapshot: 160,
      deferred_metrics: [],
    });
    mockUpdateFinanceTransaction.mockResolvedValue({
      entry_id: 'txn-1',
      entry_date: '2026-03-15T10:00:00+00:00',
      entry_type: 'payment',
      direction: 'in',
      category: 'bank transfer',
      amount: 150,
      reference: 'PAY-1001',
      note: 'Updated receipt',
      payment_status: 'completed',
    });

    render(<FinanceWorkspace />);

    await waitFor(() => expect(screen.getByText('Record money movement')).toBeTruthy());
    fireEvent.click(screen.getByRole('button', { name: /^edit$/i }));
    expect(screen.getByDisplayValue('cash')).toBeTruthy();
    expect(screen.getByDisplayValue('120')).toBeTruthy();

    fireEvent.change(screen.getByLabelText(/^amount$/i), { target: { value: '150' } });
    fireEvent.change(screen.getByLabelText(/category or method/i), { target: { value: 'bank transfer' } });
    fireEvent.change(screen.getByLabelText(/note/i), { target: { value: 'Updated receipt' } });
    fireEvent.click(screen.getByRole('button', { name: /update transaction/i }));

    await waitFor(() =>
      expect(mockUpdateFinanceTransaction).toHaveBeenCalledWith(
        'txn-1',
        expect.objectContaining({
          entry_type: 'payment',
          direction: 'in',
          category: 'bank transfer',
          amount: 150,
          reference: 'PAY-1001',
          note: 'Updated receipt',
          payment_status: 'completed',
        })
      )
    );
  });
});
