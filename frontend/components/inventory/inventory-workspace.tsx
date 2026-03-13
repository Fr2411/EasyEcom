'use client';

import { useEffect, useMemo, useState } from 'react';
import { getCatalogProducts } from '@/lib/api/catalog';
import {
  createInventoryAdjustment,
  createOpeningStock,
  getInventoryDetail,
  getInventoryItems,
  getInventoryMovements,
} from '@/lib/api/inventory';
import type { CatalogProductRecord } from '@/types/catalog';
import type { InventoryItem, InventoryMovement } from '@/types/inventory';

type AdjustmentType = 'stock_in' | 'stock_out' | 'correction';

type OpeningStockLineDraft = {
  tempId: string;
  variant_id: string;
  qty: number;
  unit_cost: number;
  reference: string;
  note: string;
};

const createOpeningLine = (variantId = '', defaultUnitCost = 0): OpeningStockLineDraft => ({
  tempId: crypto.randomUUID(),
  variant_id: variantId,
  qty: 1,
  unit_cost: defaultUnitCost,
  reference: '',
  note: '',
});

const toFiniteNumber = (value: unknown): number => {
  const parsed = typeof value === 'number' ? value : Number(value);
  return Number.isFinite(parsed) ? parsed : 0;
};

const fmtQty = (value: unknown): string => toFiniteNumber(value).toFixed(2);
const fmtMoney = (value: unknown): string => toFiniteNumber(value).toFixed(2);

function toErrorMessage(error: unknown, fallback: string): string {
  if (!(error instanceof Error)) return fallback;
  if (!error.message.trim()) return fallback;
  try {
    const parsed = JSON.parse(error.message) as { detail?: string; message?: string };
    return parsed.detail || parsed.message || error.message;
  } catch {
    return error.message;
  }
}

function availabilityLabel(status: InventoryItem['availability_status']): string {
  switch (status) {
    case 'in_stock':
      return 'In stock';
    case 'incoming':
      return 'Incoming';
    case 'low_stock':
      return 'Low stock';
    case 'out_of_stock':
      return 'Out of stock';
    default:
      return 'Unmapped';
  }
}

function findVariantDefaultCost(product: CatalogProductRecord | null, variantId: string): number {
  if (!product || !variantId) return 0;
  return (
    product.variants.find((variant) => variant.variant_id === variantId)?.defaultPurchasePrice ?? 0
  );
}

