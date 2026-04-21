'use client';

import type { FormEvent } from 'react';
import { useEffect, useMemo, useRef, useState } from 'react';
import { useSearchParams } from 'next/navigation';
import {
  createInventoryAdjustment,
  getInventoryIntakeLookup,
  getInventoryWorkspace,
  receiveInventoryStock,
  saveCatalogProduct,
} from '@/lib/api/commerce';
import { ApiError } from '@/lib/api/client';
import { formatMoney, formatQuantity, numberFromString } from '@/lib/commerce-format';
import { buildSkuPreview, buildVariantCombinations, signatureForVariant, type VariantOptionValues } from '@/lib/variant-generator';
import { ProductPhotoField } from '@/components/commerce/product-photo-field';
import {
  WorkspaceEmpty,
  WorkspaceHint,
  WorkspaceNotice,
  WorkspacePanel,
  WorkspaceToast,
} from '@/components/commerce/workspace-primitives';
import type { CatalogProduct, CatalogVariant, CatalogVariantInput, ProductIdentityInput, ProductMedia } from '@/types/catalog';
import type { InventoryAdjustmentPayload, InventoryStockRow, ReceiveStockPayload } from '@/types/inventory';

type LookupMode = 'idle' | 'exact' | 'product' | 'new';

type LookupSummary = {
  mode: LookupMode;
  title: string;
  detail: string;
};

type VariantDraft = CatalogVariantInput & {
  row_id: string;
  receive_selected: boolean;
  receive_quantity: string;
  receive_unit_cost: string;
};

type UnifiedDraft = {
  product_id?: string;
  identity: ProductIdentityInput;
  variants: VariantDraft[];
  notes: string;
};

