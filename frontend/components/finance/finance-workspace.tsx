'use client';

import { useEffect, useMemo, useState } from 'react';
import { createFinanceTransaction, getFinanceReport, getFinanceWorkspace, updateFinanceTransaction } from '@/lib/api/finance';
import { formatDateTime, formatMoney, numberFromString } from '@/lib/commerce-format';
import type { FinanceOverview, FinancePayable, FinanceReceivable, FinanceReport, FinanceTransaction, FinanceTransactionInput } from '@/types/finance';
import type { SuggestedAction } from '@/types/guided-workflow';
import {
  DraftRecommendationCard,
  StagedActionFooter,
  SuggestedNextStep,
  WorkspaceEmpty,
  WorkspaceNotice,
  WorkspacePanel,
  WorkspaceTabs,
} from '@/components/commerce/workspace-primitives';

type JournalFilter = 'all' | 'payment' | 'expense';

type FinanceDraft = {
  entry_id: string | null;
  entry_type: 'payment' | 'expense';
  entry_date: string;
  category: string;
  direction: 'in' | 'out';
  amount: string;
  reference: string;
  note: string;
  vendor_name: string;
  payment_status: string;
};

const JOURNAL_TABS: Array<{ id: JournalFilter; label: string }> = [
  { id: 'all', label: 'All entries' },
  { id: 'payment', label: 'Payments' },
  { id: 'expense', label: 'Expenses' },
];

function currentLocalDateTime() {
  const now = new Date();
  const local = new Date(now.getTime() - now.getTimezoneOffset() * 60000);
  return local.toISOString().slice(0, 16);
}

function isoToLocalInput(value: string) {
  const date = new Date(value);
  if (Number.isNaN(date.valueOf())) return currentLocalDateTime();
  const local = new Date(date.getTime() - date.getTimezoneOffset() * 60000);
  return local.toISOString().slice(0, 16);
}

function buildEmptyDraft(): FinanceDraft {
  return {
    entry_id: null,
    entry_type: 'payment',
    entry_date: currentLocalDateTime(),
    category: 'manual',
    direction: 'in',
    amount: '',
    reference: '',
    note: '',
    vendor_name: '',
    payment_status: 'completed',
  };
}

function buildDraftFromTransaction(transaction: FinanceTransaction): FinanceDraft {
  return {
    entry_id: transaction.entry_id,
    entry_type: transaction.entry_type,
    entry_date: isoToLocalInput(transaction.entry_date),
    category: transaction.category,
    direction: transaction.direction,
    amount: String(transaction.amount),
    reference: transaction.reference,
    note: transaction.note,
    vendor_name: transaction.vendor_name ?? '',
    payment_status: transaction.payment_status ?? (transaction.entry_type === 'expense' ? 'unpaid' : 'completed'),
  };
}

function buildPayload(draft: FinanceDraft): FinanceTransactionInput {
  return {
    entry_type: draft.entry_type,
    entry_date: new Date(draft.entry_date).toISOString(),
    category: draft.category.trim() || (draft.entry_type === 'payment' ? 'manual' : 'general'),
    amount: numberFromString(draft.amount),
    direction: draft.entry_type === 'expense' ? 'out' : draft.direction,
    reference: draft.reference.trim(),
    note: draft.note.trim(),
    vendor_name: draft.entry_type === 'expense' ? draft.vendor_name.trim() : undefined,
    payment_status: draft.entry_type === 'expense' ? draft.payment_status : 'completed',
  };
}

function buildRecommendation(draft: FinanceDraft, report: FinanceReport | null): SuggestedAction {
  const amount = formatMoney(draft.amount || '0');
  if (draft.entry_type === 'expense') {
    const payablePressure = report?.payables_total ? ` Open payables currently total ${formatMoney(report.payables_total)}.` : '';
    return {
      title: draft.entry_id ? 'Update the expense draft' : 'Post an expense',
      detail: `This will record ${amount} as an outgoing expense${draft.vendor_name.trim() ? ` for ${draft.vendor_name.trim()}` : ''}.${payablePressure}`,
      actionLabel: draft.entry_id ? 'Review update' : 'Post expense',
      tone: 'warning',
    };
  }

  return {
    title: draft.entry_id ? 'Update the payment draft' : 'Post a payment',
    detail: `This will record ${amount} as a ${draft.direction === 'out' ? 'cash outflow' : 'cash inflow'} with ${draft.category.trim() || 'manual'} as the method.`,
    actionLabel: draft.entry_id ? 'Review update' : 'Post payment',
    tone: 'success',
  };
}

