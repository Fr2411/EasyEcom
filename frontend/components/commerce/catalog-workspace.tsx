'use client';

import { FormEvent, useEffect, useMemo, useState, useTransition } from 'react';
import { useSearchParams } from 'next/navigation';
import { ApiError } from '@/lib/api/client';
import { getCatalogWorkspace, saveCatalogProduct } from '@/lib/api/commerce';
import { buildSkuPreview, buildVariantCombinations, signatureForVariant, type VariantOptionValues } from '@/lib/variant-generator';
import type {
  CatalogProduct,
  ProductMedia,
  CatalogUpsertPayload,
  CatalogVariantInput,
  ProductIdentityInput,
  VariantOptions,
  CatalogWorkspace,
} from '@/types/catalog';
import type { SuggestedAction } from '@/types/guided-workflow';
import {
  DraftRecommendationCard,
  IntentInput,
  MatchGroupList,
  StagedActionFooter,
  SuggestedNextStep,
  WorkspaceEmpty,
  WorkspaceHint,
  WorkspaceNotice,
  WorkspacePanel,
  WorkspaceTabs,
  WorkspaceToast,
} from '@/components/commerce/workspace-primitives';
import { formatMoney, formatPercent, formatQuantity, numberFromString } from '@/lib/commerce-format';
import { ProductPhotoField } from '@/components/commerce/product-photo-field';


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

type CatalogRecommendation = SuggestedAction & {
  kind: 'idle' | 'exact' | 'likely' | 'new';
};

