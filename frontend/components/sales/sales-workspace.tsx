'use client';

import { useEffect, useMemo, useState } from 'react';
import { createSale, getSaleDetail, getSales, getSalesFormOptions } from '@/lib/api/sales';
import type { SaleDetail, SaleLookupCustomer, SaleLookupProduct } from '@/types/sales';

type DraftLine = { product_id: string; qty: number; unit_price: number };

export function SalesWorkspace() {
  const [sales, setSales] = useState<SaleDetail[]>([]);
  const [selectedSale, setSelectedSale] = useState<SaleDetail | null>(null);
  const [customers, setCustomers] = useState<SaleLookupCustomer[]>([]);
  const [products, setProducts] = useState<SaleLookupProduct[]>([]);
  const [query, setQuery] = useState('');
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [customerId, setCustomerId] = useState('');
  const [discount, setDiscount] = useState(0);
  const [tax, setTax] = useState(0);
  const [note, setNote] = useState('');
  const [lines, setLines] = useState<DraftLine[]>([{ product_id: '', qty: 1, unit_price: 0 }]);

  const load = async (q = query) => {
    try {
      setLoading(true);
      setError(null);
      const [salesRes, options] = await Promise.all([getSales(q), getSalesFormOptions('')]);
      setSales(salesRes.items.map((item) => ({ ...item, lines: [], note: '' })) as SaleDetail[]);
      setCustomers(options.customers);
      setProducts(options.products);
    } catch {
      setError('Unable to load sales workspace.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { load(''); }, []);

  const subtotal = useMemo(() => lines.reduce((sum, line) => sum + line.qty * line.unit_price, 0), [lines]);
  const total = useMemo(() => Math.max(0, subtotal - discount + tax), [subtotal, discount, tax]);

  const addLine = () => setLines((prev) => [...prev, { product_id: '', qty: 1, unit_price: 0 }]);

  const updateLine = (idx: number, patch: Partial<DraftLine>) => {
    setLines((prev) => prev.map((line, i) => (i === idx ? { ...line, ...patch } : line)));
  };

  const submitSale = async () => {
    if (!customerId || lines.some((l) => !l.product_id || l.qty <= 0)) return;
    try {
      setSaving(true);
      setError(null);
      await createSale({ customer_id: customerId, lines, discount, tax, note });
      setLines([{ product_id: '', qty: 1, unit_price: 0 }]);
      setDiscount(0); setTax(0); setNote('');
      await load(query);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unable to create sale.');
    } finally {
      setSaving(false);
    }
  };

  const openDetail = async (saleId: string) => {
    try {
      const detail = await getSaleDetail(saleId);
      setSelectedSale(detail);
    } catch {
      setError('Unable to load sale detail.');
    }
  };

  return (
    <section className="sales-module">
      <div className="sales-toolbar">
        <input aria-label="Search sales" placeholder="Search by sale no, customer, date" value={query} onChange={(e) => setQuery(e.target.value)} />
        <button onClick={() => load(query)} type="button">Search</button>
      </div>
      {error ? <p className="sales-error">{error}</p> : null}
      <div className="sales-grid">
        <div className="sales-panel">
          <h3>Recent Sales</h3>
          {loading ? <p>Loading sales...</p> : null}
          {!loading && sales.length === 0 ? <div className="sales-empty"><h4>No sales yet</h4><p>Create your first sale transaction to begin order operations.</p></div> : null}
          {!loading && sales.length > 0 ? <table className="sales-table"><thead><tr><th>Sale #</th><th>Customer</th><th>Date</th><th>Total</th></tr></thead><tbody>
            {sales.map((sale) => <tr key={sale.sale_id} onClick={() => openDetail(sale.sale_id)}><td>{sale.sale_no}</td><td>{sale.customer_name || 'Walk-in'}</td><td>{sale.timestamp}</td><td>{sale.total.toFixed(2)}</td></tr>)}
          </tbody></table> : null}
        </div>

        <aside className="sales-panel">
          <h3>Create Sale</h3>
          <label>Customer
            <select value={customerId} onChange={(e) => setCustomerId(e.target.value)}>
              <option value="">Select customer</option>
              {customers.map((customer) => <option key={customer.customer_id} value={customer.customer_id}>{customer.full_name}</option>)}
            </select>
          </label>
          {lines.map((line, idx) => (
            <div key={idx} className="sale-line-row">
              <select value={line.product_id} onChange={(e) => {
                const picked = products.find((item) => item.product_id === e.target.value);
                updateLine(idx, { product_id: e.target.value, unit_price: picked?.default_unit_price ?? line.unit_price });
              }}>
                <option value="">Select product/variant</option>
                {products.map((product) => <option key={product.product_id} value={product.product_id}>{product.label} (Stock: {product.available_qty})</option>)}
              </select>
              <input aria-label={`Quantity ${idx + 1}`} type="number" min={1} value={line.qty} onChange={(e) => updateLine(idx, { qty: Number(e.target.value || 0) })} />
              <input aria-label={`Unit price ${idx + 1}`} type="number" min={0} step="0.01" value={line.unit_price} onChange={(e) => updateLine(idx, { unit_price: Number(e.target.value || 0) })} />
              <strong>{(line.qty * line.unit_price).toFixed(2)}</strong>
            </div>
          ))}
          <button type="button" onClick={addLine}>Add line</button>
          <label>Discount<input type="number" min={0} step="0.01" value={discount} onChange={(e) => setDiscount(Number(e.target.value || 0))} /></label>
          <label>Tax<input type="number" min={0} step="0.01" value={tax} onChange={(e) => setTax(Number(e.target.value || 0))} /></label>
          <label>Note<textarea value={note} onChange={(e) => setNote(e.target.value)} /></label>
          <div className="sales-total-card"><p>Subtotal: {subtotal.toFixed(2)}</p><p>Total: {total.toFixed(2)}</p></div>
          <button type="button" onClick={submitSale} disabled={saving}>{saving ? 'Submitting...' : 'Submit Sale'}</button>
        </aside>
      </div>
      {selectedSale ? <section className="sales-panel"><h3>Sale Detail · {selectedSale.sale_no}</h3><p>{selectedSale.customer_name}</p><ul>{selectedSale.lines.map((line) => <li key={line.line_id}>{line.product_name} · {line.qty} × {line.unit_price} = {line.line_total}</li>)}</ul></section> : null}
    </section>
  );
}
