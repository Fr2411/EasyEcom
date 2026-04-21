'use client';

import type { FormEvent } from 'react';
import { useEffect, useMemo, useState, useTransition } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import {
  createInventoryAdjustment,
  getInventoryIntakeLookup,
  getInventoryWorkspace,
  receiveInventoryStock,
  updateInventoryInlineFields,
} from '@/lib/api/commerce';
import {
  WorkspaceEmpty,
  WorkspaceHint,
  WorkspaceNotice,
  WorkspacePanel,
  WorkspaceToast,
} from '@/components/commerce/workspace-primitives';
import { formatMoney, formatQuantity, numberFromString } from '@/lib/commerce-format';
import type { CatalogProduct, CatalogVariant } from '@/types/catalog';
import type { InventoryAdjustmentPayload, InventoryStockRow, ReceiveStockPayload } from '@/types/inventory';
import styles from '@/components/commerce/inventory-ops-workspace.module.css';

const EMPTY_ADJUSTMENT: InventoryAdjustmentPayload = {
  variant_id: '',
  quantity_delta: '',
  reason: '',
  notes: '',
};

type ReceiveLineDraft = {
  line_id: string;
  is_new: boolean;
  variant_id?: string;
  label: string;
  sku: string;
  barcode: string;
  size: string;
  color: string;
  other: string;
  reorder_level: string;
  quantity: string;
  unit_cost: string;
};

type InlineVariantDraft = {
  barcode: string;
  reorder_level: string;
};

function rowId(prefix: string) {
  return `${prefix}-${Date.now()}-${Math.random().toString(36).slice(2, 9)}`;
}

function valueOrEmpty(value: string | null | undefined) {
  return value ?? '';
}

function existingVariantLine(variant: CatalogVariant): ReceiveLineDraft {
  return {
    line_id: rowId('existing'),
    is_new: false,
    variant_id: variant.variant_id,
    label: variant.label,
    sku: variant.sku,
    barcode: variant.barcode,
    size: variant.options.size,
    color: variant.options.color,
    other: variant.options.other,
    reorder_level: variant.reorder_level,
    quantity: '1',
    unit_cost: valueOrEmpty(variant.unit_cost),
  };
}

function newVariantLine(): ReceiveLineDraft {
  return {
    line_id: rowId('new'),
    is_new: true,
    label: 'New variant',
    sku: '',
    barcode: '',
    size: '',
    color: '',
    other: '',
    reorder_level: '0',
    quantity: '1',
    unit_cost: '',
  };
}

function collectLookupProducts(payload: Awaited<ReturnType<typeof getInventoryIntakeLookup>>) {
  const map = new Map<string, CatalogProduct>();
  payload.exact_variants.forEach((match) => {
    map.set(match.product.product_id, match.product);
  });
  payload.product_matches.forEach((product) => {
    map.set(product.product_id, product);
  });
  return Array.from(map.values()).sort((a, b) => a.name.localeCompare(b.name));
}

function receiveIdentityFromProduct(product: CatalogProduct) {
  return {
    product_id: product.product_id,
    product_name: product.name,
    supplier: product.supplier,
    category: product.category,
    brand: product.brand,
    description: product.description,
    image_url: product.image_url,
    pending_primary_media_upload_id: '',
    remove_primary_image: false,
    sku_root: product.sku_root,
    default_selling_price: valueOrEmpty(product.default_price),
    min_selling_price: valueOrEmpty(product.min_price),
    max_discount_percent: valueOrEmpty(product.max_discount_percent),
    status: product.status || 'active',
  };
}

function statusLabel(row: InventoryStockRow) {
  const available = numberFromString(row.available_to_sell);
  if (available <= 0) return 'Out';
  if (row.low_stock) return 'Low';
  return 'Normal';
}

function statusClass(row: InventoryStockRow) {
  const available = numberFromString(row.available_to_sell);
  if (available <= 0) return styles.statusOut;
  if (row.low_stock) return styles.statusLow;
  return styles.statusNormal;
}

