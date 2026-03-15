'use client';

import { FormEvent, useEffect, useMemo, useState, useTransition } from 'react';
import { useSearchParams } from 'next/navigation';
import { ApiError } from '@/lib/api/client';
import { getCatalogWorkspace, saveCatalogProduct } from '@/lib/api/commerce';
import { buildSkuPreview, buildVariantCombinations, signatureForVariant, type VariantOptionValues } from '@/lib/variant-generator';
import type {
  CatalogProduct,
  CatalogUpsertPayload,
  CatalogVariantInput,
  ProductIdentityInput,
  VariantOptions,
} from '@/types/catalog';
import { WorkspaceEmpty, WorkspaceNotice, WorkspacePanel, WorkspaceTabs, WorkspaceToast } from '@/components/commerce/workspace-primitives';
import { formatMoney, formatPercent, formatQuantity, numberFromString } from '@/lib/commerce-format';


type CatalogTab = 'products' | 'edit';

type VariantGeneratorState = {
  size_values: string;
  color_values: string;
  other_values: string;
  default_purchase_price: string;
  default_selling_price: string;
  min_selling_price: string;
  reorder_level: string;
};

type VariantCombo = VariantOptionValues;

const EMPTY_IDENTITY: ProductIdentityInput = {
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
};

const EMPTY_VARIANT: CatalogVariantInput = {
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
};

const EMPTY_GENERATOR: VariantGeneratorState = {
  size_values: '',
  color_values: '',
  other_values: '',
  default_purchase_price: '',
  default_selling_price: '',
  min_selling_price: '',
  reorder_level: '',
};


function valueOrEmpty(value: string | null | undefined) {
  return value ?? '';
}


function firstFilled(values: Array<string | null | undefined>) {
  return values.find((value) => Boolean(value && value.trim())) ?? '';
}


function isUntouchedDefaultVariant(variant: CatalogVariantInput) {
  return !variant.variant_id
    && !variant.size.trim()
    && !variant.color.trim()
    && !variant.other.trim()
    && !variant.sku.trim()
    && !variant.barcode.trim()
    && !variant.default_purchase_price.trim()
    && !variant.default_selling_price.trim()
    && !variant.min_selling_price.trim()
    && !variant.reorder_level.trim()
    && variant.status === 'active';
}


function calculateDerivedDiscount(defaultPrice: string, minPrice: string) {
  const defaultValue = numberFromString(defaultPrice);
  const minValue = numberFromString(minPrice);
  if (!defaultPrice.trim() || !minPrice.trim() || defaultValue <= 0) return '';
  const percent = ((defaultValue - minValue) / defaultValue) * 100;
  return Number.isFinite(percent) && percent >= 0 ? percent.toFixed(2) : '';
}


function variantToInput(options: VariantOptions, variant: CatalogProduct['variants'][number]): CatalogVariantInput {
  return {
    variant_id: variant.variant_id,
    sku: variant.sku,
    barcode: variant.barcode,
    size: options.size,
    color: options.color,
    other: options.other,
    default_purchase_price: valueOrEmpty(variant.unit_cost),
    default_selling_price: valueOrEmpty(variant.unit_price),
    min_selling_price: valueOrEmpty(variant.min_price),
    reorder_level: variant.reorder_level,
    status: variant.status,
  };
}


function productToPayload(product: CatalogProduct): CatalogUpsertPayload {
  return {
    product_id: product.product_id,
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
    variants: product.variants.map((variant) => variantToInput(variant.options, variant)),
  };
}


function generatorFromProduct(product: CatalogProduct): VariantGeneratorState {
  const payload = productToPayload(product);
  return {
    size_values: Array.from(new Set(payload.variants.map((variant) => variant.size).filter(Boolean))).join(', '),
    color_values: Array.from(new Set(payload.variants.map((variant) => variant.color).filter(Boolean))).join(', '),
    other_values: Array.from(new Set(payload.variants.map((variant) => variant.other).filter(Boolean))).join(', '),
    default_purchase_price: firstFilled(payload.variants.map((variant) => variant.default_purchase_price)),
    default_selling_price: firstFilled([
      ...payload.variants.map((variant) => variant.default_selling_price),
      payload.identity.default_selling_price,
    ]),
    min_selling_price: firstFilled([
      ...payload.variants.map((variant) => variant.min_selling_price),
      payload.identity.min_selling_price,
    ]),
    reorder_level: firstFilled(payload.variants.map((variant) => variant.reorder_level)),
  };
}


