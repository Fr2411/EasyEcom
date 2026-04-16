'use client';

import Link from 'next/link';
import { FormEvent, Fragment, useEffect, useMemo, useRef, useState, useTransition } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import { createPortal } from 'react-dom';
import { useAuth } from '@/components/auth/auth-provider';
import {
  createInventoryAdjustment,
  getInventoryIntakeLookup,
  getInventoryWorkspace,
  receiveInventoryStock,
  updateInventoryInlineFields,
} from '@/lib/api/commerce';
import type { CatalogProduct, CatalogVariant, ProductIdentityInput, ProductMedia } from '@/types/catalog';
import type {
  InventoryAdjustmentPayload,
  InventoryIntakeExactVariantMatch,
  InventoryIntakeIdentityInput,
  InventoryStockRow,
  ReceiveStockLineInput,
  ReceiveStockPayload,
} from '@/types/inventory';
import {
  WorkspaceEmpty,
  WorkspaceHint,
  WorkspaceNotice,
  WorkspacePanel,
  WorkspaceTabs,
} from '@/components/commerce/workspace-primitives';
import { formatMoney, formatQuantity } from '@/lib/commerce-format';
import { buildSkuPreview, buildVariantCombinations, signatureForVariant } from '@/lib/variant-generator';
import { ProductPhotoField } from '@/components/commerce/product-photo-field';
import { getPurchaseOrder, listPurchaseOrders } from '@/lib/api/purchases';
import type { PurchaseDetail } from '@/types/purchases';


type InventoryTab = 'stock' | 'receive' | 'adjust' | 'low-stock';
type InventoryStockSegment = 'all' | 'normal' | 'low' | 'out';
type InventoryColumnKey = 'supplier' | 'on_hand' | 'reserved' | 'available' | 'variants' | 'alerts';

type InventoryProductGroup = {
  product_id: string;
  product_name: string;
  supplier: string;
  category: string;
  image_url: string;
  image: ProductMedia | null;
  on_hand: number;
  reserved: number;
  available_to_sell: number;
  low_stock_count: number;
  variants: InventoryStockRow[];
};

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

type IntakeRecommendation =
  | {
      kind: 'idle';
      title: string;
      summary: string;
      actionLabel: string;
    }
  | {
      kind: 'exact';
      title: string;
      summary: string;
      actionLabel: string;
    }
  | {
      kind: 'product';
      title: string;
      summary: string;
      actionLabel: string;
    }
  | {
      kind: 'new';
      title: string;
      summary: string;
      actionLabel: string;
    };

const EMPTY_IDENTITY: InventoryIntakeIdentityInput = {
  product_name: '',
  product_id: '',
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

const EMPTY_LINE: ReceiveStockLineInput = {
  variant_id: '',
  sku: '',
  barcode: '',
  size: '',
  color: '',
  other: '',
  quantity: '',
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
  quantity: '',
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
    image_url: product.image_url || '',
    pending_primary_media_upload_id: '',
    remove_primary_image: false,
    sku_root: product.sku_root,
    default_selling_price: valueOrEmpty(product.default_price),
    min_selling_price: valueOrEmpty(product.min_price),
    max_discount_percent: valueOrEmpty(product.max_discount_percent),
    status: product.status,
  };
}

function lineFromExistingVariant(variant: CatalogVariant, quantity = '1'): ReceiveStockLineInput {
  return {
    variant_id: variant.variant_id,
    sku: variant.sku,
    barcode: variant.barcode,
    size: variant.options.size,
    color: variant.options.color,
    other: variant.options.other,
    quantity,
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
    quantity: '',
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
    quantity: generator.quantity,
    default_purchase_price: generator.default_purchase_price,
    default_selling_price: generator.default_selling_price || identity.default_selling_price,
    min_selling_price: generator.min_selling_price || identity.min_selling_price,
    reorder_level: generator.reorder_level,
  };
}

function cloneLine(line: ReceiveStockLineInput): ReceiveStockLineInput {
  return { ...line };
}