type GeneratorDraft = {
  size_values: string;
  color_values: string;
  other_values: string;
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

const EMPTY_GENERATOR: GeneratorDraft = {
  size_values: '',
  color_values: '',
  other_values: '',
};

const EMPTY_ADJUSTMENT: InventoryAdjustmentPayload = {
  variant_id: '',
  quantity_delta: '',
  reason: '',
  notes: '',
};

function safeErrorMessage(error: unknown, fallback: string) {
  if (error instanceof Error) {
    return error.message;
  }
  return fallback;
}

function normalizeSkuRoot(value: string) {
  return value
    .trim()
    .toUpperCase()
    .replace(/[^A-Z0-9]+/g, '-')
    .replace(/^-+|-+$/g, '')
    .replace(/-+/g, '-');
}

function valueOrEmpty(value: string | null | undefined) {
  return value ?? '';
}

function variantTitle(values: VariantOptionValues) {
  return [values.size, values.color, values.other].filter((value) => value.trim()).join(' / ') || 'Default';
}

function nextRowId(prefix: string, counter: React.MutableRefObject<number>) {
  counter.current += 1;
  return `${prefix}-${counter.current}`;
}

function createEmptyVariantRow(counter: React.MutableRefObject<number>, seed?: Partial<CatalogVariantInput>): VariantDraft {
  return {
    row_id: nextRowId('variant', counter),
    variant_id: seed?.variant_id,
    sku: seed?.sku ?? '',
    barcode: seed?.barcode ?? '',
    size: seed?.size ?? '',
    color: seed?.color ?? '',
    other: seed?.other ?? '',
    default_purchase_price: seed?.default_purchase_price ?? '',
    default_selling_price: seed?.default_selling_price ?? '',
    min_selling_price: seed?.min_selling_price ?? '',
    reorder_level: seed?.reorder_level ?? '0',
    status: seed?.status ?? 'active',
    receive_selected: false,
    receive_quantity: '',
    receive_unit_cost: seed?.default_purchase_price ?? '',
  };
}

function variantToDraftRow(
  counter: React.MutableRefObject<number>,
  variant: CatalogVariant,
  selectedForReceive = false,
): VariantDraft {
  return {
    row_id: nextRowId('variant', counter),
    variant_id: variant.variant_id,
    sku: variant.sku,
    barcode: variant.barcode,
    size: variant.options.size,
    color: variant.options.color,
    other: variant.options.other,
    default_purchase_price: valueOrEmpty(variant.unit_cost),
    default_selling_price: valueOrEmpty(variant.unit_price ?? variant.effective_unit_price),
    min_selling_price: valueOrEmpty(variant.min_price ?? variant.effective_min_price),
    reorder_level: variant.reorder_level || '0',
    status: variant.status || 'active',
    receive_selected: selectedForReceive,
    receive_quantity: selectedForReceive ? '1' : '',
    receive_unit_cost: valueOrEmpty(variant.unit_cost),
  };
}

function productIdentityFromCatalog(product: CatalogProduct): ProductIdentityInput {
  return {
    ...EMPTY_IDENTITY,
    product_name: product.name,
    supplier: product.supplier,
    category: product.category,
    brand: product.brand,
    description: product.description,
    image_url: product.image_url,
    sku_root: product.sku_root,
    default_selling_price: valueOrEmpty(product.default_price),
    min_selling_price: valueOrEmpty(product.min_price),
    max_discount_percent: valueOrEmpty(product.max_discount_percent),
    status: product.status || 'active',
  };
}

function productToDraft(
  counter: React.MutableRefObject<number>,
  product: CatalogProduct,
  options?: { selectVariantId?: string },
): UnifiedDraft {
  return {
    product_id: product.product_id,
    identity: productIdentityFromCatalog(product),
    variants: product.variants.map((variant) =>
      variantToDraftRow(counter, variant, options?.selectVariantId === variant.variant_id)
    ),
    notes: '',
  };
}

function createDraftFromSuggestion(counter: React.MutableRefObject<number>, productName: string, skuRoot: string): UnifiedDraft {
  return {
    identity: {
      ...EMPTY_IDENTITY,
      product_name: productName,
      sku_root: skuRoot,
    },
    variants: [createEmptyVariantRow(counter, {})],
    notes: '',
  };
}

function trimOrEmpty(value: string | undefined | null) {
  return (value ?? '').trim();
}

function normalizeIdentity(identity: ProductIdentityInput): ProductIdentityInput {
  return {
    ...identity,
    product_name: trimOrEmpty(identity.product_name),
    supplier: trimOrEmpty(identity.supplier),
    category: trimOrEmpty(identity.category),
    brand: trimOrEmpty(identity.brand),
    description: trimOrEmpty(identity.description),
    image_url: trimOrEmpty(identity.image_url),
    pending_primary_media_upload_id: trimOrEmpty(identity.pending_primary_media_upload_id),
    sku_root: trimOrEmpty(identity.sku_root),
    default_selling_price: trimOrEmpty(identity.default_selling_price),
    min_selling_price: trimOrEmpty(identity.min_selling_price),
    max_discount_percent: trimOrEmpty(identity.max_discount_percent),
    status: trimOrEmpty(identity.status) || 'active',
    remove_primary_image: Boolean(identity.remove_primary_image),
  };
}

function normalizeVariantRows(rows: VariantDraft[]): CatalogVariantInput[] {
  const cleaned = rows.map((row) => ({
    variant_id: trimOrEmpty(row.variant_id) || undefined,
    sku: trimOrEmpty(row.sku),
    barcode: trimOrEmpty(row.barcode),
    size: trimOrEmpty(row.size),
    color: trimOrEmpty(row.color),
    other: trimOrEmpty(row.other),
    default_purchase_price: trimOrEmpty(row.default_purchase_price),
    default_selling_price: trimOrEmpty(row.default_selling_price),
    min_selling_price: trimOrEmpty(row.min_selling_price),
    reorder_level: trimOrEmpty(row.reorder_level) || '0',
    status: trimOrEmpty(row.status) || 'active',
  }));

  const meaningful = cleaned.filter((row, index) => {
    if (row.variant_id) return true;
    if (index === 0) return true;
    return Boolean(
      row.sku
      || row.barcode
      || row.size
      || row.color
      || row.other
      || row.default_purchase_price
      || row.default_selling_price
      || row.min_selling_price
      || (row.reorder_level && row.reorder_level !== '0')
    );
  });

  return meaningful.length ? meaningful : [cleaned[0] ?? {
    sku: '',
    barcode: '',
    size: '',
    color: '',
    other: '',
    default_purchase_price: '',
    default_selling_price: '',
    min_selling_price: '',
    reorder_level: '0',
    status: 'active',
  }];
}

function validateVariantUniqueness(rows: CatalogVariantInput[]) {
  const optionSignatureSeen = new Set<string>();
  const skuSeen = new Set<string>();

  for (const row of rows) {
    const optionSignature = signatureForVariant({
      size: row.size,
      color: row.color,
      other: row.other,
    });
    if (optionSignatureSeen.has(optionSignature)) {
      return 'Duplicate variant option combinations are not allowed.';
    }
    optionSignatureSeen.add(optionSignature);

    const sku = trimOrEmpty(row.sku).toLowerCase();
    if (sku) {
      if (skuSeen.has(sku)) {
        return 'Duplicate SKUs are not allowed.';
      }
      skuSeen.add(sku);
    }
  }

  return '';
}

function mergeReceiptDrafts(
  counter: React.MutableRefObject<number>,
  previousRows: VariantDraft[],
  savedProduct: CatalogProduct,
): VariantDraft[] {
  const previousById = new Map(previousRows.filter((row) => row.variant_id).map((row) => [row.variant_id as string, row]));
  const previousBySignature = new Map(
    previousRows.map((row) => [signatureForVariant({ size: row.size, color: row.color, other: row.other }), row]),
  );

  return savedProduct.variants.map((variant) => {
    const fallback = variantToDraftRow(counter, variant, false);
    const previous = previousById.get(variant.variant_id)
      ?? previousBySignature.get(signatureForVariant(variant.options));
    if (!previous) {
      return fallback;
    }
    return {
      ...fallback,
      receive_selected: previous.receive_selected,
      receive_quantity: previous.receive_quantity,
      receive_unit_cost: previous.receive_unit_cost || fallback.receive_unit_cost,
    };
  });
}

function buildReceiveLines(
  savedProduct: CatalogProduct,
  rows: VariantDraft[],
): ReceiveStockPayload['lines'] {
  const byId = new Map(savedProduct.variants.map((variant) => [variant.variant_id, variant]));
  const bySignature = new Map(
    savedProduct.variants.map((variant) => [signatureForVariant(variant.options), variant]),
  );
  const bySku = new Map(
    savedProduct.variants
      .filter((variant) => variant.sku.trim())
      .map((variant) => [variant.sku.trim().toLowerCase(), variant]),
  );

  const selected = rows.filter((row) => row.receive_selected);
  if (!selected.length) {
    throw new Error('Select at least one variant row for stock receipt.');
  }

  const lines: ReceiveStockPayload['lines'] = [];
  for (const row of selected) {
    const matched = (row.variant_id && byId.get(row.variant_id))
      || (trimOrEmpty(row.sku) && bySku.get(trimOrEmpty(row.sku).toLowerCase()))
      || bySignature.get(signatureForVariant({ size: row.size, color: row.color, other: row.other }));

    if (!matched) {
      throw new Error(`Unable to map a saved variant for row "${variantTitle(row)}". Save product again and retry.`);
    }

    const quantity = trimOrEmpty(row.receive_quantity);
    if (!quantity || numberFromString(quantity) <= 0) {
      throw new Error(`Enter a valid receipt quantity for "${matched.label}".`);
    }

    const unitCost = trimOrEmpty(row.receive_unit_cost)
      || trimOrEmpty(row.default_purchase_price)
      || valueOrEmpty(matched.unit_cost);
    if (!unitCost) {
      throw new Error(`Unit cost is required for receiving "${matched.label}".`);
    }

    lines.push({
      variant_id: matched.variant_id,
      sku: matched.sku,
      barcode: matched.barcode,
      size: matched.options.size,
      color: matched.options.color,
      other: matched.options.other,
      default_purchase_price: unitCost,
      default_selling_price:
        trimOrEmpty(row.default_selling_price)
        || valueOrEmpty(matched.unit_price ?? matched.effective_unit_price),
      min_selling_price:
        trimOrEmpty(row.min_selling_price)
        || valueOrEmpty(matched.min_price ?? matched.effective_min_price),
      reorder_level: trimOrEmpty(row.reorder_level) || matched.reorder_level || '0',
      status: trimOrEmpty(row.status) || 'active',
      quantity,
    });
  }

  return lines;
}

function variantOptionValues(
  row: CatalogVariantInput | CatalogVariant,
): VariantOptionValues {
  if ('options' in row) {
    return {
      size: row.options.size,
      color: row.options.color,
      other: row.options.other,
    };
  }
  return {
    size: row.size,
    color: row.color,
    other: row.other,
  };
}

function variantsToGenerator(rows: Array<CatalogVariantInput | CatalogVariant>): GeneratorDraft {
  const sizeValues = Array.from(new Set(rows.map((row) => variantOptionValues(row).size.trim()).filter(Boolean)));
  const colorValues = Array.from(new Set(rows.map((row) => variantOptionValues(row).color.trim()).filter(Boolean)));
  const otherValues = Array.from(new Set(rows.map((row) => variantOptionValues(row).other.trim()).filter(Boolean)));
  return {
    size_values: sizeValues.join(', '),
    color_values: colorValues.join(', '),
    other_values: otherValues.join(', '),
  };
}

function stockOptionLabel(item: InventoryStockRow) {
  return `${item.product_name} / ${item.label} · SKU ${item.sku} · Available ${formatQuantity(item.available_to_sell)}`;
}

function responseToLookupSummary(mode: LookupMode, payload: { query: string; productName: string }) {
  if (mode === 'exact') {
    return {
      mode,
      title: `Exact variant matched for "${payload.query}"`,
      detail: `Loaded ${payload.productName}. Receipt is pre-selected for the exact matched variant.`,
    };
  }
  if (mode === 'product') {
    return {
      mode,
      title: `Existing product matched for "${payload.query}"`,
      detail: `Loaded ${payload.productName}. Add/edit variant rows, then save or receive stock.`,
    };
  }
  if (mode === 'new') {
    return {
      mode,
      title: `No product matched "${payload.query}"`,
      detail: 'A new product draft has been prepared. Complete product and variant rows, then save.',
    };
  }
  return {
    mode,
    title: 'Search by name, SKU, or barcode',
    detail: 'The workspace will open exact variant, existing product, or new draft automatically.',
  };
}

export function ProductsStockWorkspace() {
  const searchParams = useSearchParams();
  const searchKey = searchParams.toString();
  const rowCounterRef = useRef(0);

  const [lookupInput, setLookupInput] = useState('');
  const [lookupPending, setLookupPending] = useState(false);
  const [draft, setDraft] = useState<UnifiedDraft>(() => createDraftFromSuggestion(rowCounterRef, '', ''));
  const [productImage, setProductImage] = useState<ProductMedia | null>(null);
  const [lookupSummary, setLookupSummary] = useState<LookupSummary>(
    responseToLookupSummary('idle', { query: '', productName: '' }),
  );
  const [generator, setGenerator] = useState<GeneratorDraft>({ ...EMPTY_GENERATOR });
  const [savePending, setSavePending] = useState(false);
  const [receivePending, setReceivePending] = useState(false);
  const [adjustPending, setAdjustPending] = useState(false);
  const [adjustmentForm, setAdjustmentForm] = useState<InventoryAdjustmentPayload>({ ...EMPTY_ADJUSTMENT });
  const [adjustOptions, setAdjustOptions] = useState<InventoryStockRow[]>([]);
  const [notice, setNotice] = useState('');
  const [error, setError] = useState('');
  const [toast, setToast] = useState('');

  useEffect(() => {
    if (!toast) return undefined;
    const timeoutId = window.setTimeout(() => setToast(''), 2800);
    return () => window.clearTimeout(timeoutId);
  }, [toast]);

  const loadAdjustWorkspace = async (query = '') => {
    try {
      const workspace = await getInventoryWorkspace({ q: query.trim() });
      setAdjustOptions(workspace.stock_items);
    } catch {
      setAdjustOptions([]);
    }
  };

  const startNewDraft = (seed?: string) => {
    const query = (seed ?? lookupInput).trim();
    const skuRoot = normalizeSkuRoot(query);
    setDraft(createDraftFromSuggestion(rowCounterRef, query, skuRoot));
    setProductImage(null);
    setGenerator({ ...EMPTY_GENERATOR });
    setLookupSummary(responseToLookupSummary('new', { query: query || 'new product', productName: query || 'new product' }));
    setNotice('Started a new product draft.');
    setError('');
  };

  const runLookup = async (rawQuery: string) => {
    const query = rawQuery.trim();
    if (!query) {
      startNewDraft('');
      return;
    }

    setLookupPending(true);
    setError('');
    setNotice('');
    try {
      const [intake] = await Promise.all([
        getInventoryIntakeLookup({ q: query }),
        loadAdjustWorkspace(query),
      ]);

      const exact = intake.exact_variants[0];
      if (exact) {
        setDraft(productToDraft(rowCounterRef, exact.product, { selectVariantId: exact.variant.variant_id }));
        setProductImage(exact.product.image);
        setGenerator(variantsToGenerator(intake.exact_variants[0].product.variants));
        setLookupSummary(responseToLookupSummary('exact', { query, productName: exact.product.name }));
        setNotice(`Loaded exact variant: ${exact.variant.label}.`);
        return;
      }

      const firstProduct = intake.product_matches[0];
      if (firstProduct) {
        setDraft(productToDraft(rowCounterRef, firstProduct));
        setProductImage(firstProduct.image);
        setGenerator(variantsToGenerator(firstProduct.variants));
        setLookupSummary(responseToLookupSummary('product', { query, productName: firstProduct.name }));
        setNotice(`Loaded existing product: ${firstProduct.name}.`);
        return;
      }

      const suggestedName = intake.suggested_new_product?.product_name || query;
      const suggestedSkuRoot = intake.suggested_new_product?.sku_root || normalizeSkuRoot(query);
      setDraft(createDraftFromSuggestion(rowCounterRef, suggestedName, suggestedSkuRoot));
      setProductImage(null);
      setGenerator({ ...EMPTY_GENERATOR });
      setLookupSummary(responseToLookupSummary('new', { query, productName: suggestedName }));
      setNotice(`Prepared new draft: ${suggestedName}.`);
    } catch (lookupError) {
      setError(safeErrorMessage(lookupError, 'Unable to search products right now.'));
    } finally {
      setLookupPending(false);
    }
  };

  useEffect(() => {
    const query = (searchParams.get('q') ?? '').trim();
    if (!query) {
      void loadAdjustWorkspace('');
      return;
    }
    setLookupInput(query);
    void runLookup(query);
  }, [searchKey]);

  const updateIdentity = <K extends keyof ProductIdentityInput>(key: K, value: ProductIdentityInput[K]) => {
    setDraft((current) => ({
      ...current,
      identity: {
        ...current.identity,
        [key]: value,
      },
    }));
  };

  const updateVariantRow = (rowId: string, patch: Partial<VariantDraft>) => {
    setDraft((current) => ({
      ...current,
      variants: current.variants.map((row) => (row.row_id === rowId ? { ...row, ...patch } : row)),
    }));
  };

  const addManualVariantRow = () => {
    setDraft((current) => ({
      ...current,
      variants: [
        ...current.variants,
        createEmptyVariantRow(rowCounterRef, {
          default_selling_price: current.identity.default_selling_price,
          min_selling_price: current.identity.min_selling_price,
        }),
      ],
    }));
  };

  const removeVariantRow = (rowId: string) => {
    setDraft((current) => {
      const remaining = current.variants.filter((row) => row.row_id !== rowId);
      return {
        ...current,
        variants: remaining.length ? remaining : [createEmptyVariantRow(rowCounterRef, {})],
      };
    });
  };

  const applyGenerator = () => {
    const combos = buildVariantCombinations(generator);
    const realCombos = combos.filter((combo) => Boolean(combo.size || combo.color || combo.other));
    if (!realCombos.length) {
      setNotice('Add size, color, or other values before generating variants.');
      return;
    }

    setDraft((current) => {
      const seen = new Set(
        current.variants.map((row) =>
          signatureForVariant({
            size: row.size,
            color: row.color,
            other: row.other,
          }),
        ),
      );

      const additions: VariantDraft[] = [];
      realCombos.forEach((combo) => {
        const signature = signatureForVariant(combo);
        if (seen.has(signature)) {
          return;
        }
        seen.add(signature);
        additions.push(
          createEmptyVariantRow(rowCounterRef, {
            size: combo.size,
            color: combo.color,
            other: combo.other,
            default_selling_price: current.identity.default_selling_price,
            min_selling_price: current.identity.min_selling_price,
          }),
        );
      });

      if (!additions.length) {
        return current;
      }

      return {
        ...current,
        variants: [...current.variants, ...additions],
      };
    });

    setNotice('Variant combinations merged into row editor.');
    setError('');
  };

  const prepareCatalogPayload = () => {
    const identity = normalizeIdentity(draft.identity);
    if (identity.product_name.length < 2) {
      throw new Error('Product name must be at least 2 characters.');
    }

    const variants = normalizeVariantRows(draft.variants);
    const duplicateError = validateVariantUniqueness(variants);
    if (duplicateError) {
      throw new Error(duplicateError);
    }

    return {
      product_id: draft.product_id,
      identity,
      variants,
    };
  };

  const applySavedProduct = (savedProduct: CatalogProduct, previousRows: VariantDraft[]) => {
    setDraft((current) => ({
      ...current,
      product_id: savedProduct.product_id,
      identity: {
        ...current.identity,
        ...productIdentityFromCatalog(savedProduct),
      },
      variants: mergeReceiptDrafts(rowCounterRef, previousRows, savedProduct),
    }));
    setProductImage(savedProduct.image);
    setGenerator(variantsToGenerator(savedProduct.variants));
  };

  const saveProductOnly = async () => {
    setSavePending(true);
    setError('');
    setNotice('');
    try {
      const payload = prepareCatalogPayload();
      const previousRows = draft.variants;
      const response = await saveCatalogProduct(payload);
      applySavedProduct(response.product, previousRows);
      setNotice(`Product saved: ${response.product.name}.`);
      setToast('Product saved successfully.');
      await loadAdjustWorkspace(response.product.name);
    } catch (saveError) {
      if (saveError instanceof ApiError && saveError.status === 404) {
        setError('Catalog save endpoint is unavailable on this backend deployment.');
      } else {
        setError(safeErrorMessage(saveError, 'Unable to save product.'));
      }
    } finally {
      setSavePending(false);
    }
  };

  const saveAndReceiveStock = async () => {
    setReceivePending(true);
    setError('');
    setNotice('');
    try {
      const payload = prepareCatalogPayload();
      const previousRows = draft.variants;
      const saveResponse = await saveCatalogProduct(payload);
      applySavedProduct(saveResponse.product, previousRows);

      const mergedRows = mergeReceiptDrafts(rowCounterRef, previousRows, saveResponse.product);
      const lines = buildReceiveLines(saveResponse.product, mergedRows);

      const receivePayload: ReceiveStockPayload = {
        action: 'receive_stock',
        notes: trimOrEmpty(draft.notes),
        update_matched_product_details: false,
        identity: {
          ...normalizeIdentity(draft.identity),
          product_id: saveResponse.product.product_id,
        },
        lines,
      };

      const receiveResponse = await receiveInventoryStock(receivePayload);
      applySavedProduct(receiveResponse.product, mergedRows.map((row) => ({
        ...row,
        receive_selected: false,
        receive_quantity: '',
        receive_unit_cost: '',
      })));
      setNotice(
        `Saved and received stock under ${receiveResponse.purchase_number || 'new receipt'} for ${receiveResponse.product.name}.`,
      );
      setToast('Product + stock receipt completed.');
      await loadAdjustWorkspace(receiveResponse.product.name);
    } catch (submitError) {
      setError(safeErrorMessage(submitError, 'Unable to save and receive stock.'));
    } finally {
      setReceivePending(false);
    }
  };

  const submitAdjustment = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setAdjustPending(true);
    setError('');
    setNotice('');
    try {
      await createInventoryAdjustment(adjustmentForm);
      setNotice('Inventory adjustment recorded.');
      setToast('Adjustment saved.');
      setAdjustmentForm({ ...EMPTY_ADJUSTMENT });
      await loadAdjustWorkspace(lookupInput);
    } catch (adjustError) {
      setError(safeErrorMessage(adjustError, 'Unable to record adjustment.'));
    } finally {
      setAdjustPending(false);
    }
  };

  const selectedReceiveCount = useMemo(
    () => draft.variants.filter((row) => row.receive_selected).length,
    [draft.variants],
  );

  const adjustableVariants = useMemo(() => {
    const fromDraft: InventoryStockRow[] = draft.variants
      .filter((row) => trimOrEmpty(row.variant_id))
      .map((row) => ({
        variant_id: row.variant_id as string,
        product_id: draft.product_id || '',
        product_name: draft.identity.product_name || 'Current draft',
        image_url: draft.identity.image_url,
        image: productImage,
        label: `${draft.identity.product_name || 'Product'} / ${variantTitle(row)}`,
        sku: row.sku || buildSkuPreview(draft.identity.product_name, draft.identity.sku_root, row),
        barcode: row.barcode,
        supplier: draft.identity.supplier,
        category: draft.identity.category,
        location_id: '',
        location_name: '',
        unit_cost: row.default_purchase_price || null,
        unit_price: row.default_selling_price || null,
        reorder_level: row.reorder_level || '0',
        on_hand: '0',
        reserved: '0',
        available_to_sell: '0',
        low_stock: false,
      }));

    const seen = new Set<string>();
    const merged: InventoryStockRow[] = [];
    [...fromDraft, ...adjustOptions].forEach((item) => {
      if (seen.has(item.variant_id)) {
        return;
      }
      seen.add(item.variant_id);
      merged.push(item);
    });
    return merged;
  }, [adjustOptions, draft.identity, draft.product_id, draft.variants, productImage]);

  return (
    <div className="workspace-stack">
      {toast ? <WorkspaceToast message={toast} onClose={() => setToast('')} /> : null}
      <WorkspacePanel
        title={
          <span className="workspace-heading">
            Products & Stock
            <WorkspaceHint
              label="Products and stock help"
              text="One flow: search product intent, edit product plus variants, then either save only or save and receive stock in one action."
            />
          </span>
        }
        description="Unified workspace for product creation, variant editing, stock receiving, and compact stock adjustments."
        actions={
          <div className="workspace-inline-actions">
            <form
              className="workspace-inline-actions"
              onSubmit={(event) => {
                event.preventDefault();
                void runLookup(lookupInput);
              }}
            >
              <input
                id="products-stock-lookup"
                type="search"
                value={lookupInput}
                placeholder="Search by product, SKU, barcode, or variant"
                onChange={(event) => setLookupInput(event.target.value)}
              />
              <button type="submit" disabled={lookupPending}>
                {lookupPending ? 'Searching…' : 'Find product'}
              </button>
            </form>
            <button
              type="button"
              className="secondary"
              onClick={() => startNewDraft(lookupInput)}
              disabled={lookupPending || savePending || receivePending}
            >
              Start new product
            </button>
          </div>
        }
      >
        {notice ? <WorkspaceNotice tone="success">{notice}</WorkspaceNotice> : null}
        {error ? <WorkspaceNotice tone="error">{error}</WorkspaceNotice> : null}

        <WorkspaceNotice tone={lookupSummary.mode === 'new' ? 'info' : 'success'}>
          <div className="workspace-stack">
            <strong>{lookupSummary.title}</strong>
            <span>{lookupSummary.detail}</span>
          </div>
        </WorkspaceNotice>

        <form
          className="workspace-form"
          onSubmit={(event) => {
            event.preventDefault();
            void saveAndReceiveStock();
          }}
        >
          <section className="workspace-subsection">
            <div className="workspace-subsection-header">
              <h4 className="workspace-heading">
                Product details
                <WorkspaceHint
                  label="Product details help"
                  text="Parent-level fields are shared across variants. Variant rows below remain the saleable SKU layer."
                />
              </h4>
            </div>
            <div className="workspace-form-grid">
              <label>
                Product name
                <input
                  value={draft.identity.product_name}
                  onChange={(event) => updateIdentity('product_name', event.target.value)}
                  required
                />
              </label>
              <label>
                Supplier
                <input
                  value={draft.identity.supplier}
                  onChange={(event) => updateIdentity('supplier', event.target.value)}
                />
              </label>
              <label>
                Category
                <input
                  value={draft.identity.category}
                  onChange={(event) => updateIdentity('category', event.target.value)}
                />
              </label>
              <label>
                Brand
                <input
                  value={draft.identity.brand}
                  onChange={(event) => updateIdentity('brand', event.target.value)}
                />
              </label>
              <label>
                SKU base
                <input
                  value={draft.identity.sku_root}
                  onChange={(event) => updateIdentity('sku_root', event.target.value)}
                  placeholder="Leave blank to auto-generate"
                />
              </label>
              <label>
                Default selling price
                <input
                  value={draft.identity.default_selling_price}
                  inputMode="decimal"
                  onChange={(event) => updateIdentity('default_selling_price', event.target.value)}
                />
              </label>
              <label>
                Minimum selling price
                <input
                  value={draft.identity.min_selling_price}
                  inputMode="decimal"
                  onChange={(event) => updateIdentity('min_selling_price', event.target.value)}
                />
              </label>
              <div className="field-span-2">
                <label>Product photo</label>
                <ProductPhotoField
                  image={productImage}
                  onUploaded={(image) => {
                    setProductImage(image);
                    setDraft((current) => ({
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
                    setDraft((current) => ({
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
            <label>
              Description
              <textarea
                rows={3}
                value={draft.identity.description}
                onChange={(event) => updateIdentity('description', event.target.value)}
              />
            </label>
          </section>

          <section className="workspace-subsection">
            <div className="workspace-subsection-header">
              <h4 className="workspace-heading">
                Variant rows
                <WorkspaceHint
                  label="Variant rows help"
                  text="Rows are primary. Use generator only when you need quick size/color/other combination expansion."
                />
              </h4>
              <button type="button" onClick={addManualVariantRow}>Add row</button>
            </div>

            <div className="workspace-form-grid compact">
              <label>
                Generate sizes
                <input
                  value={generator.size_values}
                  placeholder="40, 41, 42"
                  onChange={(event) => setGenerator((current) => ({ ...current, size_values: event.target.value }))}
                />
              </label>
              <label>
                Generate colors
                <input
                  value={generator.color_values}
                  placeholder="Black, White"
                  onChange={(event) => setGenerator((current) => ({ ...current, color_values: event.target.value }))}
                />
              </label>
              <label>
                Generate other options
                <input
                  value={generator.other_values}
                  placeholder="Men, Women"
                  onChange={(event) => setGenerator((current) => ({ ...current, other_values: event.target.value }))}
                />
              </label>
              <div className="workspace-actions">
                <button type="button" onClick={applyGenerator}>Generate combinations</button>
              </div>
            </div>

            <div className="table-scroll">
              <table className="workspace-table workspace-table-sticky">
                <thead>
                  <tr>
                    <th>Receive</th>
                    <th>Variant</th>
                    <th>SKU preview</th>
                    <th>Barcode</th>
                    <th>Sell price</th>
                    <th>Min price</th>
                    <th>Reorder</th>
                    <th>Qty</th>
                    <th>Unit cost</th>
                    <th>Action</th>
                  </tr>
                </thead>
                <tbody>
                  {draft.variants.map((row) => {
                    const previewSku = buildSkuPreview(draft.identity.product_name, draft.identity.sku_root, row);
                    const isSaved = Boolean(row.variant_id);
                    return (
                      <tr key={row.row_id}>
                        <td>
                          <input
                            type="checkbox"
                            checked={row.receive_selected}
                            onChange={(event) =>
                              updateVariantRow(row.row_id, {
                                receive_selected: event.target.checked,
                                receive_quantity: event.target.checked && !row.receive_quantity ? '1' : row.receive_quantity,
                                receive_unit_cost:
                                  event.target.checked && !row.receive_unit_cost
                                    ? row.default_purchase_price
                                    : row.receive_unit_cost,
                              })
                            }
                          />
                        </td>
                        <td>
                          <div className="workspace-form-grid compact">
                            <input
                              value={row.size}
                              placeholder="Size"
                              onChange={(event) => updateVariantRow(row.row_id, { size: event.target.value })}
                            />
                            <input
                              value={row.color}
                              placeholder="Color"
                              onChange={(event) => updateVariantRow(row.row_id, { color: event.target.value })}
                            />
                            <input
                              value={row.other}
                              placeholder="Other"
                              onChange={(event) => updateVariantRow(row.row_id, { other: event.target.value })}
                            />
                          </div>
                          <p className="workspace-field-note">
                            {isSaved ? 'Saved variant' : 'New variant'} · {variantTitle(row)}
                          </p>
                        </td>
                        <td>
                          <input
                            value={previewSku}
                            readOnly
                          />
                        </td>
                        <td>
                          <input
                            value={row.barcode}
                            onChange={(event) => updateVariantRow(row.row_id, { barcode: event.target.value })}
                          />
                        </td>
                        <td>
                          <input
                            value={row.default_selling_price}
                            inputMode="decimal"
                            onChange={(event) => updateVariantRow(row.row_id, { default_selling_price: event.target.value })}
                          />
                        </td>
                        <td>
                          <input
                            value={row.min_selling_price}
                            inputMode="decimal"
                            onChange={(event) => updateVariantRow(row.row_id, { min_selling_price: event.target.value })}
                          />
                        </td>
                        <td>
                          <input
                            value={row.reorder_level}
                            inputMode="decimal"
                            onChange={(event) => updateVariantRow(row.row_id, { reorder_level: event.target.value })}
                          />
                        </td>
                        <td>
                          <input
                            value={row.receive_quantity}
                            inputMode="decimal"
                            placeholder={row.receive_selected ? 'Required' : 'Optional'}
                            onChange={(event) => updateVariantRow(row.row_id, { receive_quantity: event.target.value })}
                          />
                        </td>
                        <td>
                          <input
                            value={row.receive_unit_cost}
                            inputMode="decimal"
                            placeholder={row.receive_selected ? 'Required' : 'Optional'}
                            onChange={(event) => updateVariantRow(row.row_id, { receive_unit_cost: event.target.value })}
                          />
                        </td>
                        <td>
                          <button type="button" className="secondary" onClick={() => removeVariantRow(row.row_id)}>
                            Remove
                          </button>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
            {!draft.variants.length ? (
              <WorkspaceEmpty
                title="No variant rows"
                message="Add at least one variant row before saving."
              />
            ) : null}
          </section>

          <section className="workspace-subsection">
            <div className="workspace-subsection-header">
              <h4 className="workspace-heading">
                Receipt notes and actions
                <WorkspaceHint
                  label="Save actions help"
                  text="Save product only keeps catalog data. Save product plus receive stock posts inventory receipt entries in the ledger."
                />
              </h4>
            </div>
            <label>
              Receive notes
              <textarea
                rows={3}
                value={draft.notes}
                onChange={(event) => setDraft((current) => ({ ...current, notes: event.target.value }))}
              />
            </label>
            <p className="workspace-field-note">
              Selected rows for receipt: {selectedReceiveCount}
            </p>
            <div className="workspace-actions">
              <button
                type="button"
                className="secondary"
                onClick={() => {
                  void saveProductOnly();
                }}
                disabled={savePending || receivePending || lookupPending}
              >
                {savePending ? 'Saving…' : 'Save product only'}
              </button>
              <button type="submit" disabled={savePending || receivePending || lookupPending}>
                {receivePending ? 'Saving & receiving…' : 'Save product + receive stock'}
              </button>
            </div>
          </section>
        </form>

        <section className="workspace-subsection">
          <div className="workspace-subsection-header">
            <h4 className="workspace-heading">
              Adjust stock (compact)
              <WorkspaceHint
                label="Adjust stock help"
                text="Use only for recount, damage, theft, loss, or corrections. All changes post to ledger."
              />
            </h4>
          </div>
          <form className="workspace-form" onSubmit={submitAdjustment}>
            <div className="workspace-form-grid compact">
              <label>
                Variant
                <select
                  value={adjustmentForm.variant_id}
                  onChange={(event) => setAdjustmentForm((current) => ({ ...current, variant_id: event.target.value }))}
                  required
                >
                  <option value="">Select variant</option>
                  {adjustableVariants.map((item) => (
                    <option key={item.variant_id} value={item.variant_id}>
                      {stockOptionLabel(item)}
                    </option>
                  ))}
                </select>
              </label>
              <label>
                Quantity delta
                <input
                  value={adjustmentForm.quantity_delta}
                  placeholder="-2 or +5"
                  onChange={(event) =>
                    setAdjustmentForm((current) => ({
                      ...current,
                      quantity_delta: event.target.value,
                    }))
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
                rows={2}
                value={adjustmentForm.notes}
                onChange={(event) => setAdjustmentForm((current) => ({ ...current, notes: event.target.value }))}
              />
            </label>
            <div className="workspace-actions">
              <button type="submit" disabled={adjustPending}>
                {adjustPending ? 'Recording…' : 'Record adjustment'}
              </button>
            </div>
          </form>
        </section>

        {draft.product_id && draft.variants.length ? (
          <section className="workspace-subsection">
            <div className="workspace-subsection-header">
              <h4 className="workspace-heading">Current variant snapshot</h4>
            </div>
            <div className="table-scroll">
              <table className="workspace-table workspace-table-sticky">
                <thead>
                  <tr>
                    <th>Variant</th>
                    <th>SKU</th>
                    <th>Price</th>
                    <th>Min price</th>
                    <th>Reorder</th>
                    <th>Unit cost</th>
                  </tr>
                </thead>
                <tbody>
                  {draft.variants.map((row) => (
                    <tr key={`snapshot-${row.row_id}`}>
                      <td>{variantTitle(row)}</td>
                      <td>{buildSkuPreview(draft.identity.product_name, draft.identity.sku_root, row)}</td>
                      <td>{formatMoney(row.default_selling_price)}</td>
                      <td>{formatMoney(row.min_selling_price)}</td>
                      <td>{formatQuantity(row.reorder_level)}</td>
                      <td>{formatMoney(row.default_purchase_price)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>
        ) : null}
      </WorkspacePanel>
    </div>
  );
}
