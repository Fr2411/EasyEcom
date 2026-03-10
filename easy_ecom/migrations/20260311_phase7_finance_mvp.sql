BEGIN;

ALTER TABLE sales_orders
  ADD COLUMN IF NOT EXISTS amount_paid VARCHAR(64) NOT NULL DEFAULT '0',
  ADD COLUMN IF NOT EXISTS outstanding_balance VARCHAR(64) NOT NULL DEFAULT '0',
  ADD COLUMN IF NOT EXISTS payment_status VARCHAR(32) NOT NULL DEFAULT 'unpaid';

UPDATE sales_orders
SET
  amount_paid = COALESCE(NULLIF(amount_paid, ''), '0'),
  outstanding_balance = CASE
    WHEN COALESCE(NULLIF(outstanding_balance, ''), '') = '' THEN COALESCE(NULLIF(grand_total, ''), '0')
    ELSE outstanding_balance
  END,
  payment_status = CASE
    WHEN payment_status IN ('paid', 'unpaid', 'partial') THEN payment_status
    WHEN COALESCE(NULLIF(outstanding_balance, ''), COALESCE(NULLIF(grand_total, ''), '0')) = '0' THEN 'paid'
    ELSE 'unpaid'
  END;

CREATE INDEX IF NOT EXISTS idx_sales_orders_client_payment_status ON sales_orders(client_id, payment_status);
CREATE INDEX IF NOT EXISTS idx_sales_orders_client_outstanding_balance ON sales_orders(client_id, outstanding_balance);

CREATE TABLE IF NOT EXISTS finance_expenses (
  expense_id VARCHAR(64) PRIMARY KEY,
  client_id VARCHAR(64) NOT NULL,
  expense_date VARCHAR(32) NOT NULL DEFAULT '',
  category VARCHAR(120) NOT NULL DEFAULT '',
  amount VARCHAR(64) NOT NULL DEFAULT '0',
  payment_status VARCHAR(32) NOT NULL DEFAULT 'paid',
  note TEXT NOT NULL DEFAULT '',
  created_by_user_id VARCHAR(64) NOT NULL DEFAULT '',
  created_at VARCHAR(64) NOT NULL DEFAULT '',
  updated_at VARCHAR(64) NOT NULL DEFAULT ''
);

CREATE INDEX IF NOT EXISTS idx_finance_expenses_client_date ON finance_expenses(client_id, expense_date);
CREATE INDEX IF NOT EXISTS idx_finance_expenses_client_status ON finance_expenses(client_id, payment_status);
CREATE INDEX IF NOT EXISTS idx_finance_expenses_client_category ON finance_expenses(client_id, category);

COMMIT;
