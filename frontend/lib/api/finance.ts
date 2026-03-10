import { apiClient } from '@/lib/api/client';
import type { Expense, FinanceOverview, FinanceTransaction, Receivable } from '@/types/finance';

export async function getFinanceOverview(): Promise<FinanceOverview> {
  return apiClient<FinanceOverview>('/finance/overview');
}

export async function getExpenses(query = ''): Promise<{ items: Expense[] }> {
  const params = new URLSearchParams();
  if (query.trim()) params.set('q', query.trim());
  return apiClient<{ items: Expense[] }>(`/finance/expenses${params.toString() ? `?${params.toString()}` : ''}`);
}

export async function createExpense(payload: {
  expense_date: string;
  category: string;
  amount: number;
  payment_status: 'paid' | 'unpaid' | 'partial';
  note: string;
}): Promise<{ expense: Expense }> {
  return apiClient<{ expense: Expense }>('/finance/expenses', { method: 'POST', body: JSON.stringify(payload) });
}

export async function updateExpense(expenseId: string, payload: {
  expense_date: string;
  category: string;
  amount: number;
  payment_status: 'paid' | 'unpaid' | 'partial';
  note: string;
}): Promise<{ expense: Expense }> {
  return apiClient<{ expense: Expense }>(`/finance/expenses/${expenseId}`, { method: 'PATCH', body: JSON.stringify(payload) });
}

export async function getReceivables(): Promise<{ items: Receivable[] }> {
  return apiClient<{ items: Receivable[] }>('/finance/receivables');
}

export async function getPayables(): Promise<{ supported: boolean; deferred_reason: string; unpaid_count: number; rows: Expense[] }> {
  return apiClient<{ supported: boolean; deferred_reason: string; unpaid_count: number; rows: Expense[] }>('/finance/payables');
}

export async function getFinanceTransactions(): Promise<{ items: FinanceTransaction[] }> {
  return apiClient<{ items: FinanceTransaction[] }>('/finance/transactions');
}
