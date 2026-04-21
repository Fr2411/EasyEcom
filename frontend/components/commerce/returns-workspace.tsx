'use client';

import { useEffect, useRef, useState } from 'react';
import { useSearchParams } from 'next/navigation';
import {
  createSalesReturn,
  getEligibleReturnLines,
  getReturns,
  recordSalesReturnRefund,
  searchReturnOrders,
} from '@/lib/api/commerce';
import type { ReturnCreatePayload, ReturnEligibleLines, ReturnLookupOrder, ReturnRecord } from '@/types/returns';
import { WorkspaceEmpty, WorkspaceNotice, WorkspacePanel, WorkspaceTabs } from '@/components/commerce/workspace-primitives';
import { formatDateTime, formatMoney, formatQuantity } from '@/lib/commerce-format';

type ReturnsTab = 'create' | 'history';

type ReturnRefundDraft = {
  refund_date: string;
  amount: string;
  method: string;
  reference: string;
  note: string;
};

function currentLocalDateTime() {
  const now = new Date();
  const local = new Date(now.getTime() - now.getTimezoneOffset() * 60000);
  return local.toISOString().slice(0, 16);
}

function createEmptyDraft(): ReturnCreatePayload {
  return {
    sales_order_id: '',
    notes: '',
    refund_status: 'pending',
    lines: [],
  };
}

function buildRefundDraft(record?: ReturnRecord | null): ReturnRefundDraft {
  const outstanding = record?.refund_outstanding_amount ? Number(record.refund_outstanding_amount) : NaN;
  const defaultAmount =
    record && !Number.isNaN(outstanding) && outstanding > 0
      ? record.refund_outstanding_amount
      : record?.refund_amount ?? '';

  return {
    refund_date: currentLocalDateTime(),
    amount: String(defaultAmount ?? ''),
    method: 'bank transfer',
    reference: record?.return_number ?? '',
    note: record ? `Refund payment for ${record.return_number}` : '',
  };
}

function buildReturnStatusLabel(record: ReturnRecord) {
  const outstanding = Number(record.refund_outstanding_amount ?? '0');
  if (record.status === 'closed') return 'Closed';
  if (outstanding > 0) return 'Refund pending';
  if (Number(record.refund_paid_amount ?? '0') > 0) return 'Refund recorded';
  return 'Open';
}

function buildSeedKey(searchParams: { get: (name: string) => string | null }) {
  return [
    (searchParams.get('seed_phone') ?? '').trim(),
    (searchParams.get('seed_email') ?? '').trim(),
  ].join('|');
}