export function InventoryOpsWorkspace() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const searchKey = searchParams.toString();

  const [queryInput, setQueryInput] = useState('');
  const [workspace, setWorkspace] = useState<Awaited<ReturnType<typeof getInventoryWorkspace>> | null>(null);
  const [notice, setNotice] = useState('');
  const [error, setError] = useState('');
  const [toast, setToast] = useState('');
  const [isPending, startTransition] = useTransition();

  const [inlineDrafts, setInlineDrafts] = useState<Record<string, InlineVariantDraft>>({});
  const [inlineSavingVariantId, setInlineSavingVariantId] = useState('');

  const [receiveOpen, setReceiveOpen] = useState(false);
  const [receiveLookupQuery, setReceiveLookupQuery] = useState('');
  const [receiveLookupPending, setReceiveLookupPending] = useState(false);
  const [receiveMatches, setReceiveMatches] = useState<CatalogProduct[]>([]);
  const [receiveProduct, setReceiveProduct] = useState<CatalogProduct | null>(null);
  const [receiveLines, setReceiveLines] = useState<ReceiveLineDraft[]>([]);
  const [receiveNotes, setReceiveNotes] = useState('');
  const [receivePending, setReceivePending] = useState(false);

  const [adjustOpen, setAdjustOpen] = useState(false);
  const [adjustPending, setAdjustPending] = useState(false);
  const [adjustmentForm, setAdjustmentForm] = useState<InventoryAdjustmentPayload>({ ...EMPTY_ADJUSTMENT });

  useEffect(() => {
    if (!toast) return undefined;
    const timer = window.setTimeout(() => setToast(''), 2800);
    return () => window.clearTimeout(timer);
  }, [toast]);

  const loadWorkspace = (query = '') => {
    const trimmed = query.trim();
    startTransition(async () => {
      try {
        const payload = await getInventoryWorkspace({ q: trimmed });
        setWorkspace(payload);
        setError('');
      } catch (loadError) {
        setWorkspace(null);
        setError(loadError instanceof Error ? loadError.message : 'Unable to load inventory workspace.');
      }
    });
  };

  useEffect(() => {
    const query = (searchParams.get('q') ?? '').trim();
    setQueryInput(query);
    loadWorkspace(query);
  }, [searchKey]);

  useEffect(() => {
    if (!workspace) return;
    setInlineDrafts((current) => {
      const next = { ...current };
      workspace.stock_items.forEach((row) => {
        if (!next[row.variant_id]) {
          next[row.variant_id] = {
            barcode: row.barcode,
            reorder_level: row.reorder_level,
          };
        }
      });
      return next;
    });
  }, [workspace]);

  const searchReceiveProducts = async (
    rawQuery: string,
    options?: { targetProductId?: string; seedVariantId?: string },
  ) => {
    const query = rawQuery.trim();
    if (!query) {
      setReceiveMatches([]);
      return;
    }
    setReceiveLookupPending(true);
    try {
      const payload = await getInventoryIntakeLookup({ q: query });
      const products = collectLookupProducts(payload);
      setReceiveMatches(products);
      if (options?.targetProductId) {
        const matched = products.find((item) => item.product_id === options.targetProductId);
        if (matched) {
          selectReceiveProduct(matched, options.seedVariantId);
          return;
        }
      }
      if (products.length === 1) {
        selectReceiveProduct(products[0], options?.seedVariantId);
      }
    } catch (lookupError) {
      setError(lookupError instanceof Error ? lookupError.message : 'Unable to search catalog products for receiving.');
    } finally {
      setReceiveLookupPending(false);
    }
  };

  const selectReceiveProduct = (product: CatalogProduct, seedVariantId?: string) => {
    setReceiveProduct(product);
    if (seedVariantId) {
      const variant = product.variants.find((item) => item.variant_id === seedVariantId);
      if (variant) {
        setReceiveLines([existingVariantLine(variant)]);
        return;
      }
    }
    setReceiveLines([]);
  };

  const openReceiveDrawer = () => {
    setReceiveOpen(true);
    setReceiveLookupQuery(queryInput.trim());
    setReceiveMatches([]);
    setReceiveProduct(null);
    setReceiveLines([]);
    setReceiveNotes('');
    setError('');
    setNotice('');
  };

  const openReceiveFromRow = (row: InventoryStockRow) => {
    openReceiveDrawer();
    setReceiveLookupQuery(row.product_name);
    void searchReceiveProducts(row.product_name, {
      targetProductId: row.product_id,
      seedVariantId: row.variant_id,
    });
  };

  const addExistingReceiveLine = (variant: CatalogVariant) => {
    setReceiveLines((current) => {
      if (current.some((line) => line.variant_id === variant.variant_id)) {
        return current;
      }
      return [...current, existingVariantLine(variant)];
    });
  };

  const addNewReceiveLine = () => {
    setReceiveLines((current) => [...current, newVariantLine()]);
  };

  const updateReceiveLine = (lineId: string, patch: Partial<ReceiveLineDraft>) => {
    setReceiveLines((current) => current.map((line) => (line.line_id === lineId ? { ...line, ...patch } : line)));
  };

  const removeReceiveLine = (lineId: string) => {
    setReceiveLines((current) => current.filter((line) => line.line_id !== lineId));
  };

  const submitReceiveStock = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!receiveProduct) {
      setError('Select a catalog product before receiving stock.');
      return;
    }
    if (!receiveLines.length) {
      setError('Add at least one receive line.');
      return;
    }

    const variantById = new Map(receiveProduct.variants.map((variant) => [variant.variant_id, variant]));
    const lines: ReceiveStockPayload['lines'] = [];

    for (const line of receiveLines) {
      const quantity = line.quantity.trim();
      const unitCost = line.unit_cost.trim();
      if (!quantity || numberFromString(quantity) <= 0) {
        setError(`Enter a valid quantity for ${line.label}.`);
        return;
      }
      if (!unitCost) {
        setError(`Unit cost is required for ${line.label}.`);
        return;
      }

      if (line.variant_id) {
        const variant = variantById.get(line.variant_id);
        if (!variant) {
          setError(`Variant ${line.label} is no longer available. Reload and retry.`);
          return;
        }
        lines.push({
          variant_id: variant.variant_id,
          sku: variant.sku,
          barcode: line.barcode.trim() || variant.barcode,
          size: variant.options.size,
          color: variant.options.color,
          other: variant.options.other,
          default_purchase_price: unitCost,
          default_selling_price: valueOrEmpty(variant.unit_price ?? variant.effective_unit_price),
          min_selling_price: valueOrEmpty(variant.min_price ?? variant.effective_min_price),
          reorder_level: line.reorder_level.trim() || variant.reorder_level,
          status: variant.status,
          quantity,
        });
        continue;
      }

      lines.push({
        sku: '',
        barcode: line.barcode.trim(),
        size: line.size.trim(),
        color: line.color.trim(),
        other: line.other.trim(),
        default_purchase_price: unitCost,
        default_selling_price: valueOrEmpty(receiveProduct.default_price),
        min_selling_price: valueOrEmpty(receiveProduct.min_price),
        reorder_level: line.reorder_level.trim() || '0',
        status: 'active',
        quantity,
      });
    }

    setReceivePending(true);
    setError('');
    setNotice('');
    try {
      const payload: ReceiveStockPayload = {
        action: 'receive_stock',
        notes: receiveNotes.trim(),
        update_matched_product_details: false,
        identity: receiveIdentityFromProduct(receiveProduct),
        lines,
      };
      const response = await receiveInventoryStock(payload);
      setReceiveOpen(false);
      setReceiveProduct(null);
      setReceiveLines([]);
      setReceiveNotes('');
      setNotice(`Received stock under ${response.purchase_number || 'new receipt'} for ${response.product.name}.`);
      setToast('Stock receipt completed.');
      loadWorkspace(queryInput);
    } catch (receiveError) {
      setError(receiveError instanceof Error ? receiveError.message : 'Unable to receive stock.');
    } finally {
      setReceivePending(false);
    }
  };

  const openAdjustDrawer = (row: InventoryStockRow) => {
    setAdjustmentForm({
      variant_id: row.variant_id,
      quantity_delta: '',
      reason: 'Stock adjustment',
      notes: '',
    });
    setAdjustOpen(true);
    setError('');
    setNotice('');
  };

  const submitAdjustment = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setAdjustPending(true);
    setError('');
    setNotice('');
    try {
      await createInventoryAdjustment(adjustmentForm);
      setAdjustOpen(false);
      setAdjustmentForm({ ...EMPTY_ADJUSTMENT });
      setNotice('Adjustment recorded successfully.');
      setToast('Inventory adjustment saved.');
      loadWorkspace(queryInput);
    } catch (adjustError) {
      setError(adjustError instanceof Error ? adjustError.message : 'Unable to record adjustment.');
    } finally {
      setAdjustPending(false);
    }
  };

  const saveInlineVariantFields = async (row: InventoryStockRow) => {
    const draft = inlineDrafts[row.variant_id];
    if (!draft) return;
    const nextBarcode = draft.barcode.trim();
    const nextReorder = draft.reorder_level.trim();
    if (!nextReorder) {
      setError('Reorder level is required.');
      return;
    }
    if (nextBarcode === row.barcode && nextReorder === row.reorder_level) {
      return;
    }

    setInlineSavingVariantId(row.variant_id);
    setError('');
    setNotice('');
    try {
      await updateInventoryInlineFields({
        variant_id: row.variant_id,
        barcode: nextBarcode,
        reorder_level: nextReorder,
      });
      setNotice(`Updated variant ops fields for ${row.label}.`);
      setToast('Variant fields updated.');
      loadWorkspace(queryInput);
    } catch (inlineError) {
      setError(inlineError instanceof Error ? inlineError.message : 'Unable to save variant fields.');
    } finally {
      setInlineSavingVariantId('');
    }
  };

  const rows = workspace?.stock_items ?? [];
  const activeReceiveProductVariants = useMemo(() => receiveProduct?.variants ?? [], [receiveProduct]);

  return (
    <div className="workspace-stack">
      {toast ? <WorkspaceToast message={toast} onClose={() => setToast('')} /> : null}

      <WorkspacePanel
        title={
          <span className="workspace-heading">
            Inventory
            <WorkspaceHint
              label="Inventory help"
              text="Inventory is for stock operations at variant level: receive stock, adjust stock, sell, and jump to catalog identity edits when needed."
            />
          </span>
        }
        description="Simple stock table for available variants with quick operations and no catalog identity overlap."
        actions={
          <div className={styles.toolbar}>
            <form
              className={styles.searchForm}
              onSubmit={(event) => {
                event.preventDefault();
                loadWorkspace(queryInput);
              }}
            >
              <input
                type="search"
                value={queryInput}
                placeholder="Search inventory variants"
                onChange={(event) => setQueryInput(event.target.value)}
              />
              <button type="submit" disabled={isPending}>Search</button>
            </form>
            <button type="button" onClick={openReceiveDrawer}>
              Receive Stock
            </button>
          </div>
        }
      >
        {notice ? <WorkspaceNotice tone="success">{notice}</WorkspaceNotice> : null}
        {error ? <WorkspaceNotice tone="error">{error}</WorkspaceNotice> : null}
        {isPending && !workspace ? <WorkspaceNotice>Loading inventory…</WorkspaceNotice> : null}

        {rows.length ? (
          <div className={styles.tableWrap}>
            <table className="workspace-table workspace-table-sticky">
              <thead>
                <tr>
                  <th>Product</th>
                  <th>Variant</th>
                  <th>SKU</th>
                  <th>Barcode / Reorder</th>
                  <th>On Hand</th>
                  <th>Reserved</th>
                  <th>Available</th>
                  <th>Unit Cost</th>
                  <th>Status</th>
                  <th>Actions</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((row) => (
                  <tr key={row.variant_id}>
                    <td>{row.product_name}</td>
                    <td>{row.label}</td>
                    <td>{row.sku}</td>
                    <td>
                      <div className={styles.inlineEdit}>
                        <input
                          value={inlineDrafts[row.variant_id]?.barcode ?? row.barcode}
                          onChange={(event) =>
                            setInlineDrafts((current) => ({
                              ...current,
                              [row.variant_id]: {
                                barcode: event.target.value,
                                reorder_level: current[row.variant_id]?.reorder_level ?? row.reorder_level,
                              },
                            }))
                          }
                          placeholder="Barcode"
                        />
                        <input
                          value={inlineDrafts[row.variant_id]?.reorder_level ?? row.reorder_level}
                          onChange={(event) =>
                            setInlineDrafts((current) => ({
                              ...current,
                              [row.variant_id]: {
                                barcode: current[row.variant_id]?.barcode ?? row.barcode,
                                reorder_level: event.target.value,
                              },
                            }))
                          }
                          inputMode="decimal"
                          placeholder="Reorder"
                        />
                        <button
                          type="button"
                          className="secondary"
                          disabled={inlineSavingVariantId === row.variant_id}
                          onClick={() => void saveInlineVariantFields(row)}
                        >
                          {inlineSavingVariantId === row.variant_id ? 'Saving…' : 'Save'}
                        </button>
                      </div>
                    </td>
                    <td>{formatQuantity(row.on_hand)}</td>
                    <td>{formatQuantity(row.reserved)}</td>
                    <td>{formatQuantity(row.available_to_sell)}</td>
                    <td>{formatMoney(row.unit_cost)}</td>
                    <td>
                      <span className={`${styles.statusCell} ${statusClass(row)}`}>{statusLabel(row)}</span>
                    </td>
                    <td>
                      <div className={styles.rowActions}>
                        <button type="button" onClick={() => openReceiveFromRow(row)}>
                          Receive Stock
                        </button>
                        <button type="button" onClick={() => openAdjustDrawer(row)}>
                          Adjust Stock
                        </button>
                        <button
                          type="button"
                          className="secondary"
                          onClick={() =>
                            router.push(
                              `/sales?seed_variant_id=${encodeURIComponent(row.variant_id)}&seed_sku=${encodeURIComponent(row.sku)}`
                            )
                          }
                        >
                          Sell
                        </button>
                        <button
                          type="button"
                          className="secondary"
                          onClick={() =>
                            router.push(
                              `/catalog?product_id=${encodeURIComponent(row.product_id)}&q=${encodeURIComponent(row.product_name)}`
                            )
                          }
                        >
                          Open Catalog
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <WorkspaceEmpty
            title="No available stock rows"
            message="Use Receive Stock to add inventory for catalog products and create first variants when needed."
          />
        )}
      </WorkspacePanel>

      {receiveOpen ? (
        <>
          <button
            type="button"
            className={styles.drawerBackdrop}
            aria-label="Close receive drawer"
            onClick={() => setReceiveOpen(false)}
          />
          <aside className={styles.drawer} aria-label="Receive stock drawer">
            <div className={styles.drawerHeader}>
              <h3 className="workspace-heading">Receive Stock</h3>
              <button type="button" className="secondary" onClick={() => setReceiveOpen(false)}>
                Close
              </button>
            </div>

            {!receiveProduct ? (
              <div className="workspace-stack">
                <form
                  className={styles.searchForm}
                  onSubmit={(event) => {
                    event.preventDefault();
                    void searchReceiveProducts(receiveLookupQuery);
                  }}
                >
                  <input
                    type="search"
                    value={receiveLookupQuery}
                    placeholder="Search catalog product for receiving"
                    onChange={(event) => setReceiveLookupQuery(event.target.value)}
                  />
                  <button type="submit" disabled={receiveLookupPending}>
                    {receiveLookupPending ? 'Searching…' : 'Find Product'}
                  </button>
                </form>

                {receiveMatches.length ? (
                  <div className={styles.receiveMatchList}>
                    {receiveMatches.map((product) => (
                      <article key={product.product_id} className={styles.receiveMatchCard}>
                        <div>
                          <strong>{product.name}</strong>
                          <p className="workspace-field-note">
                            Variants: {product.variants.length} · Supplier: {product.supplier || 'Not set'}
                          </p>
                        </div>
                        <button type="button" onClick={() => selectReceiveProduct(product)}>
                          Use Product
                        </button>
                      </article>
                    ))}
                  </div>
                ) : (
                  <WorkspaceNotice>
                    Search a catalog product to start receiving. If the product does not exist yet, create it in Catalog first.
                  </WorkspaceNotice>
                )}
              </div>
            ) : (
              <form className="workspace-form" onSubmit={submitReceiveStock}>
                <div className="workspace-subsection">
                  <div className="workspace-subsection-header">
                    <h4 className="workspace-heading">
                      {receiveProduct.name}
                      <WorkspaceHint
                        label="Receive product help"
                        text="Add existing variants or add new variant lines, then post one stock receipt."
                      />
                    </h4>
                    <div className={styles.receiveActions}>
                      <button type="button" className="secondary" onClick={() => setReceiveProduct(null)}>
                        Change Product
                      </button>
                      <button
                        type="button"
                        className="secondary"
                        onClick={() =>
                          router.push(
                            `/catalog?product_id=${encodeURIComponent(receiveProduct.product_id)}&q=${encodeURIComponent(receiveProduct.name)}`
                          )
                        }
                      >
                        Open Catalog
                      </button>
                    </div>
                  </div>

                  {activeReceiveProductVariants.length ? (
                    <div className={styles.tableWrap}>
                      <table className="workspace-table workspace-table-sticky">
                        <thead>
                          <tr>
                            <th>Variant</th>
                            <th>SKU</th>
                            <th>Available</th>
                            <th>Cost</th>
                            <th>Action</th>
                          </tr>
                        </thead>
                        <tbody>
                          {activeReceiveProductVariants.map((variant) => (
                            <tr key={variant.variant_id}>
                              <td>{variant.label}</td>
                              <td>{variant.sku}</td>
                              <td>{formatQuantity(variant.available_to_sell)}</td>
                              <td>{formatMoney(variant.unit_cost)}</td>
                              <td>
                                <button type="button" onClick={() => addExistingReceiveLine(variant)}>
                                  Add Line
                                </button>
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  ) : (
                    <WorkspaceNotice>
                      This product currently has no variants. Add a new variant line below for the first stock receipt.
                    </WorkspaceNotice>
                  )}
                </div>

                <div className="workspace-subsection">
                  <div className="workspace-subsection-header">
                    <h4 className="workspace-heading">Receive Lines</h4>
                    <button type="button" onClick={addNewReceiveLine}>Add New Variant Line</button>
                  </div>

                  {receiveLines.length ? (
                    <div className="workspace-stack">
                      {receiveLines.map((line) => (
                        <article key={line.line_id} className={styles.receiveLineCard}>
                          <div className={styles.receiveLineHeader}>
                            <strong>{line.is_new ? 'New variant line' : line.label}</strong>
                            <button type="button" className="secondary" onClick={() => removeReceiveLine(line.line_id)}>
                              Remove
                            </button>
                          </div>

                          <div className={styles.receiveLineGrid}>
                            <label>
                              Quantity
                              <input
                                value={line.quantity}
                                inputMode="decimal"
                                onChange={(event) => updateReceiveLine(line.line_id, { quantity: event.target.value })}
                                required
                              />
                            </label>
                            <label>
                              Unit cost
                              <input
                                value={line.unit_cost}
                                inputMode="decimal"
                                onChange={(event) => updateReceiveLine(line.line_id, { unit_cost: event.target.value })}
                                required
                              />
                            </label>
                            <label>
                              Barcode
                              <input
                                value={line.barcode}
                                onChange={(event) => updateReceiveLine(line.line_id, { barcode: event.target.value })}
                                disabled={!line.is_new}
                              />
                            </label>
                            <label>
                              Reorder
                              <input
                                value={line.reorder_level}
                                inputMode="decimal"
                                onChange={(event) => updateReceiveLine(line.line_id, { reorder_level: event.target.value })}
                              />
                            </label>
                            <label>
                              Size
                              <input
                                value={line.size}
                                onChange={(event) => updateReceiveLine(line.line_id, { size: event.target.value })}
                                disabled={!line.is_new}
                              />
                            </label>
                            <label>
                              Color
                              <input
                                value={line.color}
                                onChange={(event) => updateReceiveLine(line.line_id, { color: event.target.value })}
                                disabled={!line.is_new}
                              />
                            </label>
                            <label>
                              Other
                              <input
                                value={line.other}
                                onChange={(event) => updateReceiveLine(line.line_id, { other: event.target.value })}
                                disabled={!line.is_new}
                              />
                            </label>
                          </div>
                        </article>
                      ))}
                    </div>
                  ) : (
                    <WorkspaceEmpty
                      title="No receive lines"
                      message="Add an existing variant line or create a new variant line to receive stock."
                    />
                  )}
                </div>

                <label>
                  Notes
                  <textarea
                    rows={3}
                    value={receiveNotes}
                    onChange={(event) => setReceiveNotes(event.target.value)}
                  />
                </label>

                <div className={styles.receiveActions}>
                  <button type="submit" disabled={receivePending}>
                    {receivePending ? 'Receiving…' : 'Receive Stock'}
                  </button>
                  <button type="button" className="secondary" onClick={() => setReceiveOpen(false)}>
                    Cancel
                  </button>
                </div>
              </form>
            )}
          </aside>
        </>
      ) : null}

      {adjustOpen ? (
        <>
          <button
            type="button"
            className={styles.drawerBackdrop}
            aria-label="Close adjustment drawer"
            onClick={() => setAdjustOpen(false)}
          />
          <aside className={styles.drawer} aria-label="Adjust stock drawer">
            <div className={styles.drawerHeader}>
              <h3 className="workspace-heading">Adjust Stock</h3>
              <button type="button" className="secondary" onClick={() => setAdjustOpen(false)}>
                Close
              </button>
            </div>

            <form className="workspace-form" onSubmit={submitAdjustment}>
              <div className="workspace-form-grid compact">
                <label>
                  Variant ID
                  <input value={adjustmentForm.variant_id} readOnly />
                </label>
                <label>
                  Quantity delta
                  <input
                    value={adjustmentForm.quantity_delta}
                    onChange={(event) =>
                      setAdjustmentForm((current) => ({
                        ...current,
                        quantity_delta: event.target.value,
                      }))
                    }
                    placeholder="-2 or +3"
                    required
                  />
                </label>
                <label>
                  Reason
                  <input
                    value={adjustmentForm.reason}
                    onChange={(event) =>
                      setAdjustmentForm((current) => ({
                        ...current,
                        reason: event.target.value,
                      }))
                    }
                    required
                  />
                </label>
              </div>

              <label>
                Notes
                <textarea
                  rows={3}
                  value={adjustmentForm.notes}
                  onChange={(event) =>
                    setAdjustmentForm((current) => ({
                      ...current,
                      notes: event.target.value,
                    }))
                  }
                />
              </label>

              <div className={styles.receiveActions}>
                <button type="submit" disabled={adjustPending}>
                  {adjustPending ? 'Saving…' : 'Adjust Stock'}
                </button>
                <button type="button" className="secondary" onClick={() => setAdjustOpen(false)}>
                  Cancel
                </button>
              </div>
            </form>
          </aside>
        </>
      ) : null}
    </div>
  );
}
