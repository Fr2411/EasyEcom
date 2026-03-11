'use client';

import { useEffect, useMemo, useState } from 'react';
import { createInboundStock, createInventoryAdjustment, getInventoryDetail, getInventoryItems, getInventoryMovements, receiveInboundStock } from '@/lib/api/inventory';
import type { InventoryItem, InventoryMovement } from '@/types/inventory';

type AdjustmentType = 'stock_in' | 'stock_out' | 'correction';

const toFiniteNumber = (value: unknown): number => {
  const parsed = typeof value === 'number' ? value : Number(value);
  return Number.isFinite(parsed) ? parsed : 0;
};

const fmtQty = (value: unknown): string => toFiniteNumber(value).toFixed(2);

const fmtMoney = (value: unknown): string => toFiniteNumber(value).toFixed(2);

export function InventoryWorkspace() {
  const [items, setItems] = useState<InventoryItem[]>([]);
  const [movements, setMovements] = useState<InventoryMovement[]>([]);
  const [selectedItemId, setSelectedItemId] = useState('');
  const [selectedMovementType, setSelectedMovementType] = useState('');
  const [startDate, setStartDate] = useState('');
  const [endDate, setEndDate] = useState('');
  const [query, setQuery] = useState('');

  const [inventoryView, setInventoryView] = useState<'catalog' | 'stocked'>('catalog');
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [adjustType, setAdjustType] = useState<AdjustmentType>('stock_in');
  const [adjustItemId, setAdjustItemId] = useState('');
  const [quantity, setQuantity] = useState(1);
  const [quantityDelta, setQuantityDelta] = useState(1);
  const [unitCost, setUnitCost] = useState(0);
  const [reason, setReason] = useState('');
  const [note, setNote] = useState('');
  const [reference, setReference] = useState('');
  const [inboundItemId, setInboundItemId] = useState('');
  const [inboundQty, setInboundQty] = useState(1);
  const [inboundCost, setInboundCost] = useState(0);
  const [inboundRef, setInboundRef] = useState('');
  const [inboundIdToReceive, setInboundIdToReceive] = useState('');
  const [receiveQty, setReceiveQty] = useState(0);
  const [receiveCost, setReceiveCost] = useState(0);

  const [detailItem, setDetailItem] = useState<InventoryItem | null>(null);
  const [detailMovements, setDetailMovements] = useState<InventoryMovement[]>([]);

  const load = async (q = query) => {
    try {
      setLoading(true);
      setError(null);
      const [itemsRes, movementRes] = await Promise.all([
        getInventoryItems(q),
        getInventoryMovements({ item_id: selectedItemId || undefined, movement_type: selectedMovementType || undefined, start_date: startDate || undefined, end_date: endDate || undefined, limit: 100 }),
      ]);
      setItems(itemsRes.items);
      setMovements(movementRes.items);
      if (!adjustItemId && itemsRes.items.length > 0) {
        setAdjustItemId(itemsRes.items[0].item_id);
      }
      if (!inboundItemId && itemsRes.items.length > 0) {
        setInboundItemId(itemsRes.items[0].item_id);
      }
    } catch {
      setError('Unable to load inventory module right now.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { load(''); }, []);

  const openDetail = async (itemId: string) => {
    try {
      const detail = await getInventoryDetail(itemId);
      setDetailItem(detail.item);
      setDetailMovements(detail.recent_movements);
    } catch {
      setError('Unable to load inventory detail.');
    }
  };

  const createInbound = async () => {
    if (!inboundItemId) return;
    try {
      setSaving(true);
      setError(null);
      await createInboundStock({ item_id: inboundItemId, quantity: inboundQty, expected_unit_cost: inboundCost, reference: inboundRef });
      setInboundRef('');
      await load(query);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Inbound creation failed.');
    } finally {
      setSaving(false);
    }
  };

  const markInboundReceived = async () => {
    if (!inboundIdToReceive) return;
    try {
      setSaving(true);
      setError(null);
      await receiveInboundStock(inboundIdToReceive, { quantity: receiveQty || undefined, unit_cost: receiveCost || undefined });
      setInboundIdToReceive('');
      setReceiveQty(0);
      await load(query);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Inbound receipt failed.');
    } finally {
      setSaving(false);
    }
  };


  const visibleItems = useMemo(() => (
    inventoryView === 'stocked'
      ? items.filter((item) => toFiniteNumber(item.on_hand_qty) > 0 || toFiniteNumber(item.incoming_qty) > 0)
      : items
  ), [inventoryView, items]);

  const submitAdjustment = async () => {
    if (!adjustItemId) return;
    try {
      setSaving(true);
      setError(null);
      await createInventoryAdjustment({
        item_id: adjustItemId,
        adjustment_type: adjustType,
        quantity: adjustType === 'correction' ? undefined : quantity,
        quantity_delta: adjustType === 'correction' ? quantityDelta : undefined,
        unit_cost: adjustType === 'stock_out' ? undefined : unitCost || undefined,
        reason,
        note,
        reference,
      });
      setReason(''); setNote(''); setReference('');
      await load(query);
      if (detailItem) await openDetail(detailItem.item_id);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Adjustment failed.');
    } finally {
      setSaving(false);
    }
  };

  return (
    <section className="inventory-module">
      <div className="inventory-toolbar">
        <input aria-label="Search inventory" placeholder="Search SKU, variant, product" value={query} onChange={(e) => setQuery(e.target.value)} />
        <button type="button" onClick={() => load(query)}>Search</button>
        <select aria-label="Inventory view mode" value={inventoryView} onChange={(e) => setInventoryView(e.target.value as 'catalog' | 'stocked')}>
          <option value="catalog">Catalog view (all active items)</option>
          <option value="stocked">Stocked only (on hand/incoming &gt; 0)</option>
        </select>
        <select aria-label="Filter item" value={selectedItemId} onChange={(e) => setSelectedItemId(e.target.value)}>
          <option value="">All items</option>
          {items.map((item) => <option key={item.item_id} value={item.item_id}>{item.item_name}</option>)}
        </select>
        <select aria-label="Filter movement type" value={selectedMovementType} onChange={(e) => setSelectedMovementType(e.target.value)}>
          <option value="">All movements</option>
          <option value="IN">IN</option>
          <option value="OUT">OUT</option>
          <option value="ADJUST">ADJUST</option>
          <option value="ADJUST+">ADJUST+</option>
          <option value="INBOUND_PENDING">INBOUND_PENDING</option>
          <option value="INBOUND_RECEIVED">INBOUND_RECEIVED</option>
        </select>
        <input aria-label="Start date" type="date" value={startDate} onChange={(e) => setStartDate(e.target.value)} />
        <input aria-label="End date" type="date" value={endDate} onChange={(e) => setEndDate(e.target.value)} />
        <button type="button" onClick={() => load(query)}>Apply Filters</button>
      </div>

      {error ? <p className="inventory-error">{error}</p> : null}
      {loading ? <p className="inventory-loading">Loading inventory…</p> : null}

      {!loading && items.length === 0 ? <div className="inventory-empty"><h3>No inventory yet</h3><p>Add stock from Products & Stock or use manual adjustments to start your ledger.</p></div> : null}

      <div className="inventory-grid">
        <div className="inventory-panel">
          <h3>Current Stock</h3>
          {!loading && visibleItems.length > 0 ? <table className="inventory-table"><thead><tr><th>Item</th><th>Parent Product</th><th>On Hand</th><th>Incoming</th><th>Sellable</th><th>Avg Cost</th><th>Value</th><th>Low stock</th></tr></thead><tbody>
            {visibleItems.map((item) => (
              <tr key={item.item_id} onClick={() => openDetail(item.item_id)}>
                <td><strong>{item.item_name}</strong><br /><span>{item.item_id}</span></td>
                <td>{item.parent_product_name || '—'}</td>
                <td>{fmtQty(item.on_hand_qty)}</td>
                <td>{fmtQty(item.incoming_qty)}</td>
                <td>{fmtQty(item.sellable_qty)}</td>
                <td>{fmtMoney(item.avg_unit_cost)}</td>
                <td>{fmtMoney(item.stock_value)}</td>
                <td>{item.low_stock ? <span className="inv-badge-low">Low</span> : '—'}</td>
              </tr>
            ))}
          </tbody></table> : null}
        </div>

        <aside className="inventory-panel">
          <h3>Adjust Stock</h3>
          <label>Item<select value={adjustItemId} onChange={(e) => setAdjustItemId(e.target.value)}>
            <option value="">Select item</option>
            {items.map((item) => <option key={item.item_id} value={item.item_id}>{item.item_name}</option>)}
          </select></label>
          <label>Adjustment type<select value={adjustType} onChange={(e) => setAdjustType(e.target.value as AdjustmentType)}>
            <option value="stock_in">Stock In</option>
            <option value="stock_out">Stock Out</option>
            <option value="correction">Correction</option>
          </select></label>
          {adjustType !== 'correction' ? <label>Quantity<input type="number" min={0.01} step="0.01" value={quantity} onChange={(e) => setQuantity(Number(e.target.value || 0))} /></label> : null}
          {adjustType === 'correction' ? <label>Quantity Delta (+/-)<input type="number" step="0.01" value={quantityDelta} onChange={(e) => setQuantityDelta(Number(e.target.value || 0))} /></label> : null}
          {adjustType !== 'stock_out' ? <label>Unit Cost<input type="number" min={0} step="0.01" value={unitCost} onChange={(e) => setUnitCost(Number(e.target.value || 0))} /></label> : null}
          <label>Reason<input value={reason} onChange={(e) => setReason(e.target.value)} /></label>
          <label>Reference<input value={reference} onChange={(e) => setReference(e.target.value)} /></label>
          <label>Note<textarea value={note} onChange={(e) => setNote(e.target.value)} /></label>
          <button type="button" onClick={submitAdjustment} disabled={saving}>{saving ? 'Applying...' : 'Apply Adjustment'}</button>
        </aside>
        <aside className="inventory-panel">
          <h3>Inbound Workflow</h3>
          <label>Item<select value={inboundItemId} onChange={(e) => setInboundItemId(e.target.value)}>
            <option value="">Select item</option>
            {items.map((item) => <option key={item.item_id} value={item.item_id}>{item.item_name}</option>)}
          </select></label>
          <label>Incoming Qty<input type="number" min={0.01} step="0.01" value={inboundQty} onChange={(e) => setInboundQty(Number(e.target.value || 0))} /></label>
          <label>Expected Unit Cost<input type="number" min={0.01} step="0.01" value={inboundCost} onChange={(e) => setInboundCost(Number(e.target.value || 0))} /></label>
          <label>Reference<input value={inboundRef} onChange={(e) => setInboundRef(e.target.value)} /></label>
          <button type="button" onClick={createInbound} disabled={saving}>{saving ? 'Saving...' : 'Create Incoming'}</button>
          <hr />
          <label>Inbound ID<input value={inboundIdToReceive} onChange={(e) => setInboundIdToReceive(e.target.value)} placeholder="INB-YYYY-00001" /></label>
          <label>Receive Qty (optional full by default)<input type="number" min={0} step="0.01" value={receiveQty} onChange={(e) => setReceiveQty(Number(e.target.value || 0))} /></label>
          <label>Receive Unit Cost (optional)<input type="number" min={0} step="0.01" value={receiveCost} onChange={(e) => setReceiveCost(Number(e.target.value || 0))} /></label>
          <button type="button" onClick={markInboundReceived} disabled={saving}>{saving ? 'Saving...' : 'Mark Received'}</button>
        </aside>

      </div>

      <div className="inventory-panel">
        <h3>Stock Movement Ledger</h3>
        {!loading && movements.length === 0 ? <p>No stock movements for selected filter.</p> : null}
        {!loading && movements.length > 0 ? <table className="inventory-table"><thead><tr><th>Date/Time</th><th>Item</th><th>Type</th><th>Qty Δ</th><th>Source</th><th>Balance</th></tr></thead><tbody>
          {movements.map((movement) => (
            <tr key={movement.txn_id}>
              <td>{movement.timestamp}</td>
              <td>{movement.item_name}</td>
              <td>{movement.movement_type}</td>
              <td className={toFiniteNumber(movement.qty_delta) >= 0 ? 'delta-positive' : 'delta-negative'}>{toFiniteNumber(movement.qty_delta) >= 0 ? '+' : ''}{fmtQty(movement.qty_delta)}</td>
              <td>{movement.source_type || 'manual'} {movement.source_id ? `· ${movement.source_id}` : ''}</td>
              <td>{movement.resulting_balance == null ? '—' : fmtQty(movement.resulting_balance)}</td>
            </tr>
          ))}
        </tbody></table> : null}
      </div>

      {detailItem ? <div className="inventory-panel"><h3>Inventory Detail · {detailItem.item_name}</h3><p>On-hand: <strong>{fmtQty(detailItem.on_hand_qty)}</strong> · Incoming: <strong>{fmtQty(detailItem.incoming_qty)}</strong> · Sellable: <strong>{fmtQty(detailItem.sellable_qty)}</strong> · Value: <strong>{fmtMoney(detailItem.stock_value)}</strong></p><ul>{detailMovements.map((movement) => <li key={movement.txn_id}>{movement.timestamp} · {movement.movement_type} · {toFiniteNumber(movement.qty_delta) >= 0 ? '+' : ''}{fmtQty(movement.qty_delta)} · {movement.note || movement.source_type}</li>)}</ul></div> : null}
    </section>
  );
}