function newVariantFromCombo(
  combo: VariantCombo,
  generator: VariantGeneratorState,
  identity: ProductIdentityInput
): CatalogVariantInput {
  return {
    ...EMPTY_VARIANT,
    size: combo.size,
    color: combo.color,
    other: combo.other,
    default_purchase_price: generator.default_purchase_price,
    default_selling_price: generator.default_selling_price || identity.default_selling_price,
    min_selling_price: generator.min_selling_price || identity.min_selling_price,
    reorder_level: generator.reorder_level,
  };
}


function cloneVariant(variant: CatalogVariantInput): CatalogVariantInput {
  return { ...variant };
}


export function CatalogWorkspace() {
  const searchParams = useSearchParams();
  const searchKey = searchParams.toString();
  const [activeTab, setActiveTab] = useState<CatalogTab>('products');
  const [queryInput, setQueryInput] = useState('');
  const [workspace, setWorkspace] = useState<Awaited<ReturnType<typeof getCatalogWorkspace>> | null>(null);
  const [form, setForm] = useState<CatalogUpsertPayload>({
    identity: EMPTY_IDENTITY,
    variants: [{ ...EMPTY_VARIANT }],
  });
  const [savedVariants, setSavedVariants] = useState<CatalogVariantInput[]>([]);
  const [generator, setGenerator] = useState<VariantGeneratorState>({ ...EMPTY_GENERATOR });
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [saveToast, setSaveToast] = useState('');
  const [isPending, startTransition] = useTransition();

  useEffect(() => {
    if (!saveToast) return undefined;
    const timeoutId = window.setTimeout(() => setSaveToast(''), 2800);
    return () => window.clearTimeout(timeoutId);
  }, [saveToast]);

  const loadWorkspace = (query = '') => {
    startTransition(async () => {
      try {
        const payload = await getCatalogWorkspace({ q: query });
        setWorkspace(payload);
        setError('');
      } catch (loadError) {
        if (loadError instanceof ApiError && loadError.status === 404) {
          setWorkspace(null);
          setError('Catalog workspace is not available on the connected API yet. Deploy the latest backend to load and list saved products.');
          return;
        }
        setError(loadError instanceof Error ? loadError.message : 'Unable to load catalog workspace.');
      }
    });
  };

  useEffect(() => {
    const query = searchParams.get('q') ?? '';
    setQueryInput(query);
    loadWorkspace(query);
  }, [searchKey]);

  const onSearch = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    loadWorkspace(queryInput.trim());
  };

  const setNewProductForm = () => {
    setForm({
      identity: { ...EMPTY_IDENTITY },
      variants: [{ ...EMPTY_VARIANT }],
    });
    setSavedVariants([]);
    setGenerator({ ...EMPTY_GENERATOR });
    setNotice('');
    setError('');
    setActiveTab('edit');
  };

  const onProductEdit = (product: CatalogProduct) => {
    const payload = productToPayload(product);
    setForm(payload);
    setSavedVariants(payload.variants.map(cloneVariant));
    setGenerator(generatorFromProduct(product));
    setActiveTab('edit');
    setNotice('');
    setError('');
  };

  const generatedCombos = useMemo(() => buildVariantCombinations(generator), [generator]);
  const derivedDiscount = calculateDerivedDiscount(form.identity.default_selling_price, form.identity.min_selling_price);

  const applyGenerator = (mode: 'merge' | 'reset') => {
    setForm((current) => {
      const rawBaseline = mode === 'reset' ? savedVariants.map(cloneVariant) : current.variants.map(cloneVariant);
      const hasRealGeneratedVariants = generatedCombos.some((combo) => Boolean(combo.size || combo.color || combo.other));
      const baseline = hasRealGeneratedVariants
        ? rawBaseline.filter((variant) => !isUntouchedDefaultVariant(variant))
        : rawBaseline;
      const indexed = new Map(baseline.map((variant) => [signatureForVariant(variant), variant]));
      const next = [...baseline];
      generatedCombos.forEach((combo) => {
        const signature = signatureForVariant(combo);
        if (!indexed.has(signature)) {
          const created = newVariantFromCombo(combo, generator, current.identity);
          indexed.set(signature, created);
          next.push(created);
        }
      });
      return {
        ...current,
        variants: next.length ? next : [{ ...EMPTY_VARIANT }],
      };
    });
    setNotice(mode === 'reset' ? 'Variants reset from generator.' : 'Generator merged new variants into the editor.');
  };

  const applyDefaultsToVariants = (scope: 'empty' | 'all') => {
    setForm((current) => ({
      ...current,
      variants: current.variants.map((variant) => {
        if (variant.status === 'archived') return variant;
        const next = { ...variant };
        const shouldWrite = (currentValue: string) => scope === 'all' || !currentValue.trim();
        if (generator.default_purchase_price.trim() && shouldWrite(next.default_purchase_price)) {
          next.default_purchase_price = generator.default_purchase_price;
        }
        if (generator.default_selling_price.trim() && shouldWrite(next.default_selling_price)) {
          next.default_selling_price = generator.default_selling_price;
        }
        if (generator.min_selling_price.trim() && shouldWrite(next.min_selling_price)) {
          next.min_selling_price = generator.min_selling_price;
        }
        if (generator.reorder_level.trim() && shouldWrite(next.reorder_level)) {
          next.reorder_level = generator.reorder_level;
        }
        return next;
      }),
    }));
    setNotice(scope === 'all' ? 'Variant defaults applied to all rows.' : 'Variant defaults filled only empty rows.');
  };

  const onSave = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setNotice('');
    setError('');
    try {
      await saveCatalogProduct(form);
      setSaveToast(form.product_id ? 'Product updated successfully.' : 'Product saved successfully.');
      setNewProductForm();
    } catch (saveError) {
      if (saveError instanceof ApiError && saveError.status === 404) {
        setError('Catalog save is not available on the connected API yet. Deploy the latest backend before trying to save products.');
        return;
      }
      setError(saveError instanceof Error ? saveError.message : 'Unable to save product.');
    }
  };

  return (
    <div className="workspace-stack">
      {saveToast ? <WorkspaceToast message={saveToast} onClose={() => setSaveToast('')} /> : null}
      <WorkspaceTabs
        tabs={[
          { id: 'products', label: 'Products' },
          { id: 'edit', label: form.product_id ? 'Edit Product' : 'Add Product' },
        ]}
        activeTab={activeTab}
        onTabChange={setActiveTab}
      />

      <WorkspacePanel
        title="Variant-first catalog"
        description="Search and manage products as parent records with saleable child variants."
        actions={
          <div className="workspace-inline-actions">
            <form className="workspace-search" onSubmit={onSearch}>
              <input
                type="search"
                value={queryInput}
                placeholder="Search by product, variant, SKU, barcode"
                onChange={(event) => setQueryInput(event.target.value)}
              />
              <button type="submit">Search</button>
            </form>
          </div>
        }
      >
        {notice ? <WorkspaceNotice tone="success">{notice}</WorkspaceNotice> : null}
        {error ? <WorkspaceNotice tone="error">{error}</WorkspaceNotice> : null}
        {isPending && !workspace ? <WorkspaceNotice>Loading catalog…</WorkspaceNotice> : null}

        {activeTab === 'products' ? (
          workspace?.items.length ? (
            <div className="workspace-card-grid">
              {workspace.items.map((product) => (
                <article key={product.product_id} className="commerce-card">
                  <div className="commerce-card-header">
                    <div>
                      <p className="eyebrow">Catalog Parent</p>
                      <h4>{product.name}</h4>
                      <p>{product.brand || 'No brand'} · {product.category || 'Uncategorized'} · {product.supplier || 'No supplier'}</p>
                    </div>
                    <button type="button" onClick={() => onProductEdit(product)}>Edit product</button>
                  </div>
                  <div className="commerce-card-meta">
                    <span>SKU Base: {product.sku_root || 'Generated from product name'}</span>
                    <span>Template Price: {formatMoney(product.default_price)}</span>
                    <span>Min Price: {formatMoney(product.min_price)}</span>
                    <span>Equivalent Max Discount: {formatPercent(product.max_discount_percent)}</span>
                  </div>
                  <div className="table-scroll">
                    <table className="workspace-table">
                      <thead>
                        <tr>
                          <th>Variant</th>
                          <th>SKU</th>
                          <th>Available</th>
                          <th>Reserved</th>
                          <th>Price</th>
                          <th>Min Price</th>
                          <th>Reorder</th>
                        </tr>
                      </thead>
                      <tbody>
                        {product.variants.map((variant) => (
                          <tr key={variant.variant_id}>
                            <td>{variant.label}</td>
                            <td>{variant.sku}</td>
                            <td>{formatQuantity(variant.available_to_sell)}</td>
                            <td>{formatQuantity(variant.reserved)}</td>
                            <td>
                              {formatMoney(variant.effective_unit_price)}
                              {variant.is_price_inherited ? <div className="workspace-field-note">Inherited from product</div> : null}
                            </td>
                            <td>
                              {formatMoney(variant.effective_min_price)}
                              {variant.is_min_price_inherited ? <div className="workspace-field-note">Inherited from product</div> : null}
                            </td>
                            <td>{formatQuantity(variant.reorder_level)}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </article>
              ))}
            </div>
          ) : (
            <WorkspaceEmpty
              title="No active in-stock catalog items"
              message="Use Add Product to create a parent product and its saleable variants."
            />
          )
        ) : (
          <form className="workspace-form" onSubmit={onSave}>
            <div className="workspace-subsection">
              <div className="workspace-subsection-header">
                <div>
                  <h4>Basic Info</h4>
                  <p>Shared product identity and code generation inputs.</p>
                </div>
              </div>
              <div className="workspace-form-grid">
                <label>
                  Product name
                  <input
                    value={form.identity.product_name}
                    onChange={(event) =>
                      setForm((current) => ({
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
                    list="catalog-suppliers"
                    value={form.identity.supplier}
                    onChange={(event) =>
                      setForm((current) => ({
                        ...current,
                        identity: { ...current.identity, supplier: event.target.value },
                      }))
                    }
                  />
                </label>
                <label>
                  Category
                  <input
                    list="catalog-categories"
                    value={form.identity.category}
                    onChange={(event) =>
                      setForm((current) => ({
                        ...current,
                        identity: { ...current.identity, category: event.target.value },
                      }))
                    }
                  />
                </label>
                <label>
                  Brand
                  <input
                    value={form.identity.brand}
                    onChange={(event) =>
                      setForm((current) => ({
                        ...current,
                        identity: { ...current.identity, brand: event.target.value },
                      }))
                    }
                  />
                </label>
                <label className="field-span-2">
                  SKU Base
                  <input
                    value={form.identity.sku_root}
                    placeholder="Leave blank to generate from product name"
                    onChange={(event) =>
                      setForm((current) => ({
                        ...current,
                        identity: { ...current.identity, sku_root: event.target.value },
                      }))
                    }
                  />
                </label>
              </div>
              <label>
                Description
                <textarea
                  rows={3}
                  value={form.identity.description}
                  onChange={(event) =>
                    setForm((current) => ({
                      ...current,
                      identity: { ...current.identity, description: event.target.value },
                    }))
                  }
                />
              </label>
            </div>

            <div className="workspace-subsection">
              <div className="workspace-subsection-header">
                <div>
                  <h4>Pricing Rules</h4>
                  <p>Product-level price rules are optional templates for new variants.</p>
                </div>
              </div>
              <div className="workspace-form-grid compact">
                <label>
                  Default selling price
                  <input
                    inputMode="decimal"
                    value={form.identity.default_selling_price}
                    placeholder="Optional template"
                    onChange={(event) =>
                      setForm((current) => ({
                        ...current,
                        identity: { ...current.identity, default_selling_price: event.target.value },
                      }))
                    }
                  />
                </label>
                <label>
                  Minimum selling price
                  <input
                    inputMode="decimal"
                    value={form.identity.min_selling_price}
                    placeholder="Optional floor"
                    onChange={(event) =>
                      setForm((current) => ({
                        ...current,
                        identity: { ...current.identity, min_selling_price: event.target.value },
                      }))
                    }
                  />
                </label>
                <label>
                  Equivalent max discount
                  <input value={derivedDiscount ? `${derivedDiscount}%` : 'Not set'} readOnly />
                </label>
              </div>
            </div>

            <div className="workspace-subsection">
              <div className="workspace-subsection-header">
                <div>
                  <h4>Variant Generator</h4>
                  <p>Generate combinations from comma-separated values, then review and edit the rows below.</p>
                </div>
                <div className="workspace-inline-actions">
                  <button type="button" onClick={() => applyGenerator('merge')}>Generate / Regenerate</button>
                  <button type="button" onClick={() => applyGenerator('reset')}>Reset from generator</button>
                </div>
              </div>
              <div className="workspace-form-grid">
                <label>
                  Sizes
                  <input
                    value={generator.size_values}
                    placeholder="40, 41, 42"
                    onChange={(event) => setGenerator((current) => ({ ...current, size_values: event.target.value }))}
                  />
                </label>
                <label>
                  Colors
                  <input
                    value={generator.color_values}
                    placeholder="Black, White"
                    onChange={(event) => setGenerator((current) => ({ ...current, color_values: event.target.value }))}
                  />
                </label>
                <label>
                  Other
                  <input
                    value={generator.other_values}
                    placeholder="Mesh, Leather"
                    onChange={(event) => setGenerator((current) => ({ ...current, other_values: event.target.value }))}
                  />
                </label>
              </div>
              <div className="commerce-card-meta">
                <span>Preview combinations: {generatedCombos.length}</span>
                <span>Saved variants: {savedVariants.length}</span>
                <span>Rows in editor: {form.variants.length}</span>
              </div>
            </div>

            <div className="workspace-subsection">
              <div className="workspace-subsection-header">
                <div>
                  <h4>Variant Defaults</h4>
                  <p>Use shared defaults when many variants have the same cost, price, minimum price, or reorder level.</p>
                </div>
                <div className="workspace-inline-actions">
                  <button type="button" onClick={() => applyDefaultsToVariants('empty')}>Apply to empty rows</button>
                  <button type="button" onClick={() => applyDefaultsToVariants('all')}>Apply to all rows</button>
                </div>
              </div>
              <div className="workspace-form-grid compact">
                <label>
                  Default purchase cost
                  <input
                    inputMode="decimal"
                    value={generator.default_purchase_price}
                    onChange={(event) =>
                      setGenerator((current) => ({ ...current, default_purchase_price: event.target.value }))
                    }
                  />
                </label>
                <label>
                  Default selling price
                  <input
                    inputMode="decimal"
                    value={generator.default_selling_price}
                    onChange={(event) =>
                      setGenerator((current) => ({ ...current, default_selling_price: event.target.value }))
                    }
                  />
                </label>
                <label>
                  Minimum selling price
                  <input
                    inputMode="decimal"
                    value={generator.min_selling_price}
                    onChange={(event) =>
                      setGenerator((current) => ({ ...current, min_selling_price: event.target.value }))
                    }
                  />
                </label>
                <label>
                  Reorder level
                  <input
                    inputMode="decimal"
                    value={generator.reorder_level}
                    onChange={(event) => setGenerator((current) => ({ ...current, reorder_level: event.target.value }))}
                  />
                </label>
              </div>
            </div>

            <div className="workspace-subsection">
              <div className="workspace-subsection-header">
                <div>
                  <h4>Variants</h4>
                  <p>Each row is still fully editable before save. Existing variants keep their SKU stable after first save.</p>
                </div>
                <button
                  type="button"
                  onClick={() =>
                    setForm((current) => ({
                      ...current,
                      variants: [...current.variants, { ...EMPTY_VARIANT }],
                    }))
                  }
                >
                  Add manual row
                </button>
              </div>

              <div className="workspace-stack">
                {form.variants.map((variant, index) => {
                  const isSavedVariant = Boolean(variant.variant_id);
                  const skuPreview = buildSkuPreview(form.identity.product_name, form.identity.sku_root, variant);
                  return (
                    <div key={`${variant.variant_id ?? 'new'}-${index}`} className={`variant-editor ${variant.status === 'archived' ? 'is-archived' : ''}`}>
                      <div className="variant-editor-header">
                        <div>
                          <strong>{variant.size || variant.color || variant.other ? [variant.size, variant.color, variant.other].filter(Boolean).join(' / ') : 'Default variant'}</strong>
                          <p className="workspace-field-note">
                            {isSavedVariant ? 'Saved variant' : 'New variant'} · {variant.status === 'archived' ? 'Archived' : 'Active'}
                          </p>
                        </div>
                        <div className="workspace-inline-actions">
                          {isSavedVariant ? (
                            <button
                              type="button"
                              onClick={() =>
                                setForm((current) => ({
                                  ...current,
                                  variants: current.variants.map((item, itemIndex) =>
                                    itemIndex === index
                                      ? { ...item, status: item.status === 'archived' ? 'active' : 'archived' }
                                      : item
                                  ),
                                }))
                              }
                            >
                              {variant.status === 'archived' ? 'Restore' : 'Archive'}
                            </button>
                          ) : (
                            <button
                              type="button"
                              onClick={() =>
                                setForm((current) => ({
                                  ...current,
                                  variants: current.variants.filter((_, itemIndex) => itemIndex !== index),
                                }))
                              }
                            >
                              Remove
                            </button>
                          )}
                        </div>
                      </div>

                      <div className="workspace-form-grid compact">
                        <label>
                          Size
                          <input
                            value={variant.size}
                            onChange={(event) =>
                              setForm((current) => ({
                                ...current,
                                variants: current.variants.map((item, itemIndex) =>
                                  itemIndex === index ? { ...item, size: event.target.value } : item
                                ),
                              }))
                            }
                          />
                        </label>
                        <label>
                          Color
                          <input
                            value={variant.color}
                            onChange={(event) =>
                              setForm((current) => ({
                                ...current,
                                variants: current.variants.map((item, itemIndex) =>
                                  itemIndex === index ? { ...item, color: event.target.value } : item
                                ),
                              }))
                            }
                          />
                        </label>
                        <label>
                          Other
                          <input
                            value={variant.other}
                            onChange={(event) =>
                              setForm((current) => ({
                                ...current,
                                variants: current.variants.map((item, itemIndex) =>
                                  itemIndex === index ? { ...item, other: event.target.value } : item
                                ),
                              }))
                            }
                          />
                        </label>
                        <label>
                          SKU Preview
                          <input value={skuPreview} readOnly />
                        </label>
                        <label>
                          Barcode
                          <input
                            value={variant.barcode}
                            onChange={(event) =>
                              setForm((current) => ({
                                ...current,
                                variants: current.variants.map((item, itemIndex) =>
                                  itemIndex === index ? { ...item, barcode: event.target.value } : item
                                ),
                              }))
                            }
                          />
                        </label>
                        <label>
                          Cost
                          <input
                            inputMode="decimal"
                            value={variant.default_purchase_price}
                            onChange={(event) =>
                              setForm((current) => ({
                                ...current,
                                variants: current.variants.map((item, itemIndex) =>
                                  itemIndex === index ? { ...item, default_purchase_price: event.target.value } : item
                                ),
                              }))
                            }
                          />
                        </label>
                        <label>
                          Price
                          <input
                            inputMode="decimal"
                            value={variant.default_selling_price}
                            placeholder={form.identity.default_selling_price ? `Inherit ${form.identity.default_selling_price}` : 'Optional override'}
                            onChange={(event) =>
                              setForm((current) => ({
                                ...current,
                                variants: current.variants.map((item, itemIndex) =>
                                  itemIndex === index ? { ...item, default_selling_price: event.target.value } : item
                                ),
                              }))
                            }
                          />
                        </label>
                        <label>
                          Minimum price
                          <input
                            inputMode="decimal"
                            value={variant.min_selling_price}
                            placeholder={form.identity.min_selling_price ? `Inherit ${form.identity.min_selling_price}` : 'Optional override'}
                            onChange={(event) =>
                              setForm((current) => ({
                                ...current,
                                variants: current.variants.map((item, itemIndex) =>
                                  itemIndex === index ? { ...item, min_selling_price: event.target.value } : item
                                ),
                              }))
                            }
                          />
                        </label>
                        <label>
                          Reorder level
                          <input
                            inputMode="decimal"
                            value={variant.reorder_level}
                            onChange={(event) =>
                              setForm((current) => ({
                                ...current,
                                variants: current.variants.map((item, itemIndex) =>
                                  itemIndex === index ? { ...item, reorder_level: event.target.value } : item
                                ),
                              }))
                            }
                          />
                        </label>
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>

            <div className="workspace-actions">
              <button type="submit">{form.product_id ? 'Update product' : 'Create product'}</button>
              <button type="button" onClick={setNewProductForm}>Reset form</button>
            </div>

            <datalist id="catalog-suppliers">
              {workspace?.suppliers.map((supplier) => <option key={supplier.supplier_id} value={supplier.name} />)}
            </datalist>
            <datalist id="catalog-categories">
              {workspace?.categories.map((category) => <option key={category.category_id} value={category.name} />)}
            </datalist>
          </form>
        )}
      </WorkspacePanel>
    </div>
  );
}
