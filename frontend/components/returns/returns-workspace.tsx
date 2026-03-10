'use client';

import { useEffect, useMemo, useState } from 'react';
import { createReturn, getReturnDetail, getReturnSalesLookup, getReturnableSale, getReturns } from '@/lib/api/returns';
import type { ReturnDetail, ReturnSummary, ReturnableSale, ReturnableSaleDetail } from '@/types/returns';

type DraftLine = { sale_item_id: string; qty: number; reason: string; condition_status: string };

export function ReturnsWorkspace() {
  const [items, setItems] = useState<ReturnSummary[]>([]);
  const [sales, setSales] = useState<ReturnableSale[]>([]);
  const [selectedSale, setSelectedSale] = useState<ReturnableSaleDetail | null>(null);
  const [selectedReturn, setSelectedReturn] = useState<ReturnDetail | null>(null);
  const [query, setQuery] = useState('');
  const [saleId, setSaleId] = useState('');
  const [reason, setReason] = useState('Customer return');
  const [note, setNote] = useState('');
  const [lines, setLines] = useState<DraftLine[]>([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = async (q = query) => {
    try {
      setLoading(true);
      setError(null);
      const [returnsRes, salesRes] = await Promise.all([getReturns(q), getReturnSalesLookup('')]);
      setItems(returnsRes.items);
      setSales(salesRes.items);
    } catch {
      setError('Unable to load returns module.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { load(''); }, []);

  const selectSale = async (nextSaleId: string) => {
    setSaleId(nextSaleId);
    setSelectedReturn(null);
    if (!nextSaleId) {
      setSelectedSale(null);
      setLines([]);
      return;
    }
    try {
      const detail = await getReturnableSale(nextSaleId);
      setSelectedSale(detail);
      const eligible = detail.lines.filter((line) => line.eligible_qty > 0);
      setLines(eligible.map((line) => ({ sale_item_id: line.sale_item_id, qty: 0, reason: reason, condition_status: '' })));
    } catch {
      setError('Unable to load sale return lines.');
    }
  };

  const updateLine = (saleItemId: string, patch: Partial<DraftLine>) => {
    setLines((prev) => prev.map((line) => (line.sale_item_id === saleItemId ? { ...line, ...patch } : line)));
  };

  const selectedLines = useMemo(() => lines.filter((line) => line.qty > 0), [lines]);

  const lineError = useMemo(() => {
    if (!selectedSale) return '';
    for (const line of selectedLines) {
      const base = selectedSale.lines.find((item) => item.sale_item_id === line.sale_item_id);
      if (!base) return 'Invalid return line selected.';
      if (line.qty > base.eligible_qty) return `Return quantity exceeds eligible for ${base.product_name}.`;
      if (!line.reason.trim()) return 'Line reason is required for all return lines.';
    }
    return '';
  }, [selectedLines, selectedSale]);

  const total = useMemo(() => {
    if (!selectedSale) return 0;
    return selectedLines.reduce((sum, line) => {
      const base = selectedSale.lines.find((item) => item.sale_item_id === line.sale_item_id);
      return sum + (base ? base.unit_price * line.qty : 0);
    }, 0);
  }, [selectedLines, selectedSale]);

  const submit = async () => {
    if (!selectedSale || selectedLines.length === 0 || lineError) return;
    try {
      setSaving(true);
      setError(null);
      await createReturn({ sale_id: selectedSale.sale_id, reason, note, lines: selectedLines });
      setSaleId('');
      setSelectedSale(null);
      setLines([]);
      setNote('');
      await load(query);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unable to create return.');
    } finally {
      setSaving(false);
    }
  };

  const openReturn = async (returnId: string) => {
    try {
      const detail = await getReturnDetail(returnId);
      setSelectedReturn(detail);
    } catch {
      setError('Unable to load return detail.');
    }
  };

  return (
    <section className="sales-module">
      <div className="sales-toolbar">
        <input aria-label="Search returns" placeholder="Search by return #, sale #, customer, date" value={query} onChange={(e) => setQuery(e.target.value)} />
        <button type="button" onClick={() => load(query)}>Search</button>
      </div>
      {error ? <p className="sales-error">{error}</p> : null}

      <div className="sales-grid">
        <div className="sales-panel">
          <h3>Recent Returns</h3>
          {loading ? <p>Loading returns...</p> : null}
          {!loading && items.length === 0 ? <div className="sales-empty"><h4>No returns yet</h4><p>Create a return against a sale to restore stock and adjust finance truthfully.</p></div> : null}
          {!loading && items.length > 0 ? <table className="sales-table"><thead><tr><th>Return #</th><th>Sale #</th><th>Customer</th><th>Total</th></tr></thead><tbody>
            {items.map((row) => <tr key={row.return_id} onClick={() => openReturn(row.return_id)}><td>{row.return_no}</td><td>{row.sale_no}</td><td>{row.customer_name || 'Unknown'}</td><td>{row.return_total.toFixed(2)}</td></tr>)}
          </tbody></table> : null}
        </div>

        <aside className="sales-panel">
          <h3>Create Return</h3>
          <label>Sale
            <select aria-label="Sale" value={saleId} onChange={(e) => selectSale(e.target.value)}>
              <option value="">Select sale</option>
              {sales.map((sale) => <option key={sale.sale_id} value={sale.sale_id}>{sale.sale_no} — {sale.customer_name}</option>)}
            </select>
          </label>
          <label>Return reason<input aria-label="Return reason" value={reason} onChange={(e) => setReason(e.target.value)} /></label>
          <label>Note<textarea aria-label="Return note" value={note} onChange={(e) => setNote(e.target.value)} /></label>
          {selectedSale ? <div>
            {selectedSale.lines.map((line) => (
              <div key={line.sale_item_id} className="sale-line-row">
                <div><strong>{line.product_name}</strong><br />Sold: {line.sold_qty} | Eligible: {line.eligible_qty}</div>
                <input aria-label={`Return qty ${line.sale_item_id}`} type="number" min={0} max={line.eligible_qty} step="0.01" value={lines.find((item) => item.sale_item_id === line.sale_item_id)?.qty ?? 0} onChange={(e) => updateLine(line.sale_item_id, { qty: Number(e.target.value || 0) })} />
                <input aria-label={`Line reason ${line.sale_item_id}`} placeholder="Line reason" value={lines.find((item) => item.sale_item_id === line.sale_item_id)?.reason ?? reason} onChange={(e) => updateLine(line.sale_item_id, { reason: e.target.value })} />
                <input aria-label={`Condition ${line.sale_item_id}`} placeholder="Condition (optional)" value={lines.find((item) => item.sale_item_id === line.sale_item_id)?.condition_status ?? ''} onChange={(e) => updateLine(line.sale_item_id, { condition_status: e.target.value })} />
              </div>
            ))}
            <p><strong>Return Total:</strong> {total.toFixed(2)}</p>
            {lineError ? <p className="sales-error">{lineError}</p> : null}
          </div> : null}
          <button type="button" disabled={saving || !selectedSale || !!lineError || selectedLines.length === 0} onClick={submit}>{saving ? 'Saving...' : 'Submit Return'}</button>
        </aside>
      </div>

      {selectedReturn ? <div className="sales-panel"><h3>Return Detail: {selectedReturn.return_no}</h3><p>Sale: {selectedReturn.sale_no} | Customer: {selectedReturn.customer_name}</p><p>Reason: {selectedReturn.reason}</p><table className="sales-table"><thead><tr><th>Product</th><th>Qty</th><th>Reason</th><th>Condition</th><th>Total</th></tr></thead><tbody>{selectedReturn.lines.map((line) => <tr key={line.return_item_id}><td>{line.product_name}</td><td>{line.return_qty}</td><td>{line.reason}</td><td>{line.condition_status || '-'}</td><td>{line.line_total.toFixed(2)}</td></tr>)}</tbody></table></div> : null}
    </section>
  );
}
