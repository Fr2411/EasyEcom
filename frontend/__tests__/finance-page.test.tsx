import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, describe, expect, test, vi } from 'vitest';

const getFinanceOverviewMock = vi.fn();
const getExpensesMock = vi.fn();
const createExpenseMock = vi.fn();
const getReceivablesMock = vi.fn();
const getPayablesMock = vi.fn();
const getFinanceTransactionsMock = vi.fn();

vi.mock('@/lib/api/finance', () => ({
  getFinanceOverview: (...args: unknown[]) => getFinanceOverviewMock(...args),
  getExpenses: (...args: unknown[]) => getExpensesMock(...args),
  createExpense: (...args: unknown[]) => createExpenseMock(...args),
  getReceivables: (...args: unknown[]) => getReceivablesMock(...args),
  getPayables: (...args: unknown[]) => getPayablesMock(...args),
  getFinanceTransactions: (...args: unknown[]) => getFinanceTransactionsMock(...args),
}));

import FinancePage from '@/app/(app)/finance/page';

afterEach(() => {
  cleanup();
  getFinanceOverviewMock.mockReset();
  getExpensesMock.mockReset();
  createExpenseMock.mockReset();
  getReceivablesMock.mockReset();
  getPayablesMock.mockReset();
  getFinanceTransactionsMock.mockReset();
});

describe('FinancePage', () => {
  test('renders finance empty state', async () => {
    getFinanceOverviewMock.mockResolvedValue({ sales_revenue: 0, expense_total: 0, receivables: 0, payables: 0, cash_in: 0, cash_out: 0, net_operating: 0 });
    getExpensesMock.mockResolvedValue({ items: [] });
    getReceivablesMock.mockResolvedValue({ items: [] });
    getPayablesMock.mockResolvedValue({ supported: true, deferred_reason: '', unpaid_count: 0, rows: [] });
    getFinanceTransactionsMock.mockResolvedValue({ items: [] });

    render(<FinancePage />);

    expect(screen.getByRole('heading', { name: 'Finance' })).toBeTruthy();
    await waitFor(() => expect(screen.getByText('No finance entries yet')).toBeTruthy());
  });

  test('renders summary and adds expense', async () => {
    getFinanceOverviewMock.mockResolvedValue({ sales_revenue: 1000, expense_total: 300, receivables: 50, payables: 20, cash_in: 1000, cash_out: 300, net_operating: 700 });
    getExpensesMock.mockResolvedValue({ items: [] });
    getReceivablesMock.mockResolvedValue({ items: [] });
    getPayablesMock.mockResolvedValue({ supported: true, deferred_reason: '', unpaid_count: 0, rows: [] });
    getFinanceTransactionsMock.mockResolvedValue({ items: [] });
    createExpenseMock.mockResolvedValue({ expense: { expense_id: 'e1' } });

    render(<FinancePage />);

    await waitFor(() => expect(screen.getByText('1,000.00')).toBeTruthy());
    fireEvent.change(screen.getByLabelText('Expense category'), { target: { value: 'Rent' } });
    fireEvent.change(screen.getByLabelText('Expense amount'), { target: { value: 250 } });
    fireEvent.click(screen.getByRole('button', { name: 'Add Expense' }));

    await waitFor(() => expect(createExpenseMock).toHaveBeenCalled());
  });
});
