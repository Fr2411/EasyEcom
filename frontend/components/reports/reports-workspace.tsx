'use client';

import { FormEvent, useEffect, useState } from 'react';
import { WorkspaceEmpty, WorkspaceNotice, WorkspacePanel } from '@/components/commerce/workspace-primitives';
import {
  getFinanceReport,
  getInventoryReport,
  getProductsReport,
  getPurchasesReport,
  getReportsOverview,
  getReturnsReport,
  getSalesReport,
} from '@/lib/api/reports';
import { formatMoney, formatQuantity } from '@/lib/commerce-format';

type ReportsState = {
  overview: Awaited<ReturnType<typeof getReportsOverview>>;
  sales: Awaited<ReturnType<typeof getSalesReport>>;
  inventory: Awaited<ReturnType<typeof getInventoryReport>>;
  purchases: Awaited<ReturnType<typeof getPurchasesReport>>;
  finance: Awaited<ReturnType<typeof getFinanceReport>>;
  returns: Awaited<ReturnType<typeof getReturnsReport>>;
  products: Awaited<ReturnType<typeof getProductsReport>>;
};

function isoDate(offsetDays = 0) {
  const current = new Date();
  current.setDate(current.getDate() + offsetDays);
  return current.toISOString().slice(0, 10);
}

function DeferredList({ items }: { items: Array<{ metric: string; reason: string }> }) {
  if (!items.length) return null;
  return (
    <div className="reports-deferred">
      <strong>Deferred metrics</strong>
      <ul className="admin-match-list">
        {items.map((item) => (
          <li key={item.metric}>
            <strong>{item.metric}</strong>
            <p className="muted">{item.reason}</p>
          </li>
        ))}
      </ul>
    </div>
  );
}