function buildSnapshotCards(overview: FinanceOverview | null, report: FinanceReport | null) {
  return [
    { key: 'sales_revenue', label: 'Sales revenue', value: overview?.sales_revenue ?? null },
    { key: 'expense_total', label: 'Expenses', value: report?.expense_total ?? overview?.expense_total ?? null },
    { key: 'receivables', label: 'Receivables', value: report?.receivables_total ?? overview?.receivables ?? null },
    { key: 'payables', label: 'Payables', value: report?.payables_total ?? overview?.payables ?? null },
    { key: 'cash_in', label: 'Cash in', value: overview?.cash_in ?? null },
    { key: 'cash_out', label: 'Cash out', value: overview?.cash_out ?? null },
    { key: 'net_operating', label: 'Net operating', value: overview?.net_operating ?? report?.net_operating_snapshot ?? null },
  ];
}

export function FinanceWorkspace() {
  const [overview, setOverview] = useState<FinanceOverview | null>(null);
  const [report, setReport] = useState<FinanceReport | null>(null);
  const [transactions, setTransactions] = useState<FinanceTransaction[]>([]);
  const [receivables, setReceivables] = useState<FinanceReceivable[]>([]);
  const [payables, setPayables] = useState<FinancePayable[]>([]);
  const [journalFilter, setJournalFilter] = useState<JournalFilter>('all');
  const [draft, setDraft] = useState<FinanceDraft>(buildEmptyDraft());
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [notice, setNotice] = useState('');
  const [error, setError] = useState('');

  async function refreshWorkspace(filter: JournalFilter = journalFilter) {
    setLoading(true);
    try {
      const [workspacePayload, reportPayload] = await Promise.all([
        getFinanceWorkspace(),
        getFinanceReport(),
      ]);
      setOverview(workspacePayload.overview);
      setReport(reportPayload);
      setTransactions(filter === 'all' ? workspacePayload.transactions : workspacePayload.transactions.filter((transaction) => transaction.entry_type === filter));
      setReceivables(workspacePayload.receivables);
      setPayables(workspacePayload.payables);
      setError('');
    } catch (loadError) {
      setError(loadError instanceof Error ? loadError.message : 'Unable to load finance workspace.');
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void refreshWorkspace();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [journalFilter]);

  const snapshotCards = useMemo(() => buildSnapshotCards(overview, report), [overview, report]);
  const recommendation = useMemo(() => buildRecommendation(draft, report), [draft, report]);

  function startEdit(transaction: FinanceTransaction) {
    setDraft(buildDraftFromTransaction(transaction));
    setNotice(`Editing ${transaction.entry_type} ${transaction.reference || transaction.entry_id}.`);
    setError('');
  }

  function resetDraft() {
    setDraft(buildEmptyDraft());
    setNotice('');
  }

  async function submitTransaction() {
    if (!draft.amount.trim() || numberFromString(draft.amount) <= 0) {
      setError('Amount must be greater than zero.');
      return;
    }
    if (!draft.category.trim()) {
      setError('Category is required.');
      return;
    }

    setSaving(true);
    setError('');
    try {
      const payload = buildPayload(draft);
      if (draft.entry_id) {
        await updateFinanceTransaction(draft.entry_id, payload);
        setNotice('Finance transaction updated.');
      } else {
        await createFinanceTransaction(payload);
        setNotice('Finance transaction recorded.');
      }
      setDraft(buildEmptyDraft());
      await refreshWorkspace();
    } catch (submitError) {
      setError(submitError instanceof Error ? submitError.message : 'Unable to save transaction.');
    } finally {
      setSaving(false);
    }
  }

  if (loading && !overview) {
    return <div className="reports-loading">Loading finance workspace…</div>;
  }

  if (error && !overview) {
    return <div className="reports-error">{error}</div>;
  }

  if (!overview) {
    return <WorkspaceEmpty title="Finance workspace unavailable" message="No finance data was returned for this tenant." />;
  }

  return (
    <div className="finance-module">
      <WorkspaceNotice tone="info">
        Payments are posted as cash movements. Expenses stay visible as open payables until they are marked paid.
      </WorkspaceNotice>
      {notice ? <WorkspaceNotice tone="success">{notice}</WorkspaceNotice> : null}
      {error ? <WorkspaceNotice tone="error">{error}</WorkspaceNotice> : null}

      <div className="finance-cards">
        {snapshotCards.map((card) => (
          <article key={card.key} className="ps-card">
            <p>{card.label}</p>
            <strong>{formatMoney(card.value)}</strong>
          </article>
        ))}
      </div>

      <div className="finance-layout">
        <WorkspacePanel title={draft.entry_id ? 'Edit transaction' : 'Record money movement'} description="Post a payment or expense with explicit confirmation.">
          <form
            className="workspace-form"
            onSubmit={(event) => {
              event.preventDefault();
              void submitTransaction();
            }}
          >
            <div className="workspace-form-grid compact">
              <label>
                Entry type
                <select
                  value={draft.entry_type}
                  onChange={(event) =>
                    setDraft((current) => ({
                      ...current,
                      entry_type: event.target.value === 'expense' ? 'expense' : 'payment',
                      direction: event.target.value === 'expense' ? 'out' : current.direction,
                      payment_status: event.target.value === 'expense' ? 'unpaid' : 'completed',
                    }))
                  }
                >
                  <option value="payment">Payment</option>
                  <option value="expense">Expense</option>
                </select>
              </label>
              <label>
                Entry date
                <input type="datetime-local" value={draft.entry_date} onChange={(event) => setDraft((current) => ({ ...current, entry_date: event.target.value }))} />
              </label>
              <label>
                Category or method
                <input
                  value={draft.category}
                  onChange={(event) => setDraft((current) => ({ ...current, category: event.target.value }))}
                  placeholder={draft.entry_type === 'payment' ? 'cash, bank transfer, card' : 'rent, shipping, payroll'}
                />
              </label>
              <label>
                Amount
                <input
                  inputMode="decimal"
                  value={draft.amount}
                  onChange={(event) => setDraft((current) => ({ ...current, amount: event.target.value }))}
                  placeholder="0.00"
                />
              </label>
              <label>
                Direction
                <select
                  value={draft.direction}
                  disabled={draft.entry_type === 'expense'}
                  onChange={(event) => setDraft((current) => ({ ...current, direction: event.target.value === 'out' ? 'out' : 'in' }))}
                >
                  <option value="in">Cash in</option>
                  <option value="out">Cash out</option>
                </select>
              </label>
              <label>
                Reference
                <input
                  value={draft.reference}
                  onChange={(event) => setDraft((current) => ({ ...current, reference: event.target.value }))}
                  placeholder="Receipt, invoice, or bill number"
                />
              </label>
              {draft.entry_type === 'expense' ? (
                <>
                  <label>
                    Vendor
                    <input
                      value={draft.vendor_name}
                      onChange={(event) => setDraft((current) => ({ ...current, vendor_name: event.target.value }))}
                      placeholder="Supplier or payee"
                    />
                  </label>
                  <label>
                    Payment status
                    <select
                      value={draft.payment_status}
                      onChange={(event) => setDraft((current) => ({ ...current, payment_status: event.target.value }))}
                    >
                      <option value="unpaid">Unpaid</option>
                      <option value="partial">Partial</option>
                      <option value="paid">Paid</option>
                    </select>
                  </label>
                </>
              ) : null}
              <label className="workspace-form-wide">
                Note
                <textarea
                  rows={4}
                  value={draft.note}
                  onChange={(event) => setDraft((current) => ({ ...current, note: event.target.value }))}
                  placeholder="Add a short audit note"
                />
              </label>
            </div>

            <DraftRecommendationCard
              title={recommendation.title}
              summary={recommendation.detail}
              actions={
                draft.entry_id ? (
                  <button type="button" className="secondary" onClick={resetDraft}>
                    Cancel edit
                  </button>
                ) : null
              }
            >
              <div className="settings-context">
                <div>
                  <dt>Write mode</dt>
                  <dd>{draft.entry_id ? 'Updating a previously recorded entry.' : 'Posting a new journal entry.'}</dd>
                </div>
                <div>
                  <dt>Journal effect</dt>
                  <dd>{draft.entry_type === 'expense' ? 'Expense increases payables until payment is recorded.' : `Direction is ${draft.direction === 'out' ? 'cash out' : 'cash in'}.`}</dd>
                </div>
                <div>
                  <dt>Reference</dt>
                  <dd>{draft.reference.trim() || 'No reference entered yet.'}</dd>
                </div>
              </div>
            </DraftRecommendationCard>

            <StagedActionFooter summary="Nothing is written until you confirm the transaction.">
              <button type="button" className="secondary" onClick={resetDraft} disabled={saving}>
                Reset
              </button>
              <button type="submit" className="btn-primary" disabled={saving}>
                {saving ? 'Saving…' : draft.entry_id ? 'Update transaction' : draft.entry_type === 'expense' ? 'Post expense' : 'Post payment'}
              </button>
            </StagedActionFooter>
          </form>
        </WorkspacePanel>

        <WorkspacePanel title="Receivables and payables" description="Use the live report to understand cash pressure before recording more money movement.">
          <div className="settings-context">
            <div>
              <dt>Receivables</dt>
              <dd>{formatMoney(report?.receivables_total ?? overview.receivables)}</dd>
            </div>
            <div>
              <dt>Payables</dt>
              <dd>{formatMoney(report?.payables_total ?? overview.payables)}</dd>
            </div>
            <div>
              <dt>Operating snapshot</dt>
              <dd>{formatMoney(report?.net_operating_snapshot ?? overview.net_operating)}</dd>
            </div>
            <div>
              <dt>Expense trend</dt>
              <dd>
                {report?.expense_trend.length
                  ? `${report.expense_trend[0].period} ${formatMoney(report.expense_trend[0].amount)}`
                  : 'No expense trend yet.'}
              </dd>
            </div>
          </div>

          <div className="finance-bridge">
            <section>
              <h4>Open receivables</h4>
              {receivables.length ? (
                <div className="guided-match-list compact">
                  {receivables.slice(0, 5).map((receivable) => (
                    <article key={receivable.sale_id} className="guided-match-item compact">
                      <div className="guided-match-item-header">
                        <div>
                          <h5>{receivable.sale_no}</h5>
                          <p>{receivable.customer_name}</p>
                        </div>
                        <strong>{formatMoney(receivable.outstanding_balance)}</strong>
                      </div>
                      <div className="guided-match-item-meta">
                        <span className="status-pill">{receivable.payment_status}</span>
                        <span>{formatDateTime(receivable.sale_date)}</span>
                      </div>
                    </article>
                  ))}
                </div>
              ) : (
                <WorkspaceEmpty title="No receivables" message="All open sales are cleared in this window." />
              )}
            </section>

            <section>
              <h4>Open payables</h4>
              {payables.length ? (
                <div className="guided-match-list compact">
                  {payables.slice(0, 5).map((payable) => (
                    <article key={payable.expense_id} className="guided-match-item compact">
                      <div className="guided-match-item-header">
                        <div>
                          <h5>{payable.expense_number}</h5>
                          <p>{payable.vendor_name}</p>
                        </div>
                        <strong>{formatMoney(payable.amount)}</strong>
                      </div>
                      <div className="guided-match-item-meta">
                        <span className="status-pill">{payable.payment_status}</span>
                        <span>{payable.category}</span>
                        <span>{formatDateTime(payable.expense_date)}</span>
                      </div>
                      {payable.note ? <p>{payable.note}</p> : null}
                    </article>
                  ))}
                </div>
              ) : (
                <WorkspaceEmpty title="No payables" message="No unpaid expense is visible in this window." />
              )}
            </section>
          </div>

          <SuggestedNextStep
            suggestion={{
              title:
                (report?.payables_total ?? overview.payables ?? 0) > 0
                  ? 'Open payables need attention'
                  : 'Finance is balanced for the current window',
              detail:
                (report?.payables_total ?? overview.payables ?? 0) > 0
                  ? `There is ${formatMoney(report?.payables_total ?? overview.payables)} of unpaid expense still sitting in payables.`
                  : 'No unpaid expense balance is currently visible in the active window.',
              actionLabel: 'Review journal',
              tone: (report?.payables_total ?? overview.payables ?? 0) > 0 ? 'warning' : 'success',
            }}
          />
        </WorkspacePanel>
      </div>

      <WorkspacePanel
        title="Money movement journal"
        description="The journal merges payments and expenses so operators can review the same ledger they write to."
        actions={<WorkspaceTabs tabs={JOURNAL_TABS} activeTab={journalFilter} onTabChange={(tab) => setJournalFilter(tab)} />}
      >
        {transactions.length ? (
          <div className="guided-match-list">
            {transactions.map((transaction) => (
              <article key={transaction.entry_id} className="guided-match-item">
                <div className="guided-match-item-header">
                  <div>
                    <h5>
                      {transaction.entry_type === 'expense' ? 'Expense' : 'Payment'} · {transaction.category}
                    </h5>
                    <p>
                      {transaction.reference || 'No reference'} · {formatDateTime(transaction.entry_date)}
                    </p>
                  </div>
                  <strong>{transaction.direction === 'out' ? `- ${formatMoney(transaction.amount)}` : `+ ${formatMoney(transaction.amount)}`}</strong>
                </div>
                <div className="guided-match-item-meta">
                  <span className="status-pill">{transaction.payment_status ?? 'completed'}</span>
                  <span>{transaction.direction === 'out' ? 'Cash out' : 'Cash in'}</span>
                  {transaction.vendor_name ? <span>{transaction.vendor_name}</span> : null}
                </div>
                {transaction.note ? <p>{transaction.note}</p> : null}
                <div className="workspace-actions">
                  <button type="button" className="secondary" onClick={() => startEdit(transaction)}>
                    Edit
                  </button>
                </div>
              </article>
            ))}
          </div>
        ) : (
          <WorkspaceEmpty title="No journal entries" message="Record the first payment or expense to seed the finance journal." />
        )}
      </WorkspacePanel>
    </div>
  );
}
