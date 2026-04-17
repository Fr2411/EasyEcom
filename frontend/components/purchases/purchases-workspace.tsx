'use client';

import Link from 'next/link';
import { FormEvent, useEffect, useState } from 'react';
import { WorkspaceEmpty, WorkspaceNotice, WorkspacePanel } from '@/components/commerce/workspace-primitives';
import { ApiError, ApiNetworkError } from '@/lib/api/client';
import { listPurchaseOrders } from '@/lib/api/purchases';
import { formatMoney } from '@/lib/commerce-format';

function stripRequestUrlFromMessage(message: string) {
  return message.replace(/\s*\(https?:\/\/[^)]+\)\s*$/i, '').trim();
}

export function safePurchaseWorkspaceErrorMessage(error: unknown) {
  if (error instanceof ApiNetworkError) {
    return 'Unable to load purchase orders right now. Check your connection and try again.';
  }
  if (error instanceof ApiError) {
    if (error.status === 403) {
      return 'You do not have permission to view purchase orders.';
    }
    if (error.status >= 500) {
      return 'Purchase orders are temporarily unavailable. Please try again in a moment.';
    }
    return 'Unable to load purchase orders. Adjust filters and try again.';
  }
  if (error instanceof Error) {
    const cleaned = stripRequestUrlFromMessage(error.message);
    if (cleaned) {
      return cleaned;
    }
  }
  return 'Unable to load purchase orders.';
}

export function PurchasesWorkspace() {
  const [status, setStatus] = useState('');
  const [queryDraft, setQueryDraft] = useState('');
  const [query, setQuery] = useState('');
  const [reloadToken, setReloadToken] = useState(0);
  const [items, setItems] = useState<Awaited<ReturnType<typeof listPurchaseOrders>>['items']>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    let active = true;
    setLoading(true);
    setError('');
    void listPurchaseOrders({ status, q: query })
      .then((payload) => {
        if (!active) return;
        setItems(payload.items);
      })
      .catch((loadError) => {
        if (!active) return;
        setError(safePurchaseWorkspaceErrorMessage(loadError));
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, [status, query, reloadToken]);

  const onSubmit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setQuery(queryDraft.trim());
  };

  const receivedCount = items.filter((item) => item.status === 'received').length;
  const draftCount = items.filter((item) => item.status === 'draft').length;

  const onRetry = () => {
    if (loading) return;
    setReloadToken((current) => current + 1);
  };

  return (
    <div className="reports-module purchases-module">
      <WorkspaceNotice tone="info">
        Use this page to track purchase orders and supplier progress. When stock arrives, complete receiving from Inventory.
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
        {error ? (
          <div className="purchases-error-state" role="alert" aria-live="assertive">
            <p className="purchases-error-title">Purchase orders could not be loaded</p>
            <p className="purchases-error-copy">{error}</p>
            <div className="purchases-error-actions">
              <button type="button" className="btn-primary" onClick={onRetry} disabled={loading}>
                {loading ? 'Retrying…' : 'Retry'}
              </button>
            </div>
          </div>
        ) : null}

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
