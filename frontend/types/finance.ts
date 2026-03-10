export type FinanceOverview = {
  sales_revenue: number | null;
  expense_total: number | null;
  receivables: number | null;
  payables: number | null;
  cash_in: number | null;
  cash_out: number | null;
  net_operating: number | null;
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
  customer_id: string;
  customer_name: string;
  sale_date: string;
  grand_total: number;
  amount_paid: number;
  outstanding_balance: number;
  payment_status: string;
};

export type FinanceTransaction = {
  entry_id: string;
  entry_date: string;
  entry_type: string;
  category: string;
  amount: number;
  direction: 'in' | 'out';
  reference: string;
  note: string;
};
