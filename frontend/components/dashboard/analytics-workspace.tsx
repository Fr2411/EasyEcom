'use client';

import Link from 'next/link';
import { FormEvent, useEffect, useMemo, useState } from 'react';
import { WorkspaceEmpty, WorkspaceNotice, WorkspacePanel } from '@/components/commerce/workspace-primitives';
import { getSalesOrders, getReturns } from '@/lib/api/commerce';
import { formatDateTime, formatMoney, formatQuantity } from '@/lib/commerce-format';
import { getDashboardAnalytics } from '@/lib/api/dashboard';
import { getFinanceOverview } from '@/lib/api/finance';
import type { DashboardAnalytics, DashboardRangeKey } from '@/types/dashboard';
import type { FinanceOverview } from '@/types/finance';
import type { ReturnRecord } from '@/types/returns';
import type { SalesOrder } from '@/types/sales';

const RANGE_OPTIONS: Array<{ value: DashboardRangeKey; label: string }> = [
  { value: 'last_7_days', label: 'Last 7 days' },
  { value: 'mtd', label: 'Month to date' },
  { value: 'last_30_days', label: 'Last 30 days' },
  { value: 'last_90_days', label: 'Last 90 days' },
  { value: 'custom', label: 'Custom range' },
];

function isoDate(offsetDays = 0) {
  const current = new Date();
  current.setDate(current.getDate() + offsetDays);
  return current.toISOString().slice(0, 10);
}

function metricValue(metrics: DashboardAnalytics['kpis'], metricId: string) {
  return metrics.find((metric) => metric.id === metricId)?.value ?? null;
}

