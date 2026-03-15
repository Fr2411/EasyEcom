'use client';

import Link from 'next/link';
import { FormEvent, useEffect, useMemo, useState, useTransition } from 'react';
import { useSearchParams } from 'next/navigation';
import { useAuth } from '@/components/auth/auth-provider';
import {
  createInventoryAdjustment,
  getInventoryIntakeLookup,
  getInventoryWorkspace,
  receiveInventoryStock,
} from '@/lib/api/commerce';
import type { CatalogProduct, CatalogVariant, ProductIdentityInput } from '@/types/catalog';
import type {
  InventoryAdjustmentPayload,
  InventoryIntakeExactVariantMatch,
  InventoryIntakeIdentityInput,
  ReceiveStockLineInput,
  ReceiveStockPayload,
} from '@/types/inventory';
import { WorkspaceEmpty, WorkspaceNotice, WorkspacePanel, WorkspaceTabs } from '@/components/commerce/workspace-primitives';
import { formatMoney, formatQuantity } from '@/lib/commerce-format';
import { buildSkuPreview, buildVariantCombinations, signatureForVariant } from '@/lib/variant-generator';


type InventoryTab = 'stock' | 'receive' | 'adjust' | 'low-stock';

type IntakeGeneratorState = {
  size_values: string;
  color_values: string;
  other_values: string;
  quantity: string;
  default_purchase_price: string;
  default_selling_price: string;
  min_selling_price: string;
  reorder_level: string;
};

const EMPTY_IDENTITY: InventoryIntakeIdentityInput = {
  product_name: '',
  product_id: '',
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
};

const EMPTY_LINE: ReceiveStockLineInput = {
  variant_id: '',
  sku: '',
  barcode: '',
  size: '',
  color: '',
  other: '',
  quantity: '1',
  default_purchase_price: '',
  default_selling_price: '',
  min_selling_price: '',
  reorder_level: '',
  status: 'active',
};

const EMPTY_GENERATOR: IntakeGeneratorState = {
  size_values: '',
  color_values: '',
  other_values: '',
  quantity: '1',
  default_purchase_price: '',
  default_selling_price: '',
  min_selling_price: '',
  reorder_level: '',
};

const EMPTY_ADJUSTMENT: InventoryAdjustmentPayload = {
  variant_id: '',
  quantity_delta: '',
  reason: '',
  notes: '',
};

function createEmptyReceive(): ReceiveStockPayload {
  return {
    action: 'receive_stock',
    notes: '',
    update_matched_product_details: false,
    identity: { ...EMPTY_IDENTITY },
    lines: [],
  };
}

function valueOrEmpty(value: string | null | undefined) {
  return value ?? '';
}

function firstFilled(values: Array<string | null | undefined>) {
  return values.find((value) => Boolean(value && value.trim())) ?? '';
}

function variantTitle(variant: { size: string; color: string; other: string }) {
  return [variant.size, variant.color, variant.other].filter((value) => value.trim()).join(' / ') || 'Default';
}

function productIdentityFromCatalog(product: CatalogProduct): InventoryIntakeIdentityInput {
  return {
    product_id: product.product_id,
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
  };
}

function lineFromExistingVariant(variant: CatalogVariant): ReceiveStockLineInput {
  return {
    variant_id: variant.variant_id,
    sku: variant.sku,
    barcode: variant.barcode,
    size: variant.options.size,
    color: variant.options.color,
    other: variant.options.other,
    quantity: '1',
    default_purchase_price: valueOrEmpty(variant.unit_cost),
    default_selling_price: valueOrEmpty(variant.unit_price ?? variant.effective_unit_price),
    min_selling_price: valueOrEmpty(variant.min_price ?? variant.effective_min_price),
    reorder_level: variant.reorder_level,
    status: variant.status,
  };
}

