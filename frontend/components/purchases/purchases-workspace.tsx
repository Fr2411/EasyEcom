'use client';

import Link from 'next/link';
import { FormEvent, useEffect, useMemo, useState } from 'react';
import { WorkspaceEmpty, WorkspaceNotice, WorkspacePanel } from '@/components/commerce/workspace-primitives';
import { ApiError, ApiNetworkError } from '@/lib/api/client';
import { listPurchaseOrders } from '@/lib/api/purchases';
import { formatDateTime, formatMoney } from '@/lib/commerce-format';

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

function purchaseLoadFailureGuidance(error: unknown) {
  const message = safePurchaseWorkspaceErrorMessage(error);
  const steps = [
    'Existing purchase orders and received stock remain unchanged.',
    'Use Retry to refresh your purchase order list.',
    'If needed, continue receiving stock from Inventory while this list refreshes.',
  ];

  if (error instanceof ApiNetworkError) {
    return {
      message,
      steps,
      recoveryTip: 'Reconnect to the internet or VPN, then retry.',
    };
  }

  if (error instanceof ApiError && error.status === 403) {
    return {
      message,
      steps,
      recoveryTip: 'Ask your tenant owner/admin to grant Purchases view access for your role.',
    };
  }

  if (error instanceof ApiError && error.status >= 500) {
    return {
      message,
      steps,
      recoveryTip: 'Purchase services are temporarily unavailable. Retry shortly.',
    };
  }

  return {
    message,
    steps,
    recoveryTip: 'Try clearing filters and searching again.',
  };
}

export function PurchasesWorkspace() {
  const [status, setStatus] = useState('');
  const [queryDraft, setQueryDraft] = useState('');
  const [query, setQuery] = useState('');
  const [reloadToken, setReloadToken] = useState(0);
  const [items, setItems] = useState<Awaited<ReturnType<typeof listPurchaseOrders>>['items']>([]);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<unknown>(null);
  const [loadFailureCount, setLoadFailureCount] = useState(0);

  useEffect(() => {
    let active = true;
    setLoading(true);
    setLoadError(null);
    void listPurchaseOrders({ status, q: query })
      .then((payload) => {
        if (!active) return;
        setItems(payload.items);
        setLoadFailureCount(0);
      })
      .catch((error) => {
        if (!active) return;
        setLoadError(error);
        setLoadFailureCount((current) => current + 1);
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

  const failureState = useMemo(() => {
    if (!loadError) return null;
    return purchaseLoadFailureGuidance(loadError);
  }, [loadError]);

  return (
    <div className="reports-module purchases-module">
      <WorkspaceNotice tone="info">
        Use this page to track purchase orders and supplier progress. When stock arrives, complete receiving from Inventory.
      </WorkspaceNotice>

      <WorkspacePanel
        title="Procurement posture"
        description="Track purchase-order volume here, then continue receiving stock from Inventory."
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
        {failureState ? (
          <div className="purchases-error-state" role="alert" aria-live="assertive">
            <p className="purchases-error-eyebrow">Temporary loading issue</p>
            <p className="purchases-error-title">We could not refresh purchase orders right now</p>
            <p className="purchases-error-context">
              This is a loading problem, not a no-orders result. Your existing order and stock records are still safe.
            </p>
            <p className="purchases-error-copy">{failureState.message}</p>
            <p className="purchases-error-copy purchases-error-recovery-tip">{failureState.recoveryTip}</p>
            {loadFailureCount >= 2 ? (
              <p className="purchases-error-copy purchases-error-repeat-warning">
                Repeated retries are still failing. Open Dashboard to refresh your session, wait a moment, then return to Purchases.
              </p>
            ) : null}
            <p className="purchases-error-guidance-title">What you can do now</p>
            <ul className="purchases-error-guidance">
              {failureState.steps.map((step) => (
                <li key={step}>{step}</li>
              ))}
            </ul>
            <div className="purchases-error-actions">
              <button type="button" className="btn-primary" onClick={onRetry} disabled={loading}>
                {loading ? 'Retrying…' : 'Retry purchase orders'}
              </button>
              <Link href="/inventory?tab=receive">Open Receive Stock</Link>
            </div>
          </div>
        ) : null}

        {!loading && !failureState && !items.length ? (
          <WorkspaceEmpty title="No purchase orders yet" message="Create or receive stock from Inventory when the first supplier delivery is ready." />
        ) : null}

        {!loading && !failureState && items.length ? (
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
                    <td>{formatDateTime(item.purchase_date)}</td>
                    <td>{item.status}</td>
                    <td>{formatMoney(item.subtotal)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : null}
      </WorkspacePanel>

      <div className="mobile-action-safe-spacer" aria-hidden="true" />
    </div>
  );
}
