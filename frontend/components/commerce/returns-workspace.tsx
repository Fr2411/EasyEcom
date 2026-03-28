'use client';

import { FormEvent, useEffect, useState, useTransition } from 'react';
import { useSearchParams } from 'next/navigation';
import { createSalesReturn, getEligibleReturnLines, getReturns, searchReturnOrders } from '@/lib/api/commerce';
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

function createEmptyDraft(): ReturnCreatePayload {
  return {
    sales_order_id: '',
    notes: '',
    refund_status: 'pending',
    lines: [],
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

  const submitReturn = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
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
      setActiveTab('history');
    } catch (submitError) {
      setError(submitError instanceof Error ? submitError.message : 'Unable to create return.');
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
                  <button type="submit">Review before creating return</button>
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
            <div className="workspace-card-grid">
              {history.map((item) => (
                <article key={item.sales_return_id} className="commerce-card">
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
                    <span>Lines: {item.lines.length}</span>
                  </div>
                  <div className="table-scroll">
                    <table className="workspace-table">
                      <thead>
                        <tr>
                          <th>Variant</th>
                          <th>Qty</th>
                          <th>Restocked</th>
                          <th>Refund</th>
                        </tr>
                      </thead>
                      <tbody>
                        {item.lines.map((line) => (
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
                </article>
              ))}
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