function generatorFromProduct(product: CatalogProduct): IntakeGeneratorState {
  return {
    size_values: Array.from(new Set(product.variants.map((variant) => variant.options.size).filter(Boolean))).join(', '),
    color_values: Array.from(new Set(product.variants.map((variant) => variant.options.color).filter(Boolean))).join(', '),
    other_values: Array.from(new Set(product.variants.map((variant) => variant.options.other).filter(Boolean))).join(', '),
    quantity: '1',
    default_purchase_price: firstFilled(product.variants.map((variant) => variant.unit_cost)),
    default_selling_price: firstFilled([
      ...product.variants.map((variant) => variant.unit_price ?? variant.effective_unit_price),
      product.default_price,
    ]),
    min_selling_price: firstFilled([
      ...product.variants.map((variant) => variant.min_price ?? variant.effective_min_price),
      product.min_price,
    ]),
    reorder_level: firstFilled(product.variants.map((variant) => variant.reorder_level)),
  };
}

function newLineFromCombo(
  combo: { size: string; color: string; other: string },
  generator: IntakeGeneratorState,
  identity: ProductIdentityInput
): ReceiveStockLineInput {
  return {
    ...EMPTY_LINE,
    size: combo.size,
    color: combo.color,
    other: combo.other,
    quantity: generator.quantity || '1',
    default_purchase_price: generator.default_purchase_price,
    default_selling_price: generator.default_selling_price || identity.default_selling_price,
    min_selling_price: generator.min_selling_price || identity.min_selling_price,
    reorder_level: generator.reorder_level,
  };
}

function cloneLine(line: ReceiveStockLineInput): ReceiveStockLineInput {
  return { ...line };
}

function isNewVariantLine(line: ReceiveStockLineInput) {
  return !line.variant_id;
}

function hasTemplateEligibleLine(lines: ReceiveStockLineInput[]) {
  return lines.some((line) => isNewVariantLine(line));
}

function canSaveTemplateOnly(roles: string[] | undefined) {
  return Boolean(roles?.includes('SUPER_ADMIN') || roles?.includes('CLIENT_OWNER'));
}

function lineKey(line: ReceiveStockLineInput) {
  return line.variant_id ? `variant:${line.variant_id}` : `new:${signatureForVariant(line)}`;
}

function advancedCatalogAllowed(roles: string[] | undefined) {
  return Boolean(roles?.includes('SUPER_ADMIN') || roles?.includes('CLIENT_OWNER'));
}

