export type FinanceOverview = {
  revenue: number | null;
  cash_collected: number | null;
  refunds_paid: number | null;
  expenses: number | null;
  receivables: number | null;
  payables: number | null;
  cash_in: number | null;
  cash_out: number | null;
  net_operating: number | null;
};

export type FinanceTransactionDirection = 'in' | 'out';
export type FinanceTransactionStatus = 'posted' | 'pending' | 'reversed' | 'completed' | 'paid' | 'unpaid' | 'partial';
export type FinanceTransactionOriginType =
  | 'sale_fulfillment'
  | 'return_refund'
  | 'manual_payment'
  | 'manual_expense';
export type FinanceCounterpartyType = 'customer' | 'vendor' | 'internal';

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
  transaction_id: string;
  reference: string;
  vendor_name: string;
  origin_type: FinanceTransactionOriginType;
  occurred_at: string;
  amount: number;
  status: string;
  note: string;
};

export type FinanceReceivable = Receivable;
export type FinancePayable = Payable;

export type FinanceTransaction = {
  transaction_id: string;
  occurred_at: string;
  origin_type: FinanceTransactionOriginType;
  origin_id: string | null;
  direction: FinanceTransactionDirection;
  status: FinanceTransactionStatus;
  currency_code: string;
  amount: number;
  reference: string;
  note: string;
  counterparty_type: FinanceCounterpartyType | null;
  counterparty_id: string | null;
  counterparty_name: string;
  finance_posted_at?: string | null;
  editable: boolean;
  source_label: string;
};

export type FinanceTransactionList = {
  transactions: FinanceTransaction[];
  total: number;
  limit: number;
  offset: number;
};

export type FinanceWorkspace = {
  overview: FinanceOverview;
  commerce_transactions: FinanceTransaction[];
  manual_transactions: FinanceTransaction[];
  recent_refunds: FinanceTransaction[];
  receivables: Receivable[];
  payables: Payable[];
};

export type FinanceTransactionInput = {
  origin_type: 'manual_payment' | 'manual_expense';
  occurred_at?: string;
  amount: number;
  direction: FinanceTransactionDirection;
  status?: FinanceTransactionStatus;
  currency_code?: string;
  reference: string;
  note: string;
  counterparty_name?: string;
  counterparty_type?: FinanceCounterpartyType;
};

export type FinanceRefundInput = {
  refund_date?: string;
  amount: number;
  method: string;
  reference: string;
  note: string;
};