const EMPTY_IDENTITY: ProductIdentityInput = {
  product_name: '',
  supplier: '',
  category: '',
  brand: '',
  description: '',
  image_url: '',
  pending_primary_media_upload_id: '',
  remove_primary_image: false,
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
      image_url: product.image_url || '',
      pending_primary_media_upload_id: '',
      remove_primary_image: false,
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

function normalizeCatalogQuery(value: string) {
  return value.trim().toLowerCase();
}

function productMatchesExact(product: CatalogProduct, query: string) {
  const normalized = normalizeCatalogQuery(query);
  if (!normalized) return false;
  if (product.name.toLowerCase() === normalized || product.sku_root.toLowerCase() === normalized) {
    return true;
  }
  return product.variants.some((variant) =>
    [variant.sku, variant.barcode, variant.label].some((value) => value.toLowerCase() === normalized)
  );
}

function productMatchesLikely(product: CatalogProduct, query: string) {
  const normalized = normalizeCatalogQuery(query);
  if (!normalized) return false;
  if (productMatchesExact(product, query)) return false;
  if (product.name.toLowerCase().includes(normalized) || product.sku_root.toLowerCase().includes(normalized)) {
    return true;
  }
  return product.variants.some((variant) =>
    [variant.label, variant.sku, variant.barcode].some((value) => value.toLowerCase().includes(normalized))
  );
}

export function deriveCatalogRecommendation(workspace: CatalogWorkspace | null): CatalogRecommendation {
  const query = workspace?.query?.trim() ?? '';
  if (!workspace || !query) {
    return {
      kind: 'idle',
      title: 'Start with one product clue',
      detail: 'Type a product name, SKU root, barcode, or variant code. The workspace will stage the best match or open a new product draft.',
      actionLabel: 'Review next step',
      tone: 'info',
    };
  }

  const exact = workspace.items.find((product) => productMatchesExact(product, query));
  if (exact) {
    return {
      kind: 'exact',
      title: `Exact catalog match: ${exact.name}`,
      detail: 'The matching product can be opened immediately for review or edit.',
      actionLabel: 'Open product',
      secondaryLabel: 'Start new product',
      tone: 'success',
    };
  }

  const likely = workspace.items.find((product) => productMatchesLikely(product, query));
  if (likely) {
    return {
      kind: 'likely',
      title: `Likely match: ${likely.name}`,
      detail: 'Review this product first. If it is not the right catalog parent, continue with a new product draft.',
      actionLabel: 'Review product',
      secondaryLabel: 'Start new product',
      tone: 'warning',
    };
  }

  return {
    kind: 'new',
    title: `No catalog match for "${workspace.query}"`,
    detail: 'A new product draft is ready with the typed clue preserved as the starting context.',
    actionLabel: 'Start new product',
    tone: 'warning',
  };
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
  const [productImage, setProductImage] = useState<ProductMedia | null>(null);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [saveToast, setSaveToast] = useState('');
  const [isPending, startTransition] = useTransition();
  const recommendation = deriveCatalogRecommendation(workspace);

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

  const setNewProductForm = (seed?: string) => {
    setForm({
      identity: {
        ...EMPTY_IDENTITY,
        product_name: seed ?? '',
      },
      variants: [{ ...EMPTY_VARIANT }],
    });
    setSavedVariants([]);
    setGenerator({ ...EMPTY_GENERATOR });
    setProductImage(null);
    setNotice('');
    setError('');
    setActiveTab('edit');
  };

  const onProductEdit = (product: CatalogProduct) => {
    const payload = productToPayload(product);
    setForm(payload);
    setSavedVariants(payload.variants.map(cloneVariant));
    setGenerator(generatorFromProduct(product));
    setProductImage(product.image);
    setActiveTab('edit');
    setNotice('');
    setError('');
  };

  const onWorkspaceIntent = async (query: string) => {
    const trimmed = query.trim();
    if (!trimmed) {
      setWorkspace(null);
      setQueryInput('');
      return;
    }
    setQueryInput(trimmed);
    await loadWorkspace(trimmed);
  };

  const openRecommendedProduct = () => {
    const exact = workspace?.items.find((product) => productMatchesExact(product, workspace.query));
    const likely = workspace?.items.find((product) => productMatchesLikely(product, workspace.query));
    const product = exact ?? likely;
    if (product) {
      onProductEdit(product);
      return;
    }
    if (queryInput.trim()) {
      void onWorkspaceIntent(queryInput);
    }
    setNewProductForm(queryInput.trim() || workspace?.query);
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
          { id: 'edit', label: form.product_id ? 'Edit Product' : 'Start New Product' },
        ]}
        activeTab={activeTab}
        onTabChange={setActiveTab}
      />

      <WorkspacePanel
        title="Variant-first catalog"
        hint="Use one product clue to open an existing catalog parent or stage a new product draft with its saleable variants."
        actions={
          <IntentInput
            label="What product are you working on?"
            hint="Search by product name, SKU root, barcode, or a variant code. The best match will be staged first."
            value={queryInput}
            placeholder="Product, SKU root, barcode, or variant"
            pending={isPending}
            submitLabel="Interpret intent"
            onChange={setQueryInput}
            onSubmit={() => void onWorkspaceIntent(queryInput)}
          >
            <span className="guided-assist-chip">Exact product matches open the editor</span>
            <span className="guided-assist-chip">No match stages a new product draft</span>
          </IntentInput>
        }
      >
        {notice ? <WorkspaceNotice tone="success">{notice}</WorkspaceNotice> : null}
        {error ? <WorkspaceNotice tone="error">{error}</WorkspaceNotice> : null}
        {isPending && !workspace ? <WorkspaceNotice>Loading catalog…</WorkspaceNotice> : null}

        <SuggestedNextStep
          suggestion={recommendation}
          onPrimary={openRecommendedProduct}
          onSecondary={() => setNewProductForm(workspace?.query)}
        />

        {activeTab === 'products' ? (
          workspace?.items.length ? (
            <MatchGroupList
              title="Catalog parents"
              description="Pick the strongest match first. Each product remains editable as a parent record with saleable child variants."
              items={workspace.items}
              renderItem={(product) => (
                <article key={product.product_id} className="guided-match-item">
                  <div className="guided-match-item-header">
                    <div className="guided-match-item-identity">
                      {product.image?.thumbnail_url ? (
                        <img className="guided-match-item-thumb" src={product.image.thumbnail_url} alt={product.name} />
                      ) : null}
                      <div>
                      <h5>{product.name}</h5>
                      <p>{product.brand || 'No brand'} · {product.category || 'Uncategorized'} · {product.supplier || 'No supplier'}</p>
                      </div>
                    </div>
                    <button type="button" onClick={() => onProductEdit(product)}>
                      Open product
                    </button>
                  </div>
                  <div className="guided-match-item-meta">
                    <span>SKU Base: {product.sku_root || 'Generated from product name'}</span>
                    <span>Variants: {product.variants.length}</span>
                    <span>Template Price: {formatMoney(product.default_price)}</span>
                    <span>Min Price: {formatMoney(product.min_price)}</span>
                    <span>Equivalent Max Discount: {formatPercent(product.max_discount_percent)}</span>
                  </div>
                </article>
              )}
            />
          ) : (
            <WorkspaceEmpty
              title="No catalog items staged"
              message="Use the intent bar above to open an existing product or start a new parent record."
            />
          )
        ) : (
          <DraftRecommendationCard
            title={form.product_id ? `Editing ${form.identity.product_name}` : 'New product draft'}
            summary={form.product_id
              ? 'Review or adjust the parent product and its variants before saving the updated catalog record.'
              : 'Start with the typed clue. The editor keeps the parent product and variants visible before the final save.'}
            actions={
              <StagedActionFooter summary="The catalog only writes when you explicitly save the product.">
                <button type="submit" form="catalog-product-form">
                  {form.product_id ? 'Review before saving' : 'Create product'}
                </button>
                <button type="button" onClick={() => setNewProductForm(workspace?.query)}>
                  Reset draft
                </button>
              </StagedActionFooter>
            }
          >
          <form id="catalog-product-form" className="workspace-form" onSubmit={onSave}>
            <div className="workspace-subsection">
              <div className="workspace-subsection-header">
                <h4 className="workspace-heading">
                  Basic Info
                  <WorkspaceHint
                    label="Basic info help"
                    text="These shared fields define the parent product and the SKU base used for generating new variant codes."
                  />
                </h4>
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
              <div className="field-span-2">
                <label>Product photo</label>
                <ProductPhotoField
                  image={productImage}
                  onUploaded={(image) => {
                    setProductImage(image);
                    setForm((current) => ({
                      ...current,
                      identity: {
                        ...current.identity,
                        pending_primary_media_upload_id: image.upload_id,
                        remove_primary_image: false,
                        image_url: image.large_url,
                      },
                    }));
                  }}
                  onRemove={() => {
                    setProductImage(null);
                    setForm((current) => ({
                      ...current,
                      identity: {
                        ...current.identity,
                        pending_primary_media_upload_id: '',
                        remove_primary_image: Boolean(current.product_id || current.identity.image_url),
                        image_url: '',
                      },
                    }));
                  }}
                />
              </div>
            </div>

            <div className="workspace-subsection">
              <div className="workspace-subsection-header">
                <h4 className="workspace-heading">
                  Pricing Rules
                  <WorkspaceHint
                    label="Pricing rules help"
                    text="Product-level price rules are optional templates. Variants can inherit them or override them row by row."
                  />
                </h4>
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
                <h4 className="workspace-heading">
                  Variant Generator
                  <WorkspaceHint
                    label="Catalog variant generator help"
                    text="Enter comma-separated option values to generate combinations, then review and edit the rows below before saving."
                  />
                </h4>
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
                <h4 className="workspace-heading">
                  Variant Defaults
                  <WorkspaceHint
                    label="Variant defaults help"
                    text="Use these shared defaults when many variants should start with the same cost, price, minimum price, or reorder level."
                  />
                </h4>
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
                <h4 className="workspace-heading">
                  Variants
                  <WorkspaceHint
                    label="Variants section help"
                    text="Each row is still fully editable before save. Existing variants keep their SKU stable after the first save."
                  />
                </h4>
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
              <button type="button" onClick={() => setNewProductForm(workspace?.query)}>Reset form</button>
            </div>

            <datalist id="catalog-suppliers">
              {workspace?.suppliers.map((supplier) => <option key={supplier.supplier_id} value={supplier.name} />)}
            </datalist>
            <datalist id="catalog-categories">
              {workspace?.categories.map((category) => <option key={category.category_id} value={category.name} />)}
            </datalist>
          </form>
          </DraftRecommendationCard>
        )}
      </WorkspacePanel>
    </div>
  );
}
