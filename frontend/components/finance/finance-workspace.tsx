'use client';

import Link from 'next/link';
import { useEffect, useState } from 'react';
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
import {
  DraftRecommendationCard,
  StagedActionFooter,
  WorkspaceEmpty,
  WorkspaceNotice,
  WorkspacePanel,
} from '@/components/commerce/workspace-primitives';

type FinanceDraft = {
  transaction_id: string | null;
  origin_type: FinanceTransactionInput['origin_type'];
  occurred_at: string;
  amount: string;
  direction: FinanceTransactionInput['direction'];
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
    direction: 'in',
    status: 'completed',
    counterparty_name: '',
    counterparty_type: 'internal',
    reference: '',
    note: '',
  };
}

function isCommerceOrigin(transaction: FinanceTransaction) {
  return transaction.origin_type === 'sale_fulfillment' || transaction.origin_type === 'return_refund';
}

function buildDraftFromTransaction(transaction: FinanceTransaction): FinanceDraft {
  return {
    transaction_id: transaction.transaction_id,
    origin_type: transaction.origin_type === 'manual_expense' ? 'manual_expense' : 'manual_payment',
    occurred_at: isoToLocalInput(transaction.occurred_at),
    amount: String(transaction.amount),
    direction: transaction.direction,
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

function originLabel(transaction: FinanceTransaction) {
  return transaction.source_label || transaction.origin_type.replaceAll('_', ' ');
}

function sourceHref(transaction: FinanceTransaction) {
  const query = encodeURIComponent(transaction.reference || transaction.origin_id || transaction.transaction_id);
  if (transaction.origin_type === 'sale_fulfillment') return `/sales?q=${query}`;
  if (transaction.origin_type === 'return_refund') return `/returns?q=${query}`;
  return null;
}

function splitStatusLabel(transaction: FinanceTransaction) {
  if (transaction.origin_type === 'sale_fulfillment' && transaction.status === 'posted') return 'Posted to finance';
  if (transaction.origin_type === 'return_refund' && transaction.status === 'posted') return 'Refund posted';
  return transaction.status;
}

export function FinanceWorkspace() {
  const [overview, setOverview] = useState<FinanceOverview | null>(null);
  const [commerceTransactions, setCommerceTransactions] = useState<FinanceTransaction[]>([]);
  const [manualTransactions, setManualTransactions] = useState<FinanceTransaction[]>([]);
  const [recentRefunds, setRecentRefunds] = useState<FinanceTransaction[]>([]);
  const [receivables, setReceivables] = useState<FinanceReceivable[]>([]);
  const [payables, setPayables] = useState<FinancePayable[]>([]);
  const [draft, setDraft] = useState<FinanceDraft>(buildEmptyDraft());
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

  function resetDraft() {
    setDraft(buildEmptyDraft());
    setNotice('');
  }

  function editManualTransaction(transaction: FinanceTransaction) {
    if (!transaction.editable || isCommerceOrigin(transaction)) return;
    setDraft(buildDraftFromTransaction(transaction));
    setNotice(`Editing ${transaction.reference || transaction.transaction_id}.`);
    setError('');
  }

  async function submitTransaction() {
    if (!draft.amount.trim() || numberFromString(draft.amount) <= 0) {
      setError('Amount must be greater than zero.');
      return;
    }

    setSaving(true);
    setError('');
    try {
      const payload = buildPayload(draft);
      if (draft.transaction_id) {
        await updateFinanceTransaction(draft.transaction_id, payload);
        setNotice('Manual finance entry updated.');
      } else {
        await createFinanceTransaction(payload);
        setNotice(payload.origin_type === 'manual_expense' ? 'Manual expense recorded.' : 'Manual payment recorded.');
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

  const snapshotCards = [
    { label: 'Revenue', value: overview.revenue },
    { label: 'Cash collected', value: overview.cash_collected },
    { label: 'Refunds paid', value: overview.refunds_paid },
    { label: 'Expenses', value: overview.expenses },
    { label: 'Receivables', value: overview.receivables },
    { label: 'Net operating', value: overview.net_operating },
  ];

  return (
    <div className="finance-module">
      <WorkspaceNotice tone="info">
        Fulfilled sales and paid refunds post automatically. Use this workspace only for manual operating payments and expenses.
      </WorkspaceNotice>
      {notice ? <WorkspaceNotice tone="success">{notice}</WorkspaceNotice> : null}
      {error ? <WorkspaceNotice tone="error">{error}</WorkspaceNotice> : null}

      <div className="finance-cards">
        {snapshotCards.map((card) => (
          <article key={card.label} className="ps-card">
            <p>{card.label}</p>
            <strong>{formatMoney(card.value)}</strong>
          </article>
        ))}
      </div>

      <div className="finance-layout">
        <WorkspacePanel
          title={draft.transaction_id ? 'Edit manual entry' : 'Record manual finance entry'}
          description="Manual finance is limited to operating cash movement. Commerce-origin transactions stay read-only and must be corrected from Sales or Returns."
        >
          <form
            className="finance-entry-form workspace-form"
            onSubmit={(event) => {
              event.preventDefault();
              void submitTransaction();
            }}
          >
            <div className="workspace-form-grid compact">
              <label>
                Entry type
                <select
                  value={draft.origin_type}
                  onChange={(event) =>
                    setDraft((current) => ({
                      ...current,
                      origin_type: event.target.value === 'manual_expense' ? 'manual_expense' : 'manual_payment',
                      direction: event.target.value === 'manual_expense' ? 'out' : 'in',
                      status: event.target.value === 'manual_expense' ? 'unpaid' : 'completed',
                      counterparty_type: event.target.value === 'manual_expense' ? 'vendor' : current.counterparty_type,
                    }))
                  }
                >
                  <option value="manual_payment">Manual payment</option>
                  <option value="manual_expense">Manual expense</option>
                </select>
              </label>
              <label>
                Occurred at
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
                Reference
                <input
                  value={draft.reference}
                  onChange={(event) => setDraft((current) => ({ ...current, reference: event.target.value }))}
                  placeholder="Receipt, transfer, or bill number"
                />
              </label>
              <label>
                Counterparty
                <input
                  value={draft.counterparty_name}
                  onChange={(event) => setDraft((current) => ({ ...current, counterparty_name: event.target.value }))}
                  placeholder={draft.origin_type === 'manual_expense' ? 'Supplier or payee' : 'Customer or internal source'}
                />
              </label>
              <label>
                Counterparty type
                <select
                  value={draft.counterparty_type}
                  onChange={(event) =>
                    setDraft((current) => ({ ...current, counterparty_type: event.target.value as FinanceCounterpartyType }))
                  }
                >
                  {draft.origin_type === 'manual_expense' ? (
                    <>
                      <option value="vendor">Vendor</option>
                      <option value="internal">Internal</option>
                    </>
                  ) : (
                    <>
                      <option value="internal">Internal</option>
                      <option value="customer">Customer</option>
                    </>
                  )}
                </select>
              </label>
              <label>
                Status
                <select
                  value={draft.status}
                  onChange={(event) => setDraft((current) => ({ ...current, status: event.target.value as FinanceDraft['status'] }))}
                >
                  {draft.origin_type === 'manual_expense' ? (
                    <>
                      <option value="unpaid">Unpaid</option>
                      <option value="partial">Partial</option>
                      <option value="paid">Paid</option>
                    </>
                  ) : (
                    <>
                      <option value="completed">Completed</option>
                      <option value="pending">Pending</option>
                      <option value="posted">Posted</option>
                    </>
                  )}
                </select>
              </label>
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
              title={draft.origin_type === 'manual_expense' ? 'Manual expense draft' : 'Manual payment draft'}
              summary="Commerce-origin events post automatically and stay read-only in this workspace."
            >
              <div className="settings-context">
                <div>
                  <dt>Write mode</dt>
                  <dd>{draft.transaction_id ? 'Updating a previously recorded manual entry.' : 'Creating a manual operating entry.'}</dd>
                </div>
                <div>
                  <dt>Journal effect</dt>
                  <dd>{draft.origin_type === 'manual_expense' ? 'Cash out via operating expense.' : 'Cash in via manual payment.'}</dd>
                </div>
                <div>
                  <dt>Counterparty</dt>
                  <dd>{draft.counterparty_name.trim() || 'Not specified yet.'}</dd>
                </div>
              </div>
            </DraftRecommendationCard>

            <StagedActionFooter summary="Manual entries stay editable. Commerce-origin events are corrected from Sales or Returns.">
              <button type="button" className="secondary" onClick={resetDraft} disabled={saving}>
                Reset
              </button>
              <button type="submit" className="btn-primary" disabled={saving}>
                {saving
                  ? 'Saving…'
                  : draft.transaction_id
                    ? 'Update manual entry'
                    : draft.origin_type === 'manual_expense'
                      ? 'Record manual expense'
                      : 'Record manual payment'}
              </button>
            </StagedActionFooter>
          </form>
        </WorkspacePanel>

        <div className="finance-side-stack">
          <WorkspacePanel
            title="Commerce-origin transactions"
            description="These transactions are created by fulfillment or refund workflows and are read-only here."
          >
            {commerceTransactions.length ? (
              <div className="finance-row-list">
                {commerceTransactions.map((transaction) => {
                  const href = sourceHref(transaction);
                  return (
                    <article key={transaction.transaction_id} className="finance-row-card finance-row-readonly">
                      <div className="finance-row-card-head">
                        <div>
                          <span className="finance-origin-pill">{originLabel(transaction)}</span>
                          <strong>{transaction.reference || transaction.source_label}</strong>
                          <p>{transaction.note || transaction.counterparty_name || transaction.source_label}</p>
                        </div>
                        <strong className={transaction.direction === 'out' ? 'delta-negative' : 'delta-positive'}>
                          {transaction.direction === 'out' ? '-' : '+'}
                          {formatMoney(transaction.amount)}
                        </strong>
                      </div>
                      <div className="finance-row-meta">
                        <span>{splitStatusLabel(transaction)}</span>
                        <span>{formatDateTime(transaction.occurred_at)}</span>
                        {transaction.counterparty_name ? <span>{transaction.counterparty_name}</span> : null}
                        {href ? (
                          <Link href={href} className="button-link secondary finance-source-link">
                            Open source
                          </Link>
                        ) : null}
                      </div>
                    </article>
                  );
                })}
              </div>
            ) : (
              <WorkspaceEmpty
                title="No commerce-origin transactions yet"
                message="Fulfilled sales and paid refunds will appear here automatically after their native workflows post finance events."
              />
            )}
          </WorkspacePanel>

          <WorkspacePanel
            title="Manual finance transactions"
            description="Keep operating cash movement here. Manual entries remain editable."
          >
            {manualTransactions.length ? (
              <div className="finance-row-list finance-row-list-tight">
                {manualTransactions.map((transaction) => (
                  <article key={transaction.transaction_id} className="finance-transaction-card">
                    <div className="finance-row-card-head">
                      <div>
                        <span className="finance-origin-pill">{originLabel(transaction)}</span>
                        <strong>{transaction.reference || transaction.source_label}</strong>
                        <p>{transaction.note || transaction.counterparty_name || transaction.source_label}</p>
                      </div>
                      <strong className={transaction.direction === 'out' ? 'delta-negative' : 'delta-positive'}>
                        {transaction.direction === 'out' ? '-' : '+'}
                        {formatMoney(transaction.amount)}
                      </strong>
                    </div>
                    <div className="finance-row-meta">
                      <span>{transaction.status}</span>
                      <span>{formatDateTime(transaction.occurred_at)}</span>
                      {transaction.counterparty_name ? <span>{transaction.counterparty_name}</span> : null}
                    </div>
                    <div className="workspace-actions">
                      <button type="button" className="secondary" onClick={() => editManualTransaction(transaction)}>
                        Edit
                      </button>
                    </div>
                  </article>
                ))}
              </div>
            ) : (
              <WorkspaceEmpty title="No manual finance entries" message="Record the first manual payment or expense to seed the journal." />
            )}
          </WorkspacePanel>
        </div>
      </div>

      <WorkspacePanel
        title="Receivables and recent refunds"
        description="Revenue stays separate from cash collected. Refund payouts appear as their own finance events."
      >
        <div className="finance-two-up">
          <section className="finance-ledger-block">
            <header>
              <h4>Receivables</h4>
              <p>{formatMoney(overview.receivables)} still open from fulfilled sales.</p>
            </header>
            {receivables.length ? (
              <div className="finance-row-list">
                {receivables.map((item) => (
                  <article key={item.sale_id} className="finance-row-card">
                    <div className="finance-row-card-head">
                      <div>
                        <strong>{item.sale_no}</strong>
                        <p>{item.customer_name}</p>
                      </div>
                      <strong>{formatMoney(item.outstanding_balance)}</strong>
                    </div>
                    <div className="finance-row-meta">
                      <span>Paid {formatMoney(item.amount_paid)}</span>
                      <span>{item.payment_status}</span>
                      <span>{formatDateTime(item.sale_date)}</span>
                    </div>
                  </article>
                ))}
              </div>
            ) : (
              <WorkspaceEmpty title="No outstanding receivables" message="Open customer balances will appear here once fulfilled sales are posted." />
            )}
          </section>

          <section className="finance-ledger-block">
            <header>
              <h4>Payables</h4>
              <p>{formatMoney(overview.payables)} still open from manual operating expenses.</p>
            </header>
            {payables.length ? (
              <div className="finance-row-list">
                {payables.map((item) => (
                  <article key={item.transaction_id} className="finance-row-card">
                    <div className="finance-row-card-head">
                      <div>
                        <strong>{item.reference || 'Manual expense'}</strong>
                        <p>{item.vendor_name || item.note || 'Operating payable'}</p>
                      </div>
                      <strong className="delta-negative">{formatMoney(item.amount)}</strong>
                    </div>
                    <div className="finance-row-meta">
                      <span>{item.status}</span>
                      <span>{formatDateTime(item.occurred_at)}</span>
                    </div>
                  </article>
                ))}
              </div>
            ) : (
              <WorkspaceEmpty title="No open payables" message="Unpaid manual operating expenses will appear here." />
            )}
          </section>
        </div>

        <section className="finance-ledger-block finance-refund-block">
          <header>
            <h4>Recent refunds</h4>
            <p>{formatMoney(overview.refunds_paid)} paid out from return workflows.</p>
          </header>
          {recentRefunds.length ? (
            <div className="finance-row-list">
              {recentRefunds.map((transaction) => (
                <article key={transaction.transaction_id} className="finance-row-card finance-row-readonly">
                  <div className="finance-row-card-head">
                    <div>
                      <span className="finance-origin-pill">From Returns</span>
                      <strong>{transaction.reference || transaction.source_label}</strong>
                      <p>{transaction.note || transaction.counterparty_name || transaction.source_label}</p>
                    </div>
                    <strong className="delta-negative">-{formatMoney(transaction.amount)}</strong>
                  </div>
                  <div className="finance-row-meta">
                    <span>{splitStatusLabel(transaction)}</span>
                    <span>{formatDateTime(transaction.occurred_at)}</span>
                    {transaction.counterparty_name ? <span>{transaction.counterparty_name}</span> : null}
                    {sourceHref(transaction) ? (
                      <Link href={sourceHref(transaction)!} className="button-link secondary finance-source-link">
                        Open return
                      </Link>
                    ) : null}
                  </div>
                </article>
              ))}
            </div>
          ) : (
            <WorkspaceEmpty title="No paid refunds yet" message="Refunds will appear here once return payment events are posted." />
          )}
        </section>
      </WorkspacePanel>
    </div>
  );
}