export function ReturnsWorkspace() {
  const searchParams = useSearchParams();
  const searchKey = searchParams.toString();
  const handledSeedKeyRef = useRef('');
  const [activeTab, setActiveTab] = useState<ReturnsTab>('create');
  const [lookupQuery, setLookupQuery] = useState('');
  const [lookupOrders, setLookupOrders] = useState<ReturnLookupOrder[]>([]);
  const [selectedOrder, setSelectedOrder] = useState<ReturnLookupOrder | null>(null);
  const [eligible, setEligible] = useState<ReturnEligibleLines | null>(null);
  const [draft, setDraft] = useState<ReturnCreatePayload>(createEmptyDraft());
  const [historyQuery, setHistoryQuery] = useState('');
  const [history, setHistory] = useState<ReturnRecord[]>([]);
  const [selectedReturn, setSelectedReturn] = useState<ReturnRecord | null>(null);
  const [refundDraft, setRefundDraft] = useState<ReturnRefundDraft>(buildRefundDraft());
  const [lookupPending, setLookupPending] = useState(false);
  const [eligiblePending, setEligiblePending] = useState(false);
  const [historyLoading, setHistoryLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [notice, setNotice] = useState('');
  const [error, setError] = useState('');

  const loadHistory = async (query = '') => {
    setHistoryLoading(true);
    try {
      const payload = await getReturns(query);
      setHistory(payload.items ?? []);
      setError('');
    } catch (loadError) {
      setError(loadError instanceof Error ? loadError.message : 'Unable to load returns.');
    } finally {
      setHistoryLoading(false);
    }
  };

  useEffect(() => {
    const q = (searchParams.get('q') ?? '').trim();
    const tab = (searchParams.get('tab') ?? '').trim();
    setHistoryQuery(q);
    if (tab === 'history' || q) {
      setActiveTab('history');
    } else if (tab === 'create') {
      setActiveTab('create');
    }
    void loadHistory(q);
  }, [searchKey]);

  useEffect(() => {
    const seedKey = buildSeedKey(searchParams);
    if (!seedKey.replaceAll('|', '')) {
      handledSeedKeyRef.current = '';
      return;
    }
    if (handledSeedKeyRef.current === seedKey) {
      return;
    }
    handledSeedKeyRef.current = seedKey;

    const seedPhone = (searchParams.get('seed_phone') ?? '').trim();
    const seedEmail = (searchParams.get('seed_email') ?? '').trim();
    const seededQuery = seedPhone || seedEmail;
    if (!seededQuery) return;

    setActiveTab('create');
    setLookupQuery(seededQuery);
    void runOrderLookup(seededQuery);
  }, [searchKey]);

  const resetCreateFlow = () => {
    setLookupQuery('');
    setLookupOrders([]);
    setSelectedOrder(null);
    setEligible(null);
    setDraft(createEmptyDraft());
  };

  const openReturnDetails = (record: ReturnRecord) => {
    setSelectedReturn(record);
    setRefundDraft(buildRefundDraft(record));
  };

  const openEligibleLines = async (order: ReturnLookupOrder) => {
    setSelectedOrder(order);
    setEligiblePending(true);
    try {
      const payload = await getEligibleReturnLines(order.sales_order_id);
      setEligible(payload);
      setDraft({
        sales_order_id: order.sales_order_id,
        notes: '',
        refund_status: 'pending',
        lines: payload.lines.map((line) => ({
          sales_order_item_id: line.sales_order_item_id,
          quantity: line.eligible_quantity === '0' ? '0' : line.eligible_quantity,
          restock_quantity: line.eligible_quantity === '0' ? '0' : line.eligible_quantity,
          disposition: 'restock',
          unit_refund_amount: line.unit_price,
          reason: '',
        })),
      });
      setError('');
    } catch (detailError) {
      setError(detailError instanceof Error ? detailError.message : 'Unable to load eligible lines.');
    } finally {
      setEligiblePending(false);
    }
  };

  const runOrderLookup = async (query: string) => {
    const trimmed = query.trim();
    if (!trimmed) {
      setLookupOrders([]);
      setSelectedOrder(null);
      setEligible(null);
      setDraft(createEmptyDraft());
      return;
    }

    setLookupPending(true);
    try {
      const payload = await searchReturnOrders(trimmed);
      setLookupOrders(payload.items ?? []);
      setError('');
      if (payload.items.length === 1) {
        await openEligibleLines(payload.items[0]);
      }
    } catch (searchError) {
      setError(searchError instanceof Error ? searchError.message : 'Unable to search completed orders.');
    } finally {
      setLookupPending(false);
    }
  };

  const submitReturn = async () => {
    if (!eligible) {
      setError('Open a completed order before creating a return.');
      return;
    }

    const payloadLines = draft.lines.filter((line) => Number(line.quantity) > 0);
    if (!payloadLines.length) {
      setError('Add at least one return line before creating the return.');
      return;
    }

    setSubmitting(true);
    try {
      const response = await createSalesReturn({
        ...draft,
        lines: payloadLines,
      });
      setNotice(`Return ${response.return_number} created.`);
      resetCreateFlow();
      await loadHistory(historyQuery);
      setSelectedReturn(response);
      setRefundDraft(buildRefundDraft(response));
      setActiveTab('history');
    } catch (submitError) {
      setError(submitError instanceof Error ? submitError.message : 'Unable to create return.');
    } finally {
      setSubmitting(false);
    }
  };

  const submitRefund = async () => {
    if (!selectedReturn) {
      setError('Select a return before recording a refund.');
      return;
    }
    if (!refundDraft.amount.trim() || Number(refundDraft.amount) <= 0) {
      setError('Refund amount must be greater than zero.');
      return;
    }

    setSubmitting(true);
    try {
      const response = await recordSalesReturnRefund(selectedReturn.sales_return_id, {
        refund_date: new Date(refundDraft.refund_date).toISOString(),
        amount: refundDraft.amount,
        method: refundDraft.method.trim(),
        reference: refundDraft.reference.trim(),
        note: refundDraft.note.trim(),
      });
      setNotice(`Refund recorded for ${response.return_number}.`);
      setSelectedReturn(response);
      setRefundDraft(buildRefundDraft(response));
      await loadHistory(historyQuery);
    } catch (refundError) {
      setError(refundError instanceof Error ? refundError.message : 'Unable to record refund.');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="operations-page returns-module">
      <div className="operations-toolbar">
        <div>
          <h2>Start from the order, then post the refund</h2>
        </div>
        <div className="operations-toolbar-actions">
          <button type="button" className="btn-primary" onClick={() => { setActiveTab('create'); resetCreateFlow(); }}>Create Return</button>
        </div>
      </div>

      <WorkspaceTabs
        tabs={[
          { id: 'create', label: 'Create' },
          { id: 'history', label: 'History' },
        ]}
        activeTab={activeTab}
        onTabChange={setActiveTab}
      />

      {notice ? <WorkspaceNotice tone="success">{notice}</WorkspaceNotice> : null}
      {error ? <WorkspaceNotice tone="error">{error}</WorkspaceNotice> : null}

      {activeTab === 'create' ? (
        <WorkspacePanel title="Create return" description="Find the completed order first, then review only the lines still eligible for return.">
          <div className="operations-detail-stack">
            <form
              className="operations-search-bar"
              onSubmit={(event) => {
                event.preventDefault();
                void runOrderLookup(lookupQuery);
              }}
            >
              <input
                type="search"
                value={lookupQuery}
                placeholder="Search order number, phone, or email"
                onChange={(event) => setLookupQuery(event.target.value)}
              />
              <button type="submit" className="btn-primary" disabled={lookupPending}>{lookupPending ? 'Searching…' : 'Search'}</button>
            </form>

            <div className="operations-split-layout returns-create-layout">
              <section>
                <div className="operations-section-heading">
                  <h4>Matching completed orders</h4>
                </div>
                {lookupOrders.length ? (
                  <div className="operations-list-stack compact">
                    {lookupOrders.map((order) => (
                      <button
                        key={order.sales_order_id}
                        type="button"
                        className={selectedOrder?.sales_order_id === order.sales_order_id ? 'operations-list-card active as-button' : 'operations-list-card as-button'}
                        onClick={() => void openEligibleLines(order)}
                      >
                        <div className="operations-list-card-head">
                          <strong>{order.order_number}</strong>
                          <span>{formatMoney(order.total_amount)}</span>
                        </div>
                        <p>{order.customer_name}</p>
                        <div className="operations-inline-meta compact">
                          <span>{order.customer_phone || order.customer_email}</span>
                          <span>{formatDateTime(order.ordered_at)}</span>
                        </div>
                      </button>
                    ))}
                  </div>
                ) : (
                  <WorkspaceEmpty title="No order staged yet" message="Search a completed order to begin the return." />
                )}
              </section>

              <section className="operations-detail-stack">
                <div className="operations-section-heading">
                  <h4>{eligible ? eligible.order_number : 'Eligible lines'}</h4>
                  {eligible ? <p>{`${eligible.customer_name} · ${eligible.customer_phone}`}</p> : null}
                </div>
                {eligible ? (
                  <>
                    <div className="table-scroll">
                      <table className="workspace-table">
                        <thead>
                          <tr>
                            <th>Item</th>
                            <th>Eligible</th>
                            <th>Return qty</th>
                            <th>Restock qty</th>
                            <th>Refund / unit</th>
                            <th>Reason</th>
                          </tr>
                        </thead>
                        <tbody>
                          {eligible.lines.map((line, index) => (
                            <tr key={line.sales_order_item_id}>
                              <td>{line.label}</td>
                              <td>{formatQuantity(line.eligible_quantity)}</td>
                              <td>
                                <input
                                  value={draft.lines[index]?.quantity ?? '0'}
                                  onChange={(event) =>
                                    setDraft((current) => ({
                                      ...current,
                                      lines: current.lines.map((item, itemIndex) => itemIndex === index ? { ...item, quantity: event.target.value } : item),
                                    }))
                                  }
                                />
                              </td>
                              <td>
                                <input
                                  value={draft.lines[index]?.restock_quantity ?? '0'}
                                  onChange={(event) =>
                                    setDraft((current) => ({
                                      ...current,
                                      lines: current.lines.map((item, itemIndex) => itemIndex === index ? { ...item, restock_quantity: event.target.value } : item),
                                    }))
                                  }
                                />
                              </td>
                              <td>
                                <input
                                  value={draft.lines[index]?.unit_refund_amount ?? line.unit_price}
                                  onChange={(event) =>
                                    setDraft((current) => ({
                                      ...current,
                                      lines: current.lines.map((item, itemIndex) => itemIndex === index ? { ...item, unit_refund_amount: event.target.value } : item),
                                    }))
                                  }
                                />
                              </td>
                              <td>
                                <input
                                  value={draft.lines[index]?.reason ?? ''}
                                  placeholder="Damaged, wrong size, changed mind"
                                  onChange={(event) =>
                                    setDraft((current) => ({
                                      ...current,
                                      lines: current.lines.map((item, itemIndex) => itemIndex === index ? { ...item, reason: event.target.value } : item),
                                    }))
                                  }
                                />
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                    <label>
                      Notes
                      <textarea rows={3} value={draft.notes} onChange={(event) => setDraft((current) => ({ ...current, notes: event.target.value }))} />
                    </label>
                    <div className="operations-toolbar-actions wrap">
                      <button type="button" className="btn-primary" onClick={() => void submitReturn()} disabled={submitting || eligiblePending}>
                        {submitting ? 'Saving…' : 'Create Return'}
                      </button>
                      <button type="button" className="secondary" onClick={resetCreateFlow}>Reset</button>
                    </div>
                  </>
                ) : (
                  <WorkspaceEmpty title="No eligible lines" message="Open one completed order to review returnable items." />
                )}
              </section>
            </div>
          </div>
        </WorkspacePanel>
      ) : (
        <WorkspacePanel
          title="Return history"
          description="Open a return to review its status and record refund payments."
          actions={
            <form
              className="operations-search-bar compact"
              onSubmit={(event) => {
                event.preventDefault();
                void loadHistory(historyQuery.trim());
              }}
            >
              <input
                type="search"
                value={historyQuery}
                placeholder="Search return number, order number, phone, or email"
                onChange={(event) => setHistoryQuery(event.target.value)}
              />
              <button type="submit" className="secondary">Search</button>
            </form>
          }
        >
          <div className="operations-split-layout returns-history-layout">
            <div className="operations-list-stack">
              {historyLoading ? <div className="reports-loading">Loading returns…</div> : null}
              {!historyLoading && history.length ? (
                history.map((item) => (
                  <button
                    key={item.sales_return_id}
                    type="button"
                    className={selectedReturn?.sales_return_id === item.sales_return_id ? 'operations-list-card active as-button' : 'operations-list-card as-button'}
                    onClick={() => openReturnDetails(item)}
                  >
                    <div className="operations-list-card-head">
                      <strong>{item.return_number}</strong>
                      <span className="status-pill">{buildReturnStatusLabel(item)}</span>
                    </div>
                    <p>{item.customer_name || item.order_number}</p>
                    <div className="operations-inline-meta compact">
                      <span>{formatMoney(item.refund_amount)}</span>
                      <span>{formatMoney(item.refund_outstanding_amount ?? '0')} outstanding</span>
                    </div>
                  </button>
                ))
              ) : null}
              {!historyLoading && !history.length ? (
                <WorkspaceEmpty title="No returns recorded" message="Processed returns will appear here automatically." />
              ) : null}
            </div>

            <div className="operations-detail-stack">
              {selectedReturn ? (
                <>
                  <div className="operations-section-heading">
                    <h4>{selectedReturn.return_number}</h4>
                    <p>{selectedReturn.customer_name || selectedReturn.order_number}</p>
                  </div>
                  <div className="operations-inline-meta wrap">
                    <span>{buildReturnStatusLabel(selectedReturn)}</span>
                    <span>{selectedReturn.refund_status}</span>
                    <span>{formatDateTime(selectedReturn.requested_at)}</span>
                    <span>{formatMoney(selectedReturn.refund_outstanding_amount ?? '0')} outstanding</span>
                  </div>

                  <div className="table-scroll">
                    <table className="workspace-table">
                      <thead>
                        <tr>
                          <th>Item</th>
                          <th>Qty</th>
                          <th>Restocked</th>
                          <th>Refund</th>
                        </tr>
                      </thead>
                      <tbody>
                        {selectedReturn.lines.map((line) => (
                          <tr key={line.sales_return_item_id}>
                            <td>{line.label}</td>
                            <td>{formatQuantity(line.quantity)}</td>
                            <td>{formatQuantity(line.restock_quantity)}</td>
                            <td>{formatMoney(line.line_total)}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>

                  <div className="operations-form-grid compact">
                    <label>
                      Refund date
                      <input
                        type="datetime-local"
                        value={refundDraft.refund_date}
                        onChange={(event) => setRefundDraft((current) => ({ ...current, refund_date: event.target.value }))}
                      />
                    </label>
                    <label>
                      Amount
                      <input
                        inputMode="decimal"
                        value={refundDraft.amount}
                        onChange={(event) => setRefundDraft((current) => ({ ...current, amount: event.target.value }))}
                        placeholder="0.00"
                      />
                    </label>
                    <label>
                      Method
                      <input
                        value={refundDraft.method}
                        onChange={(event) => setRefundDraft((current) => ({ ...current, method: event.target.value }))}
                        placeholder="Cash, bank transfer, card reversal"
                      />
                    </label>
                    <label>
                      Reference
                      <input
                        value={refundDraft.reference}
                        onChange={(event) => setRefundDraft((current) => ({ ...current, reference: event.target.value }))}
                        placeholder="Refund receipt or transfer id"
                      />
                    </label>
                    <label className="field-span-2">
                      Note
                      <textarea
                        rows={3}
                        value={refundDraft.note}
                        onChange={(event) => setRefundDraft((current) => ({ ...current, note: event.target.value }))}
                      />
                    </label>
                  </div>

                  {selectedReturn.recent_refunds?.length ? (
                    <div className="operations-list-stack compact">
                      {selectedReturn.recent_refunds.map((refund) => (
                        <div key={refund.transaction_id} className="operations-list-card static">
                          <div className="operations-list-card-head">
                            <strong>{refund.reference || 'Refund payment'}</strong>
                            <span>-{formatMoney(refund.amount)}</span>
                          </div>
                          <p>{refund.note || 'Refund posted'}</p>
                          <div className="operations-inline-meta compact">
                            <span>{formatDateTime(refund.posted_at)}</span>
                          </div>
                        </div>
                      ))}
                    </div>
                  ) : null}

                  <div className="operations-toolbar-actions wrap">
                    <button type="button" className="btn-primary" onClick={() => void submitRefund()} disabled={submitting}>
                      {submitting ? 'Saving…' : 'Record Refund'}
                    </button>
                    <button type="button" className="secondary" onClick={() => setRefundDraft(buildRefundDraft(selectedReturn))}>Reset</button>
                  </div>
                </>
              ) : (
                <WorkspaceEmpty title="Select a return" message="Choose one return from history to review it and record refund payments." />
              )}
            </div>
          </div>
        </WorkspacePanel>
      )}
      <div className="mobile-action-safe-spacer" aria-hidden="true" />
    </div>
  );
}
