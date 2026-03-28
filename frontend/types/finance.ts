export type FinanceOverview = {
  sales_revenue: number | null;
  expense_total: number | null;
  receivables: number | null;
  payables: number | null;
  cash_in: number | null;
  cash_out: number | null;
  net_operating: number | null;
};

export type FinanceReport = {
  from_date: string;
  to_date: string;
  expense_total: number;
  expense_trend: Array<{ period: string; amount: number }>;
  receivables_total: number;
  payables_total: number | null;
  net_operating_snapshot: number | null;
  deferred_metrics: Array<{ metric: string; reason: string }>;
};

export type Expense = {
  expense_id: string;
  expense_date: string;
  category: string;
  amount: number;
  payment_status: 'paid' | 'unpaid' | 'partial';
  note: string;
  created_at: string;
  updated_at: string;
};

export type Receivable = {
  sale_id: string;
  sale_no: string;
  customer_id?: string | null;
  customer_name: string;
  sale_date: string;
  grand_total: number;
  amount_paid: number;
  outstanding_balance: number;
  payment_status: string;
};

export type Payable = {
  expense_id: string;
  expense_number: string;
  vendor_name: string;
  category: string;
  expense_date: string;
  amount: number;
  payment_status: string;
  note: string;
};

export type FinanceReceivable = Receivable;
export type FinancePayable = Payable;

export type FinanceTransaction = {
  entry_id: string;
  entry_date: string;
  entry_type: 'payment' | 'expense';
  direction: 'in' | 'out';
  category: string;
  amount: number;
  reference: string;
  note: string;
  payment_status?: string | null;
  vendor_name?: string | null;
};

export type FinanceTransactionList = {
  transactions: FinanceTransaction[];
  total: number;
  limit: number;
  offset: number;
};

export type FinanceWorkspace = {
  overview: FinanceOverview;
  transactions: FinanceTransaction[];
  receivables: Receivable[];
  payables: Payable[];
};

export type FinanceTransactionInput = {
  entry_type: 'payment' | 'expense';
  entry_date?: string;
  category: string;
  amount: number;
  direction: 'in' | 'out';
  reference: string;
  note: string;
  vendor_name?: string;
  payment_status?: string;
};
