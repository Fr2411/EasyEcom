'use client';

import Link from 'next/link';
import { useEffect, useMemo, useState } from 'react';
import { createFinanceTransaction, getFinanceWorkspace, updateFinanceTransaction } from '@/lib/api/finance';
import { formatDateTime, formatMoney, numberFromString } from '@/lib/commerce-format';
import type {
  FinanceCounterpartyType,
  FinanceOverview,
  FinancePayable,
  FinanceReceivable,
  FinanceTransaction,
  FinanceTransactionInput,
} from '@/types/finance';
import { WorkspaceEmpty, WorkspaceNotice, WorkspacePanel } from '@/components/commerce/workspace-primitives';

type FinanceDraft = {
  transaction_id: string | null;
  origin_type: FinanceTransactionInput['origin_type'];
  occurred_at: string;
  amount: string;
  status: NonNullable<FinanceTransactionInput['status']>;
  counterparty_name: string;
  counterparty_type: FinanceCounterpartyType;
  reference: string;
  note: string;
};

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
    transaction_id: null,
    origin_type: 'manual_payment',
    occurred_at: currentLocalDateTime(),
    amount: '',
    status: 'completed',
    counterparty_name: '',
    counterparty_type: 'internal',
    reference: '',
    note: '',
  };
}

function buildDraftFromTransaction(transaction: FinanceTransaction): FinanceDraft {
  return {
    transaction_id: transaction.transaction_id,
    origin_type: transaction.origin_type === 'manual_expense' ? 'manual_expense' : 'manual_payment',
    occurred_at: isoToLocalInput(transaction.occurred_at),
    amount: String(transaction.amount),
    status: transaction.status,
    counterparty_name: transaction.counterparty_name ?? '',
    counterparty_type: transaction.counterparty_type ?? 'internal',
    reference: transaction.reference,
    note: transaction.note,
  };
}

function buildPayload(draft: FinanceDraft): FinanceTransactionInput {
  return {
    origin_type: draft.origin_type,
    occurred_at: new Date(draft.occurred_at).toISOString(),
    amount: numberFromString(draft.amount),
    direction: draft.origin_type === 'manual_expense' ? 'out' : 'in',
    status: draft.origin_type === 'manual_expense' ? draft.status : draft.status === 'unpaid' ? 'pending' : draft.status,
    reference: draft.reference.trim(),
    note: draft.note.trim(),
    counterparty_name: draft.counterparty_name.trim() || undefined,
    counterparty_type: draft.counterparty_name.trim() ? draft.counterparty_type : undefined,
  };
}

function buildModuleHref(path: '/sales' | '/returns', params: Record<string, string | undefined>) {
  const search = new URLSearchParams();
  Object.entries(params).forEach(([key, value]) => {
    if (!value) return;
    search.set(key, value);
  });
  const query = search.toString();
  return query ? `${path}?${query}` : path;
}

function sourceHref(transaction: FinanceTransaction) {
  const query = transaction.reference || transaction.origin_id || transaction.transaction_id;
  if (transaction.origin_type === 'sale_fulfillment') {
    return buildModuleHref('/sales', {
      seed_order_id: transaction.origin_id ?? undefined,
      q: query,
    });
  }
  if (transaction.origin_type === 'return_refund') {
    return buildModuleHref('/returns', {
      seed_return_id: transaction.origin_id ?? undefined,
      q: query,
      tab: 'history',
    });
  }
  return null;
}

function isEditableManual(transaction: FinanceTransaction) {
  return transaction.editable && (transaction.origin_type === 'manual_payment' || transaction.origin_type === 'manual_expense');
}

