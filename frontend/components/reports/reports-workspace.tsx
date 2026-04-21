'use client';

import { FormEvent, useEffect, useMemo, useState } from 'react';
import { WorkspaceEmpty, WorkspaceNotice, WorkspacePanel, WorkspaceTabs } from '@/components/commerce/workspace-primitives';
import {
  getFinanceReport,
  getInventoryReport,
  getProductsReport,
  getReportsOverview,
  getReturnsReport,
  getSalesReport,
} from '@/lib/api/reports';
import { formatMoney, formatQuantity } from '@/lib/commerce-format';

type ReportView = 'sales' | 'inventory' | 'finance' | 'returns';

type ReportsState = {
  overview: Awaited<ReturnType<typeof getReportsOverview>>;
  sales: Awaited<ReturnType<typeof getSalesReport>>;
  inventory: Awaited<ReturnType<typeof getInventoryReport>>;
  finance: Awaited<ReturnType<typeof getFinanceReport>>;
  returns: Awaited<ReturnType<typeof getReturnsReport>>;
  products: Awaited<ReturnType<typeof getProductsReport>>;
};

function isoDate(offsetDays = 0) {
  const current = new Date();
  current.setDate(current.getDate() + offsetDays);
  return current.toISOString().slice(0, 10);
}

function downloadCsv(filename: string, rows: Array<Array<string | number | null | undefined>>) {
  const csv = rows
    .map((row) => row.map((cell) => `"${String(cell ?? '').replaceAll('"', '""')}"`).join(','))
    .join('\n');
  const blob = new Blob([csv], { type: 'text/csv;charset=utf-8' });
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = filename;
  link.click();
  URL.revokeObjectURL(url);
}