export function receiveLinesFromPurchaseOrder(order: PurchaseDetail): ReceiveStockLineInput[] {
  return order.lines
    .filter((line) => line.variant_id)
    .map((line) => ({
      ...EMPTY_LINE,
      variant_id: line.variant_id,
      quantity: String(line.qty ?? ''),
      default_purchase_price: String(line.unit_cost ?? ''),
    }));
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

export function deriveIntakeRecommendation(results: Awaited<ReturnType<typeof getInventoryIntakeLookup>> | null): IntakeRecommendation {
  if (!results) {
    return {
      kind: 'idle',
      title: 'Start with one item',
      summary: 'Scan a barcode, SKU, product name, or variant and the workspace will stage the best match.',
      actionLabel: 'Review next step',
    };
  }

  const exact = results.exact_variants[0];
  if (exact) {
    return {
      kind: 'exact',
      title: `Exact match: ${exact.variant.label}`,
      summary: `Matched by ${exact.match_reason}. The workspace has already focused this variant for receiving.`,
      actionLabel: 'Continue receiving',
    };
  }

  const product = results.product_matches[0];
  if (product) {
    const variantCount = product.variants.length;
    return {
      kind: 'product',
      title: `Existing product: ${product.name}`,
      summary: `${variantCount} saved variant${variantCount === 1 ? '' : 's'} found. Review the product and choose the line you want to receive.`,
      actionLabel: 'Review product',
    };
  }

  const suggestion = results.suggested_new_product;
  return {
    kind: 'new',
    title: suggestion ? `No match found: ${suggestion.product_name}` : 'No match found',
    summary: suggestion
      ? 'A new product draft is staged with the best available identity hints.'
      : 'Start a new item draft with the typed intent details.',
    actionLabel: 'Start new product',
  };
}

function productVariantCount(product: CatalogProduct) {
  return product.variants.length;
}

function toNumber(value: string) {
  return Number(value || '0');
}

function stockStatusForGroup(group: InventoryProductGroup): Exclude<InventoryStockSegment, 'all'> {
  if (group.available_to_sell <= 0) {
    return 'out';
  }
  if (group.low_stock_count > 0) {
    return 'low';
  }
  return 'normal';
}

function matchesStockSegment(group: InventoryProductGroup, stockFilter: InventoryStockSegment) {
  return stockFilter === 'all' ? true : stockStatusForGroup(group) === stockFilter;
}

const INVENTORY_COLUMN_CONFIG: Array<{ key: InventoryColumnKey; label: string }> = [
  { key: 'supplier', label: 'Supplier' },
  { key: 'on_hand', label: 'On Hand' },
  { key: 'reserved', label: 'Reserved' },
  { key: 'available', label: 'Available' },
  { key: 'variants', label: 'Variants' },
  { key: 'alerts', label: 'Alerts' },
];

const DEFAULT_VISIBLE_COLUMNS: Record<InventoryColumnKey, boolean> = {
  supplier: true,
  on_hand: true,
  reserved: true,
  available: true,
  variants: true,
  alerts: true,
};

function matchesTagFilter(group: InventoryProductGroup, filterValue: string) {
  const normalized = filterValue.trim().toLowerCase();
  if (!normalized) {
    return true;
  }
  const tags = [
    group.product_name,
    group.supplier,
    group.category,
    ...group.variants.flatMap((variant) => [variant.label, variant.sku, variant.barcode]),
  ]
    .map((value) => value.trim().toLowerCase())
    .filter(Boolean);
  return tags.some((tag) => tag.includes(normalized));
}

export function deriveInventoryProductGroups(items: InventoryStockRow[]): InventoryProductGroup[] {
  const groups = new Map<string, InventoryProductGroup>();
  items.forEach((item) => {
    const existing = groups.get(item.product_id);
    if (existing) {
      existing.variants.push(item);
      existing.on_hand += toNumber(item.on_hand);
      existing.reserved += toNumber(item.reserved);
      existing.available_to_sell += toNumber(item.available_to_sell);
      existing.low_stock_count += item.low_stock ? 1 : 0;
      return;
    }
    groups.set(item.product_id, {
      product_id: item.product_id,
      product_name: item.product_name,
      supplier: item.supplier,
      category: item.category,
      image_url: item.image_url,
      image: item.image,
      on_hand: toNumber(item.on_hand),
      reserved: toNumber(item.reserved),
      available_to_sell: toNumber(item.available_to_sell),
      low_stock_count: item.low_stock ? 1 : 0,
      variants: [item],
    });
  });
  return Array.from(groups.values()).sort((left, right) => left.product_name.localeCompare(right.product_name));
}

export function deriveInventorySearchSuggestions(
  items: InventoryStockRow[],
  query: string,
  limit = 12
): string[] {
  const normalizedQuery = query.trim().toLowerCase();
  const ranked = new Map<string, number>();
  items.forEach((item) => {
    const candidates = [
      item.product_name,
      item.sku,
      item.label,
      item.barcode,
      item.supplier,
      item.category,
    ];
    candidates.forEach((raw) => {
      const candidate = raw.trim();
      if (!candidate) {
        return;
      }
      const lower = candidate.toLowerCase();
      if (!normalizedQuery || lower.includes(normalizedQuery)) {
        const score = normalizedQuery && lower.startsWith(normalizedQuery) ? 0 : 1;
        const existing = ranked.get(candidate);
        if (existing === undefined || score < existing) {
          ranked.set(candidate, score);
        }
      }
    });
  });
  return Array.from(ranked.entries())
    .sort(([leftText, leftScore], [rightText, rightScore]) => {
      if (leftScore !== rightScore) {
        return leftScore - rightScore;
      }
      return leftText.localeCompare(rightText);
    })
    .slice(0, limit)
    .map(([text]) => text);
}

export function InventoryWorkspace() {
  const { user } = useAuth();
  const router = useRouter();
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
  const [productImage, setProductImage] = useState<ProductMedia | null>(null);
  const [generator, setGenerator] = useState<IntakeGeneratorState>({ ...EMPTY_GENERATOR });
  const [notice, setNotice] = useState('');
  const [error, setError] = useState('');
  const [lookupPending, setLookupPending] = useState(false);
  const [submitPending, setSubmitPending] = useState(false);
  const [expandedProducts, setExpandedProducts] = useState<Record<string, boolean>>({});
  const [openQuickActionsFor, setOpenQuickActionsFor] = useState<string | null>(null);
  const [quickActionsPosition, setQuickActionsPosition] = useState<{ top: number; left: number } | null>(null);
  const [filtersOpen, setFiltersOpen] = useState(false);
  const [supplierFilter, setSupplierFilter] = useState('');
  const [categoryFilter, setCategoryFilter] = useState('');
  const [tagFilter, setTagFilter] = useState('');
  const [stockFilter, setStockFilter] = useState<InventoryStockSegment>('all');
  const [adjustmentProductId, setAdjustmentProductId] = useState<string>('');
  const [columnSelectorOpen, setColumnSelectorOpen] = useState(false);
  const [visibleColumns, setVisibleColumns] = useState<Record<InventoryColumnKey, boolean>>(DEFAULT_VISIBLE_COLUMNS);
  const [supplierDrafts, setSupplierDrafts] = useState<Record<string, string>>({});
  const [reorderDrafts, setReorderDrafts] = useState<Record<string, string>>({});
  const [savingSupplierFor, setSavingSupplierFor] = useState<string | null>(null);
  const [savingReorderFor, setSavingReorderFor] = useState<string | null>(null);
  const [outstandingPurchaseOrders, setOutstandingPurchaseOrders] = useState<Awaited<ReturnType<typeof listPurchaseOrders>>['items']>([]);
  const [selectedPurchaseOrderId, setSelectedPurchaseOrderId] = useState('');
  const [loadingPurchaseOrders, setLoadingPurchaseOrders] = useState(false);
  const [isPending, startTransition] = useTransition();
  const quickActionsMenuRef = useRef<HTMLDivElement | null>(null);
  const quickActionsButtonRefs = useRef<Record<string, HTMLButtonElement | null>>({});
  const intakeRecommendation = deriveIntakeRecommendation(intakeResults);
  const exactVariantMatches = intakeResults?.exact_variants ?? [];
  const visibleProductMatches = useMemo(() => {
    if (!intakeResults?.product_matches.length) {
      return [];
    }
    const exactProductIds = new Set((intakeResults.exact_variants ?? []).map((match) => match.product.product_id));
    return intakeResults.product_matches.filter((product) => !exactProductIds.has(product.product_id));
  }, [intakeResults]);
  const newProductSuggestion = intakeResults?.suggested_new_product ?? null;
  const productGroups = useMemo(
    () => deriveInventoryProductGroups(workspace?.stock_items ?? []),
    [workspace?.stock_items],
  );
  const filteredProductGroups = useMemo(() => {
    return productGroups.filter((group) => {
      const supplierMatch = !supplierFilter.trim() || group.supplier.toLowerCase().includes(supplierFilter.trim().toLowerCase());
      const categoryMatch = !categoryFilter.trim() || group.category.toLowerCase().includes(categoryFilter.trim().toLowerCase());
      const stockMatch = matchesStockSegment(group, stockFilter);
      const tagMatch = matchesTagFilter(group, tagFilter);
      return supplierMatch && categoryMatch && stockMatch && tagMatch;
    });
  }, [categoryFilter, productGroups, stockFilter, supplierFilter, tagFilter]);
  const searchSuggestions = useMemo(
    () => deriveInventorySearchSuggestions(workspace?.stock_items ?? [], queryInput),
    [queryInput, workspace?.stock_items],
  );
  const supplierOptions = useMemo(
    () => Array.from(new Set(productGroups.map((group) => group.supplier.trim()).filter(Boolean))).sort((a, b) => a.localeCompare(b)),
    [productGroups],
  );
  const categoryOptions = useMemo(
    () => Array.from(new Set(productGroups.map((group) => group.category.trim()).filter(Boolean))).sort((a, b) => a.localeCompare(b)),
    [productGroups],
  );
  const stockCounts = useMemo(() => {
    const counts: Record<InventoryStockSegment, number> = {
      all: productGroups.length,
      normal: 0,
      low: 0,
      out: 0,
    };
    productGroups.forEach((group) => {
      counts[stockStatusForGroup(group)] += 1;
    });
    return counts;
  }, [productGroups]);
  const hasActiveInventoryFilters = Boolean(
    supplierFilter.trim() || categoryFilter.trim() || tagFilter.trim() || stockFilter !== 'all',
  );
  const openQuickActionGroup = useMemo(
    () => filteredProductGroups.find((group) => group.product_id === openQuickActionsFor) ?? null,
    [filteredProductGroups, openQuickActionsFor],
  );
  const adjustmentOptions = useMemo(() => {
    if (!adjustmentProductId || !workspace?.stock_items.length) {
      return workspace?.stock_items ?? [];
    }
    return workspace.stock_items.filter((item) => item.product_id === adjustmentProductId);
  }, [adjustmentProductId, workspace?.stock_items]);

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

  const loadOutstandingPurchaseOrders = async () => {
    setLoadingPurchaseOrders(true);
    try {
      const payload = await listPurchaseOrders({ status: 'draft' });
      setOutstandingPurchaseOrders(payload.items);
    } finally {
      setLoadingPurchaseOrders(false);
    }
  };

  const positionQuickActionsMenu = (button: HTMLButtonElement) => {
    const rect = button.getBoundingClientRect();
    const horizontalMargin = 8;
    const verticalMargin = 8;
    const estimatedWidth = 176;
    const estimatedHeight = 156;
    let left = rect.right - estimatedWidth;
    if (left < horizontalMargin) {
      left = rect.left;
    }
    left = Math.min(left, window.innerWidth - estimatedWidth - horizontalMargin);
    left = Math.max(horizontalMargin, left);
    let top = rect.bottom + verticalMargin;
    if (top + estimatedHeight > window.innerHeight - verticalMargin) {
      top = rect.top - estimatedHeight - verticalMargin;
    }
    top = Math.max(verticalMargin, top);
    setQuickActionsPosition({ top, left });
  };

  const toggleQuickActions = (productId: string, button: HTMLButtonElement) => {
    setOpenQuickActionsFor((current) => {
      if (current === productId) {
        setQuickActionsPosition(null);
        return null;
      }
      positionQuickActionsMenu(button);
      return productId;
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

  useEffect(() => {
    if (activeTab !== 'receive') {
      return;
    }
    void loadOutstandingPurchaseOrders().catch((purchaseOrderError) => {
      setError(purchaseOrderError instanceof Error ? purchaseOrderError.message : 'Unable to load outstanding purchase orders.');
    });
  }, [activeTab]);

  useEffect(() => {
    if (typeof window === 'undefined') {
      return;
    }
    const raw = window.localStorage.getItem('inventory-stock-visible-columns');
    if (!raw) {
      return;
    }
    try {
      const parsed = JSON.parse(raw) as Partial<Record<InventoryColumnKey, boolean>>;
      setVisibleColumns({
        ...DEFAULT_VISIBLE_COLUMNS,
        ...parsed,
      });
    } catch {
      setVisibleColumns(DEFAULT_VISIBLE_COLUMNS);
    }
  }, []);

  useEffect(() => {
    if (typeof window === 'undefined') {
      return;
    }
    window.localStorage.setItem('inventory-stock-visible-columns', JSON.stringify(visibleColumns));
  }, [visibleColumns]);

  useEffect(() => {
    setSupplierDrafts((current) => {
      const next = { ...current };
      filteredProductGroups.forEach((group) => {
        if (next[group.product_id] === undefined) {
          next[group.product_id] = group.supplier || '';
        }
      });
      return next;
    });
    setReorderDrafts((current) => {
      const next = { ...current };
      filteredProductGroups.forEach((group) => {
        group.variants.forEach((variant) => {
          if (next[variant.variant_id] === undefined) {
            next[variant.variant_id] = variant.reorder_level;
          }
        });
      });
      return next;
    });
  }, [filteredProductGroups]);

  useEffect(() => {
    if (!openQuickActionsFor) {
      return;
    }
    const button = quickActionsButtonRefs.current[openQuickActionsFor];
    if (!button) {
      setOpenQuickActionsFor(null);
      setQuickActionsPosition(null);
      return;
    }
    const reposition = () => positionQuickActionsMenu(button);
    reposition();
    const closeOnOutsideClick = (event: MouseEvent) => {
      const target = event.target as Node;
      if (quickActionsMenuRef.current?.contains(target)) {
        return;
      }
      if (button.contains(target)) {
        return;
      }
      setOpenQuickActionsFor(null);
      setQuickActionsPosition(null);
    };
    window.addEventListener('resize', reposition);
    window.addEventListener('scroll', reposition, true);
    document.addEventListener('mousedown', closeOnOutsideClick);
    return () => {
      window.removeEventListener('resize', reposition);
      window.removeEventListener('scroll', reposition, true);
      document.removeEventListener('mousedown', closeOnOutsideClick);
    };
  }, [openQuickActionsFor]);

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
    setProductImage(null);
  };

  const beginAdjustmentForProduct = (productGroup: InventoryProductGroup) => {
    setAdjustmentProductId(productGroup.product_id);
    setAdjustmentForm({
      ...EMPTY_ADJUSTMENT,
      variant_id: productGroup.variants.length === 1 ? productGroup.variants[0].variant_id : '',
    });
    setActiveTab('adjust');
    setNotice(
      productGroup.variants.length === 1
        ? `Adjustment opened for ${productGroup.product_name}.`
        : `Select the variant to adjust for ${productGroup.product_name}.`,
    );
    setError('');
  };

  const beginReceiveForProduct = (productGroup: InventoryProductGroup) => {
    const matchingProduct = intakeResults?.product_matches.find((item) => item.product_id === productGroup.product_id) ?? selectedProduct;
    if (matchingProduct && matchingProduct.product_id === productGroup.product_id) {
      beginExistingProduct(
        matchingProduct,
        matchingProduct.variants.length === 1 ? [lineFromExistingVariant(matchingProduct.variants[0])] : [],
      );
      setActiveTab('receive');
      setOpenQuickActionsFor(null);
      return;
    }
    void openQuickReceive(productGroup.variants[0]?.sku || productGroup.product_name);
    setOpenQuickActionsFor(null);
  };

  const beginModifyProduct = (productGroup: InventoryProductGroup) => {
    setOpenQuickActionsFor(null);
    router.push(`/catalog?q=${encodeURIComponent(productGroup.product_name)}&product_id=${encodeURIComponent(productGroup.product_id)}&edit=1`);
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
    setProductImage(null);
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
    setProductImage(product.image);
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
    const payload = await runIntakeLookup(intakeQuery);
    if (!payload) {
      return;
    }
    const exact = payload.exact_variants[0];
    if (exact) {
      openExactVariantMatch(exact);
      setActiveTab('receive');
      return;
    }
    const product = payload.product_matches[0];
    if (product) {
      beginExistingProduct(product, productVariantCount(product) === 1 ? [lineFromExistingVariant(product.variants[0])] : []);
      setActiveTab('receive');
      return;
    }
    beginNewProduct(payload.suggested_new_product ?? null);
    setActiveTab('receive');
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
      const product = payload.product_matches[0];
      beginExistingProduct(product, productVariantCount(product) === 1 ? [lineFromExistingVariant(product.variants[0])] : []);
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
            next.push(lineFromExistingVariant(existingVariant, generator.quantity));
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

  const applyPurchaseOrderToReceive = async () => {
    if (!selectedPurchaseOrderId) {
      setError('Select an outstanding purchase order first.');
      return;
    }
    setLookupPending(true);
    setNotice('');
    setError('');
    try {
      const order = await getPurchaseOrder(selectedPurchaseOrderId);
      const firstLine = order.lines[0];
      if (!firstLine) {
        setError('Selected purchase order has no lines.');
        return;
      }
      setReceiveForm((current) => ({
        ...current,
        source_purchase_order_id: order.purchase_id,
        notes: current.notes.trim() ? current.notes : `Receiving against ${order.purchase_no}`,
        identity: {
          ...current.identity,
          product_name: current.identity.product_name.trim() || firstLine.product_name || 'Purchase order receipt',
        },
        lines: receiveLinesFromPurchaseOrder(order),
      }));
      setNotice(`Loaded ${order.lines.length} line(s) from ${order.purchase_no}.`);
    } catch (orderError) {
      setError(orderError instanceof Error ? orderError.message : 'Unable to load purchase order details.');
    } finally {
      setLookupPending(false);
    }
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

  const toggleColumnVisibility = (key: InventoryColumnKey) => {
    setVisibleColumns((current) => ({ ...current, [key]: !current[key] }));
  };

  const saveSupplierInline = async (group: InventoryProductGroup) => {
    const variant = group.variants[0];
    if (!variant) {
      return;
    }
    const draft = (supplierDrafts[group.product_id] ?? '').trim();
    if (draft === (group.supplier || '').trim()) {
      return;
    }
    setSavingSupplierFor(group.product_id);
    setNotice('');
    setError('');
    try {
      await updateInventoryInlineFields({
        variant_id: variant.variant_id,
        supplier: draft,
      });
      setNotice(`Updated supplier for ${group.product_name}.`);
      await loadWorkspace(queryInput.trim());
    } catch (saveError) {
      setError(saveError instanceof Error ? saveError.message : 'Unable to update supplier.');
    } finally {
      setSavingSupplierFor(null);
    }
  };

  const saveReorderInline = async (variant: InventoryStockRow) => {
    const draft = (reorderDrafts[variant.variant_id] ?? '').trim();
    if (!draft) {
      setError('Reorder level is required.');
      return;
    }
    if (draft === variant.reorder_level) {
      return;
    }
    setSavingReorderFor(variant.variant_id);
    setNotice('');
    setError('');
    try {
      await updateInventoryInlineFields({
        variant_id: variant.variant_id,
        reorder_level: draft,
      });
      setNotice(`Updated reorder level for ${variant.label}.`);
      await loadWorkspace(queryInput.trim());
    } catch (saveError) {
      setError(saveError instanceof Error ? saveError.message : 'Unable to update reorder level.');
    } finally {
      setSavingReorderFor(null);
    }
  };

  const canEditSavedDetails = !selectedProduct || receiveForm.update_matched_product_details;
  const showAdvancedCatalog = advancedCatalogAllowed(user?.roles);
  const templateAllowed = canSaveTemplateOnly(user?.roles);
  const templateDisabled = !hasTemplateEligibleLine(receiveForm.lines);
  const activeTabLabel: Record<InventoryTab, string> = {
    stock: 'Available Stock',
    receive: 'Receive Stock',
    adjust: 'Adjustments',
    'low-stock': 'Low Stock',
  };

  return (
    <div className="workspace-stack inventory-command-center">
      <nav className="inventory-breadcrumb" aria-label="Inventory breadcrumb">
        <ol>
          <li>
            <Link href="/dashboard">Home</Link>
          </li>
          <li aria-hidden="true">/</li>
          <li>
            <Link href="/inventory">Inventory</Link>
          </li>
          <li aria-hidden="true">/</li>
          <li aria-current="page">
            <strong>{activeTabLabel[activeTab]}</strong>
          </li>
        </ol>
      </nav>
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
        title={
          <span className="workspace-heading">
            Variant-level inventory control
            <WorkspaceHint
              label="Inventory workspace help"
              text="Use Receive Stock for day-to-day intake. Available Stock, Low Stock, and Adjustments stay ledger-driven so every movement remains auditable."
            />
          </span>
        }
        actions={
          <div className="inventory-panel-actions">
            <form className="workspace-search" onSubmit={onSearch}>
              <input
                type="search"
                value={queryInput}
                placeholder="Search products, variants, SKU, or barcode (Cmd/Ctrl+K)"
                list="inventory-stock-search-suggestions"
                onChange={(event) => setQueryInput(event.target.value)}
              />
              <button type="submit">Search</button>
            </form>
            <datalist id="inventory-stock-search-suggestions">
              {searchSuggestions.map((suggestion) => <option key={suggestion} value={suggestion} />)}
            </datalist>
            <button
              type="button"
              className="btn-secondary"
              aria-expanded={filtersOpen}
              onClick={() => setFiltersOpen((current) => !current)}
            >
              {filtersOpen ? 'Hide Filters' : 'Filters'}
            </button>
            <button
              type="button"
              className="btn-secondary"
              aria-expanded={columnSelectorOpen}
              onClick={() => setColumnSelectorOpen((current) => !current)}
            >
              Columns
            </button>
            <button
              type="button"
              className="btn-primary"
              onClick={() => {
                beginNewProduct(null);
                setActiveTab('receive');
                setOpenQuickActionsFor(null);
              }}
            >
              Add New Product
            </button>
          </div>
        }
      >
        {notice ? <WorkspaceNotice tone="success">{notice}</WorkspaceNotice> : null}
        {error ? <WorkspaceNotice tone="error">{error}</WorkspaceNotice> : null}
        {isPending && !workspace ? <WorkspaceNotice>Loading inventory…</WorkspaceNotice> : null}
        <section className="inventory-status-segments" aria-label="Stock status segmentation">
          <button
            type="button"
            className={stockFilter === 'all' ? 'active' : ''}
            onClick={() => setStockFilter('all')}
          >
            All
            <span>{stockCounts.all}</span>
          </button>
          <button
            type="button"
            className={stockFilter === 'normal' ? 'active' : ''}
            onClick={() => setStockFilter('normal')}
          >
            Healthy
            <span>{stockCounts.normal}</span>
          </button>
          <button
            type="button"
            className={stockFilter === 'low' ? 'active' : ''}
            onClick={() => setStockFilter('low')}
          >
            Low
            <span>{stockCounts.low}</span>
          </button>
          <button
            type="button"
            className={stockFilter === 'out' ? 'active' : ''}
            onClick={() => setStockFilter('out')}
          >
            Out
            <span>{stockCounts.out}</span>
          </button>
        </section>
        {filtersOpen ? (
          <section className="inventory-filters" aria-label="Inventory filters">
            <label>
              Supplier
              <input
                list="inventory-supplier-filter-options"
                value={supplierFilter}
                onChange={(event) => setSupplierFilter(event.target.value)}
                placeholder="Filter by supplier"
              />
            </label>
            <label>
              Category
              <input
                list="inventory-category-filter-options"
                value={categoryFilter}
                onChange={(event) => setCategoryFilter(event.target.value)}
                placeholder="Filter by category"
              />
            </label>
            <label>
              Tags
              <input
                value={tagFilter}
                onChange={(event) => setTagFilter(event.target.value)}
                placeholder="Filter by SKU, barcode, or variant"
              />
            </label>
            <label>
              Stock status
              <select value={stockFilter} onChange={(event) => setStockFilter(event.target.value as typeof stockFilter)}>
                <option value="all">All</option>
                <option value="normal">Healthy</option>
                <option value="low">Low stock</option>
                <option value="out">Out of stock</option>
              </select>
            </label>
            <button
              type="button"
              className="btn-secondary inventory-filter-reset"
              onClick={() => {
                setSupplierFilter('');
                setCategoryFilter('');
                setTagFilter('');
                setStockFilter('all');
              }}
            >
              Clear filters
            </button>
            <datalist id="inventory-supplier-filter-options">
              {supplierOptions.map((value) => <option key={value} value={value} />)}
            </datalist>
            <datalist id="inventory-category-filter-options">
              {categoryOptions.map((value) => <option key={value} value={value} />)}
            </datalist>
          </section>
        ) : null}
        {columnSelectorOpen ? (
          <section className="inventory-filters" aria-label="Inventory column visibility">
            {INVENTORY_COLUMN_CONFIG.map((column) => (
              <label key={column.key}>
                <input
                  type="checkbox"
                  checked={visibleColumns[column.key]}
                  onChange={() => toggleColumnVisibility(column.key)}
                />
                {column.label}
              </label>
            ))}
          </section>
        ) : null}

        {activeTab === 'stock' ? (
          filteredProductGroups.length ? (
            <div className="table-scroll inventory-stock-table-scroll">
              <table className="workspace-table workspace-table-sticky inventory-grouped-table">
                <thead>
                  <tr>
                    <th>Product</th>
                    {visibleColumns.supplier ? <th>Supplier</th> : null}
                    {visibleColumns.on_hand ? <th>On Hand</th> : null}
                    {visibleColumns.reserved ? <th>Reserved</th> : null}
                    {visibleColumns.available ? <th>Available</th> : null}
                    {visibleColumns.variants ? <th>Variants</th> : null}
                    {visibleColumns.alerts ? <th>Alerts</th> : null}
                    <th>Quick Action</th>
                  </tr>
                </thead>
                <tbody>
                  {filteredProductGroups.map((group) => {
                    const isExpanded = Boolean(expandedProducts[group.product_id]);
                    const isMenuOpen = openQuickActionsFor === group.product_id;
                    return (
                      <Fragment key={group.product_id}>
                        <tr className={`inventory-product-row${isMenuOpen ? ' menu-open' : ''}`}>
                          <td>
                            <div className="inventory-product-cell">
                              <button
                                type="button"
                                className="inventory-expand-button"
                                onClick={() =>
                                  setExpandedProducts((current) => ({
                                    ...current,
                                    [group.product_id]: !current[group.product_id],
                                  }))
                                }
                                aria-expanded={isExpanded}
                              >
                                {isExpanded ? '−' : '+'}
                              </button>
                              {group.image?.thumbnail_url ? (
                                <img
                                  className="inventory-product-thumb"
                                  src={group.image.thumbnail_url}
                                  alt={group.product_name}
                                />
                              ) : (
                                <div className="inventory-product-thumb placeholder" aria-hidden="true">
                                  {group.product_name.charAt(0).toUpperCase()}
                                </div>
                              )}
                              <div>
                                <strong>{group.product_name}</strong>
                                <p>{group.category || 'Uncategorized'}</p>
                              </div>
                            </div>
                          </td>
                          {visibleColumns.supplier ? (
                            <td>
                              <div className="workspace-inline-actions">
                                <input
                                  value={supplierDrafts[group.product_id] ?? group.supplier ?? ''}
                                  onChange={(event) =>
                                    setSupplierDrafts((current) => ({
                                      ...current,
                                      [group.product_id]: event.target.value,
                                    }))
                                  }
                                  placeholder="Supplier"
                                />
                                <button
                                  type="button"
                                  onClick={() => void saveSupplierInline(group)}
                                  disabled={savingSupplierFor === group.product_id}
                                >
                                  {savingSupplierFor === group.product_id ? 'Saving…' : 'Save'}
                                </button>
                              </div>
                            </td>
                          ) : null}
                          {visibleColumns.on_hand ? <td>{formatQuantity(group.on_hand.toFixed(3))}</td> : null}
                          {visibleColumns.reserved ? <td>{formatQuantity(group.reserved.toFixed(3))}</td> : null}
                          {visibleColumns.available ? <td>{formatQuantity(group.available_to_sell.toFixed(3))}</td> : null}
                          {visibleColumns.variants ? <td>{group.variants.length}</td> : null}
                          {visibleColumns.alerts ? (
                            <td>
                              {group.available_to_sell <= 0 ? (
                                <span className="inventory-status-badge out">Out</span>
                              ) : group.low_stock_count ? (
                                <span className="inventory-status-badge low">{group.low_stock_count} low</span>
                              ) : (
                                <span className="inventory-status-badge healthy">Healthy</span>
                              )}
                            </td>
                          ) : null}
                          <td>
                            <div className="quick-actions-menu">
                              <button
                                type="button"
                                ref={(node) => {
                                  quickActionsButtonRefs.current[group.product_id] = node;
                                }}
                                onClick={(event) => toggleQuickActions(group.product_id, event.currentTarget)}
                                aria-expanded={isMenuOpen}
                                aria-haspopup="menu"
                              >
                                More
                              </button>
                            </div>
                          </td>
                        </tr>
                        {isExpanded ? (
                          <tr className="inventory-variant-container-row">
                            <td colSpan={2 + INVENTORY_COLUMN_CONFIG.filter((column) => visibleColumns[column.key]).length}>
                              <div className="inventory-variant-table-wrap">
                                <table className="workspace-table workspace-table-sticky inventory-variant-table">
                                  <thead>
                                    <tr>
                                      <th>Variant</th>
                                      <th>SKU</th>
                                      <th>Barcode</th>
                                      <th>On Hand</th>
                                      <th>Reserved</th>
                                      <th>Available</th>
                                      <th>Reorder</th>
                                      <th>Unit Cost</th>
                                      <th>Unit Price</th>
                                      <th>Status</th>
                                    </tr>
                                  </thead>
                                  <tbody>
                                    {group.variants.map((variant) => (
                                      <tr key={variant.variant_id} className="inventory-variant-row">
                                        <td>
                                          <div className="inventory-variant-identity">
                                            {group.image?.thumbnail_url ? (
                                              <img
                                                className="inventory-variant-thumb"
                                                src={group.image.thumbnail_url}
                                                alt={group.product_name}
                                              />
                                            ) : (
                                              <div className="inventory-variant-thumb placeholder" aria-hidden="true">
                                                {group.product_name.charAt(0).toUpperCase()}
                                              </div>
                                            )}
                                            <div>
                                              <strong>{variant.label}</strong>
                                              <p>{group.product_name}</p>
                                            </div>
                                          </div>
                                        </td>
                                        <td>{variant.sku}</td>
                                        <td>{variant.barcode || 'No barcode'}</td>
                                        <td>{formatQuantity(variant.on_hand)}</td>
                                        <td>{formatQuantity(variant.reserved)}</td>
                                        <td>{formatQuantity(variant.available_to_sell)}</td>
                                        <td>
                                          <div className="workspace-inline-actions">
                                            <input
                                              value={reorderDrafts[variant.variant_id] ?? variant.reorder_level}
                                              onChange={(event) =>
                                                setReorderDrafts((current) => ({
                                                  ...current,
                                                  [variant.variant_id]: event.target.value,
                                                }))
                                              }
                                              inputMode="decimal"
                                            />
                                            <button
                                              type="button"
                                              onClick={() => void saveReorderInline(variant)}
                                              disabled={savingReorderFor === variant.variant_id}
                                            >
                                              {savingReorderFor === variant.variant_id ? 'Saving…' : 'Save'}
                                            </button>
                                          </div>
                                        </td>
                                        <td>{formatMoney(variant.unit_cost)}</td>
                                        <td>{formatMoney(variant.unit_price)}</td>
                                        <td>
                                          {toNumber(variant.available_to_sell) <= 0 ? (
                                            <span className="inventory-status-badge out">Out</span>
                                          ) : variant.low_stock ? (
                                            <span className="inventory-status-badge low">Low</span>
                                          ) : (
                                            <span className="inventory-status-badge healthy">Normal</span>
                                          )}
                                        </td>
                                      </tr>
                                    ))}
                                  </tbody>
                                </table>
                              </div>
                            </td>
                          </tr>
                        ) : null}
                      </Fragment>
                    );
                  })}
                </tbody>
              </table>
            </div>
          ) : (
            <>
              {productGroups.length && hasActiveInventoryFilters ? (
                <WorkspaceNotice>
                  No rows match the current filter set. Clear or broaden filters to continue.
                </WorkspaceNotice>
              ) : null}
              <WorkspaceEmpty
                title={productGroups.length ? 'No stock matches the current filters' : 'No available stock'}
                message={
                  productGroups.length
                    ? 'Adjust supplier, category, tag, or stock filters to see more products.'
                    : 'Receive stock or return sellable items to bring variants back into the operating list.'
                }
              />
            </>
          )
        ) : null}
        {openQuickActionGroup && quickActionsPosition && typeof document !== 'undefined'
          ? createPortal(
              <div
                ref={quickActionsMenuRef}
                className="quick-actions-popover quick-actions-popover-floating"
                style={{ top: quickActionsPosition.top, left: quickActionsPosition.left }}
                role="menu"
              >
                <button type="button" onClick={() => beginReceiveForProduct(openQuickActionGroup)}>Receive Stock</button>
                <button type="button" onClick={() => beginAdjustmentForProduct(openQuickActionGroup)}>Adjustment</button>
                <button type="button" onClick={() => beginModifyProduct(openQuickActionGroup)}>Modify</button>
              </div>,
              document.body,
            )
          : null}

        {activeTab === 'receive' ? (
          <div className="workspace-stack">
            <section className="workspace-subsection">
              <div className="workspace-subsection-header">
                <h4 className="workspace-heading">
                  Outstanding Purchase Orders
                  <WorkspaceHint
                    label="Outstanding purchase orders help"
                    text="When an open PO exists, load it first to prefill expected variants and quantities before posting the stock receipt."
                  />
                </h4>
              </div>
              <div className="workspace-inline-actions">
                <label>
                  Draft purchase order
                  <select
                    value={selectedPurchaseOrderId}
                    onChange={(event) => setSelectedPurchaseOrderId(event.target.value)}
                    disabled={loadingPurchaseOrders}
                  >
                    <option value="">Select outstanding PO</option>
                    {outstandingPurchaseOrders.map((order) => (
                      <option key={order.purchase_id} value={order.purchase_id}>
                        {order.purchase_no} · {order.supplier_name || 'No supplier'} · {order.purchase_date || 'No date'}
                      </option>
                    ))}
                  </select>
                </label>
                <button type="button" onClick={() => void applyPurchaseOrderToReceive()} disabled={!selectedPurchaseOrderId || lookupPending}>
                  {lookupPending ? 'Loading…' : 'Load PO lines'}
                </button>
                <button type="button" className="btn-secondary" onClick={() => void loadOutstandingPurchaseOrders()}>
                  Refresh POs
                </button>
                <span>
                  {loadingPurchaseOrders
                    ? 'Refreshing outstanding orders…'
                    : outstandingPurchaseOrders.length
                      ? `${outstandingPurchaseOrders.length} draft PO(s) available`
                      : 'No outstanding draft POs'}
                </span>
              </div>
            </section>

            <section className="workspace-subsection">
              <div className="workspace-subsection-header">
                <h4 className="workspace-heading">
                  What are you receiving?
                  <WorkspaceHint
                    label="Inventory intake help"
                    text="Scan or type one item intent. The workspace will stage the best existing match first and only open a new draft when nothing exists."
                  />
                </h4>
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
                  placeholder="Scan barcode, SKU, product, or variant"
                  onChange={(event) => setIntakeQuery(event.target.value)}
                />
                <button type="submit" disabled={lookupPending}>
                  {lookupPending ? 'Reviewing…' : intakeRecommendation.actionLabel}
                </button>
              </form>

              {intakeResults ? (
                <WorkspaceNotice tone={intakeRecommendation.kind === 'new' ? 'info' : 'success'}>
                  <div className="workspace-stack">
                    <strong>{intakeRecommendation.title}</strong>
                    <span>{intakeRecommendation.summary}</span>
                  </div>
                </WorkspaceNotice>
              ) : (
                <WorkspaceNotice>
                  <div className="workspace-stack">
                    <strong>{intakeRecommendation.title}</strong>
                    <span>{intakeRecommendation.summary}</span>
                  </div>
                </WorkspaceNotice>
              )}

              {exactVariantMatches.length ? (
                <div className="workspace-stack">
                  <p className="eyebrow">Exact Variant Matches</p>
                  <div className="workspace-card-grid compact">
                    {exactVariantMatches.map((match) => (
                      <article key={`${match.variant.variant_id}-${match.match_reason}`} className="commerce-card compact">
                        <div className="commerce-card-header">
                          <div className="guided-match-item-identity">
                            {match.product.image?.thumbnail_url ? (
                              <img className="guided-match-item-thumb" src={match.product.image.thumbnail_url} alt={match.product.name} />
                            ) : null}
                            <div>
                            <h4>{match.variant.label}</h4>
                            <p>
                              Matched by {match.match_reason} · SKU {match.variant.sku} · Available {formatQuantity(match.variant.available_to_sell)}
                            </p>
                            </div>
                          </div>
                          <button type="button" onClick={() => openExactVariantMatch(match)}>
                            Use exact variant
                          </button>
                        </div>
                      </article>
                    ))}
                  </div>
                </div>
              ) : null}

              {visibleProductMatches.length ? (
                <div className="workspace-stack">
                  <p className="eyebrow">Existing Products</p>
                  <div className="workspace-card-grid compact">
                    {visibleProductMatches.map((product) => (
                      <article key={product.product_id} className="commerce-card compact">
                        <div className="commerce-card-header">
                          <div className="guided-match-item-identity">
                            {product.image?.thumbnail_url ? (
                              <img className="guided-match-item-thumb" src={product.image.thumbnail_url} alt={product.name} />
                            ) : null}
                            <div>
                            <h4>{product.name}</h4>
                            <p>
                              {product.variants.length} saved variants · Supplier {product.supplier || 'Not set'} · Category {product.category || 'Not set'}
                            </p>
                            </div>
                          </div>
                          <button
                            type="button"
                            onClick={() =>
                              beginExistingProduct(
                                product,
                                productVariantCount(product) === 1 ? [lineFromExistingVariant(product.variants[0])] : []
                              )
                            }
                          >
                            Review product
                          </button>
                        </div>
                      </article>
                    ))}
                  </div>
                </div>
              ) : null}

              {newProductSuggestion ? (
                <article className="commerce-card compact">
                  <div className="commerce-card-header">
                    <div>
                      <p className="eyebrow">Create New Product</p>
                      <h4>{newProductSuggestion.product_name}</h4>
                      <p>We did not attach this automatically. Start a new item only if the existing matches above are not correct.</p>
                    </div>
                    <button type="button" onClick={() => beginNewProduct(newProductSuggestion)}>
                      Start new product
                    </button>
                  </div>
                </article>
              ) : null}
            </section>

            {receiveForm.identity.product_name ? (
              <section className="workspace-subsection">
                <div className="workspace-subsection-header">
                  <h4 className="workspace-heading">
                    Review Variants and Receive
                    <WorkspaceHint
                      label="Review and receive help"
                      text="Confirm the product details first, then add saved variants or generate new ones. One save posts a single audited receipt with all of the lines below."
                    />
                  </h4>
                </div>

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
                    <span className="workspace-heading">
                      Edit saved product details
                      <WorkspaceHint
                        label="Edit saved product details help"
                        text="Keep this off for normal receiving. Turn it on only when you need to update the saved catalog details for the matched product."
                      />
                    </span>
                  </label>
                ) : null}

                {selectedProduct?.variants.length ? (
                  <div className="workspace-stack">
                    <p className="eyebrow">Saved Variants</p>
                    <div className="table-scroll">
                      <table className="workspace-table workspace-table-sticky">
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

                <form
                  className="workspace-form"
                  onSubmit={(event) => {
                    event.preventDefault();
                    void submitReceive('receive_stock');
                  }}
                >
                  <div className="workspace-subsection">
                    <div className="workspace-subsection-header">
                      <h4 className="workspace-heading">
                        Product Details
                        <WorkspaceHint
                          label="Product details help"
                          text="These shared details define the product identity and the fallback selling-price rules for any new variants created in this receipt."
                        />
                      </h4>
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
                      <div className="field-span-2">
                        <label>Product photo</label>
                        <ProductPhotoField
                          image={productImage}
                          onUploaded={(image) => {
                            setProductImage(image);
                            setReceiveForm((current) => ({
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
                            setReceiveForm((current) => ({
                              ...current,
                              identity: {
                                ...current.identity,
                                pending_primary_media_upload_id: '',
                                remove_primary_image: Boolean(current.identity.product_id || current.identity.image_url),
                                image_url: '',
                              },
                            }));
                          }}
                        />
                      </div>
                    </div>
                  </div>

                  <div className="workspace-subsection">
                    <div className="workspace-subsection-header">
                      <h4 className="workspace-heading">
                        Variant Generator
                        <WorkspaceHint
                          label="Variant generator help"
                          text="Enter comma-separated values to generate many variants at once. Matching saved combinations reuse the existing variant, and new combinations become editable receipt lines."
                        />
                      </h4>
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
                        <span className="workspace-heading">
                          Default Qty Each Variant
                          <WorkspaceHint
                            label="Default quantity for each variant help"
                            text="Leave this blank when each generated line will receive a different quantity. Fill it only when the same quantity should prefill every generated line."
                          />
                        </span>
                        <input
                          value={generator.quantity}
                          onChange={(event) => setGenerator((current) => ({ ...current, quantity: event.target.value }))}
                          placeholder="Leave blank for line-by-line quantity"
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

                  <div className="workspace-subsection">
                    <div className="workspace-subsection-header">
                      <h4 className="workspace-heading">
                        Receipt Lines
                        <WorkspaceHint
                          label="Receipt lines help"
                          text="Each line becomes one purchase item. Existing variants keep their saved identity, and new variants can still be edited before you save the receipt."
                        />
                      </h4>
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
                        message="Add an existing variant or use the generator below Product Details to create the lines you want to receive."
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
                  {adjustmentOptions.map((item) => (
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
              <table className="workspace-table workspace-table-sticky">
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