export function ReportsWorkspace() {
  const [filters, setFilters] = useState({ fromDate: isoDate(-29), toDate: isoDate(0) });
  const [draftFilters, setDraftFilters] = useState(filters);
  const [state, setState] = useState<ReportsState | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    let active = true;
    setLoading(true);
    void Promise.all([
      getReportsOverview(filters),
      getSalesReport(filters),
      getInventoryReport(filters),
      getPurchasesReport(filters),
      getFinanceReport(filters),
      getReturnsReport(filters),
      getProductsReport(filters),
    ])
      .then(([overview, sales, inventory, purchases, finance, returns, products]) => {
        if (!active) return;
        setState({ overview, sales, inventory, purchases, finance, returns, products });
        setError('');
      })
      .catch((loadError) => {
        if (!active) return;
        setError(loadError instanceof Error ? loadError.message : 'Unable to load reports.');
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

  return (
    <div className="reports-module">
      <WorkspaceNotice tone="info">
        <strong>Start here</strong>
        <ol>
          <li>Confirm today&apos;s result first: revenue captured and orders converted.</li>
          <li>Use Sales and Inventory to decide your next action: push demand or protect stock.</li>
          <li>Then verify Purchases, Finance, and Returns to control cash pressure and margin drag.</li>
        </ol>
      </WorkspaceNotice>
      <form className="reports-filter-bar" onSubmit={onSubmit}>
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
        <button type="submit">Refresh reports</button>
      </form>

      {loading ? (
        <div className="reports-loading" role="status" aria-live="polite">
          <strong>Loading tenant reports…</strong>
          <p className="muted">Refreshing tenant-scoped metrics from audited records. Existing orders and stock ledgers stay unchanged during loading.</p>
        </div>
      ) : null}
      {error ? <div className="reports-error">{error}</div> : null}

      {!loading && !error && state ? (
        <>
          <div className="reports-grid reports-kpi-grid">
            <article className="ps-card reports-kpi-card reports-kpi-card-featured reports-kpi-card-primary">
              <p>Revenue captured</p>
              <strong>{formatMoney(state.overview.sales_revenue_total)}</strong>
              <span>Total money collected from completed sales in this window.</span>
            </article>
            <article className="ps-card reports-kpi-card reports-kpi-card-featured reports-kpi-card-primary">
              <p>Orders converted</p>
              <strong>{state.overview.sales_count}</strong>
              <span>Completed orders your team turned into shipped business.</span>
            </article>
            <article className="ps-card reports-kpi-card">
              <p>Operating expenses</p>
              <strong>{formatMoney(state.overview.expense_total)}</strong>
              <span>Spend pressure currently reducing operating margin.</span>
            </article>
            <article className="ps-card reports-kpi-card">
              <p>Units returned</p>
              <strong>{state.overview.returns_total}</strong>
              <span>Items coming back that can slow net growth.</span>
            </article>
            <article className="ps-card reports-kpi-card">
              <p>Inventory purchased</p>
              <strong>{formatMoney(state.overview.purchases_total)}</strong>
              <span>Inbound stock investment committed in this period.</span>
            </article>
          </div>

          <WorkspacePanel title="Sales" description="Use this first to verify what actually generated revenue in the selected window.">
            {state.sales.top_products.length ? (
              <ul className="admin-match-list">
                {state.sales.top_products.slice(0, 5).map((item) => (
                  <li key={`${item.product_id}-${item.product_name}`}>
                    <strong>{item.product_name}</strong>
                    <p className="muted">
                      Qty {item.qty_sold} • Revenue {formatMoney(item.revenue)}
                    </p>
                  </li>
                ))}
              </ul>
            ) : (
              <WorkspaceEmpty title="No sales in range" message="This report window has no completed sales yet." />
            )}
            <DeferredList items={state.sales.deferred_metrics} />
          </WorkspacePanel>

          <WorkspacePanel title="Inventory" description="Variant-first stock posture and low-stock pressure from the live ledger.">
            <div className="settings-context">
              <div>
                <dt>SKUs with stock</dt>
                <dd>{state.inventory.total_skus_with_stock}</dd>
              </div>
              <div>
                <dt>Total stock units</dt>
                <dd>{formatQuantity(state.inventory.total_stock_units)}</dd>
              </div>
              <div>
                <dt>Inventory value</dt>
                <dd>{formatMoney(state.inventory.inventory_value)}</dd>
              </div>
            </div>
            <DeferredList items={state.inventory.deferred_metrics} />
          </WorkspacePanel>

          <WorkspacePanel title="Purchases & Finance" description="Then validate cash-out and receivable pressure against sales performance.">
            <div className="reports-grid">
              <article className="ps-card">
                <p>Purchase orders</p>
                <strong>{state.purchases.purchases_count}</strong>
              </article>
              <article className="ps-card">
                <p>Purchase subtotal</p>
                <strong>{formatMoney(state.purchases.purchases_subtotal)}</strong>
              </article>
              <article className="ps-card">
                <p>Receivables</p>
                <strong>{formatMoney(state.finance.receivables_total)}</strong>
              </article>
              <article className="ps-card">
                <p>Expenses</p>
                <strong>{formatMoney(state.finance.expense_total)}</strong>
              </article>
              <article className="ps-card">
                <p>Net operating snapshot</p>
                <strong>{formatMoney(state.finance.net_operating_snapshot)}</strong>
              </article>
            </div>
            <DeferredList items={[...state.purchases.deferred_metrics, ...state.finance.deferred_metrics]} />
          </WorkspacePanel>

          <WorkspacePanel title="Returns & Products" description="Finally confirm return drag and product-level outliers impacting margin.">
            <div className="settings-context">
              <div>
                <dt>Returns count</dt>
                <dd>{state.returns.returns_count}</dd>
              </div>
              <div>
                <dt>Returned quantity</dt>
                <dd>{state.returns.return_qty_total}</dd>
              </div>
              <div>
                <dt>Return amount</dt>
                <dd>{formatMoney(state.returns.return_amount_total)}</dd>
              </div>
            </div>
            {state.products.highest_selling.length ? (
              <ul className="admin-match-list">
                {state.products.highest_selling.slice(0, 5).map((item) => (
                  <li key={`${item.product_id}-${item.product_name}`}>
                    <strong>{item.product_name}</strong>
                    <p className="muted">
                      Qty {item.qty_sold} • Revenue {formatMoney(item.revenue)}
                    </p>
                  </li>
                ))}
              </ul>
            ) : (
              <WorkspaceNotice tone="info">No product movement qualified for this range yet.</WorkspaceNotice>
            )}
            <DeferredList items={[...state.returns.deferred_metrics, ...state.products.deferred_metrics]} />
          </WorkspacePanel>
        </>
      ) : null}
    </div>
  );
}
