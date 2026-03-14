'use client';

import { FormEvent, useEffect, useState, useTransition } from 'react';
import { useSearchParams } from 'next/navigation';
import { createInventoryAdjustment, getCatalogWorkspace, getInventoryWorkspace, receiveInventoryStock } from '@/lib/api/commerce';
import type { CatalogProduct } from '@/types/catalog';
import type { InventoryAdjustmentPayload, ReceiveStockPayload } from '@/types/inventory';
import { WorkspaceEmpty, WorkspaceNotice, WorkspacePanel, WorkspaceTabs } from '@/components/commerce/workspace-primitives';
import { formatMoney, formatQuantity } from '@/lib/commerce-format';


type InventoryTab = 'stock' | 'receive' | 'adjust' | 'low-stock';

function valueOrEmpty(value: string | null | undefined) {
  return value ?? '';
}

const EMPTY_RECEIVE: ReceiveStockPayload = {
  mode: 'new_product',
  quantity: '1',
  notes: '',
  identity: {
    product_name: '',
    supplier: '',
    category: '',
    brand: '',
    description: '',
    image_url: '',
    sku_root: '',
    default_selling_price: '',
    min_selling_price: '',
    max_discount_percent: '',
    status: 'active',
  },
  variant: {
    sku: '',
    barcode: '',
    size: '',
    color: '',
    other: '',
    default_purchase_price: '',
    default_selling_price: '',
    min_selling_price: '',
    reorder_level: '',
    status: 'active',
  },
};

const EMPTY_ADJUSTMENT: InventoryAdjustmentPayload = {
  variant_id: '',
  quantity_delta: '',
  reason: '',
  notes: '',
};


function productToReceive(product: CatalogProduct): ReceiveStockPayload {
  const primaryVariant = product.variants[0];
  return {
    mode: 'existing_variant',
    quantity: '1',
    notes: '',
    identity: {
      product_name: product.name,
      supplier: product.supplier,
      category: product.category,
      brand: product.brand,
      description: product.description,
      image_url: '',
      sku_root: product.sku_root,
      default_selling_price: valueOrEmpty(product.default_price),
      min_selling_price: valueOrEmpty(product.min_price),
      max_discount_percent: valueOrEmpty(product.max_discount_percent),
      status: product.status,
    },
    variant: {
      variant_id: primaryVariant?.variant_id,
      sku: primaryVariant?.sku ?? '',
      barcode: primaryVariant?.barcode ?? '',
      size: primaryVariant?.options.size ?? '',
      color: primaryVariant?.options.color ?? '',
      other: primaryVariant?.options.other ?? '',
      default_purchase_price: valueOrEmpty(primaryVariant?.unit_cost),
      default_selling_price: valueOrEmpty(primaryVariant?.unit_price),
      min_selling_price: valueOrEmpty(primaryVariant?.min_price),
      reorder_level: primaryVariant?.reorder_level ?? '',
      status: primaryVariant?.status ?? 'active',
    },
  };
}


