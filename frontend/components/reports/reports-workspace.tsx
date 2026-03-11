'use client';

import { useEffect, useMemo, useState } from 'react';
import { getFinanceReport, getInventoryReport, getProductsReport, getPurchasesReport, getReportsOverview, getReturnsReport, getSalesReport } from '@/lib/api/reports';
import type { FinanceReport, InventoryReport, ProductsReport, PurchasesReport, ReportsOverview, ReturnsReport, SalesReport } from '@/types/reports';

const fmtMoney = (v: number | null) => (v === null ? 'Deferred' : new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD' }).format(v));
const today = new Date().toISOString().slice(0, 10);
const past30 = new Date(Date.now() - 29 * 86400000).toISOString().slice(0, 10);

export function ReportsWorkspace() {
  const [fromDate, setFromDate] = useState(past30);
  const [toDate, setToDate] = useState(today);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [warnings, setWarnings] = useState<string[]>([]);
  const [overview, setOverview] = useState<ReportsOverview | null>(null);
  const [sales, setSales] = useState<SalesReport | null>(null);
  const [inventory, setInventory] = useState<InventoryReport | null>(null);
  const [products, setProducts] = useState<ProductsReport | null>(null);
  const [finance, setFinance] = useState<FinanceReport | null>(null);
  const [returnsData, setReturnsData] = useState<ReturnsReport | null>(null);
  const [purchases, setPurchases] = useState<PurchasesReport | null>(null);

  const load = async () => {
    try {
      setLoading(true);
      setError(null);
      setWarnings([]);
      const filters = { fromDate, toDate };
      const sections = await Promise.allSettled([
        getReportsOverview(filters),
        getSalesReport(filters),
        getInventoryReport(filters),
        getProductsReport(filters),
        getFinanceReport(filters),
        getReturnsReport(filters),
        getPurchasesReport(filters),
      ]);

      const nextWarnings: string[] = [];
      if (sections[0].status === 'fulfilled') setOverview(sections[0].value);
      else { setOverview(null); setError('Unable to load reporting overview.'); }
      if (sections[1].status === 'fulfilled') setSales(sections[1].value);
      else { setSales(null); nextWarnings.push('Sales report is temporarily unavailable.'); }
      if (sections[2].status === 'fulfilled') setInventory(sections[2].value);
      else { setInventory(null); nextWarnings.push('Inventory report is temporarily unavailable.'); }
      if (sections[3].status === 'fulfilled') setProducts(sections[3].value);
      else { setProducts(null); nextWarnings.push('Products report is temporarily unavailable.'); }
      if (sections[4].status === 'fulfilled') setFinance(sections[4].value);
      else { setFinance(null); nextWarnings.push('Finance report is temporarily unavailable.'); }
      if (sections[5].status === 'fulfilled') setReturnsData(sections[5].value);
      else { setReturnsData(null); nextWarnings.push('Returns report is temporarily unavailable.'); }
      if (sections[6].status === 'fulfilled') setPurchases(sections[6].value);
      else { setPurchases(null); nextWarnings.push('Purchases report is temporarily unavailable.'); }

      setWarnings(nextWarnings);
    } catch {
      setError('Unable to load reporting data.');
    } finally { setLoading(false); }
  };

  useEffect(() => { void load(); }, []);

  const deferred = useMemo(() => [sales, inventory, products, finance, returnsData, purchases].flatMap((section) => section?.deferred_metrics ?? []), [sales, inventory, products, finance, returnsData, purchases]);

  if (loading) return <div className="reports-loading">Loading analytics...</div>;
  if (error || !overview) return <div className="reports-error">{error ?? 'Reports response is incomplete.'}</div>;

  return <section className="reports-module"><div className="reports-filter-bar"><label>From <input aria-label="From date" type="date" value={fromDate} onChange={(e) => setFromDate(e.target.value)} /></label><label>To <input aria-label="To date" type="date" value={toDate} onChange={(e) => setToDate(e.target.value)} /></label><button type="button" onClick={() => void load()}>Apply</button></div>
    <div className="kpi-grid"><article className="kpi-card"><p>Sales Revenue</p><h3>{fmtMoney(overview.sales_revenue_total)}</h3></article><article className="kpi-card"><p>Sales Count</p><h3>{overview.sales_count}</h3></article><article className="kpi-card"><p>Expenses</p><h3>{fmtMoney(overview.expense_total)}</h3></article><article className="kpi-card"><p>Returns Impact</p><h3>{fmtMoney(overview.returns_total)}</h3></article></div>
    {warnings.length > 0 ? <div className="reports-deferred"><h4>Partial data warnings</h4><ul>{warnings.map((warning, idx) => <li key={idx}>{warning}</li>)}</ul></div> : null}
    <div className="reports-grid"><article className="section-card"><h3>Sales trend</h3>{sales ? <ul>{sales.sales_trend.slice(-7).map((t) => <li key={t.period}>{t.period}: {fmtMoney(t.value)}</li>)}</ul> : <p className="muted">Temporarily unavailable.</p>}</article><article className="section-card"><h3>Inventory health</h3>{inventory ? <><p>SKUs with stock: <strong>{inventory.total_skus_with_stock}</strong></p><p>Total stock units: <strong>{inventory.total_stock_units}</strong></p><p>Inventory value: <strong>{fmtMoney(inventory.inventory_value)}</strong></p></> : <p className="muted">Temporarily unavailable.</p>}</article><article className="section-card section-card-wide"><h3>Top products</h3>{!sales ? <p className="muted">Temporarily unavailable.</p> : sales.top_products.length === 0 ? <p className="muted">No sales movement in selected range.</p> : <table className="top-products-table"><thead><tr><th>Product</th><th>Qty</th><th>Revenue</th></tr></thead><tbody>{sales.top_products.slice(0, 8).map((p) => <tr key={p.product_id}><td>{p.product_name}</td><td>{p.qty_sold}</td><td>{fmtMoney(p.revenue)}</td></tr>)}</tbody></table>}</article><article className="section-card"><h3>Finance snapshot</h3>{finance ? <><p>Receivables: <strong>{fmtMoney(finance.receivables_total)}</strong></p><p>Payables: <strong>{fmtMoney(finance.payables_total)}</strong></p><p>Net operating snapshot: <strong>{fmtMoney(finance.net_operating_snapshot)}</strong></p></> : <p className="muted">Temporarily unavailable.</p>}</article><article className="section-card"><h3>Returns & purchases</h3>{returnsData || purchases ? <><p>Returns count: <strong>{returnsData?.returns_count ?? '—'}</strong></p><p>Return qty total: <strong>{returnsData?.return_qty_total ?? '—'}</strong></p><p>Purchases subtotal: <strong>{fmtMoney(purchases?.purchases_subtotal ?? null)}</strong></p></> : <p className="muted">Temporarily unavailable.</p>}</article><article className="section-card"><h3>Low/zero movement</h3>{!products ? <p className="muted">Temporarily unavailable.</p> : products.low_or_zero_movement.length === 0 ? <p className="muted">No low-movement products in range.</p> : <ul>{products.low_or_zero_movement.slice(0, 6).map((p) => <li key={p.product_id}>{p.product_name}</li>)}</ul>}</article></div>
    {deferred.length > 0 ? <div className="reports-deferred"><h4>Deferred metrics</h4><ul>{deferred.map((d, idx) => <li key={`${d.metric}-${idx}`}><strong>{d.metric}:</strong> {d.reason}</li>)}</ul></div> : null}
  </section>;
}