export function InventoryWorkspace() {
  const [items, setItems] = useState<InventoryItem[]>([]);
  const [allItems, setAllItems] = useState<InventoryItem[]>([]);
  const [movements, setMovements] = useState<InventoryMovement[]>([]);
  const [catalogProducts, setCatalogProducts] = useState<CatalogProductRecord[]>([]);
  const [selectedItemId, setSelectedItemId] = useState('');
  const [selectedMovementType, setSelectedMovementType] = useState('');
  const [startDate, setStartDate] = useState('');
  const [endDate, setEndDate] = useState('');
  const [query, setQuery] = useState('');

  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState<'adjustment' | 'opening' | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);

  const [adjustType, setAdjustType] = useState<AdjustmentType>('stock_in');
  const [adjustItemId, setAdjustItemId] = useState('');
  const [quantity, setQuantity] = useState(1);
  const [quantityDelta, setQuantityDelta] = useState(1);
  const [unitCost, setUnitCost] = useState(0);
  const [reason, setReason] = useState('');
  const [note, setNote] = useState('');
  const [reference, setReference] = useState('');

  const [openingProductId, setOpeningProductId] = useState('');
  const [openingLines, setOpeningLines] = useState<OpeningStockLineDraft[]>([]);

  const [detailItem, setDetailItem] = useState<InventoryItem | null>(null);
  const [detailMovements, setDetailMovements] = useState<InventoryMovement[]>([]);

  const actionableItems = useMemo(
    () => allItems.filter((item) => item.item_type === 'variant' && item.actionable),
    [allItems],
  );

  const openingProduct = useMemo(
    () => catalogProducts.find((product) => product.product_id === openingProductId) ?? null,
    [catalogProducts, openingProductId],
  );

  const loadCatalog = async () => {
    const snapshot = await getCatalogProducts();
    setCatalogProducts(snapshot.products);
  };

  const loadInventory = async (q = query) => {
    try {
      setLoading(true);
      setError(null);
      const [filteredItemsRes, allItemsRes, movementRes] = await Promise.all([
        getInventoryItems(q),
        q.trim() ? getInventoryItems('') : Promise.resolve<{ items: InventoryItem[] }>({ items }),
        getInventoryMovements({
          item_id: selectedItemId || undefined,
          movement_type: selectedMovementType || undefined,
          start_date: startDate || undefined,
          end_date: endDate || undefined,
          limit: 100,
        }),
      ]);
      const inventoryItems = filteredItemsRes.items;
      const baselineItems = q.trim() ? allItemsRes.items : inventoryItems;
      setItems(inventoryItems);
      setAllItems(baselineItems);
      setMovements(movementRes.items);
      const actionableIds = new Set(
        baselineItems
          .filter((item) => item.item_type === 'variant' && item.actionable)
          .map((item) => item.item_id),
      );
      if (!adjustItemId || !actionableIds.has(adjustItemId)) {
        const firstActionable = baselineItems.find(
          (item) => item.item_type === 'variant' && item.actionable,
        );
        setAdjustItemId(firstActionable?.item_id ?? '');
      }
    } catch (loadError) {
      setError(toErrorMessage(loadError, 'Unable to load inventory right now.'));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    Promise.all([loadInventory(''), loadCatalog()]).catch((loadError) => {
      setError(toErrorMessage(loadError, 'Unable to load inventory workspace right now.'));
      setLoading(false);
    });
  }, []);

  useEffect(() => {
    if (!openingProductId && catalogProducts.length > 0) {
      setOpeningProductId(catalogProducts[0].product_id);
    }
  }, [catalogProducts, openingProductId]);

  useEffect(() => {
    if (!openingProduct) {
      setOpeningLines([]);
      return;
    }
    setOpeningLines((current) => {
      const validVariantIds = new Set(
        openingProduct.variants
          .map((variant) => variant.variant_id)
          .filter((variantId): variantId is string => Boolean(variantId)),
      );
      const filtered = current.filter((line) => validVariantIds.has(line.variant_id));
      if (filtered.length > 0) {
        return filtered;
      }
      const firstVariantId = openingProduct.variants[0]?.variant_id ?? '';
      return firstVariantId
        ? [createOpeningLine(firstVariantId, findVariantDefaultCost(openingProduct, firstVariantId))]
        : [];
    });
  }, [openingProduct]);

  const openDetail = async (itemId: string) => {
    try {
      const detail = await getInventoryDetail(itemId);
      setDetailItem(detail.item);
      setDetailMovements(detail.recent_movements);
    } catch (detailError) {
      setError(toErrorMessage(detailError, 'Unable to load inventory detail.'));
    }
  };

  const submitAdjustment = async () => {
    if (!adjustItemId) return;
    try {
      setSubmitting('adjustment');
      setError(null);
      setMessage(null);
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
      setReason('');
      setNote('');
      setReference('');
      setMessage('Inventory adjustment posted successfully.');
      await loadInventory(query);
      if (detailItem) await openDetail(detailItem.item_id);
    } catch (submitError) {
      setError(toErrorMessage(submitError, 'Adjustment failed.'));
    } finally {
      setSubmitting(null);
    }
  };

  const submitOpeningStock = async () => {
    if (!openingProduct) {
      setError('Select a product before recording opening stock.');
      return;
    }
    if (openingLines.length === 0) {
      setError('Add at least one opening stock line.');
      return;
    }
    if (openingLines.some((line) => !line.variant_id || line.qty <= 0 || line.unit_cost <= 0)) {
      setError('Each opening stock line must include a variant, quantity, and unit cost.');
      return;
    }

    try {
      setSubmitting('opening');
      setError(null);
      setMessage(null);
      const response = await createOpeningStock({
        product_id: openingProduct.product_id,
        lines: openingLines.map((line) => ({
          variant_id: line.variant_id,
          qty: line.qty,
          unit_cost: line.unit_cost,
          reference: line.reference,
          note: line.note,
        })),
      });
      setMessage(`Opening stock recorded into ${response.lot_ids.length} lot(s).`);
      const firstVariantId = openingProduct.variants[0]?.variant_id ?? '';
      setOpeningLines(
        firstVariantId
          ? [createOpeningLine(firstVariantId, findVariantDefaultCost(openingProduct, firstVariantId))]
          : [],
      );
      await loadInventory(query);
    } catch (submitError) {
      setError(toErrorMessage(submitError, 'Opening stock failed.'));
    } finally {
      setSubmitting(null);
    }
  };

  return (
    <section className="inventory-module">
      <div className="inventory-toolbar">
        <input
          aria-label="Search inventory"
          placeholder="Search SKU, variant, or product"
          value={query}
          onChange={(event) => setQuery(event.target.value)}
        />
        <button type="button" onClick={() => loadInventory(query)}>Search</button>
        <select
          aria-label="Filter movement type"
          value={selectedMovementType}
          onChange={(event) => setSelectedMovementType(event.target.value)}
        >
          <option value="">All movements</option>
          <option value="IN">Inbound</option>
          <option value="OUT">Outbound</option>
          <option value="INBOUND_PENDING">Incoming planned</option>
          <option value="INBOUND_RECEIVED">Incoming received</option>
        </select>
        <input aria-label="Start date" type="date" value={startDate} onChange={(event) => setStartDate(event.target.value)} />
        <input aria-label="End date" type="date" value={endDate} onChange={(event) => setEndDate(event.target.value)} />
      </div>

      {error ? <p className="inventory-error">{error}</p> : null}
      {message ? <p className="inventory-success">{message}</p> : null}

      <div className="inventory-grid">
        <div className="inventory-panel">
          <h3>Inventory by Variant</h3>
          {loading ? <p>Loading inventory...</p> : null}
          {!loading && items.length === 0 ? (
            <div className="inventory-empty">
              <h4>No variants found</h4>
              <p>Create products in Catalog, then record opening stock or purchases to begin tracking inventory.</p>
            </div>
          ) : null}
          {!loading && items.length > 0 ? (
            <table className="inventory-table">
              <thead>
                <tr>
                  <th>Variant</th>
                  <th>Parent Product</th>
                  <th>Status</th>
                  <th>On Hand</th>
                  <th>Incoming</th>
                  <th>Sellable</th>
                  <th>Avg Cost</th>
                  <th>Value</th>
                </tr>
              </thead>
              <tbody>
                {items.map((item) => (
                  <tr key={item.item_id} onClick={() => openDetail(item.item_id)}>
                    <td>
                      <strong>{item.item_name}</strong>
                      <br />
                      <span>{item.item_id}</span>
                    </td>
                    <td>{item.parent_product_name || '—'}</td>
                    <td>
                      {item.low_stock ? (
                        <span className="inv-badge-low">{availabilityLabel(item.availability_status)}</span>
                      ) : (
                        availabilityLabel(item.availability_status)
                      )}
                    </td>
                    <td>{fmtQty(item.on_hand_qty)}</td>
                    <td>{fmtQty(item.incoming_qty)}</td>
                    <td>{fmtQty(item.sellable_qty)}</td>
                    <td>{fmtMoney(item.avg_unit_cost)}</td>
                    <td>{fmtMoney(item.stock_value)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          ) : null}
        </div>

        <aside className="inventory-panel">
          <h3>Opening Stock</h3>
          {catalogProducts.length === 0 ? (
            <p className="inventory-hint">Create a catalog product first, then come back here to record opening stock.</p>
          ) : (
            <>
              <label>
                Product
                <select value={openingProductId} onChange={(event) => setOpeningProductId(event.target.value)}>
                  {catalogProducts.map((product) => (
                    <option key={product.product_id} value={product.product_id}>
                      {product.identity.productName}
                    </option>
                  ))}
                </select>
              </label>
              {openingLines.map((line) => (
                <div key={line.tempId}>
                  <label>
                    Variant
                    <select
                      value={line.variant_id}
                      onChange={(event) =>
                        setOpeningLines((current) =>
                          current.map((currentLine) =>
                            currentLine.tempId !== line.tempId
                              ? currentLine
                              : {
                                  ...currentLine,
                                  variant_id: event.target.value,
                                  unit_cost: findVariantDefaultCost(
                                    openingProduct,
                                    event.target.value,
                                  ),
                                }
                          )
                        )
                      }
                    >
                      {(openingProduct?.variants ?? []).map((variant) => (
                        <option key={variant.tempId} value={variant.variant_id}>
                          {[variant.size, variant.color, variant.other].filter(Boolean).join(' / ') || 'Default'}
                        </option>
                      ))}
                    </select>
                  </label>
                  <label>
                    Quantity
                    <input
                      type="number"
                      min={0.01}
                      step="0.01"
                      value={line.qty}
                      onChange={(event) =>
                        setOpeningLines((current) =>
                          current.map((currentLine) =>
                            currentLine.tempId !== line.tempId
                              ? currentLine
                              : { ...currentLine, qty: Number(event.target.value || 0) }
                          )
                        )
                      }
                    />
                  </label>
                  <label>
                    Unit Cost
                    <input
                      type="number"
                      min={0.01}
                      step="0.01"
                      value={line.unit_cost}
                      onChange={(event) =>
                        setOpeningLines((current) =>
                          current.map((currentLine) =>
                            currentLine.tempId !== line.tempId
                              ? currentLine
                              : { ...currentLine, unit_cost: Number(event.target.value || 0) }
                          )
                        )
                      }
                    />
                  </label>
                  <label>
                    Reference
                    <input
                      value={line.reference}
                      onChange={(event) =>
                        setOpeningLines((current) =>
                          current.map((currentLine) =>
                            currentLine.tempId !== line.tempId
                              ? currentLine
                              : { ...currentLine, reference: event.target.value }
                          )
                        )
                      }
                    />
                  </label>
                  <label>
                    Note
                    <textarea
                      value={line.note}
                      onChange={(event) =>
                        setOpeningLines((current) =>
                          current.map((currentLine) =>
                            currentLine.tempId !== line.tempId
                              ? currentLine
                              : { ...currentLine, note: event.target.value }
                          )
                        )
                      }
                    />
                  </label>
                  <button
                    type="button"
                    onClick={() =>
                      setOpeningLines((current) =>
                        current.length === 1
                          ? current
                          : current.filter((currentLine) => currentLine.tempId !== line.tempId)
                      )
                    }
                    disabled={openingLines.length === 1}
                  >
                    Remove line
                  </button>
                </div>
              ))}
              <button
                type="button"
                onClick={() => {
                  const firstVariantId = openingProduct?.variants[0]?.variant_id ?? '';
                  if (!firstVariantId) return;
                  setOpeningLines((current) => [
                    ...current,
                    createOpeningLine(
                      firstVariantId,
                      findVariantDefaultCost(openingProduct, firstVariantId),
                    ),
                  ]);
                }}
                disabled={!openingProduct?.variants.length}
              >
                Add opening stock line
              </button>
              <button
                type="button"
                onClick={submitOpeningStock}
                disabled={submitting === 'opening' || !openingProduct?.variants.length}
              >
                {submitting === 'opening' ? 'Posting...' : 'Post Opening Stock'}
              </button>
            </>
          )}
        </aside>

        <aside className="inventory-panel">
          <h3>Adjust Stock</h3>
          <label>
            Variant
            <select value={adjustItemId} onChange={(event) => setAdjustItemId(event.target.value)}>
              <option value="">Select variant</option>
              {actionableItems.map((item) => (
                <option key={item.item_id} value={item.item_id}>
                  {item.parent_product_name ? `${item.parent_product_name} / ` : ''}
                  {item.item_name}
                </option>
              ))}
            </select>
          </label>
          <label>
            Adjustment type
            <select value={adjustType} onChange={(event) => setAdjustType(event.target.value as AdjustmentType)}>
              <option value="stock_in">Stock In</option>
              <option value="stock_out">Stock Out</option>
              <option value="correction">Correction</option>
            </select>
          </label>
          {adjustType !== 'correction' ? (
            <label>
              Quantity
              <input
                type="number"
                min={0.01}
                step="0.01"
                value={quantity}
                onChange={(event) => setQuantity(Number(event.target.value || 0))}
              />
            </label>
          ) : null}
          {adjustType === 'correction' ? (
            <label>
              Quantity Delta (+/-)
              <input
                type="number"
                step="0.01"
                value={quantityDelta}
                onChange={(event) => setQuantityDelta(Number(event.target.value || 0))}
              />
            </label>
          ) : null}
          {adjustType !== 'stock_out' ? (
            <label>
              Unit Cost
              <input
                type="number"
                min={0}
                step="0.01"
                value={unitCost}
                onChange={(event) => setUnitCost(Number(event.target.value || 0))}
              />
            </label>
          ) : null}
          <label>
            Reason
            <input value={reason} onChange={(event) => setReason(event.target.value)} />
          </label>
          <label>
            Reference
            <input value={reference} onChange={(event) => setReference(event.target.value)} />
          </label>
          <label>
            Note
            <textarea value={note} onChange={(event) => setNote(event.target.value)} />
          </label>
          <button type="button" onClick={submitAdjustment} disabled={submitting === 'adjustment'}>
            {submitting === 'adjustment' ? 'Applying...' : 'Apply Adjustment'}
          </button>
        </aside>
      </div>

      <div className="inventory-panel">
        <h3>Stock Movement Ledger</h3>
        {!loading && movements.length === 0 ? <p>No stock movements for the selected filter.</p> : null}
        {!loading && movements.length > 0 ? (
          <table className="inventory-table">
            <thead>
              <tr>
                <th>Date/Time</th>
                <th>Item</th>
                <th>Type</th>
                <th>Qty Delta</th>
                <th>Source</th>
                <th>Balance</th>
              </tr>
            </thead>
            <tbody>
              {movements.map((movement) => (
                <tr key={movement.txn_id}>
                  <td>{movement.timestamp}</td>
                  <td>{movement.item_name}</td>
                  <td>{movement.movement_type}</td>
                  <td className={toFiniteNumber(movement.qty_delta) >= 0 ? 'delta-positive' : 'delta-negative'}>
                    {toFiniteNumber(movement.qty_delta) >= 0 ? '+' : ''}
                    {fmtQty(movement.qty_delta)}
                  </td>
                  <td>
                    {movement.source_type || 'manual'}
                    {movement.source_id ? ` · ${movement.source_id}` : ''}
                  </td>
                  <td>{movement.resulting_balance == null ? '—' : fmtQty(movement.resulting_balance)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        ) : null}
      </div>

      {detailItem ? (
        <div className="inventory-panel">
          <h3>Inventory Detail · {detailItem.item_name}</h3>
          <p>
            Status: <strong>{availabilityLabel(detailItem.availability_status)}</strong> · On-hand:{' '}
            <strong>{fmtQty(detailItem.on_hand_qty)}</strong> · Incoming:{' '}
            <strong>{fmtQty(detailItem.incoming_qty)}</strong> · Sellable:{' '}
            <strong>{fmtQty(detailItem.sellable_qty)}</strong> · Value:{' '}
            <strong>{fmtMoney(detailItem.stock_value)}</strong>
          </p>
          <ul>
            {detailMovements.map((movement) => (
              <li key={movement.txn_id}>
                {movement.timestamp} · {movement.movement_type} ·{' '}
                {toFiniteNumber(movement.qty_delta) >= 0 ? '+' : ''}
                {fmtQty(movement.qty_delta)} · {movement.note || movement.source_type}
              </li>
            ))}
          </ul>
        </div>
      ) : null}
    </section>
  );
}
