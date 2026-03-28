'use client';

import { FormEvent, useEffect, useState, useTransition } from 'react';
import { useSearchParams } from 'next/navigation';
import {
  createSalesReturn,
  getEligibleReturnLines,
  getReturns,
  recordSalesReturnRefund,
  searchReturnOrders,
} from '@/lib/api/commerce';
import type { SuggestedAction } from '@/types/guided-workflow';
import type { ReturnCreatePayload, ReturnEligibleLines, ReturnLookupOrder, ReturnRecord } from '@/types/returns';
import {
  DraftRecommendationCard,
  IntentInput,
  MatchGroupList,
  StagedActionFooter,
  SuggestedNextStep,
  WorkspaceEmpty,
  WorkspaceNotice,
  WorkspacePanel,
  WorkspaceTabs,
} from '@/components/commerce/workspace-primitives';
import { formatDateTime, formatMoney, formatQuantity } from '@/lib/commerce-format';

type ReturnsTab = 'create' | 'history';

type ReturnsSuggestion = {
  kind: 'idle' | 'likely' | 'exact' | 'draft';
  title: string;
  detail: string;
  actionLabel?: string;
  secondaryLabel?: string;
  tone?: SuggestedAction['tone'];
};

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

function normalizeLookupQuery(value: string) {
  return value.trim().toLowerCase();
}

export function deriveReturnSuggestion(
  query: string,
  lookupOrders: ReturnLookupOrder[],
  eligible: ReturnEligibleLines | null
): ReturnsSuggestion {
  const trimmed = query.trim();
  if (eligible) {
    return {
      kind: 'draft',
      title: `Return draft ready for ${eligible.order_number}`,
      detail: 'Eligible lines are staged. Review quantities, restock amounts, and refund values before creating the return.',
      actionLabel: 'Review before creating return',
      tone: 'success',
    };
  }

  if (!trimmed && !lookupOrders.length) {
    return {
      kind: 'idle',
      title: 'Start with one completed order clue',
      detail: 'Type an order number, customer phone, or email. The workspace will stage the most likely return candidate.',
      actionLabel: 'Interpret order clue',
      tone: 'info',
    };
  }

  if (!lookupOrders.length) {
    return {
      kind: 'idle',
      title: 'No completed order staged yet',
      detail: 'Search a completed order first, then the workspace will open eligible lines for review.',
      actionLabel: 'Interpret order clue',
      tone: 'warning',
    };
  }

  const exact = lookupOrders.find((order) => {
    const normalized = normalizeLookupQuery(trimmed);
    return (
      order.order_number.toLowerCase() === normalized ||
      order.customer_phone.toLowerCase() === normalized ||
      order.customer_email.toLowerCase() === normalized
    );
  });

  if (exact) {
    return {
      kind: 'exact',
      title: `Exact order found: ${exact.order_number}`,
      detail: 'Open the order to stage eligible return lines and review them before any write happens.',
      actionLabel: 'Open eligible lines',
      tone: 'success',
    };
  }

  if (lookupOrders.length === 1) {
    return {
      kind: 'likely',
      title: `One likely completed order found: ${lookupOrders[0].order_number}`,
      detail: 'Use the staged order below to review eligible lines and continue to the return draft.',
      actionLabel: 'Open eligible lines',
      tone: 'success',
    };
  }

  return {
    kind: 'likely',
    title: `We found ${lookupOrders.length} likely completed orders`,
    detail: 'Pick the correct order from the list below. The UI will then stage the eligible return lines for review.',
    actionLabel: 'Open eligible lines',
    secondaryLabel: 'Search again',
    tone: 'warning',
  };
}

