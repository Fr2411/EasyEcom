'use client';

import { useEffect, useMemo, useState } from 'react';
import { createInventoryAdjustment, getInventoryDetail, getInventoryItems, getInventoryMovements } from '@/lib/api/inventory';
import { getProductsStockSnapshot, saveProductStock } from '@/lib/api/products-stock';
import { ProductChooser } from '@/components/products-stock/product-chooser';
import { ProductIdentityForm } from '@/components/products-stock/product-identity';
import { SaveSummary } from '@/components/products-stock/save-summary';
import { VariantGenerator } from '@/components/products-stock/variant-generator';
import { VariantGrid } from '@/components/products-stock/variant-grid';
import { createEmptyVariant, generateVariantsFromInputs, summarizeVariants } from '@/lib/products-stock/variant-utils';
import type { InventoryItem, InventoryMovement } from '@/types/inventory';
import type { ProductIdentity, ProductRecord, Variant, VariantMode } from '@/types/products-stock';

type AdjustmentType = 'stock_in' | 'stock_out' | 'correction';

const EMPTY_IDENTITY: ProductIdentity = {
  productName: '',
  supplier: '',
  category: '',
  description: '',
  features: [],
};

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

  const [detailItem, setDetailItem] = useState<InventoryItem | null>(null);
  const [detailMovements, setDetailMovements] = useState<InventoryMovement[]>([]);

  const [products, setProducts] = useState<ProductRecord[]>([]);
  const [suppliers, setSuppliers] = useState<string[]>([]);
  const [categories, setCategories] = useState<string[]>([]);
  const [mode, setMode] = useState<VariantMode>('new');
  const [identity, setIdentity] = useState<ProductIdentity>(EMPTY_IDENTITY);
  const [variants, setVariants] = useState<Variant[]>([]);
  const [sameCostEnabled, setSameCostEnabled] = useState(false);
  const [sharedCost, setSharedCost] = useState('');
  const [catalogMessage, setCatalogMessage] = useState<string>();

  const visibleItems = useMemo(
    () => items.filter((item) => toFiniteNumber(item.sellable_qty) > 0 || toFiniteNumber(item.on_hand_qty) > 0),
    [items],
  );
  const summary = useMemo(() => summarizeVariants(variants), [variants]);
  const actionableItems = useMemo(
    () => items.filter((item) => item.item_type === 'variant' && item.actionable),
    [items],
  );

  const loadInventory = async (q = query) => {
    try {
      setLoading(true);
      setError(null);
      const [itemsRes, movementRes] = await Promise.all([
        getInventoryItems(q),
        getInventoryMovements({
          item_id: selectedItemId || undefined,
          movement_type: selectedMovementType || undefined,
          start_date: startDate || undefined,
          end_date: endDate || undefined,
          limit: 100,
        }),
      ]);
      setItems(itemsRes.items);
      setMovements(movementRes.items);
      const actionableIds = new Set(
        itemsRes.items.filter((item) => item.item_type === 'variant' && item.actionable).map((item) => item.item_id),
      );
      if (!adjustItemId || !actionableIds.has(adjustItemId)) {
        const firstActionable = itemsRes.items.find((item) => item.item_type === 'variant' && item.actionable);
        setAdjustItemId(firstActionable?.item_id ?? '');
      }
    } catch {
      setError('Unable to load inventory module right now.');
    } finally {
      setLoading(false);
    }
  };

  const loadCatalog = async () => {
    try {
      const snapshot = await getProductsStockSnapshot();
      setProducts(snapshot.products);
      setSuppliers(snapshot.suppliers);
      setCategories(snapshot.categories);
    } catch {
      setCatalogMessage('Unable to load product finder at the moment.');
    }
  };

  useEffect(() => {
    void Promise.all([loadInventory(''), loadCatalog()]);
  }, []);

  const openDetail = async (itemId: string) => {
    try {
      const detail = await getInventoryDetail(itemId);
      setDetailItem(detail.item);
      setDetailMovements(detail.recent_movements);
    } catch {
      setError('Unable to load inventory detail.');
    }
  };

  const loadExistingProduct = (productId: string) => {
    const existing = products.find((product) => product.id === productId);
    if (!existing) return;
    setMode('existing');
    setIdentity(existing.identity);
    setVariants(existing.variants);
    setCatalogMessage(undefined);
  };

  const startNewProduct = (typedName: string) => {
    setMode('new');
    setIdentity({ ...EMPTY_IDENTITY, productName: typedName });
    setVariants([]);
    setCatalogMessage(undefined);
  };

  const resetCatalog = () => {
    setMode('new');
    setIdentity(EMPTY_IDENTITY);
    setVariants([]);
    setCatalogMessage(undefined);
    setSameCostEnabled(false);
    setSharedCost('');
  };

  const handleVariantChange = (id: string, field: keyof Variant, value: string) => {
    setVariants((current) =>
      current.map((variant) => {
        if (variant.id !== id) return variant;
        if (field === 'qty' || field === 'cost' || field === 'defaultSellingPrice' || field === 'maxDiscountPct') {
          return { ...variant, [field]: Number(value) || 0 };
        }
        return { ...variant, [field]: value };
      }),
    );
  };

  const validateCatalog = (): string | undefined => {
    if (!identity.productName.trim()) return 'Product name is required.';
    if (variants.length === 0) return 'At least one variant is required.';
    return undefined;
  };

  const saveCatalogEntry = async () => {
    const validationError = validateCatalog();
    if (validationError) {
      setCatalogMessage(validationError);
      return;
    }

    try {
      setSaving(true);
      setCatalogMessage(undefined);
      await saveProductStock({ mode, identity, variants });
      setCatalogMessage('Product and stock saved successfully.');
      await Promise.all([loadCatalog(), loadInventory(query)]);
    } catch (err) {
      setCatalogMessage(err instanceof Error ? err.message : 'Unable to save product details.');
    } finally {
      setSaving(false);
    }
  };

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
      setReason('');
      setNote('');
      setReference('');
      await loadInventory(query);
      if (detailItem) await openDetail(detailItem.item_id);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Adjustment failed.');
    } finally {
      setSaving(false);
    }
  };

  return (
    <section className="inventory-module">
      <div className="products-stock-layout" data-mode={mode}>
        <ProductChooser
          products={products.map((product) => ({ id: product.id, name: product.identity.productName }))}
          onSelectExisting={loadExistingProduct}
          onCreateNew={startNewProduct}
        />
        <ProductIdentityForm
          identity={identity}
          suppliers={suppliers}
          categories={categories}
          onIdentityChange={setIdentity}
          onAddSupplier={(supplier) => setSuppliers((prev) => (prev.includes(supplier) ? prev : [...prev, supplier]))}
          onAddCategory={(category) => setCategories((prev) => (prev.includes(category) ? prev : [...prev, category]))}
        />
        {mode === 'new' ? (
          <VariantGenerator
            onGenerate={({ size, color, other }) =>
              setVariants(generateVariantsFromInputs({ size, color, other }))
            }
          />
        ) : null}
        <VariantGrid
          variants={variants}
          sameCostEnabled={sameCostEnabled}
          sharedCost={sharedCost}
          onSameCostEnabledChange={setSameCostEnabled}
          onSharedCostChange={setSharedCost}
          onApplySharedCost={() => {
            const parsed = Number(sharedCost) || 0;
            setVariants((current) => current.map((variant) => ({ ...variant, cost: parsed })));
          }}
          onVariantChange={handleVariantChange}
          onAddVariant={() => setVariants((current) => [...current, createEmptyVariant()])}
          onRemoveVariant={(id) => setVariants((current) => current.filter((variant) => variant.id !== id))}
        />
        <SaveSummary
          variantCount={summary.variantCount}
          totalQty={summary.totalQty}
          estimatedStockCost={summary.estimatedStockCost}
          isSaving={saving}
          isSaveDisabled={Boolean(validateCatalog())}
          validationMessage={catalogMessage}
          onSave={saveCatalogEntry}
          onReset={resetCatalog}
        />
      </div>

      <div className="inventory-toolbar">
        <input aria-label="Search inventory" placeholder="Search SKU, variant, product" value={query} onChange={(e) => setQuery(e.target.value)} />
        <button type="button" onClick={() => loadInventory(query)}>Search</button>
        <select aria-label="Filter movement type" value={selectedMovementType} onChange={(e) => setSelectedMovementType(e.target.value)}>
          <option value="">All movements</option>
          <option value="IN">Inbound</option>
          <option value="OUT">Outbound</option>
          <option value="RESERVE">Reserve</option>
          <option value="RELEASE">Release</option>
          <option value="ADJUST">Adjustments</option>
          <option value="CORRECTION">Corrections</option>
        </select>
        <input aria-label="Start date" type="date" value={startDate} onChange={(e) => setStartDate(e.target.value)} />
        <input aria-label="End date" type="date" value={endDate} onChange={(e) => setEndDate(e.target.value)} />
      </div>

      {error ? <p className="inventory-error">{error}</p> : null}
      <div className="inventory-grid">
        <div className="inventory-panel">
          <h3>Current Stock (Available Items)</h3>
          {loading ? <p>Loading inventory...</p> : null}
          {!loading && visibleItems.length === 0 ? <div className="inventory-empty"><h4>No inventory yet</h4><p>Add stock from Inventory to start tracking available products.</p></div> : null}
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
          <h3>Adjust Stock (Variant Only)</h3>
          <label>Item<select value={adjustItemId} onChange={(e) => setAdjustItemId(e.target.value)}>
            <option value="">Select variant</option>
            {actionableItems.map((item) => <option key={item.item_id} value={item.item_id}>{item.item_name}</option>)}
          </select></label>
          {actionableItems.length === 0 ? <p className="inventory-hint">Only variants are actionable for stock adjustments.</p> : null}
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
