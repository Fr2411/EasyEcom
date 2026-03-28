import { apiClient } from '@/lib/api/client';
import type {
  FinanceOverview,
  FinanceReport,
  FinanceTransaction,
  FinanceTransactionInput,
  FinanceTransactionList,
  FinanceWorkspace,
} from '@/types/finance';

function buildFinanceQuery(params: { transactionType?: FinanceTransaction['origin_type']; limit?: number; offset?: number } = {}) {
  const search = new URLSearchParams();
  if (params.transactionType) {
    search.set('transaction_type', params.transactionType);
  }
  if (typeof params.limit === 'number') {
    search.set('limit', String(params.limit));
  }
  if (typeof params.offset === 'number') {
    search.set('offset', String(params.offset));
  }
  const text = search.toString();
  return text ? `?${text}` : '';
}

function buildReportQuery(params: { fromDate?: string; toDate?: string } = {}) {
  const search = new URLSearchParams();
  if (params.fromDate?.trim()) {
    search.set('from_date', params.fromDate.trim());
  }
  if (params.toDate?.trim()) {
    search.set('to_date', params.toDate.trim());
  }
  const text = search.toString();
  return text ? `?${text}` : '';
}

export async function getFinanceOverview() {
  return apiClient<FinanceOverview>('/finance/overview');
}

export async function getFinanceWorkspace() {
  return apiClient<FinanceWorkspace>('/finance/workspace');
}

export async function getFinanceTransactions(params: { transactionType?: FinanceTransaction['origin_type']; limit?: number; offset?: number } = {}) {
  return apiClient<FinanceTransactionList>(`/finance/transactions${buildFinanceQuery(params)}`);
}

export async function getFinanceTransaction(transactionId: string) {
  return apiClient<FinanceTransaction>(`/finance/transactions/${transactionId}`);
}

export async function createFinanceTransaction(payload: FinanceTransactionInput) {
  return apiClient<FinanceTransaction>('/finance/transactions', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export async function updateFinanceTransaction(transactionId: string, payload: FinanceTransactionInput) {
  return apiClient<FinanceTransaction>(`/finance/transactions/${transactionId}`, {
    method: 'PUT',
    body: JSON.stringify(payload),
  });
}

export async function getFinanceReport(params: { fromDate?: string; toDate?: string } = {}) {
  return apiClient<FinanceReport>(`/reports/finance${buildReportQuery(params)}`);
}
