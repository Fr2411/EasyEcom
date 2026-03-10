'use client';

import { useEffect, useMemo, useState } from 'react';

import { ApiError, ApiNetworkError } from '@/lib/api/client';
import { getDashboardOverview } from '@/lib/api/dashboard';
import type { DashboardOverview } from '@/types/dashboard';

function fmtCurrency(value: number | null): string {
  if (value === null) return 'Not available yet';
  return new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD', maximumFractionDigits: 2 }).format(value);
}

function fmtNumber(value: number): string {
  return new Intl.NumberFormat('en-US').format(value);
}

export function DashboardOverviewPanel() {
  const [data, setData] = useState<DashboardOverview | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let mounted = true;
    const run = async () => {
      try {
        setLoading(true);
        setError(null);
        const snapshot = await getDashboardOverview();
        if (mounted) {
          setData(snapshot);
        }
      } catch (err) {
        if (!mounted) return;
        if (err instanceof ApiNetworkError) {
          setError('Unable to connect to the dashboard service.');
        } else if (err instanceof ApiError && err.status === 401) {
          setError('Your session has expired. Please sign in again.');
        } else {
          setError('Dashboard data is currently unavailable.');
        }
      } finally {
        if (mounted) setLoading(false);
      }
    };
    run();
    return () => {
      mounted = false;
    };
  }, []);

  const isEmpty = useMemo(() => {
    if (!data) return false;
    return (
      data.kpis.total_products === 0 &&
      data.kpis.total_variants === 0 &&
      data.kpis.current_stock_units === 0 &&
      data.recent_activity.length === 0 &&
      data.top_products.length === 0
    );
  }, [data]);

  if (loading) {
    return <div className="dashboard-loading">Loading dashboard...</div>;
  }

  if (error) {
    return <div className="dashboard-error">{error}</div>;
  }

  if (!data) {
    return <div className="dashboard-error">No dashboard response was returned.</div>;
  }

  return (
    <section className="dashboard-v2">
      <div className="kpi-grid">
        <article className="kpi-card"><p>Total Products</p><h3>{fmtNumber(data.kpis.total_products)}</h3></article>
        <article className="kpi-card"><p>Total Variants / SKUs</p><h3>{fmtNumber(data.kpis.total_variants)}</h3></article>
        <article className="kpi-card"><p>Current Stock Units</p><h3>{fmtNumber(data.kpis.current_stock_units)}</h3></article>
        <article className="kpi-card"><p>Low Stock Items</p><h3>{fmtNumber(data.kpis.low_stock_items)}</h3></article>
      </div>

      {isEmpty ? <div className="dashboard-empty">No products or inventory activity yet. Add products and stock to populate this dashboard.</div> : null}

      <div className="dashboard-grid">
        <article className="section-card">
          <h3>Business Health</h3>
          <ul>
            <li><span>Inventory Value</span><strong>{fmtCurrency(data.business_health.inventory_value)}</strong></li>
            <li><span>Recent Stock Movements (7d)</span><strong>{fmtNumber(data.business_health.recent_stock_movements_count)}</strong></li>
            <li><span>Sales Count (30d)</span><strong>{data.business_health.sales_count_last_30_days ?? 'Not available yet'}</strong></li>
            <li><span>Revenue Snapshot (30d)</span><strong>{fmtCurrency(data.business_health.revenue_last_30_days)}</strong></li>
          </ul>
        </article>

        <article className="section-card">
          <h3>Recent Activity</h3>
          {data.recent_activity.length === 0 ? (
            <p className="muted">No stock activity recorded in the last 7 days.</p>
          ) : (
            <ul className="activity-list">
              {data.recent_activity.map((item) => (
                <li key={`${item.timestamp}-${item.product_name}-${item.qty}`}>
                  <div>
                    <strong>{item.product_name || 'Unknown product'}</strong>
                    <p>{item.txn_type} · Qty {fmtNumber(item.qty)}</p>
                  </div>
                  <time>{new Date(item.timestamp).toLocaleString()}</time>
                </li>
              ))}
            </ul>
          )}
        </article>

        <article className="section-card section-card-wide">
          <h3>Top Products by Stock Value</h3>
          {data.top_products.length === 0 ? (
            <p className="muted">No stock leaderboard available yet.</p>
          ) : (
            <table className="top-products-table">
              <thead>
                <tr><th>Product</th><th>Stock Units</th><th>Stock Value</th></tr>
              </thead>
              <tbody>
                {data.top_products.map((product) => (
                  <tr key={product.product_id}>
                    <td>{product.product_name || product.product_id}</td>
                    <td>{fmtNumber(product.current_qty)}</td>
                    <td>{fmtCurrency(product.stock_value)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </article>
      </div>
    </section>
  );
}