export function InventoryWorkspace() {
  const { user } = useAuth();
  const searchParams = useSearchParams();
  const searchKey = searchParams.toString();
  const [activeTab, setActiveTab] = useState<InventoryTab>('stock');
  const [queryInput, setQueryInput] = useState('');
  const [workspace, setWorkspace] = useState<Awaited<ReturnType<typeof getInventoryWorkspace>> | null>(null);
  const [receiveForm, setReceiveForm] = useState<ReceiveStockPayload>(createEmptyReceive());
  const [adjustmentForm, setAdjustmentForm] = useState<InventoryAdjustmentPayload>({ ...EMPTY_ADJUSTMENT });
  const [intakeQuery, setIntakeQuery] = useState('');
  const [intakeResults, setIntakeResults] = useState<Awaited<ReturnType<typeof getInventoryIntakeLookup>> | null>(null);
  const [selectedProduct, setSelectedProduct] = useState<CatalogProduct | null>(null);
  const [generator, setGenerator] = useState<IntakeGeneratorState>({ ...EMPTY_GENERATOR });
  const [notice, setNotice] = useState('');
  const [error, setError] = useState('');
  const [lookupPending, setLookupPending] = useState(false);
  const [submitPending, setSubmitPending] = useState(false);
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

  const resetReceiveFlow = () => {
    setReceiveForm(createEmptyReceive());
    setSelectedProduct(null);
    setGenerator({ ...EMPTY_GENERATOR });
    setIntakeResults(null);
    setIntakeQuery('');
  };

  const beginNewProduct = (seed?: { product_name: string; sku_root: string } | null) => {
    setSelectedProduct(null);
    setReceiveForm({
      action: 'receive_stock',
      notes: '',
      update_matched_product_details: false,
      identity: {
        ...EMPTY_IDENTITY,
        product_name: seed?.product_name ?? '',
        sku_root: seed?.sku_root ?? '',
      },
      lines: [],
    });
    setGenerator({ ...EMPTY_GENERATOR });
    setNotice('');
    setError('');
  };

  const beginExistingProduct = (product: CatalogProduct, initialLines: ReceiveStockLineInput[] = []) => {
    setSelectedProduct(product);
    setReceiveForm({
      action: 'receive_stock',
      notes: '',
      update_matched_product_details: false,
      identity: productIdentityFromCatalog(product),
      lines: initialLines.map(cloneLine),
    });
    setGenerator(generatorFromProduct(product));
    setNotice('');
    setError('');
  };

  const runIntakeLookup = async (query: string) => {
    const trimmed = query.trim();
    if (!trimmed) {
      setIntakeResults(null);
      return null;
    }
    setLookupPending(true);
    try {
      const payload = await getInventoryIntakeLookup({ q: trimmed });
      setIntakeResults(payload);
      setError('');
      return payload;
    } catch (lookupError) {
      setError(lookupError instanceof Error ? lookupError.message : 'Unable to search intake records.');
      return null;
    } finally {
      setLookupPending(false);
    }
  };

  const onIntakeSearch = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    await runIntakeLookup(intakeQuery);
  };

  const addExistingVariantLine = (variant: CatalogVariant) => {
    setReceiveForm((current) => {
      if (current.lines.some((line) => line.variant_id === variant.variant_id)) {
        return current;
      }
      return {
        ...current,
        lines: [...current.lines, lineFromExistingVariant(variant)],
      };
    });
    setNotice(`Added ${variant.label} to the receipt.`);
  };

  const openExactVariantMatch = (match: InventoryIntakeExactVariantMatch) => {
    beginExistingProduct(match.product, [lineFromExistingVariant(match.variant)]);
  };

  const openQuickReceive = async (lookupValue: string) => {
    const payload = await runIntakeLookup(lookupValue);
    if (!payload) {
      return;
    }
    const exact = payload.exact_variants[0];
    if (exact) {
      openExactVariantMatch(exact);
      setIntakeQuery(lookupValue);
      setActiveTab('receive');
      return;
    }
    if (payload.product_matches[0]) {
      beginExistingProduct(payload.product_matches[0]);
      setIntakeQuery(lookupValue);
      setActiveTab('receive');
    }
  };

  const generatedCombos = useMemo(() => buildVariantCombinations(generator), [generator]);
  const existingVariantBySignature = useMemo(() => {
    const map = new Map<string, CatalogVariant>();
    selectedProduct?.variants.forEach((variant) => {
      map.set(signatureForVariant(variant.options), variant);
    });
    return map;
  }, [selectedProduct]);

  const applyGenerator = () => {
    setReceiveForm((current) => {
      const indexed = new Set(current.lines.map(lineKey));
      const next = current.lines.map(cloneLine);
      generatedCombos.forEach((combo) => {
        const existingVariant = existingVariantBySignature.get(signatureForVariant(combo));
        if (existingVariant) {
          const existingKey = `variant:${existingVariant.variant_id}`;
          if (!indexed.has(existingKey)) {
            next.push(lineFromExistingVariant(existingVariant));
            indexed.add(existingKey);
          }
          return;
        }
        const created = newLineFromCombo(combo, generator, current.identity);
        const key = lineKey(created);
        if (!indexed.has(key)) {
          next.push(created);
          indexed.add(key);
        }
      });
      return { ...current, lines: next };
    });
    setNotice('Generator merged variants into the receipt review.');
  };

  const applyDefaultsToLines = (scope: 'empty' | 'all') => {
    setReceiveForm((current) => ({
      ...current,
      lines: current.lines.map((line) => {
        const next = { ...line };
        const shouldWrite = (value: string) => scope === 'all' || !value.trim();
        if (generator.quantity.trim() && shouldWrite(next.quantity)) {
          next.quantity = generator.quantity;
        }
        if (generator.default_purchase_price.trim() && shouldWrite(next.default_purchase_price)) {
          next.default_purchase_price = generator.default_purchase_price;
        }
        if (isNewVariantLine(next) && generator.default_selling_price.trim() && shouldWrite(next.default_selling_price)) {
          next.default_selling_price = generator.default_selling_price;
        }
        if (isNewVariantLine(next) && generator.min_selling_price.trim() && shouldWrite(next.min_selling_price)) {
          next.min_selling_price = generator.min_selling_price;
        }
        if (isNewVariantLine(next) && generator.reorder_level.trim() && shouldWrite(next.reorder_level)) {
          next.reorder_level = generator.reorder_level;
        }
        return next;
      }),
    }));
    setNotice(scope === 'all' ? 'Generator defaults applied to all receipt lines.' : 'Generator defaults filled empty receipt fields.');
  };

  const submitReceive = async (action: ReceiveStockPayload['action']) => {
    if (!receiveForm.identity.product_name.trim()) {
      setError('Select or create a product before reviewing variants.');
      return;
    }
    if (!receiveForm.lines.length) {
      setError('Add at least one existing or generated variant line before saving.');
      return;
    }
    setSubmitPending(true);
    setNotice('');
    setError('');
    try {
      const response = await receiveInventoryStock({
        ...receiveForm,
        action,
      });
      setNotice(
        action === 'save_template_only'
          ? 'Template saved without stock movement. You can receive quantities later.'
          : `Stock received successfully under ${response.purchase_number}.`
      );
      resetReceiveFlow();
      await loadWorkspace(queryInput.trim());
      if (action === 'receive_stock') {
        setActiveTab('stock');
      }
    } catch (submitError) {
      setError(submitError instanceof Error ? submitError.message : 'Unable to save intake.');
    } finally {
      setSubmitPending(false);
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

  const canEditSavedDetails = !selectedProduct || receiveForm.update_matched_product_details;
  const showAdvancedCatalog = advancedCatalogAllowed(user?.roles);
  const templateAllowed = canSaveTemplateOnly(user?.roles);
  const templateDisabled = !hasTemplateEligibleLine(receiveForm.lines);

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
        description="Use Receive Stock as the main intake flow, then keep every stock movement auditable."
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
                            void openQuickReceive(item.sku);
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
            <section className="workspace-subsection">
              <div className="workspace-subsection-header">
                <div>
                  <h4>Find or Create Item</h4>
                  <p>Search by barcode, SKU, product name, or product plus variant text before creating anything new.</p>
                </div>
                {showAdvancedCatalog ? (
                  <Link href="/catalog" className="nav-link">
                    Open Advanced Catalog
                  </Link>
                ) : null}
              </div>

              <form className="workspace-inline-actions" onSubmit={onIntakeSearch}>
                <input
                  type="search"
                  value={intakeQuery}
                  placeholder="Search barcode, SKU, or product / variant"
                  onChange={(event) => setIntakeQuery(event.target.value)}
                />
                <button type="submit" disabled={lookupPending}>
                  {lookupPending ? 'Searching…' : 'Find item'}
                </button>
                <button
                  type="button"
                  onClick={() => beginNewProduct(intakeResults?.suggested_new_product ?? null)}
                  disabled={!intakeQuery.trim() && !intakeResults?.suggested_new_product}
                >
                  Create new item
                </button>
              </form>

              {!intakeResults ? (
                <WorkspaceNotice>Start with a search so we can match an existing record safely before creating a new one.</WorkspaceNotice>
              ) : null}

              {intakeResults?.exact_variants.length ? (
                <div className="workspace-stack">
                  <p className="eyebrow">Exact Variant Matches</p>
                  <div className="workspace-card-grid compact">
                    {intakeResults.exact_variants.map((match) => (
                      <article key={`${match.variant.variant_id}-${match.match_reason}`} className="commerce-card compact">
                        <div className="commerce-card-header">
                          <div>
                            <h4>{match.variant.label}</h4>
                            <p>
                              Matched by {match.match_reason} · SKU {match.variant.sku} · Available {formatQuantity(match.variant.available_to_sell)}
                            </p>
                          </div>
                          <button type="button" onClick={() => openExactVariantMatch(match)}>
                            Use variant
                          </button>
                        </div>
                      </article>
                    ))}
                  </div>
                </div>
              ) : null}

              {intakeResults?.product_matches.length ? (
                <div className="workspace-stack">
                  <p className="eyebrow">Existing Products</p>
                  <div className="workspace-card-grid compact">
                    {intakeResults.product_matches.map((product) => (
                      <article key={product.product_id} className="commerce-card compact">
                        <div className="commerce-card-header">
                          <div>
                            <h4>{product.name}</h4>
                            <p>
                              {product.variants.length} saved variants · Supplier {product.supplier || 'Not set'} · Category {product.category || 'Not set'}
                            </p>
                          </div>
                          <button type="button" onClick={() => beginExistingProduct(product)}>
                            Use product
                          </button>
                        </div>
                      </article>
                    ))}
                  </div>
                </div>
              ) : null}

              {intakeResults?.suggested_new_product ? (
                <article className="commerce-card compact">
                  <div className="commerce-card-header">
                    <div>
                      <p className="eyebrow">Create New Product</p>
                      <h4>{intakeResults.suggested_new_product.product_name}</h4>
                      <p>We did not attach this automatically. Start a new item only if the existing matches above are not correct.</p>
                    </div>
                    <button type="button" onClick={() => beginNewProduct(intakeResults.suggested_new_product)}>
                      Start new item
                    </button>
                  </div>
                </article>
              ) : null}
            </section>

            {receiveForm.identity.product_name ? (
              <section className="workspace-subsection">
                <div className="workspace-subsection-header">
                  <div>
                    <h4>Review Variants and Receive</h4>
                    <p>Receive existing variants or generate new ones under the selected product before posting one auditable receipt.</p>
                  </div>
                </div>

                {selectedProduct ? (
                  <WorkspaceNotice>
                    Saved product details are locked by default so warehouse users do not accidentally rewrite your catalog.
                  </WorkspaceNotice>
                ) : null}

                {selectedProduct ? (
                  <label className="workspace-toggle">
                    <input
                      type="checkbox"
                      checked={receiveForm.update_matched_product_details}
                      onChange={(event) =>
                        setReceiveForm((current) => ({
                          ...current,
                          update_matched_product_details: event.target.checked,
                        }))
                      }
                    />
                    Edit saved product details
                  </label>
                ) : null}

                {selectedProduct?.variants.length ? (
                  <div className="workspace-stack">
                    <p className="eyebrow">Saved Variants</p>
                    <div className="table-scroll">
                      <table className="workspace-table">
                        <thead>
                          <tr>
                            <th>Variant</th>
                            <th>SKU</th>
                            <th>Available</th>
                            <th>Cost</th>
                            <th>Price</th>
                            <th>Action</th>
                          </tr>
                        </thead>
                        <tbody>
                          {selectedProduct.variants.map((variant) => (
                            <tr key={variant.variant_id}>
                              <td>{variant.label}</td>
                              <td>{variant.sku}</td>
                              <td>{formatQuantity(variant.available_to_sell)}</td>
                              <td>{formatMoney(variant.unit_cost)}</td>
                              <td>{formatMoney(variant.effective_unit_price)}</td>
                              <td>
                                <button type="button" onClick={() => addExistingVariantLine(variant)}>
                                  Add line
                                </button>
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  </div>
                ) : null}

                <div className="workspace-subsection">
                  <div className="workspace-subsection-header">
                    <div>
                      <h4>Variant Generator</h4>
                      <p>Enter comma-separated values to generate multiple variants at once. Existing option combinations will reuse saved variants automatically.</p>
                    </div>
                  </div>
                  <div className="workspace-form-grid">
                    <label>
                      Sizes
                      <input
                        value={generator.size_values}
                        onChange={(event) => setGenerator((current) => ({ ...current, size_values: event.target.value }))}
                        placeholder="40, 41, 42"
                      />
                    </label>
                    <label>
                      Colors
                      <input
                        value={generator.color_values}
                        onChange={(event) => setGenerator((current) => ({ ...current, color_values: event.target.value }))}
                        placeholder="Black, White"
                      />
                    </label>
                    <label>
                      Other
                      <input
                        value={generator.other_values}
                        onChange={(event) => setGenerator((current) => ({ ...current, other_values: event.target.value }))}
                        placeholder="Men, Women, Wide"
                      />
                    </label>
                    <label>
                      Default quantity
                      <input
                        value={generator.quantity}
                        onChange={(event) => setGenerator((current) => ({ ...current, quantity: event.target.value }))}
                      />
                    </label>
                    <label>
                      Default unit cost
                      <input
                        value={generator.default_purchase_price}
                        onChange={(event) =>
                          setGenerator((current) => ({ ...current, default_purchase_price: event.target.value }))
                        }
                      />
                    </label>
                    <label>
                      Default price
                      <input
                        value={generator.default_selling_price}
                        onChange={(event) =>
                          setGenerator((current) => ({ ...current, default_selling_price: event.target.value }))
                        }
                      />
                    </label>
                    <label>
                      Minimum price
                      <input
                        value={generator.min_selling_price}
                        onChange={(event) =>
                          setGenerator((current) => ({ ...current, min_selling_price: event.target.value }))
                        }
                      />
                    </label>
                    <label>
                      Reorder level
                      <input
                        value={generator.reorder_level}
                        onChange={(event) => setGenerator((current) => ({ ...current, reorder_level: event.target.value }))}
                      />
                    </label>
                  </div>
                  <div className="workspace-actions">
                    <button type="button" onClick={applyGenerator}>Generate variants</button>
                    <button type="button" onClick={() => applyDefaultsToLines('empty')}>Fill empty line fields</button>
                    <button type="button" onClick={() => applyDefaultsToLines('all')}>Overwrite all line defaults</button>
                  </div>
                </div>

                <form
                  className="workspace-form"
                  onSubmit={(event) => {
                    event.preventDefault();
                    void submitReceive('receive_stock');
                  }}
                >
                  <div className="workspace-subsection">
                    <div className="workspace-subsection-header">
                      <div>
                        <h4>Product Details</h4>
                        <p>Shared identity and pricing defaults for this intake.</p>
                      </div>
                    </div>
                    <div className="workspace-form-grid">
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
                          disabled={!canEditSavedDetails}
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
                          disabled={!canEditSavedDetails}
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
                          disabled={!canEditSavedDetails}
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
                          disabled={!canEditSavedDetails}
                        />
                      </label>
                      <label>
                        SKU Base
                        <input
                          value={receiveForm.identity.sku_root}
                          onChange={(event) =>
                            setReceiveForm((current) => ({
                              ...current,
                              identity: { ...current.identity, sku_root: event.target.value },
                            }))
                          }
                          disabled={!canEditSavedDetails}
                        />
                      </label>
                      <label>
                        Default selling price
                        <input
                          value={receiveForm.identity.default_selling_price}
                          onChange={(event) =>
                            setReceiveForm((current) => ({
                              ...current,
                              identity: { ...current.identity, default_selling_price: event.target.value },
                            }))
                          }
                          disabled={!canEditSavedDetails}
                        />
                      </label>
                      <label>
                        Minimum selling price
                        <input
                          value={receiveForm.identity.min_selling_price}
                          onChange={(event) =>
                            setReceiveForm((current) => ({
                              ...current,
                              identity: { ...current.identity, min_selling_price: event.target.value },
                            }))
                          }
                          disabled={!canEditSavedDetails}
                        />
                      </label>
                    </div>
                  </div>

                  <div className="workspace-subsection">
                    <div className="workspace-subsection-header">
                      <div>
                        <h4>Receipt Lines</h4>
                        <p>Each line becomes one purchase item. Existing variants keep their saved identity; new variants can be edited before saving.</p>
                      </div>
                    </div>

                    {receiveForm.lines.length ? (
                      <div className="workspace-card-grid">
                        {receiveForm.lines.map((line, index) => {
                          const isExisting = Boolean(line.variant_id);
                          const previewSku = buildSkuPreview(receiveForm.identity.product_name, receiveForm.identity.sku_root, line);
                          return (
                            <article key={lineKey(line)} className="commerce-card">
                              <div className="commerce-card-header">
                                <div>
                                  <p className="eyebrow">{isExisting ? 'Existing variant' : 'New variant'}</p>
                                  <h4>{variantTitle(line)}</h4>
                                  <p>{previewSku}</p>
                                </div>
                                <button
                                  type="button"
                                  onClick={() =>
                                    setReceiveForm((current) => ({
                                      ...current,
                                      lines: current.lines.filter((_, currentIndex) => currentIndex !== index),
                                    }))
                                  }
                                >
                                  Remove line
                                </button>
                              </div>

                              <div className="workspace-form-grid">
                                <label>
                                  Quantity
                                  <input
                                    value={line.quantity}
                                    onChange={(event) =>
                                      setReceiveForm((current) => ({
                                        ...current,
                                        lines: current.lines.map((item, currentIndex) =>
                                          currentIndex === index ? { ...item, quantity: event.target.value } : item
                                        ),
                                      }))
                                    }
                                    required
                                  />
                                </label>
                                <label>
                                  Unit cost
                                  <input
                                    value={line.default_purchase_price}
                                    onChange={(event) =>
                                      setReceiveForm((current) => ({
                                        ...current,
                                        lines: current.lines.map((item, currentIndex) =>
                                          currentIndex === index
                                            ? { ...item, default_purchase_price: event.target.value }
                                            : item
                                        ),
                                      }))
                                    }
                                    required
                                  />
                                </label>
                                <label>
                                  SKU
                                  <input value={previewSku} disabled />
                                </label>
                                <label>
                                  Barcode
                                  <input
                                    value={line.barcode}
                                    onChange={(event) =>
                                      setReceiveForm((current) => ({
                                        ...current,
                                        lines: current.lines.map((item, currentIndex) =>
                                          currentIndex === index ? { ...item, barcode: event.target.value } : item
                                        ),
                                      }))
                                    }
                                    disabled={isExisting}
                                  />
                                </label>
                                <label>
                                  Size
                                  <input
                                    value={line.size}
                                    onChange={(event) =>
                                      setReceiveForm((current) => ({
                                        ...current,
                                        lines: current.lines.map((item, currentIndex) =>
                                          currentIndex === index ? { ...item, size: event.target.value } : item
                                        ),
                                      }))
                                    }
                                    disabled={isExisting}
                                  />
                                </label>
                                <label>
                                  Color
                                  <input
                                    value={line.color}
                                    onChange={(event) =>
                                      setReceiveForm((current) => ({
                                        ...current,
                                        lines: current.lines.map((item, currentIndex) =>
                                          currentIndex === index ? { ...item, color: event.target.value } : item
                                        ),
                                      }))
                                    }
                                    disabled={isExisting}
                                  />
                                </label>
                                <label>
                                  Other
                                  <input
                                    value={line.other}
                                    onChange={(event) =>
                                      setReceiveForm((current) => ({
                                        ...current,
                                        lines: current.lines.map((item, currentIndex) =>
                                          currentIndex === index ? { ...item, other: event.target.value } : item
                                        ),
                                      }))
                                    }
                                    disabled={isExisting}
                                  />
                                </label>
                                <label>
                                  Selling price
                                  <input
                                    value={line.default_selling_price}
                                    onChange={(event) =>
                                      setReceiveForm((current) => ({
                                        ...current,
                                        lines: current.lines.map((item, currentIndex) =>
                                          currentIndex === index
                                            ? { ...item, default_selling_price: event.target.value }
                                            : item
                                        ),
                                      }))
                                    }
                                    disabled={isExisting}
                                  />
                                </label>
                                <label>
                                  Minimum price
                                  <input
                                    value={line.min_selling_price}
                                    onChange={(event) =>
                                      setReceiveForm((current) => ({
                                        ...current,
                                        lines: current.lines.map((item, currentIndex) =>
                                          currentIndex === index
                                            ? { ...item, min_selling_price: event.target.value }
                                            : item
                                        ),
                                      }))
                                    }
                                    disabled={isExisting}
                                  />
                                </label>
                                <label>
                                  Reorder level
                                  <input
                                    value={line.reorder_level}
                                    onChange={(event) =>
                                      setReceiveForm((current) => ({
                                        ...current,
                                        lines: current.lines.map((item, currentIndex) =>
                                          currentIndex === index ? { ...item, reorder_level: event.target.value } : item
                                        ),
                                      }))
                                    }
                                    disabled={isExisting}
                                  />
                                </label>
                              </div>
                            </article>
                          );
                        })}
                      </div>
                    ) : (
                      <WorkspaceEmpty
                        title="No receipt lines yet"
                        message="Add an existing variant or use the generator above to create the lines you want to receive."
                      />
                    )}
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
                    <button type="submit" disabled={submitPending}>
                      {submitPending ? 'Saving…' : 'Receive stock'}
                    </button>
                    {templateAllowed ? (
                      <button
                        type="button"
                        disabled={submitPending || templateDisabled}
                        onClick={() => {
                          void submitReceive('save_template_only');
                        }}
                      >
                        Save as template only
                      </button>
                    ) : null}
                    <button
                      type="button"
                      onClick={() => {
                        resetReceiveFlow();
                        setNotice('');
                        setError('');
                      }}
                    >
                      Reset intake
                    </button>
                  </div>
                </form>
              </section>
            ) : null}
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