export function ReportsWorkspace() {
  const [filters, setFilters] = useState({ fromDate: isoDate(-29), toDate: isoDate(0) });
  const [draftFilters, setDraftFilters] = useState(filters);
  const [activeView, setActiveView] = useState<ReportView>('sales');
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
      getFinanceReport(filters),
      getReturnsReport(filters),
      getProductsReport(filters),
    ])
      .then(([overview, sales, inventory, finance, returns, products]) => {
        if (!active) return;
        setState({ overview, sales, inventory, finance, returns, products });
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

  const exportActiveView = () => {
    if (!state) return;

    if (activeView === 'sales') {
      downloadCsv('sales-report.csv', [
        ['Product', 'Quantity Sold', 'Revenue'],
        ...state.sales.top_products.map((item) => [item.product_name, item.qty_sold, item.revenue]),
      ]);
      return;
    }

    if (activeView === 'inventory') {
      downloadCsv('inventory-report.csv', [
        ['Product', 'Current Qty'],
        ...state.inventory.low_stock_items.map((item) => [item.product_name, item.current_qty]),
      ]);
      return;
    }

    if (activeView === 'finance') {
      downloadCsv('finance-report.csv', [
        ['Metric', 'Value'],
        ['Receivables', state.finance.receivables_total],
        ['Expenses', state.finance.expense_total],
        ['Net Operating Snapshot', state.finance.net_operating_snapshot ?? ''],
      ]);
      return;
    }

    downloadCsv('returns-report.csv', [
      ['Metric', 'Value'],
      ['Returns Count', state.returns.returns_count],
      ['Return Quantity', state.returns.return_qty_total],
      ['Return Amount', state.returns.return_amount_total],
    ]);
  };

  const onSubmit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setFilters(draftFilters);
  };

  const kpis = useMemo(() => {
    if (!state) return [];
    return [
      { label: 'Sales revenue', value: formatMoney(state.overview.sales_revenue_total) },
      { label: 'Completed orders', value: String(state.overview.sales_count) },
      { label: 'Operating expense', value: formatMoney(state.overview.expense_total) },
      { label: 'Receivables', value: formatMoney(state.finance.receivables_total) },
      { label: 'Returns', value: String(state.returns.returns_count) },
    ];
  }, [state]);

  return (
    <div className="operations-page reports-module">
      <div className="operations-toolbar">
        <div>
          <h2>Focus on one report at a time</h2>
        </div>
        <div className="operations-toolbar-actions">
          <button type="button" className="secondary" onClick={exportActiveView} disabled={!state}>Export</button>
        </div>
      </div>

      <form className="operations-filter-bar" onSubmit={onSubmit}>
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
        <button type="submit" className="btn-primary">Refresh Report</button>
      </form>

      {loading ? <div className="reports-loading">Loading reports…</div> : null}
      {error ? <WorkspaceNotice tone="error">{error}</WorkspaceNotice> : null}

      {!loading && state ? (
        <>
          <div className="operations-kpi-grid">
            {kpis.map((item) => (
              <article key={item.label} className="operations-kpi-card">
                <span>{item.label}</span>
                <strong>{item.value}</strong>
              </article>
            ))}
          </div>

          <WorkspaceTabs
            tabs={[
              { id: 'sales', label: 'Sales' },
              { id: 'inventory', label: 'Inventory' },
              { id: 'finance', label: 'Finance' },
              { id: 'returns', label: 'Returns' },
            ]}
            activeTab={activeView}
            onTabChange={setActiveView}
          />

          {activeView === 'sales' ? (
            <WorkspacePanel title="Sales" description="Top products and customers in the selected period.">
              <div className="operations-kpi-grid compact">
                <article className="operations-kpi-card">
                  <span>Revenue</span>
                  <strong>{formatMoney(state.sales.revenue_total)}</strong>
                </article>
                <article className="operations-kpi-card">
                  <span>Orders</span>
                  <strong>{state.sales.sales_count}</strong>
                </article>
              </div>
              <div className="operations-dual-section">
                <section>
                  <div className="operations-section-heading">
                    <h4>Top products</h4>
                  </div>
                  {state.sales.top_products.length ? (
                    <div className="operations-list-stack compact">
                      {state.sales.top_products.map((item) => (
                        <div key={`${item.product_id}-${item.product_name}`} className="operations-list-card static">
                          <div className="operations-list-card-head">
                            <strong>{item.product_name}</strong>
                            <span>{formatMoney(item.revenue)}</span>
                          </div>
                          <p>Qty sold {item.qty_sold}</p>
                        </div>
                      ))}
                    </div>
                  ) : (
                    <WorkspaceEmpty title="No sales in range" message="Completed sales will appear here for the selected date range." />
                  )}
                </section>
                <section>
                  <div className="operations-section-heading">
                    <h4>Top customers</h4>
                  </div>
                  {state.sales.top_customers.length ? (
                    <div className="operations-list-stack compact">
                      {state.sales.top_customers.map((item) => (
                        <div key={`${item.customer_id}-${item.customer_name}`} className="operations-list-card static">
                          <div className="operations-list-card-head">
                            <strong>{item.customer_name}</strong>
                            <span>{formatMoney(item.revenue)}</span>
                          </div>
                          <p>{item.sales_count} orders</p>
                        </div>
                      ))}
                    </div>
                  ) : (
                    <WorkspaceEmpty title="No customer data" message="Top customer activity will appear here after completed sales are recorded." />
                  )}
                </section>
              </div>
            </WorkspacePanel>
          ) : null}

          {activeView === 'inventory' ? (
            <WorkspacePanel title="Inventory" description="Stock coverage and low-stock pressure from live ledger data.">
              <div className="operations-kpi-grid compact">
                <article className="operations-kpi-card">
                  <span>SKUs with stock</span>
                  <strong>{state.inventory.total_skus_with_stock}</strong>
                </article>
                <article className="operations-kpi-card">
                  <span>Total stock units</span>
                  <strong>{formatQuantity(state.inventory.total_stock_units)}</strong>
                </article>
                <article className="operations-kpi-card">
                  <span>Inventory value</span>
                  <strong>{formatMoney(state.inventory.inventory_value)}</strong>
                </article>
              </div>
              {state.inventory.low_stock_items.length ? (
                <div className="operations-list-stack compact">
                  {state.inventory.low_stock_items.map((item) => (
                    <div key={`${item.product_id}-${item.product_name}`} className="operations-list-card static">
                      <div className="operations-list-card-head">
                        <strong>{item.product_name}</strong>
                        <span>{item.current_qty}</span>
                      </div>
                      <p>Current quantity at or near reorder pressure.</p>
                    </div>
                  ))}
                </div>
              ) : (
                <WorkspaceEmpty title="No low-stock items" message="Items under stock pressure will appear here for the selected range." />
              )}
            </WorkspacePanel>
          ) : null}

          {activeView === 'finance' ? (
            <WorkspacePanel title="Finance" description="Cash pressure and outstanding collection in the selected range.">
              <div className="operations-kpi-grid compact">
                <article className="operations-kpi-card">
                  <span>Receivables</span>
                  <strong>{formatMoney(state.finance.receivables_total)}</strong>
                </article>
                <article className="operations-kpi-card">
                  <span>Expenses</span>
                  <strong>{formatMoney(state.finance.expense_total)}</strong>
                </article>
                <article className="operations-kpi-card">
                  <span>Net operating</span>
                  <strong>{formatMoney(state.finance.net_operating_snapshot)}</strong>
                </article>
              </div>
              {state.finance.deferred_metrics.length ? (
                <WorkspaceNotice tone="info">
                  Some finance metrics are deferred until more transactional data is available.
                </WorkspaceNotice>
              ) : null}
            </WorkspacePanel>
          ) : null}

          {activeView === 'returns' ? (
            <WorkspacePanel title="Returns" description="Return drag and low-movement product context in the same review view.">
              <div className="operations-kpi-grid compact">
                <article className="operations-kpi-card">
                  <span>Returns count</span>
                  <strong>{state.returns.returns_count}</strong>
                </article>
                <article className="operations-kpi-card">
                  <span>Returned quantity</span>
                  <strong>{state.returns.return_qty_total}</strong>
                </article>
                <article className="operations-kpi-card">
                  <span>Return amount</span>
                  <strong>{formatMoney(state.returns.return_amount_total)}</strong>
                </article>
              </div>
              <div className="operations-dual-section">
                <section>
                  <div className="operations-section-heading">
                    <h4>Highest selling products</h4>
                  </div>
                  {state.products.highest_selling.length ? (
                    <div className="operations-list-stack compact">
                      {state.products.highest_selling.map((item) => (
                        <div key={`${item.product_id}-${item.product_name}`} className="operations-list-card static">
                          <div className="operations-list-card-head">
                            <strong>{item.product_name}</strong>
                            <span>{formatMoney(item.revenue)}</span>
                          </div>
                          <p>Qty sold {item.qty_sold}</p>
                        </div>
                      ))}
                    </div>
                  ) : (
                    <WorkspaceEmpty title="No product movement" message="Product movement will appear here after completed sales are recorded." />
                  )}
                </section>
                <section>
                  <div className="operations-section-heading">
                    <h4>Low or zero movement</h4>
                  </div>
                  {state.products.low_or_zero_movement.length ? (
                    <div className="operations-list-stack compact">
                      {state.products.low_or_zero_movement.map((item) => (
                        <div key={`${item.product_id}-${item.product_name}`} className="operations-list-card static">
                          <div className="operations-list-card-head">
                            <strong>{item.product_name}</strong>
                            <span>{formatMoney(item.revenue)}</span>
                          </div>
                          <p>Qty sold {item.qty_sold}</p>
                        </div>
                      ))}
                    </div>
                  ) : (
                    <WorkspaceEmpty title="No low-movement products" message="Low-movement products will appear here when a selected range has little or no demand." />
                  )}
                </section>
              </div>
            </WorkspacePanel>
          ) : null}
        </>
      ) : null}
      <div className="mobile-action-safe-spacer" aria-hidden="true" />
    </div>
  );
}