export function DashboardAnalyticsWorkspace() {
  const [filters, setFilters] = useState({
    rangeKey: 'mtd' as DashboardRangeKey,
    locationId: '',
    fromDate: isoDate(-29),
    toDate: isoDate(0),
  });
  const [draftFilters, setDraftFilters] = useState(filters);
  const [dashboard, setDashboard] = useState<DashboardAnalytics | null>(null);
  const [financeOverview, setFinanceOverview] = useState<FinanceOverview | null>(null);
  const [openOrders, setOpenOrders] = useState<SalesOrder[]>([]);
  const [returns, setReturns] = useState<ReturnRecord[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    let active = true;
    setLoading(true);
    void Promise.allSettled([
      getDashboardAnalytics({
        rangeKey: filters.rangeKey,
        locationId: filters.locationId || undefined,
        fromDate: filters.rangeKey === 'custom' ? filters.fromDate : undefined,
        toDate: filters.rangeKey === 'custom' ? filters.toDate : undefined,
      }),
      getFinanceOverview(),
      getSalesOrders({ status: 'draft' }),
      getSalesOrders({ status: 'confirmed' }),
      getReturns(''),
    ])
      .then((results) => {
        if (!active) return;
        const dashboardResult = results[0];
        if (dashboardResult.status !== 'fulfilled') {
          throw dashboardResult.reason;
        }
        setDashboard(dashboardResult.value);
        setFinanceOverview(results[1].status === 'fulfilled' ? results[1].value : null);
        setOpenOrders(
          [
            ...(results[2].status === 'fulfilled' ? results[2].value.items ?? [] : []),
            ...(results[3].status === 'fulfilled' ? results[3].value.items ?? [] : []),
          ],
        );
        setReturns(results[4].status === 'fulfilled' ? results[4].value.items ?? [] : []);
        setError('');
      })
      .catch((loadError) => {
        if (!active) return;
        setError(loadError instanceof Error ? loadError.message : 'Unable to load dashboard.');
      })
      .finally(() => {
        if (active) setLoading(false);
      });

    return () => {
      active = false;
    };
  }, [filters]);

  const onSubmit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setFilters(draftFilters);
  };

  const pendingReturns = useMemo(
    () => returns.filter((item) => Number(item.refund_outstanding_amount ?? '0') > 0).slice(0, 5),
    [returns],
  );

  const priorityCards = useMemo(() => {
    if (!dashboard) return [];
    return [
      {
        label: 'Low-stock variants',
        value: String(dashboard.tables.low_stock_variants.length),
        href: '/inventory',
        cta: 'Open Inventory',
      },
      {
        label: 'Open orders',
        value: String(openOrders.length),
        href: '/sales?tab=open',
        cta: 'Open Sales',
      },
      {
        label: 'Pending refunds',
        value: String(pendingReturns.length),
        href: '/returns?tab=history',
        cta: 'Open Returns',
      },
      {
        label: 'Receivables',
        value: formatMoney(financeOverview?.receivables),
        href: '/finance',
        cta: 'Open Finance',
      },
    ];
  }, [dashboard, financeOverview, openOrders.length, pendingReturns.length]);

  if (loading && !dashboard) {
    return <div className="reports-loading">Loading dashboard…</div>;
  }

  if (error && !dashboard) {
    return <div className="reports-error">{error}</div>;
  }

  if (!dashboard) {
    return <WorkspaceEmpty title="Dashboard unavailable" message="No dashboard data was returned for this workspace." />;
  }

  return (
    <div className="operations-page dashboard-module">
      <div className="operations-toolbar">
        <div>
          <p className="operations-eyebrow">Today board</p>
          <h2>Exceptions that need attention now</h2>
          <p>Use this page to decide what needs action first, then move into the transaction workspace that owns the fix.</p>
        </div>
        <div className="operations-toolbar-actions">
          <Link href="/sales" className="btn-primary">Open Sales</Link>
        </div>
      </div>

      <form className="operations-filter-bar" onSubmit={onSubmit}>
        <label>
          Range
          <select
            value={draftFilters.rangeKey}
            onChange={(event) => setDraftFilters({ ...draftFilters, rangeKey: event.target.value as DashboardRangeKey })}
          >
            {RANGE_OPTIONS.map((option) => (
              <option key={option.value} value={option.value}>{option.label}</option>
            ))}
          </select>
        </label>
        {dashboard.locations.length > 1 ? (
          <label>
            Location
            <select
              value={draftFilters.locationId}
              onChange={(event) => setDraftFilters({ ...draftFilters, locationId: event.target.value })}
            >
              <option value="">All locations</option>
              {dashboard.locations.map((location) => (
                <option key={location.location_id} value={location.location_id}>{location.name}</option>
              ))}
            </select>
          </label>
        ) : null}
        {draftFilters.rangeKey === 'custom' ? (
          <>
            <label>
              From
              <input
                type="date"
                value={draftFilters.fromDate}
                onChange={(event) => setDraftFilters({ ...draftFilters, fromDate: event.target.value })}
              />
            </label>
            <label>
              To
              <input
                type="date"
                value={draftFilters.toDate}
                onChange={(event) => setDraftFilters({ ...draftFilters, toDate: event.target.value })}
              />
            </label>
          </>
        ) : null}
        <button type="submit" className="secondary">Apply Filters</button>
      </form>

      {error ? <WorkspaceNotice tone="error">{error}</WorkspaceNotice> : null}

      <div className="operations-kpi-grid">
        <article className="operations-kpi-card">
          <span>Completed sales</span>
          <strong>{formatMoney(metricValue(dashboard.kpis, 'completed_sales_revenue'))}</strong>
        </article>
        <article className="operations-kpi-card">
          <span>Completed orders</span>
          <strong>{String(metricValue(dashboard.kpis, 'completed_orders') ?? 0)}</strong>
        </article>
        <article className="operations-kpi-card">
          <span>Low-stock variants</span>
          <strong>{String(metricValue(dashboard.kpis, 'low_stock_variants') ?? dashboard.tables.low_stock_variants.length)}</strong>
        </article>
        <article className="operations-kpi-card">
          <span>Open orders</span>
          <strong>{openOrders.length}</strong>
        </article>
        <article className="operations-kpi-card">
          <span>Receivables</span>
          <strong>{formatMoney(financeOverview?.receivables)}</strong>
        </article>
      </div>

      <WorkspacePanel title="Priority queue" description="Each card opens the workspace that owns the next action.">
        <div className="operations-priority-grid">
          {priorityCards.map((item) => (
            <Link key={item.label} href={item.href} className="operations-priority-card">
              <span>{item.label}</span>
              <strong>{item.value}</strong>
              <em>{item.cta}</em>
            </Link>
          ))}
        </div>
      </WorkspacePanel>

      <div className="operations-split-layout dashboard-split-layout">
        <WorkspacePanel title="Stock pressure" description="Variants already at or below reorder level.">
          {dashboard.tables.low_stock_variants.length ? (
            <div className="operations-list-stack compact">
              {dashboard.tables.low_stock_variants.slice(0, 6).map((item) => (
                <Link key={item.variant_id} href="/inventory" className="operations-list-card as-link">
                  <div className="operations-list-card-head">
                    <strong>{item.label}</strong>
                    <span>{formatQuantity(item.available_qty)}</span>
                  </div>
                  <p>{item.product_name}</p>
                  <div className="operations-inline-meta compact">
                    <span>Reorder {formatQuantity(item.reorder_level)}</span>
                    <span>Reserved {formatQuantity(item.reserved_qty)}</span>
                  </div>
                </Link>
              ))}
            </div>
          ) : (
            <WorkspaceEmpty title="No low-stock pressure" message="Variants under reorder pressure will appear here automatically." />
          )}
        </WorkspacePanel>

        <WorkspacePanel title="Pending returns and refunds" description="Returns still waiting on refund completion.">
          {pendingReturns.length ? (
            <div className="operations-list-stack compact">
              {pendingReturns.map((item) => (
                <Link key={item.sales_return_id} href={`/returns?q=${encodeURIComponent(item.return_number)}&tab=history`} className="operations-list-card as-link">
                  <div className="operations-list-card-head">
                    <strong>{item.return_number}</strong>
                    <span>{formatMoney(item.refund_outstanding_amount)}</span>
                  </div>
                  <p>{item.customer_name || item.order_number}</p>
                  <div className="operations-inline-meta compact">
                    <span>{item.refund_status}</span>
                    <span>{formatDateTime(item.requested_at)}</span>
                  </div>
                </Link>
              ))}
            </div>
          ) : (
            <WorkspaceEmpty title="No pending refunds" message="Returns with unpaid refund balances will appear here." />
          )}
        </WorkspacePanel>
      </div>

      <WorkspacePanel title="Sales and activity snapshot" description="A fast read on what is moving and what happened most recently.">
        <div className="operations-dual-section">
          <section>
            <div className="operations-section-heading">
              <h4>Top products</h4>
              <p>Products leading the current reporting window.</p>
            </div>
            {dashboard.tables.top_products_by_units_sold.length ? (
              <div className="operations-list-stack compact">
                {dashboard.tables.top_products_by_units_sold.slice(0, 5).map((item) => (
                  <div key={`${item.product_id}-${item.product_name}`} className="operations-list-card static">
                    <div className="operations-list-card-head">
                      <strong>{item.product_name}</strong>
                      <span>{formatQuantity(item.units_sold)}</span>
                    </div>
                    <p>{formatMoney(item.revenue)}</p>
                  </div>
                ))}
              </div>
            ) : (
              <WorkspaceEmpty title="No completed sales yet" message="Top products will appear here once the selected range has completed sales." />
            )}
          </section>
          <section>
            <div className="operations-section-heading">
              <h4>Recent activity</h4>
              <p>Latest stock and sales events from the selected scope.</p>
            </div>
            {dashboard.tables.recent_activity.length ? (
              <div className="operations-list-stack compact">
                {dashboard.tables.recent_activity.slice(0, 6).map((item, index) => (
                  <div key={`${item.timestamp}-${index}`} className="operations-list-card static">
                    <div className="operations-list-card-head">
                      <strong>{item.label}</strong>
                      <span>{formatQuantity(item.quantity)}</span>
                    </div>
                    <p>{item.product_name}</p>
                    <div className="operations-inline-meta compact">
                      <span>{item.event_type.replaceAll('_', ' ')}</span>
                      <span>{formatDateTime(item.timestamp)}</span>
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <WorkspaceEmpty title="No recent activity" message="Ledger-backed activity will appear here once transactions are recorded in the selected range." />
            )}
          </section>
        </div>
      </WorkspacePanel>
      <div className="mobile-action-safe-spacer" aria-hidden="true" />
    </div>
  );
}