export function InventoryWorkspace() {
  const searchParams = useSearchParams();
  const searchKey = searchParams.toString();
  const [activeTab, setActiveTab] = useState<InventoryTab>('stock');
  const [queryInput, setQueryInput] = useState('');
  const [workspace, setWorkspace] = useState<Awaited<ReturnType<typeof getInventoryWorkspace>> | null>(null);
  const [receiveForm, setReceiveForm] = useState<ReceiveStockPayload>({ ...EMPTY_RECEIVE });
  const [adjustmentForm, setAdjustmentForm] = useState<InventoryAdjustmentPayload>({ ...EMPTY_ADJUSTMENT });
  const [receiveQuery, setReceiveQuery] = useState('');
  const [receiveMatches, setReceiveMatches] = useState<CatalogProduct[]>([]);
  const [notice, setNotice] = useState('');
  const [error, setError] = useState('');
  const [isPending, startTransition] = useTransition();

  const loadWorkspace = (query = '') => {
    startTransition(async () => {
      try {
        const payload = await getInventoryWorkspace({ q: query });
        setWorkspace(payload);
        setError('');
      } catch (loadError) {
        setError(loadError instanceof Error ? loadError.message : 'Unable to load inventory workspace.');
      }
    });
  };

  useEffect(() => {
    const query = searchParams.get('q') ?? '';
    const tab = searchParams.get('tab');
    setQueryInput(query);
    if (tab === 'receive') {
      setActiveTab('receive');
    }
    loadWorkspace(query);
  }, [searchKey]);

  const onSearch = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    loadWorkspace(queryInput.trim());
  };

  const searchExistingRecords = async () => {
    try {
      const payload = await getCatalogWorkspace({ q: receiveQuery.trim(), includeOos: true });
      setReceiveMatches(payload.items);
      setError('');
    } catch (lookupError) {
      setError(lookupError instanceof Error ? lookupError.message : 'Unable to search existing records.');
    }
  };

  const submitReceive = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setNotice('');
    setError('');
    try {
      await receiveInventoryStock(receiveForm);
      setNotice('Stock received and ledger updated.');
      setReceiveForm({ ...EMPTY_RECEIVE });
      await loadWorkspace(queryInput.trim());
      setActiveTab('stock');
    } catch (submitError) {
      setError(submitError instanceof Error ? submitError.message : 'Unable to receive stock.');
    }
  };

  const submitAdjustment = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setNotice('');
    setError('');
    try {
      await createInventoryAdjustment(adjustmentForm);
      setNotice('Inventory adjustment recorded.');
      setAdjustmentForm({ ...EMPTY_ADJUSTMENT });
      await loadWorkspace(queryInput.trim());
      setActiveTab('stock');
    } catch (submitError) {
      setError(submitError instanceof Error ? submitError.message : 'Unable to save adjustment.');
    }
  };

  return (
    <div className="workspace-stack">
      <WorkspaceTabs
        tabs={[
          { id: 'stock', label: 'Available Stock' },
          { id: 'receive', label: 'Receive Stock' },
          { id: 'adjust', label: 'Adjustments' },
          { id: 'low-stock', label: 'Low Stock' },
        ]}
        activeTab={activeTab}
        onTabChange={setActiveTab}
      />

      <WorkspacePanel
        title="Variant-level inventory control"
        description="Only sellable stock is shown in the operating view. Receiving and adjustments stay fully auditable."
        actions={
          <form className="workspace-search" onSubmit={onSearch}>
            <input
              type="search"
              value={queryInput}
              placeholder="Search available stock by product, variant, SKU, barcode"
              onChange={(event) => setQueryInput(event.target.value)}
            />
            <button type="submit">Search</button>
          </form>
        }
      >
        {notice ? <WorkspaceNotice tone="success">{notice}</WorkspaceNotice> : null}
        {error ? <WorkspaceNotice tone="error">{error}</WorkspaceNotice> : null}
        {isPending && !workspace ? <WorkspaceNotice>Loading inventory…</WorkspaceNotice> : null}

        {activeTab === 'stock' ? (
          workspace?.stock_items.length ? (
            <div className="table-scroll">
              <table className="workspace-table">
                <thead>
                  <tr>
                    <th>Variant</th>
                    <th>Supplier</th>
                    <th>On Hand</th>
                    <th>Reserved</th>
                    <th>Available</th>
                    <th>Unit Cost</th>
                    <th>Unit Price</th>
                    <th>Quick Action</th>
                  </tr>
                </thead>
                <tbody>
                  {workspace.stock_items.map((item) => (
                    <tr key={item.variant_id}>
                      <td>{item.label}</td>
                      <td>{item.supplier || 'No supplier'}</td>
                      <td>{formatQuantity(item.on_hand)}</td>
                      <td>{formatQuantity(item.reserved)}</td>
                      <td>{formatQuantity(item.available_to_sell)}</td>
                      <td>{formatMoney(item.unit_cost)}</td>
                      <td>{formatMoney(item.unit_price)}</td>
                      <td>
                        <button
                          type="button"
                          onClick={() => {
                            setReceiveForm((current) => ({
                              ...current,
                              mode: 'existing_variant',
                              identity: {
                                ...current.identity,
                                product_name: item.product_name,
                                supplier: item.supplier,
                                category: item.category,
                                sku_root: item.sku.split('-')[0] ?? '',
                              },
                              variant: {
                                ...current.variant,
                                variant_id: item.variant_id,
                                sku: item.sku,
                                barcode: item.barcode,
                                default_purchase_price: valueOrEmpty(item.unit_cost),
                                default_selling_price: valueOrEmpty(item.unit_price),
                                reorder_level: item.reorder_level,
                              },
                            }));
                            setActiveTab('receive');
                          }}
                        >
                          Receive
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <WorkspaceEmpty
              title="No available stock"
              message="Receive stock or return sellable items to bring variants back into the operating list."
            />
          )
        ) : null}

        {activeTab === 'receive' ? (
          <div className="workspace-stack">
            <div className="workspace-inline-actions">
              <input
                type="search"
                value={receiveQuery}
                placeholder="Find existing product or variant, including OOS records"
                onChange={(event) => setReceiveQuery(event.target.value)}
              />
              <button type="button" onClick={searchExistingRecords}>Find existing record</button>
            </div>
            {receiveMatches.length ? (
              <div className="workspace-card-grid compact">
                {receiveMatches.map((product) => (
                  <article key={product.product_id} className="commerce-card compact">
                    <div className="commerce-card-header">
                      <div>
                        <h4>{product.name}</h4>
                        <p>{product.variants.length} variants available in record</p>
                      </div>
                      <button
                        type="button"
                        onClick={() => {
                          setReceiveForm(productToReceive(product));
                          setNotice('Existing record prefills loaded. You can edit before receiving.');
                        }}
                      >
                        Use details
                      </button>
                    </div>
                  </article>
                ))}
              </div>
            ) : null}

            <form className="workspace-form" onSubmit={submitReceive}>
              <div className="workspace-form-grid">
                <label>
                  Receive mode
                  <select
                    value={receiveForm.mode}
                    onChange={(event) =>
                      setReceiveForm((current) => ({
                        ...current,
                        mode: event.target.value as ReceiveStockPayload['mode'],
                      }))
                    }
                  >
                    <option value="new_product">Brand new product</option>
                    <option value="existing_product_new_variant">New variant under existing product</option>
                    <option value="existing_variant">Existing variant</option>
                  </select>
                </label>
                <label>
                  Quantity
                  <input
                    value={receiveForm.quantity}
                    onChange={(event) => setReceiveForm((current) => ({ ...current, quantity: event.target.value }))}
                    required
                  />
                </label>
                <label>
                  Product name
                  <input
                    value={receiveForm.identity.product_name}
                    onChange={(event) =>
                      setReceiveForm((current) => ({
                        ...current,
                        identity: { ...current.identity, product_name: event.target.value },
                      }))
                    }
                    required
                  />
                </label>
                <label>
                  Supplier
                  <input
                    value={receiveForm.identity.supplier}
                    onChange={(event) =>
                      setReceiveForm((current) => ({
                        ...current,
                        identity: { ...current.identity, supplier: event.target.value },
                      }))
                    }
                  />
                </label>
                <label>
                  Category
                  <input
                    value={receiveForm.identity.category}
                    onChange={(event) =>
                      setReceiveForm((current) => ({
                        ...current,
                        identity: { ...current.identity, category: event.target.value },
                      }))
                    }
                  />
                </label>
                <label>
                  Brand
                  <input
                    value={receiveForm.identity.brand}
                    onChange={(event) =>
                      setReceiveForm((current) => ({
                        ...current,
                        identity: { ...current.identity, brand: event.target.value },
                      }))
                    }
                  />
                </label>
                <label>
                  SKU
                  <input
                    value={receiveForm.variant.sku}
                    onChange={(event) =>
                      setReceiveForm((current) => ({
                        ...current,
                        variant: { ...current.variant, sku: event.target.value },
                      }))
                    }
                    required
                  />
                </label>
                <label>
                  Barcode
                  <input
                    value={receiveForm.variant.barcode}
                    onChange={(event) =>
                      setReceiveForm((current) => ({
                        ...current,
                        variant: { ...current.variant, barcode: event.target.value },
                      }))
                    }
                  />
                </label>
                <label>
                  Size
                  <input
                    value={receiveForm.variant.size}
                    onChange={(event) =>
                      setReceiveForm((current) => ({
                        ...current,
                        variant: { ...current.variant, size: event.target.value },
                      }))
                    }
                  />
                </label>
                <label>
                  Color
                  <input
                    value={receiveForm.variant.color}
                    onChange={(event) =>
                      setReceiveForm((current) => ({
                        ...current,
                        variant: { ...current.variant, color: event.target.value },
                      }))
                    }
                  />
                </label>
                <label>
                  Other
                  <input
                    value={receiveForm.variant.other}
                    onChange={(event) =>
                      setReceiveForm((current) => ({
                        ...current,
                        variant: { ...current.variant, other: event.target.value },
                      }))
                    }
                  />
                </label>
                <label>
                  Unit cost
                  <input
                    value={receiveForm.variant.default_purchase_price}
                    onChange={(event) =>
                      setReceiveForm((current) => ({
                        ...current,
                        variant: { ...current.variant, default_purchase_price: event.target.value },
                      }))
                    }
                  />
                </label>
                <label>
                  Unit price
                  <input
                    value={receiveForm.variant.default_selling_price}
                    onChange={(event) =>
                      setReceiveForm((current) => ({
                        ...current,
                        variant: { ...current.variant, default_selling_price: event.target.value },
                      }))
                    }
                  />
                </label>
                <label>
                  Reorder level
                  <input
                    value={receiveForm.variant.reorder_level}
                    onChange={(event) =>
                      setReceiveForm((current) => ({
                        ...current,
                        variant: { ...current.variant, reorder_level: event.target.value },
                      }))
                    }
                  />
                </label>
              </div>
              <label>
                Receive notes
                <textarea
                  rows={3}
                  value={receiveForm.notes}
                  onChange={(event) => setReceiveForm((current) => ({ ...current, notes: event.target.value }))}
                />
              </label>
              <div className="workspace-actions">
                <button type="submit">Receive stock</button>
                <button type="button" onClick={() => setReceiveForm({ ...EMPTY_RECEIVE })}>Reset form</button>
              </div>
            </form>
          </div>
        ) : null}

        {activeTab === 'adjust' ? (
          <form className="workspace-form" onSubmit={submitAdjustment}>
            <div className="workspace-form-grid">
              <label>
                Variant
                <select
                  value={adjustmentForm.variant_id}
                  onChange={(event) => setAdjustmentForm((current) => ({ ...current, variant_id: event.target.value }))}
                  required
                >
                  <option value="">Select a variant</option>
                  {workspace?.stock_items.map((item) => (
                    <option key={item.variant_id} value={item.variant_id}>
                      {item.label}
                    </option>
                  ))}
                </select>
              </label>
              <label>
                Quantity delta
                <input
                  value={adjustmentForm.quantity_delta}
                  placeholder="Use negative for loss or positive for recount gain"
                  onChange={(event) =>
                    setAdjustmentForm((current) => ({ ...current, quantity_delta: event.target.value }))
                  }
                  required
                />
              </label>
              <label>
                Reason
                <input
                  value={adjustmentForm.reason}
                  onChange={(event) => setAdjustmentForm((current) => ({ ...current, reason: event.target.value }))}
                  required
                />
              </label>
            </div>
            <label>
              Notes
              <textarea
                rows={3}
                value={adjustmentForm.notes}
                onChange={(event) => setAdjustmentForm((current) => ({ ...current, notes: event.target.value }))}
              />
            </label>
            <div className="workspace-actions">
              <button type="submit">Record adjustment</button>
            </div>
          </form>
        ) : null}

        {activeTab === 'low-stock' ? (
          workspace?.low_stock_items.length ? (
            <div className="table-scroll">
              <table className="workspace-table">
                <thead>
                  <tr>
                    <th>Variant</th>
                    <th>Available</th>
                    <th>Reorder Level</th>
                    <th>Supplier</th>
                  </tr>
                </thead>
                <tbody>
                  {workspace.low_stock_items.map((item) => (
                    <tr key={item.variant_id}>
                      <td>{item.label}</td>
                      <td>{formatQuantity(item.available_to_sell)}</td>
                      <td>{formatQuantity(item.reorder_level)}</td>
                      <td>{item.supplier || 'No supplier'}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <WorkspaceEmpty
              title="No low-stock variants"
              message="Everything currently sits above its reorder trigger."
            />
          )
        ) : null}
      </WorkspacePanel>
    </div>
  );
}
