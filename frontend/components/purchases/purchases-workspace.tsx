'use client';

import Link from 'next/link';
import { FormEvent, useEffect, useState } from 'react';
import { WorkspaceEmpty, WorkspaceNotice, WorkspacePanel } from '@/components/commerce/workspace-primitives';
import { listPurchaseOrders } from '@/lib/api/purchases';
import { formatMoney } from '@/lib/commerce-format';

export function PurchasesWorkspace() {
  const [status, setStatus] = useState('');
  const [queryDraft, setQueryDraft] = useState('');
  const [query, setQuery] = useState('');
  const [items, setItems] = useState<Awaited<ReturnType<typeof listPurchaseOrders>>['items']>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    let active = true;
    setLoading(true);
    void listPurchaseOrders({ status, q: query })
      .then((payload) => {
        if (!active) return;
        setItems(payload.items);
        setError('');
      })
      .catch((loadError) => {
        if (!active) return;
        setError(loadError instanceof Error ? loadError.message : 'Unable to load purchase orders.');
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, [status, query]);

  const onSubmit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setQuery(queryDraft.trim());
  };

  const receivedCount = items.filter((item) => item.status === 'received').length;
  const draftCount = items.filter((item) => item.status === 'draft').length;

  return (
    <div className="reports-module">
      <WorkspaceNotice tone="info">
        Purchases remain embedded in Inventory for stock receipt because that is the canonical ledger-backed write path. This workspace is the procurement board for orders and receiving status.
      </WorkspaceNotice>

      <WorkspacePanel
        title="Procurement posture"
        description="Track purchase-order volume here, then receive stock through the inventory intake flow that writes the variant ledger."
        actions={<Link href="/inventory?tab=receive">Open Receive Stock</Link>}
      >
        <div className="reports-grid">
          <article className="ps-card">
            <p>Total orders</p>
            <strong>{items.length}</strong>
          </article>
          <article className="ps-card">
            <p>Draft orders</p>
            <strong>{draftCount}</strong>
          </article>
          <article className="ps-card">
            <p>Received orders</p>
            <strong>{receivedCount}</strong>
          </article>
        </div>
      </WorkspacePanel>

      <WorkspacePanel title="Purchase orders" description="Search and filter the current tenant’s purchase orders.">
        <form className="reports-filter-bar" onSubmit={onSubmit}>
          <label>
            Search
            <input value={queryDraft} onChange={(event) => setQueryDraft(event.target.value)} placeholder="PO number or notes" />
          </label>
          <label>
            Status
            <select value={status} onChange={(event) => setStatus(event.target.value)}>
              <option value="">All</option>
              <option value="draft">Draft</option>
              <option value="received">Received</option>
              <option value="cancelled">Cancelled</option>
            </select>
          </label>
          <button type="submit">Apply</button>
        </form>

        {loading ? <div className="reports-loading">Loading purchase orders…</div> : null}
        {error ? <div className="reports-error">{error}</div> : null}

        {!loading && !error && !items.length ? (
          <WorkspaceEmpty title="No purchase orders yet" message="Create or receive stock from Inventory when the first supplier delivery is ready." />
        ) : null}

        {!loading && !error && items.length ? (
          <div className="admin-table-wrap">
            <table className="admin-table">
              <thead>
                <tr>
                  <th>Purchase no</th>
                  <th>Supplier</th>
                  <th>Date</th>
                  <th>Status</th>
                  <th>Subtotal</th>
                </tr>
              </thead>
              <tbody>
                {items.map((item) => (
                  <tr key={item.purchase_id}>
                    <td>{item.purchase_no}</td>
                    <td>{item.supplier_name}</td>
                    <td>{item.purchase_date}</td>
                    <td>{item.status}</td>
                    <td>{formatMoney(item.subtotal)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : null}
      </WorkspacePanel>
    </div>
  );
}
