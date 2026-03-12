'use client';

import { useEffect, useMemo, useState } from 'react';
import { createPurchase, getPurchaseDetail, getPurchaseFormOptions, getPurchases } from '@/lib/api/purchases';
import type { PurchaseDetail, PurchaseLookupProduct, PurchaseLookupSupplier } from '@/types/purchases';

type DraftLine = { variant_id: string; qty: number; unit_cost: number };

function todayIso(): string {
  return new Date().toISOString().slice(0, 10);
}

export function PurchasesWorkspace() {
  const [purchases, setPurchases] = useState<PurchaseDetail[]>([]);
  const [selectedPurchase, setSelectedPurchase] = useState<PurchaseDetail | null>(null);
  const [products, setProducts] = useState<PurchaseLookupProduct[]>([]);
  const [suppliers, setSuppliers] = useState<PurchaseLookupSupplier[]>([]);
  const [query, setQuery] = useState('');
  const [productQuery, setProductQuery] = useState('');
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [purchaseDate, setPurchaseDate] = useState(todayIso());
  const [supplierId, setSupplierId] = useState('');
  const [referenceNo, setReferenceNo] = useState('');
  const [paymentStatus, setPaymentStatus] = useState<'paid' | 'unpaid' | 'partial'>('unpaid');
  const [note, setNote] = useState('');
  const [lines, setLines] = useState<DraftLine[]>([{ variant_id: '', qty: 1, unit_cost: 0 }]);

  const load = async (q = query) => {
    try {
      setLoading(true);
      setError(null);
      const [purchasesRes, options] = await Promise.all([getPurchases(q), getPurchaseFormOptions(productQuery)]);
      setPurchases(purchasesRes.items.map((item) => ({ ...item, lines: [], note: '', created_by_user_id: '' })) as PurchaseDetail[]);
      setProducts(options.products);
      setSuppliers(options.suppliers);
    } catch {
      setError('Unable to load purchases workspace.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void load('');
  }, [productQuery]);

  const subtotal = useMemo(() => lines.reduce((sum, line) => sum + line.qty * line.unit_cost, 0), [lines]);

  const addLine = () => setLines((prev) => [...prev, { variant_id: '', qty: 1, unit_cost: 0 }]);
  const updateLine = (idx: number, patch: Partial<DraftLine>) => {
    setLines((prev) => prev.map((line, i) => (i === idx ? { ...line, ...patch } : line)));
  };

  const submitPurchase = async () => {
    if (!purchaseDate || lines.some((line) => !line.variant_id || line.qty <= 0 || line.unit_cost < 0)) return;
    try {
      setSaving(true);
      setError(null);
      await createPurchase({ purchase_date: purchaseDate, supplier_id: supplierId, reference_no: referenceNo, payment_status: paymentStatus, note, lines });
      setPurchaseDate(todayIso());
      setSupplierId('');
      setReferenceNo('');
      setPaymentStatus('unpaid');
      setNote('');
      setLines([{ variant_id: '', qty: 1, unit_cost: 0 }]);
      await load(query);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unable to create purchase.');
    } finally {
      setSaving(false);
    }
  };

  const openDetail = async (purchaseId: string) => {
    try {
      const detail = await getPurchaseDetail(purchaseId);
      setSelectedPurchase(detail);
    } catch {
      setError('Unable to load purchase detail.');
    }
  };

  return (
    <section className="sales-module">
      <div className="sales-toolbar">
        <input aria-label="Search purchases" placeholder="Search by purchase no, supplier, date, reference" value={query} onChange={(e) => setQuery(e.target.value)} />
        <button onClick={() => load(query)} type="button">Search</button>
      </div>
      {error ? <p className="sales-error">{error}</p> : null}
      <div className="sales-grid">
        <div className="sales-panel">
          <h3>Recent Purchases</h3>
          {loading ? <p>Loading purchases...</p> : null}
          {!loading && purchases.length === 0 ? <div className="sales-empty"><h4>No purchases yet</h4><p>Create your first stock-in purchase to increase inventory on-hand.</p></div> : null}
          {!loading && purchases.length > 0 ? <table className="sales-table"><thead><tr><th>Purchase #</th><th>Date</th><th>Supplier</th><th>Total</th></tr></thead><tbody>
            {purchases.map((purchase) => <tr key={purchase.purchase_id} onClick={() => openDetail(purchase.purchase_id)}><td>{purchase.purchase_no}</td><td>{purchase.purchase_date}</td><td>{purchase.supplier_name || '—'}</td><td>{purchase.subtotal.toFixed(2)}</td></tr>)}
          </tbody></table> : null}
        </div>

        <aside className="sales-panel">
          <h3>Create Purchase / Stock-In</h3>
          <label>Purchase date
            <input type="date" value={purchaseDate} onChange={(e) => setPurchaseDate(e.target.value)} />
          </label>
          <label>Supplier
            <select value={supplierId} onChange={(e) => setSupplierId(e.target.value)}>
              <option value="">Select supplier (optional)</option>
              {suppliers.map((supplier) => <option key={supplier.supplier_id} value={supplier.supplier_id}>{supplier.name}</option>)}
            </select>
          </label>
          <label>Reference no
            <input value={referenceNo} onChange={(e) => setReferenceNo(e.target.value)} placeholder="Invoice/PO reference" />
          </label>
          <label>Search variant (SKU/barcode/name)
            <input value={productQuery} onChange={(e) => setProductQuery(e.target.value)} placeholder="Type SKU, barcode, product, variant" />
          </label>
          <label>Payment status
            <select value={paymentStatus} onChange={(e) => setPaymentStatus(e.target.value as 'paid' | 'unpaid' | 'partial')}>
              <option value="unpaid">Unpaid</option>
              <option value="partial">Partial</option>
              <option value="paid">Paid</option>
            </select>
          </label>
          {lines.map((line, idx) => (
            <div key={idx} className="sale-line-row">
              <select value={line.variant_id} onChange={(e) => updateLine(idx, { variant_id: e.target.value })}>
                <option value="">Select product/variant</option>
                {products.map((product) => <option key={product.variant_id} value={product.variant_id}>{product.label} (Stock: {product.current_stock})</option>)}
              </select>
              <input aria-label={`Purchase quantity ${idx + 1}`} type="number" min={1} value={line.qty} onChange={(e) => updateLine(idx, { qty: Number(e.target.value || 0) })} />
              <input aria-label={`Unit cost ${idx + 1}`} type="number" min={0} step="0.01" value={line.unit_cost} onChange={(e) => updateLine(idx, { unit_cost: Number(e.target.value || 0) })} />
              <strong>{(line.qty * line.unit_cost).toFixed(2)}</strong>
            </div>
          ))}
          <button type="button" onClick={addLine}>Add line</button>
          <label>Note<textarea value={note} onChange={(e) => setNote(e.target.value)} /></label>
          <div className="sales-total-card"><p>Purchase Total: {subtotal.toFixed(2)}</p><p>Stock impact: +{lines.reduce((sum, line) => sum + Math.max(0, line.qty), 0)} units</p></div>
          <button type="button" onClick={submitPurchase} disabled={saving}>{saving ? 'Submitting...' : 'Submit Purchase'}</button>
        </aside>
      </div>
      {selectedPurchase ? <section className="sales-panel"><h3>Purchase Detail · {selectedPurchase.purchase_no}</h3><p>Supplier: {selectedPurchase.supplier_name || '—'} · Date: {selectedPurchase.purchase_date}</p><p>Reference: {selectedPurchase.reference_no || '—'}</p><ul>{selectedPurchase.lines.map((line) => <li key={line.line_id}>{line.product_name} · {line.qty} × {line.unit_cost} = {line.line_total}</li>)}</ul><p><strong>Total:</strong> {selectedPurchase.subtotal.toFixed(2)}</p></section> : null}
    </section>
  );
}
