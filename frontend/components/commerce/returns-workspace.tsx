'use client';

import { FormEvent, useEffect, useState, useTransition } from 'react';
import { useSearchParams } from 'next/navigation';
import { createSalesReturn, getEligibleReturnLines, getReturns, searchReturnOrders } from '@/lib/api/commerce';
import type { ReturnCreatePayload, ReturnEligibleLines, ReturnLookupOrder, ReturnRecord } from '@/types/returns';
import { WorkspaceEmpty, WorkspaceNotice, WorkspacePanel, WorkspaceTabs } from '@/components/commerce/workspace-primitives';
import { formatDateTime, formatMoney, formatQuantity } from '@/lib/commerce-format';


type ReturnsTab = 'create' | 'history';


export function ReturnsWorkspace() {
  const searchParams = useSearchParams();
  const searchKey = searchParams.toString();
  const [activeTab, setActiveTab] = useState<ReturnsTab>('create');
  const [searchQuery, setSearchQuery] = useState('');
  const [lookupOrders, setLookupOrders] = useState<ReturnLookupOrder[]>([]);
  const [eligible, setEligible] = useState<ReturnEligibleLines | null>(null);
  const [history, setHistory] = useState<ReturnRecord[]>([]);
  const [draft, setDraft] = useState<ReturnCreatePayload>({
    sales_order_id: '',
    notes: '',
    refund_status: 'pending',
    lines: [],
  });
  const [notice, setNotice] = useState('');
  const [error, setError] = useState('');
  const [isPending, startTransition] = useTransition();

  const loadHistory = (query = '') => {
    startTransition(async () => {
      try {
        const payload = await getReturns(query);
        setHistory(payload.items);
        setError('');
      } catch (loadError) {
        setError(loadError instanceof Error ? loadError.message : 'Unable to load returns.');
      }
    });
  };

  useEffect(() => {
    const query = searchParams.get('q') ?? '';
    setSearchQuery(query);
    loadHistory(query);
  }, [searchKey]);

  const onOrderSearch = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    try {
      const payload = await searchReturnOrders(searchQuery.trim());
      setLookupOrders(payload.items);
      setError('');
    } catch (searchError) {
      setError(searchError instanceof Error ? searchError.message : 'Unable to search completed orders.');
    }
  };

  const loadEligible = async (orderId: string) => {
    try {
      const payload = await getEligibleReturnLines(orderId);
      setEligible(payload);
      setDraft({
        sales_order_id: orderId,
        notes: '',
        refund_status: 'pending',
        lines: payload.lines.map((line) => ({
          sales_order_item_id: line.sales_order_item_id,
          quantity: '0',
          restock_quantity: '0',
          disposition: 'restock',
          unit_refund_amount: line.unit_price,
          reason: '',
        })),
      });
      setError('');
    } catch (detailError) {
      setError(detailError instanceof Error ? detailError.message : 'Unable to load returnable lines.');
    }
  };

  const submitReturn = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setNotice('');
    setError('');
    try {
      const response = await createSalesReturn({
        ...draft,
        lines: draft.lines.filter((line) => Number(line.quantity) > 0),
      });
      setNotice(`Return ${response.return_number} created.`);
      setEligible(null);
      setDraft({
        sales_order_id: '',
        notes: '',
        refund_status: 'pending',
        lines: [],
      });
      await loadHistory();
      setActiveTab('history');
    } catch (submitError) {
      setError(submitError instanceof Error ? submitError.message : 'Unable to create return.');
    }
  };

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
        description="Start from completed orders, validate eligible quantities, and restock only what becomes sellable again."
      >
        {notice ? <WorkspaceNotice tone="success">{notice}</WorkspaceNotice> : null}
        {error ? <WorkspaceNotice tone="error">{error}</WorkspaceNotice> : null}
        {isPending && !history.length ? <WorkspaceNotice>Loading returns workspace…</WorkspaceNotice> : null}

        {activeTab === 'create' ? (
          <div className="workspace-stack">
            <form className="workspace-search" onSubmit={onOrderSearch}>
              <input
                type="search"
                value={searchQuery}
                placeholder="Search completed orders by order number, phone, or email"
                onChange={(event) => setSearchQuery(event.target.value)}
              />
              <button type="submit">Find orders</button>
            </form>

            {lookupOrders.length ? (
              <div className="workspace-card-grid compact">
                {lookupOrders.map((order) => (
                  <button
                    key={order.sales_order_id}
                    type="button"
                    className="selection-card"
                    onClick={() => loadEligible(order.sales_order_id)}
                  >
                    <strong>{order.order_number}</strong>
                    <span>{order.customer_name} · {order.customer_phone || order.customer_email}</span>
                    <span>{formatMoney(order.total_amount)}</span>
                  </button>
                ))}
              </div>
            ) : (
              <WorkspaceEmpty
                title="Find a completed order"
                message="Returns begin with an order search, not a customer directory."
              />
            )}

            {eligible ? (
              <form className="workspace-form" onSubmit={submitReturn}>
                <div className="workspace-subsection">
                  <div className="workspace-subsection-header">
                    <div>
                      <h4>{eligible.order_number}</h4>
                      <p>{eligible.customer_name} · {eligible.customer_phone}</p>
                    </div>
                  </div>
                  <div className="table-scroll">
                    <table className="workspace-table">
                      <thead>
                        <tr>
                          <th>Variant</th>
                          <th>Eligible</th>
                          <th>Return Qty</th>
                          <th>Restock Qty</th>
                          <th>Refund / Unit</th>
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
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
                <label>
                  Return notes
                  <textarea
                    rows={3}
                    value={draft.notes}
                    onChange={(event) => setDraft((current) => ({ ...current, notes: event.target.value }))}
                  />
                </label>
                <div className="workspace-actions">
                  <button type="submit">Create return</button>
                </div>
              </form>
            ) : null}
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