export function ReturnsWorkspace() {
  const searchParams = useSearchParams();
  const searchKey = searchParams.toString();
  const [activeTab, setActiveTab] = useState<ReturnsTab>('create');
  const [intentQuery, setIntentQuery] = useState('');
  const [lookupOrders, setLookupOrders] = useState<ReturnLookupOrder[]>([]);
  const [selectedOrder, setSelectedOrder] = useState<ReturnLookupOrder | null>(null);
  const [eligible, setEligible] = useState<ReturnEligibleLines | null>(null);
  const [historyQuery, setHistoryQuery] = useState('');
  const [history, setHistory] = useState<ReturnRecord[]>([]);
  const [selectedReturn, setSelectedReturn] = useState<ReturnRecord | null>(null);
  const [refundDraft, setRefundDraft] = useState<ReturnRefundDraft>(buildRefundDraft());
  const [draft, setDraft] = useState<ReturnCreatePayload>(createEmptyDraft());
  const [notice, setNotice] = useState('');
  const [error, setError] = useState('');
  const [lookupPending, setLookupPending] = useState(false);
  const [eligiblePending, setEligiblePending] = useState(false);
  const [historyPending, setHistoryPending] = useState(false);
  const [isPending, startTransition] = useTransition();

  const loadHistory = (query = '') => {
    setHistoryPending(true);
    startTransition(async () => {
      try {
        const payload = await getReturns(query);
        setHistory(payload.items);
        setError('');
      } catch (loadError) {
        setError(loadError instanceof Error ? loadError.message : 'Unable to load returns.');
      } finally {
        setHistoryPending(false);
      }
    });
  };

  useEffect(() => {
    const query = searchParams.get('q') ?? '';
    setHistoryQuery(query);
    loadHistory(query);
  }, [searchKey]);

  const resetReturnDraft = () => {
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
      setError(detailError instanceof Error ? detailError.message : 'Unable to load returnable lines.');
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
      setLookupOrders(payload.items);
      setError('');

      const normalized = normalizeLookupQuery(trimmed);
      const exact = payload.items.find((order) => {
        return (
          order.order_number.toLowerCase() === normalized ||
          order.customer_phone.toLowerCase() === normalized ||
          order.customer_email.toLowerCase() === normalized
        );
      });

      if (exact) {
        await openEligibleLines(exact);
        return;
      }

      if (payload.items.length === 1) {
        await openEligibleLines(payload.items[0]);
      }
    } catch (searchError) {
      setError(searchError instanceof Error ? searchError.message : 'Unable to search completed orders.');
    } finally {
      setLookupPending(false);
    }
  };

  const submitReturn = async (event?: FormEvent<HTMLFormElement>) => {
    event?.preventDefault();
    if (!eligible) {
      setError('Open a completed order before creating a return.');
      return;
    }

    const payloadLines = draft.lines.filter((line) => Number(line.quantity) > 0);
    if (!payloadLines.length) {
      setError('Add at least one return line before creating the return.');
      return;
    }

    setNotice('');
    setError('');
    try {
      const response = await createSalesReturn({
        ...draft,
        lines: payloadLines,
      });
      setNotice(`Return ${response.return_number} created.`);
      resetReturnDraft();
      await loadHistory(historyQuery);
      setSelectedReturn(response);
      setRefundDraft(buildRefundDraft(response));
      setActiveTab('history');
    } catch (submitError) {
      setError(submitError instanceof Error ? submitError.message : 'Unable to create return.');
    }
  };

  const submitRefund = async (event?: FormEvent<HTMLFormElement>) => {
    event?.preventDefault();
    if (!selectedReturn) {
      setError('Select a return before recording a refund.');
      return;
    }
    if (!refundDraft.amount.trim() || Number(refundDraft.amount) <= 0) {
      setError('Refund amount must be greater than zero.');
      return;
    }

    setNotice('');
    setError('');
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
      setError(refundError instanceof Error ? refundError.message : 'Unable to record refund payment.');
    }
  };

  const suggestion = deriveReturnSuggestion(intentQuery, lookupOrders, eligible);

  return (
    <div className="workspace-stack">
      <WorkspaceTabs
        tabs={[
          { id: 'create', label: 'Create Return' },
          { id: 'history', label: 'History' },
        ]}
        activeTab={activeTab}
        onTabChange={setActiveTab}
      />

      <WorkspacePanel
        title="Return and restock control"
        hint="Start from one completed-order clue, open eligible lines, and stage the return draft before any stock or refund write occurs."
      >
        {notice ? <WorkspaceNotice tone="success">{notice}</WorkspaceNotice> : null}
        {error ? <WorkspaceNotice tone="error">{error}</WorkspaceNotice> : null}
        {(isPending || historyPending) && !history.length ? <WorkspaceNotice>Loading returns workspace…</WorkspaceNotice> : null}

        {activeTab === 'create' ? (
          <div className="workspace-stack">
            <IntentInput
              label="Which completed order is being returned?"
              hint="Type one clue. The workspace will interpret an order number, phone number, or email and stage the eligible lines."
              value={intentQuery}
              placeholder="Order number, phone, or email"
              pending={lookupPending || eligiblePending}
              submitLabel="Interpret order clue"
              onChange={setIntentQuery}
              onSubmit={() => runOrderLookup(intentQuery)}
            >
              <span className="guided-assist-chip">Exact order numbers open eligible lines automatically</span>
              <span className="guided-assist-chip">Manual searching is replaced by staged order selection</span>
            </IntentInput>

            <SuggestedNextStep
              suggestion={suggestion}
              onPrimary={() => {
                if (selectedOrder) {
                  void openEligibleLines(selectedOrder);
                  return;
                }
                if (lookupOrders[0]) {
                  void openEligibleLines(lookupOrders[0]);
                  return;
                }
                if (intentQuery.trim()) {
                  void runOrderLookup(intentQuery);
                }
              }}
              onSecondary={() => {
                setLookupOrders([]);
                setSelectedOrder(null);
                setEligible(null);
                setDraft(createEmptyDraft());
              }}
            />

            <MatchGroupList
              title="Likely completed orders"
              description="Pick the correct order when there is more than one match."
              items={lookupOrders}
              emptyMessage="No completed order has been staged yet."
              renderItem={(order) => (
                <article key={order.sales_order_id} className="guided-match-item">
                  <div className="guided-match-item-header">
                    <div>
                      <h5>{order.order_number}</h5>
                      <p>{order.customer_name}</p>
                    </div>
                    <button type="button" onClick={() => void openEligibleLines(order)}>
                      Open eligible lines
                    </button>
                  </div>
                  <div className="guided-match-item-meta">
                    <span>{order.customer_phone || order.customer_email}</span>
                    <span>{formatMoney(order.total_amount)}</span>
                    <span>{order.status}</span>
                  </div>
                </article>
              )}
            />

            {eligible ? (
              <DraftRecommendationCard
                title={eligible.order_number}
                summary={`Eligible return lines are staged for ${eligible.customer_name}. Review quantities and refund values before creating the return.`}
              >
                <div className="workspace-form-grid compact">
                  <div className="guided-match-item-meta">
                    <span>Customer: {eligible.customer_name}</span>
                    <span>{eligible.customer_phone}</span>
                  </div>
                </div>

                {eligible.lines.length ? (
                  <div className="table-scroll">
                    <table className="workspace-table">
                      <thead>
                        <tr>
                          <th>Variant</th>
                          <th>Eligible</th>
                          <th>Return Qty</th>
                          <th>Restock Qty</th>
                          <th>Refund / Unit</th>
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
                                    lines: current.lines.map((item, itemIndex) =>
                                      itemIndex === index ? { ...item, quantity: event.target.value } : item
                                    ),
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
                                    lines: current.lines.map((item, itemIndex) =>
                                      itemIndex === index ? { ...item, restock_quantity: event.target.value } : item
                                    ),
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
                                    lines: current.lines.map((item, itemIndex) =>
                                      itemIndex === index ? { ...item, unit_refund_amount: event.target.value } : item
                                    ),
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
                                    lines: current.lines.map((item, itemIndex) =>
                                      itemIndex === index ? { ...item, reason: event.target.value } : item
                                    ),
                                  }))
                                }
                              />
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                ) : (
                  <WorkspaceEmpty
                    title="No eligible return lines"
                    message="This completed order does not currently have returnable lines."
                  />
                )}

                <label>
                  Return notes
                  <textarea
                    rows={3}
                    value={draft.notes}
                    onChange={(event) => setDraft((current) => ({ ...current, notes: event.target.value }))}
                  />
                </label>

                <StagedActionFooter summary="The return will not be written until you explicitly create it.">
                  <button
                    type="button"
                    onClick={() => void submitReturn()}
                    disabled={!eligible || eligiblePending || lookupPending}
                  >
                    Review before creating return
                  </button>
                  <button
                    type="button"
                    className="secondary"
                    onClick={() => {
                      resetReturnDraft();
                      setLookupOrders([]);
                      setIntentQuery('');
                      setNotice('');
                    }}
                  >
                    Reset return draft
                  </button>
                </StagedActionFooter>
              </DraftRecommendationCard>
            ) : (
              <WorkspaceNotice>
                Open a completed order and the workspace will stage its returnable lines for review.
              </WorkspaceNotice>
            )}
          </div>
        ) : (
          history.length ? (
            <div className="returns-history-layout">
              <div className="workspace-card-grid">
                {history.map((item) => (
                  <article
                    key={item.sales_return_id}
                    className={selectedReturn?.sales_return_id === item.sales_return_id ? 'commerce-card selected' : 'commerce-card'}
                  >
                    <div className="commerce-card-header">
                      <div>
                        <p className="eyebrow">Return</p>
                        <h4>{item.return_number}</h4>
                        <p>{item.customer_name} · {item.order_number}</p>
                      </div>
                      <span className="status-pill">{item.status}</span>
                    </div>
                    <div className="commerce-card-meta">
                      <span>Requested: {formatDateTime(item.requested_at)}</span>
                      <span>Refund: {formatMoney(item.refund_amount)}</span>
                      <span>Paid: {formatMoney(item.refund_paid_amount ?? '0')}</span>
                      <span>Outstanding: {formatMoney(item.refund_outstanding_amount ?? '0')}</span>
                    </div>
                    <div className="workspace-actions">
                      <button type="button" className="secondary" onClick={() => openReturnDetails(item)}>
                        Open refund details
                      </button>
                    </div>
                  </article>
                ))}
              </div>

              <WorkspacePanel
                title={selectedReturn ? selectedReturn.return_number : 'Refund recording'}
                description="Refunds are recorded separately from the return itself. Pick a return, then post each refund payment explicitly."
              >
                {selectedReturn ? (
                  <div className="workspace-stack">
                    <DraftRecommendationCard
                      title={selectedReturn.return_number}
                      summary={`Refund status: ${selectedReturn.refund_status}. Finance status: ${selectedReturn.finance_status ?? 'not_posted'}.`}
                    >
                      <div className="guided-match-item-meta">
                        <span>Customer: {selectedReturn.customer_name}</span>
                        <span>Order: {selectedReturn.order_number}</span>
                        <span>Requested: {formatDateTime(selectedReturn.requested_at)}</span>
                        <span>Paid: {formatMoney(selectedReturn.refund_paid_amount ?? '0')}</span>
                        <span>Outstanding: {formatMoney(selectedReturn.refund_outstanding_amount ?? '0')}</span>
                      </div>
                      {selectedReturn.recent_refunds?.length ? (
                        <div className="finance-row-list">
                          {selectedReturn.recent_refunds.map((refund) => (
                            <article key={refund.transaction_id} className="finance-row-card finance-row-readonly">
                              <div className="finance-row-card-head">
                                <div>
                                  <span className="finance-origin-pill">Refund payment</span>
                                  <strong>{refund.reference}</strong>
                                  <p>{refund.note || 'Refund payment posted'}</p>
                                </div>
                                <strong className="delta-negative">-{formatMoney(refund.amount)}</strong>
                              </div>
                              <div className="finance-row-meta">
                                <span>{formatDateTime(refund.posted_at)}</span>
                              </div>
                            </article>
                          ))}
                        </div>
                      ) : (
                        <WorkspaceEmpty
                          title="No refund payments recorded yet"
                          message="The return is staged, but no cash has been posted out yet."
                        />
                      )}
                    </DraftRecommendationCard>

                    <form
                      className="workspace-stack"
                      onSubmit={(event) => {
                        event.preventDefault();
                        void submitRefund(event);
                      }}
                    >
                      <div className="workspace-form-grid compact">
                        <label>
                          Refund date
                          <input
                            type="datetime-local"
                            value={refundDraft.refund_date}
                            onChange={(event) =>
                              setRefundDraft((current) => ({ ...current, refund_date: event.target.value }))
                            }
                          />
                        </label>
                        <label>
                          Amount
                          <input
                            inputMode="decimal"
                            value={refundDraft.amount}
                            onChange={(event) =>
                              setRefundDraft((current) => ({ ...current, amount: event.target.value }))
                            }
                            placeholder="0.00"
                          />
                        </label>
                        <label>
                          Method
                          <input
                            value={refundDraft.method}
                            onChange={(event) =>
                              setRefundDraft((current) => ({ ...current, method: event.target.value }))
                            }
                            placeholder="Cash, bank transfer, card reversal"
                          />
                        </label>
                        <label>
                          Reference
                          <input
                            value={refundDraft.reference}
                            onChange={(event) =>
                              setRefundDraft((current) => ({ ...current, reference: event.target.value }))
                            }
                            placeholder="Refund receipt or transfer id"
                          />
                        </label>
                        <label className="workspace-form-wide">
                          Note
                          <textarea
                            rows={3}
                            value={refundDraft.note}
                            onChange={(event) =>
                              setRefundDraft((current) => ({ ...current, note: event.target.value }))
                            }
                            placeholder="Add a short audit note"
                          />
                        </label>
                      </div>

                      <StagedActionFooter summary="Refund cash posts only when you record the payment. The return itself stays separate from finance.">
                      <button
                        type="button"
                        className="btn-primary"
                        disabled={!selectedReturn || eligiblePending || lookupPending}
                        onClick={() => void submitRefund()}
                      >
                        Record refund payment
                      </button>
                        <button
                          type="button"
                          className="secondary"
                          onClick={() => setRefundDraft(buildRefundDraft(selectedReturn))}
                        >
                          Reset refund draft
                        </button>
                      </StagedActionFooter>
                    </form>
                  </div>
                ) : (
                  <WorkspaceEmpty
                    title="Select a return to record refund payments"
                    message="Open any return from the history list to review refund balances and post cash out events."
                  />
                )}
              </WorkspacePanel>
            </div>
          ) : (
            <WorkspaceEmpty
              title="No returns recorded"
              message="Return history will appear here after staff process completed-order returns."
            />
          )
        )}
      </WorkspacePanel>
    </div>
  );
}
