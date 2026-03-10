'use client';

import { useEffect, useMemo, useState } from 'react';
import { createExpense, getExpenses, getFinanceOverview, getFinanceTransactions, getPayables, getReceivables } from '@/lib/api/finance';
import type { Expense, FinanceOverview, FinanceTransaction, Receivable } from '@/types/finance';

type Tab = 'expenses' | 'receivables' | 'payables' | 'transactions';

const money = (value: number | null) => (value ?? 0).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 });

export function FinanceWorkspace() {
  const [overview, setOverview] = useState<FinanceOverview | null>(null);
  const [expenses, setExpenses] = useState<Expense[]>([]);
  const [receivables, setReceivables] = useState<Receivable[]>([]);
  const [payables, setPayables] = useState<{ supported: boolean; deferred_reason: string; unpaid_count: number; rows: Expense[] } | null>(null);
  const [transactions, setTransactions] = useState<FinanceTransaction[]>([]);
  const [activeTab, setActiveTab] = useState<Tab>('expenses');
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [expenseDate, setExpenseDate] = useState('');
  const [category, setCategory] = useState('');
  const [amount, setAmount] = useState(0);
  const [paymentStatus, setPaymentStatus] = useState<'paid' | 'unpaid' | 'partial'>('paid');
  const [note, setNote] = useState('');

  const load = async () => {
    try {
      setLoading(true);
      setError(null);
      const [o, e, r, p, t] = await Promise.all([
        getFinanceOverview(),
        getExpenses(''),
        getReceivables(),
        getPayables(),
        getFinanceTransactions(),
      ]);
      setOverview(o);
      setExpenses(e.items);
      setReceivables(r.items);
      setPayables(p);
      setTransactions(t.items);
    } catch {
      setError('Unable to load finance module.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    const today = new Date().toISOString().slice(0, 10);
    setExpenseDate(today);
    load();
  }, []);

  const hasData = useMemo(() => expenses.length + receivables.length + (transactions.length > 0 ? 1 : 0) > 0, [expenses, receivables, transactions]);

  const submitExpense = async () => {
    if (!expenseDate || !category || amount <= 0) return;
    try {
      setSaving(true);
      await createExpense({ expense_date: expenseDate, category, amount, payment_status: paymentStatus, note });
      setCategory('');
      setAmount(0);
      setNote('');
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unable to save expense.');
    } finally {
      setSaving(false);
    }
  };

  return (
    <section className="finance-module">
      {error ? <p className="sales-error">{error}</p> : null}
      <div className="finance-cards">
        <article className="ps-card"><p>Sales Revenue</p><strong>{money(overview?.sales_revenue ?? null)}</strong></article>
        <article className="ps-card"><p>Expense Total</p><strong>{money(overview?.expense_total ?? null)}</strong></article>
        <article className="ps-card"><p>Receivables</p><strong>{money(overview?.receivables ?? null)}</strong></article>
        <article className="ps-card"><p>Payables</p><strong>{money(overview?.payables ?? null)}</strong></article>
        <article className="ps-card"><p>Net Operating</p><strong>{money(overview?.net_operating ?? null)}</strong></article>
      </div>

      <div className="sales-toolbar">
        <button type="button" onClick={() => setActiveTab('expenses')}>Expenses</button>
        <button type="button" onClick={() => setActiveTab('receivables')}>Receivables</button>
        <button type="button" onClick={() => setActiveTab('payables')}>Payables</button>
        <button type="button" onClick={() => setActiveTab('transactions')}>Transactions</button>
      </div>

      {loading ? <p>Loading finance data...</p> : null}
      {!loading && !hasData ? <div className="sales-empty"><h4>No finance entries yet</h4><p>Add your first expense to start tracking business cash movement.</p></div> : null}

      {!loading && activeTab === 'expenses' ? <div className="sales-grid"><div className="sales-panel"><h3>Expense Entries</h3><table className="sales-table"><thead><tr><th>Date</th><th>Category</th><th>Status</th><th>Amount</th><th>Note</th></tr></thead><tbody>{expenses.map((item) => <tr key={item.expense_id}><td>{item.expense_date}</td><td>{item.category}</td><td>{item.payment_status}</td><td>{money(item.amount)}</td><td>{item.note}</td></tr>)}</tbody></table></div><aside className="sales-panel"><h3>Add Expense</h3><label>Date<input aria-label="Expense date" type="date" value={expenseDate} onChange={(e) => setExpenseDate(e.target.value)} /></label><label>Category<input aria-label="Expense category" value={category} onChange={(e) => setCategory(e.target.value)} /></label><label>Amount<input aria-label="Expense amount" type="number" min={0} step="0.01" value={amount} onChange={(e) => setAmount(Number(e.target.value || 0))} /></label><label>Payment Status<select aria-label="Expense payment status" value={paymentStatus} onChange={(e) => setPaymentStatus(e.target.value as 'paid' | 'unpaid' | 'partial')}><option value="paid">Paid</option><option value="unpaid">Unpaid</option><option value="partial">Partial</option></select></label><label>Note<textarea aria-label="Expense note" value={note} onChange={(e) => setNote(e.target.value)} /></label><button type="button" onClick={submitExpense} disabled={saving}>{saving ? 'Saving...' : 'Add Expense'}</button></aside></div> : null}

      {!loading && activeTab === 'receivables' ? <div className="sales-panel"><h3>Receivables</h3><table className="sales-table"><thead><tr><th>Sale #</th><th>Customer</th><th>Total</th><th>Paid</th><th>Outstanding</th></tr></thead><tbody>{receivables.map((row) => <tr key={row.sale_id}><td>{row.sale_no}</td><td>{row.customer_name}</td><td>{money(row.grand_total)}</td><td>{money(row.amount_paid)}</td><td>{money(row.outstanding_balance)}</td></tr>)}</tbody></table></div> : null}

      {!loading && activeTab === 'payables' ? <div className="sales-panel"><h3>Payables</h3>{payables?.supported ? <table className="sales-table"><thead><tr><th>Date</th><th>Category</th><th>Status</th><th>Amount</th></tr></thead><tbody>{payables.rows.map((row) => <tr key={row.expense_id}><td>{row.expense_date}</td><td>{row.category}</td><td>{row.payment_status}</td><td>{money(row.amount)}</td></tr>)}</tbody></table> : <p>{payables?.deferred_reason || 'Payables currently deferred.'}</p>}</div> : null}

      {!loading && activeTab === 'transactions' ? <div className="sales-panel"><h3>Finance Transactions</h3><table className="sales-table"><thead><tr><th>Date</th><th>Type</th><th>Category</th><th>Direction</th><th>Amount</th></tr></thead><tbody>{transactions.map((row) => <tr key={`${row.entry_type}-${row.entry_id}`}><td>{row.entry_date}</td><td>{row.entry_type}</td><td>{row.category}</td><td>{row.direction}</td><td>{money(row.amount)}</td></tr>)}</tbody></table></div> : null}
    </section>
  );
}