export function FinanceWorkspace() {
  const [overview, setOverview] = useState<FinanceOverview | null>(null);
  const [commerceTransactions, setCommerceTransactions] = useState<FinanceTransaction[]>([]);
  const [manualTransactions, setManualTransactions] = useState<FinanceTransaction[]>([]);
  const [recentRefunds, setRecentRefunds] = useState<FinanceTransaction[]>([]);
  const [receivables, setReceivables] = useState<FinanceReceivable[]>([]);
  const [payables, setPayables] = useState<FinancePayable[]>([]);
  const [draft, setDraft] = useState<FinanceDraft>(buildEmptyDraft());
  const [showEntryForm, setShowEntryForm] = useState(false);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [notice, setNotice] = useState('');
  const [error, setError] = useState('');

  async function refreshWorkspace() {
    setLoading(true);
    try {
      const payload = await getFinanceWorkspace();
      setOverview(payload.overview);
      setCommerceTransactions(payload.commerce_transactions ?? []);
      setManualTransactions(payload.manual_transactions ?? []);
      setRecentRefunds(payload.recent_refunds ?? []);
      setReceivables(payload.receivables ?? []);
      setPayables(payload.payables ?? []);
      setError('');
    } catch (loadError) {
      setError(loadError instanceof Error ? loadError.message : 'Unable to load finance workspace.');
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void refreshWorkspace();
  }, []);

  const cards = useMemo(() => {
    if (!overview) return [];
    return [
      { label: 'Cash collected', value: overview.cash_collected },
      { label: 'Refunds paid', value: overview.refunds_paid },
      { label: 'Expenses', value: overview.expenses },
      { label: 'Receivables', value: overview.receivables },
      { label: 'Net operating', value: overview.net_operating },
    ];
  }, [overview]);

  const resetDraft = () => {
    setDraft(buildEmptyDraft());
    setShowEntryForm(false);
  };

  const editTransaction = (transaction: FinanceTransaction) => {
    if (!isEditableManual(transaction)) return;
    setDraft(buildDraftFromTransaction(transaction));
    setShowEntryForm(true);
    setNotice(`Editing ${transaction.reference || transaction.transaction_id}.`);
    setError('');
  };

  const submitTransaction = async () => {
    if (!draft.amount.trim() || numberFromString(draft.amount) <= 0) {
      setError('Amount must be greater than zero.');
      return;
    }

    setSaving(true);
    try {
      const payload = buildPayload(draft);
      if (draft.transaction_id) {
        await updateFinanceTransaction(draft.transaction_id, payload);
        setNotice('Cash entry updated.');
      } else {
        await createFinanceTransaction(payload);
        setNotice(payload.origin_type === 'manual_expense' ? 'Expense entry recorded.' : 'Cash entry recorded.');
      }
      resetDraft();
      await refreshWorkspace();
    } catch (submitError) {
      setError(submitError instanceof Error ? submitError.message : 'Unable to save cash entry.');
    } finally {
      setSaving(false);
    }
  };

  if (loading && !overview) {
    return <div className="reports-loading">Loading finance…</div>;
  }

  if (error && !overview) {
    return <div className="reports-error">{error}</div>;
  }

  if (!overview) {
    return <WorkspaceEmpty title="Finance unavailable" message="No finance data was returned for this workspace." />;
  }

  return (
    <div className="operations-page finance-module">
      <div className="operations-toolbar">
        <div>
          <h2>Operational cash visibility</h2>
        </div>
        <div className="operations-toolbar-actions">
          <button type="button" className="btn-primary" onClick={() => setShowEntryForm((current) => !current)}>
            {showEntryForm ? 'Close Entry' : 'Add Cash Entry'}
          </button>
        </div>
      </div>

      {notice ? <WorkspaceNotice tone="success">{notice}</WorkspaceNotice> : null}
      {error ? <WorkspaceNotice tone="error">{error}</WorkspaceNotice> : null}

      <div className="operations-kpi-grid">
        {cards.map((card) => (
          <article key={card.label} className="operations-kpi-card">
            <span>{card.label}</span>
            <strong>{formatMoney(card.value)}</strong>
          </article>
        ))}
      </div>

      <div className="operations-split-layout finance-split-layout">
        <WorkspacePanel title="Receivables and refund status" description="Review money still to collect, refund payments already posted, and commerce-linked activity.">
          <div className="operations-dual-section">
            <section>
              <div className="operations-section-heading">
                <h4>Receivables</h4>
              </div>
              {receivables.length ? (
                <div className="operations-list-stack compact">
                  {receivables.map((item) => (
                    <Link
                      key={item.sale_id}
                      href={buildModuleHref('/sales', {
                        seed_order_id: item.sale_id,
                        q: item.sale_no,
                      })}
                      className="operations-list-card as-link"
                    >
                      <div className="operations-list-card-head">
                        <strong>{item.sale_no}</strong>
                        <span>{formatMoney(item.outstanding_balance)}</span>
                      </div>
                      <p>{item.customer_name}</p>
                      <div className="operations-inline-meta compact">
                        <span>{item.payment_status}</span>
                        <span>{formatDateTime(item.sale_date)}</span>
                      </div>
                    </Link>
                  ))}
                </div>
              ) : (
                <WorkspaceEmpty title="No open receivables" message="Outstanding customer balances will appear here once unpaid sales exist." />
              )}
            </section>

            <section>
              <div className="operations-section-heading">
                <h4>Recent refunds</h4>
              </div>
              {recentRefunds.length ? (
                <div className="operations-list-stack compact">
                  {recentRefunds.map((item) => (
                    <Link
                      key={item.transaction_id}
                      href={buildModuleHref('/returns', {
                        seed_return_id: item.origin_id ?? undefined,
                        q: item.reference,
                        tab: 'history',
                      })}
                      className="operations-list-card as-link"
                    >
                      <div className="operations-list-card-head">
                        <strong>{item.reference || 'Refund payment'}</strong>
                        <span>-{formatMoney(item.amount)}</span>
                      </div>
                      <p>{item.counterparty_name || 'Customer refund'}</p>
                      <div className="operations-inline-meta compact">
                        <span>{formatDateTime(item.occurred_at)}</span>
                        <span>{item.status}</span>
                      </div>
                    </Link>
                  ))}
                </div>
              ) : (
                <WorkspaceEmpty title="No recent refunds" message="Refund cash-out events will appear here after return refunds are posted." />
              )}
            </section>
          </div>

          {payables.length ? (
            <section className="operations-subsection-block">
              <div className="operations-section-heading">
                <h4>Outstanding payables</h4>
              </div>
              <div className="operations-list-stack compact">
                {payables.map((item) => (
                  <div key={item.transaction_id} className="operations-list-card static">
                    <div className="operations-list-card-head">
                      <strong>{item.reference}</strong>
                      <span>{formatMoney(item.amount)}</span>
                    </div>
                    <p>{item.vendor_name || item.note || 'Payable entry'}</p>
                    <div className="operations-inline-meta compact">
                      <span>{item.status}</span>
                      <span>{formatDateTime(item.occurred_at)}</span>
                    </div>
                  </div>
                ))}
              </div>
            </section>
          ) : null}

          <section className="operations-subsection-block">
            <div className="operations-section-heading">
              <h4>Commerce-linked activity</h4>
            </div>
            {commerceTransactions.length ? (
              <div className="operations-list-stack compact">
                {commerceTransactions.map((item) => {
                  const href = sourceHref(item);
                  const card = (
                    <div className="operations-list-card-head">
                      <strong>{item.reference || item.source_label}</strong>
                      <span>{item.direction === 'out' ? '-' : ''}{formatMoney(item.amount)}</span>
                    </div>
                  );
                  return href ? (
                    <Link key={item.transaction_id} href={href} className="operations-list-card as-link">
                      {card}
                      <p>{item.counterparty_name || item.source_label}</p>
                      <div className="operations-inline-meta compact">
                        <span>{item.source_label}</span>
                        <span>{formatDateTime(item.occurred_at)}</span>
                      </div>
                    </Link>
                  ) : (
                    <div key={item.transaction_id} className="operations-list-card static">
                      {card}
                      <p>{item.counterparty_name || item.source_label}</p>
                      <div className="operations-inline-meta compact">
                        <span>{item.source_label}</span>
                        <span>{formatDateTime(item.occurred_at)}</span>
                      </div>
                    </div>
                  );
                })}
              </div>
            ) : (
              <WorkspaceEmpty title="No commerce activity yet" message="Completed sales and refund postings will appear here automatically." />
            )}
          </section>
        </WorkspacePanel>

        <WorkspacePanel title="Manual cash ledger" description="Create or edit manual cash-in and expense entries without changing commerce-origin transactions.">
          {showEntryForm ? (
            <div className="operations-detail-stack">
              <div className="operations-form-grid compact">
                <label>
                  Entry type
                  <select
                    value={draft.origin_type}
                    onChange={(event) =>
                      setDraft((current) => ({
                        ...current,
                        origin_type: event.target.value === 'manual_expense' ? 'manual_expense' : 'manual_payment',
                        status: event.target.value === 'manual_expense' ? 'unpaid' : 'completed',
                        counterparty_type: event.target.value === 'manual_expense' ? 'vendor' : 'internal',
                      }))
                    }
                  >
                    <option value="manual_payment">Cash in</option>
                    <option value="manual_expense">Expense</option>
                  </select>
                </label>
                <label>
                  Date and time
                  <input
                    type="datetime-local"
                    value={draft.occurred_at}
                    onChange={(event) => setDraft((current) => ({ ...current, occurred_at: event.target.value }))}
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
                  Status
                  <select
                    value={draft.status}
                    onChange={(event) => setDraft((current) => ({ ...current, status: event.target.value as FinanceDraft['status'] }))}
                  >
                    <option value="completed">Completed</option>
                    <option value="pending">Pending</option>
                    <option value="unpaid">Unpaid</option>
                    <option value="paid">Paid</option>
                  </select>
                </label>
                <label>
                  Counterparty
                  <input
                    value={draft.counterparty_name}
                    onChange={(event) => setDraft((current) => ({ ...current, counterparty_name: event.target.value }))}
                    placeholder="Supplier, courier, internal transfer"
                  />
                </label>
                <label>
                  Counterparty type
                  <select
                    value={draft.counterparty_type}
                    onChange={(event) => setDraft((current) => ({ ...current, counterparty_type: event.target.value as FinanceCounterpartyType }))}
                  >
                    <option value="internal">Internal</option>
                    <option value="vendor">Vendor</option>
                    <option value="customer">Customer</option>
                  </select>
                </label>
                <label>
                  Reference
                  <input
                    value={draft.reference}
                    onChange={(event) => setDraft((current) => ({ ...current, reference: event.target.value }))}
                    placeholder="Voucher or transfer reference"
                  />
                </label>
                <label className="field-span-2">
                  Note
                  <textarea
                    rows={3}
                    value={draft.note}
                    onChange={(event) => setDraft((current) => ({ ...current, note: event.target.value }))}
                    placeholder="Short audit note"
                  />
                </label>
              </div>
              <div className="operations-toolbar-actions">
                <button type="button" className="btn-primary" onClick={() => void submitTransaction()} disabled={saving}>
                  {saving ? 'Saving…' : 'Save Entry'}
                </button>
                <button type="button" className="secondary" onClick={resetDraft}>Reset</button>
              </div>
            </div>
          ) : null}

          {manualTransactions.length ? (
            <div className="operations-list-stack compact">
              {manualTransactions.map((item) => (
                <button key={item.transaction_id} type="button" className="operations-list-card static as-button" onClick={() => editTransaction(item)}>
                  <div className="operations-list-card-head">
                    <strong>{item.reference || item.source_label}</strong>
                    <span>{item.direction === 'out' ? '-' : ''}{formatMoney(item.amount)}</span>
                  </div>
                  <p>{item.counterparty_name || item.note || 'Manual cash entry'}</p>
                  <div className="operations-inline-meta compact">
                    <span>{item.origin_type === 'manual_expense' ? 'Expense' : 'Cash in'}</span>
                    <span>{item.status}</span>
                    <span>{formatDateTime(item.occurred_at)}</span>
                  </div>
                </button>
              ))}
            </div>
          ) : (
            <WorkspaceEmpty title="No manual cash entries" message="Use Add Cash Entry to record money-in or expense items that are not created by sales or returns." />
          )}
        </WorkspacePanel>
      </div>
      <div className="mobile-action-safe-spacer" aria-hidden="true" />
    </div>
  );
}
