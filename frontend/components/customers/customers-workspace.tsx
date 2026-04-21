'use client';

import Link from 'next/link';
import { useEffect, useMemo, useState } from 'react';
import { useSearchParams } from 'next/navigation';
import { WorkspaceEmpty, WorkspaceNotice, WorkspacePanel } from '@/components/commerce/workspace-primitives';
import { getCustomersWorkspace } from '@/lib/api/customers';
import { formatDateTime, formatMoney } from '@/lib/commerce-format';
import type { CustomerWorkspaceItem } from '@/types/customers';

function buildSalesSeedHref(customer: CustomerWorkspaceItem) {
  const params = new URLSearchParams();
  if (customer.name.trim()) params.set('seed_name', customer.name.trim());
  if (customer.phone.trim()) params.set('seed_phone', customer.phone.trim());
  if (customer.email.trim()) params.set('seed_email', customer.email.trim());
  return `/sales?${params.toString()}`;
}

function buildReturnsSeedHref(customer: CustomerWorkspaceItem) {
  const params = new URLSearchParams();
  if (customer.phone.trim()) params.set('seed_phone', customer.phone.trim());
  if (customer.email.trim()) params.set('seed_email', customer.email.trim());
  return `/returns?${params.toString()}`;
}

export function CustomersWorkspace() {
  const searchParams = useSearchParams();
  const searchKey = searchParams.toString();
  const query = (searchParams.get('q') ?? '').trim();
  const [items, setItems] = useState<CustomerWorkspaceItem[]>([]);
  const [selectedCustomerId, setSelectedCustomerId] = useState('');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    let active = true;
    setLoading(true);
    void getCustomersWorkspace(query)
      .then((payload) => {
        if (!active) return;
        setItems(payload.items);
        setSelectedCustomerId((current) => current || payload.items[0]?.customer_id || '');
        setError('');
      })
      .catch((loadError) => {
        if (!active) return;
        setError(loadError instanceof Error ? loadError.message : 'Unable to load customers.');
      })
      .finally(() => {
        if (active) setLoading(false);
      });

    return () => {
      active = false;
    };
  }, [query, searchKey]);

  useEffect(() => {
    if (!items.length) {
      setSelectedCustomerId('');
      return;
    }
    if (!items.some((item) => item.customer_id === selectedCustomerId)) {
      setSelectedCustomerId(items[0].customer_id);
    }
  }, [items, selectedCustomerId]);

  const selectedCustomer = useMemo(
    () => items.find((item) => item.customer_id === selectedCustomerId) ?? null,
    [items, selectedCustomerId],
  );

  const totals = useMemo(() => {
    return items.reduce(
      (summary, item) => ({
        openOrders: summary.openOrders + item.open_orders,
        outstandingBalance: summary.outstandingBalance + Number(item.outstanding_balance || '0'),
      }),
      { openOrders: 0, outstandingBalance: 0 },
    );
  }, [items]);

  return (
    <div className="operations-page customers-module">
      <div className="operations-toolbar">
        <div>
          <h2>{query ? 'Customer search results' : 'Recent customers'}</h2>
        </div>
        <div className="operations-toolbar-actions">
          <Link href="/sales" className="btn-primary">Open Sales</Link>
          <Link href="/returns" className="secondary">Open Returns</Link>
        </div>
      </div>

      {error ? <WorkspaceNotice tone="error">{error}</WorkspaceNotice> : null}

      <div className="operations-kpi-grid customers-kpi-grid">
        <article className="operations-kpi-card">
          <span>Customers shown</span>
          <strong>{items.length}</strong>
        </article>
        <article className="operations-kpi-card">
          <span>Open orders</span>
          <strong>{totals.openOrders}</strong>
        </article>
        <article className="operations-kpi-card">
          <span>Outstanding balance</span>
          <strong>{formatMoney(totals.outstandingBalance)}</strong>
        </article>
      </div>

      {loading ? <div className="reports-loading">Loading customers…</div> : null}

      {!loading && !items.length ? (
        <WorkspaceEmpty
          title={query ? 'No customer matched that search' : 'No customers yet'}
          message={query ? 'Try another phone number, email, or customer name.' : 'Customers will appear here after sales and returns create customer records.'}
        />
      ) : null}

      {!loading && items.length ? (
        <div className="operations-split-layout customers-split-layout">
          <WorkspacePanel
            title={query ? 'Matches' : 'Recent customers'}
            description="Select one customer to review their latest orders, returns, and outstanding balance."
          >
            <div className="operations-list-stack">
              {items.map((customer) => (
                <button
                  key={customer.customer_id}
                  type="button"
                  className={selectedCustomerId === customer.customer_id ? 'operations-list-card active' : 'operations-list-card'}
                  onClick={() => setSelectedCustomerId(customer.customer_id)}
                >
                  <div className="operations-list-card-head">
                    <strong>{customer.name}</strong>
                    {customer.outstanding_balance !== '0' ? <span className="status-pill">Balance due</span> : null}
                  </div>
                  <p>{customer.phone || customer.email || 'No contact details saved'}</p>
                  <div className="operations-inline-meta compact">
                    <span>{customer.total_orders} orders</span>
                    <span>{customer.total_returns} returns</span>
                    <span>{formatMoney(customer.outstanding_balance)}</span>
                  </div>
                </button>
              ))}
            </div>
          </WorkspacePanel>

          <WorkspacePanel
            title={selectedCustomer ? selectedCustomer.name : 'Customer summary'}
            description="Use this page to identify the customer quickly. Keep order and return edits inside the transaction modules."
          >
            {selectedCustomer ? (
              <div className="operations-detail-stack">
                <div className="operations-inline-meta wrap">
                  {selectedCustomer.phone ? <span>{selectedCustomer.phone}</span> : null}
                  {selectedCustomer.email ? <span>{selectedCustomer.email}</span> : null}
                  {selectedCustomer.last_order_at ? <span>Last order {formatDateTime(selectedCustomer.last_order_at)}</span> : null}
                  {selectedCustomer.last_return_at ? <span>Last return {formatDateTime(selectedCustomer.last_return_at)}</span> : null}
                </div>

                <div className="operations-kpi-grid compact">
                  <article className="operations-kpi-card">
                    <span>Total orders</span>
                    <strong>{selectedCustomer.total_orders}</strong>
                  </article>
                  <article className="operations-kpi-card">
                    <span>Open orders</span>
                    <strong>{selectedCustomer.open_orders}</strong>
                  </article>
                  <article className="operations-kpi-card">
                    <span>Total returns</span>
                    <strong>{selectedCustomer.total_returns}</strong>
                  </article>
                  <article className="operations-kpi-card">
                    <span>Lifetime revenue</span>
                    <strong>{formatMoney(selectedCustomer.lifetime_revenue)}</strong>
                  </article>
                </div>

                <div className="operations-toolbar-actions customers-detail-actions">
                  <Link href={buildSalesSeedHref(selectedCustomer)} className="btn-primary">Open Sales</Link>
                  <Link href={buildReturnsSeedHref(selectedCustomer)} className="secondary">Open Returns</Link>
                </div>

                <div className="operations-dual-section">
                  <section>
                    <div className="operations-section-heading">
                      <h4>Recent orders</h4>
                    </div>
                    {selectedCustomer.recent_orders.length ? (
                      <div className="operations-list-stack compact">
                        {selectedCustomer.recent_orders.map((order) => (
                          <Link key={order.sales_order_id} href={`/sales?q=${encodeURIComponent(order.order_number)}&tab=${order.status === 'completed' ? 'completed' : 'open'}`} className="operations-list-card as-link">
                            <div className="operations-list-card-head">
                              <strong>{order.order_number}</strong>
                              <span className="status-pill">{order.status}</span>
                            </div>
                            <p>{formatDateTime(order.ordered_at)}</p>
                            <div className="operations-inline-meta compact">
                              <span>{order.payment_status}</span>
                              <span>{formatMoney(order.total_amount)}</span>
                            </div>
                          </Link>
                        ))}
                      </div>
                    ) : (
                      <WorkspaceEmpty title="No orders yet" message="Sales history will appear here after the first order is created." />
                    )}
                  </section>

                  <section>
                    <div className="operations-section-heading">
                      <h4>Recent returns</h4>
                    </div>
                    {selectedCustomer.recent_returns.length ? (
                      <div className="operations-list-stack compact">
                        {selectedCustomer.recent_returns.map((record) => (
                          <Link key={record.sales_return_id} href={`/returns?q=${encodeURIComponent(record.return_number)}&tab=history`} className="operations-list-card as-link">
                            <div className="operations-list-card-head">
                              <strong>{record.return_number}</strong>
                              <span className="status-pill">{record.refund_status}</span>
                            </div>
                            <p>{record.order_number || 'No linked order number'}</p>
                            <div className="operations-inline-meta compact">
                              <span>{formatDateTime(record.requested_at)}</span>
                              <span>{formatMoney(record.refund_amount)}</span>
                            </div>
                          </Link>
                        ))}
                      </div>
                    ) : (
                      <WorkspaceEmpty title="No returns yet" message="Return history will appear here after the first completed return." />
                    )}
                  </section>
                </div>
              </div>
            ) : (
              <WorkspaceEmpty title="Select a customer" message="Choose one customer from the list to review their summary and recent activity." />
            )}
          </WorkspacePanel>
        </div>
      ) : null}
      <div className="mobile-action-safe-spacer" aria-hidden="true" />
    </div>
  );
}
