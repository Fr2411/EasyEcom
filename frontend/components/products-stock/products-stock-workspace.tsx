'use client';

import { useEffect, useMemo, useState } from 'react';
import { PageShell } from '@/components/ui/page-shell';
import { ProductChooser } from '@/components/products-stock/product-chooser';
import { ProductIdentityForm } from '@/components/products-stock/product-identity';
import { VariantGenerator } from '@/components/products-stock/variant-generator';
import { VariantGrid } from '@/components/products-stock/variant-grid';
import { SaveSummary } from '@/components/products-stock/save-summary';
import { ApiError, ApiNetworkError } from '@/lib/api/client';
import { getCatalogProduct, getCatalogProducts, saveCatalogProduct } from '@/lib/api/catalog';
import { getPublicEnv } from '@/lib/env';
import {
  createEmptyVariant,
  generateVariantsFromInputs,
  hasIdentity,
  mergeCatalogVariants,
  summarizeVariants,
  variantIdentityKey,
} from '@/lib/products-stock/variant-utils';
import type {
  CatalogMode,
  CatalogProductRecord,
  CatalogVariant,
  ProductIdentity,
  SaveCatalogPayload,
} from '@/types/catalog';

const EMPTY_IDENTITY: ProductIdentity = {
  productName: '',
  supplier: '',
  category: '',
  description: '',
  features: [],
};

const toLookup = (products: CatalogProductRecord[]) =>
  products.map((product) => ({ id: product.product_id, name: product.identity.productName }));

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

function toActiveVariants(variants: CatalogVariant[]): CatalogVariant[] {
  return variants.filter((variant) => !variant.isArchived);
}

function toArchiveVariantIds(variants: CatalogVariant[]): string[] {
  return variants
    .filter((variant) => variant.isArchived && variant.variant_id)
    .map((variant) => String(variant.variant_id));
}

function classifyCatalogLoadError(error: unknown): string {
  let apiBaseUrl = '';
  try {
    apiBaseUrl = getPublicEnv().apiBaseUrl;
  } catch (envError) {
    return toErrorMessage(
      envError,
      'Catalog cannot load because NEXT_PUBLIC_API_BASE_URL is missing.',
    );
  }

  if (
    typeof window !== 'undefined' &&
    window.location.protocol === 'https:' &&
    apiBaseUrl.startsWith('http://')
  ) {
    return 'Catalog cannot reach the API because NEXT_PUBLIC_API_BASE_URL uses http on an https site. Update Amplify to an https backend URL.';
  }

  if (error instanceof ApiNetworkError) {
    return 'Catalog cannot reach the API. Check NEXT_PUBLIC_API_BASE_URL, HTTPS, and whether the backend is running.';
  }

  if (error instanceof ApiError) {
    if (error.status === 401) {
      return 'Catalog could not load because your session is not authorized. Sign in again and verify cookie and CORS settings.';
    }
    if (error.status >= 500) {
      return 'Catalog failed because the backend returned a server error. Check the API logs and confirm the latest catalog migration is applied.';
    }
  }

  return toErrorMessage(error, 'Unable to load catalog right now.');
}

function classifyCatalogSaveError(error: unknown): string {
  if (error instanceof ApiError && error.status === 409) {
    return 'A product with this name already exists. Load the existing product and add variants there.';
  }
  return toErrorMessage(error, 'Save failed due to server or network error.');
}

export function CatalogWorkspace() {
  const [products, setProducts] = useState<CatalogProductRecord[]>([]);
  const [suppliers, setSuppliers] = useState<string[]>([]);
  const [categories, setCategories] = useState<string[]>([]);
  const [mode, setMode] = useState<CatalogMode>('new');
  const [selectedProductId, setSelectedProductId] = useState<string | null>(null);
  const [identity, setIdentity] = useState<ProductIdentity>(EMPTY_IDENTITY);
  const [variants, setVariants] = useState<CatalogVariant[]>([]);
  const [isSaving, setIsSaving] = useState(false);
  const [isLoadingCatalog, setIsLoadingCatalog] = useState(true);
  const [isLoadingProduct, setIsLoadingProduct] = useState(false);
  const [validationMessage, setValidationMessage] = useState<string>();

  const loadCatalog = async () => {
    const snapshot = await getCatalogProducts();
    setProducts(snapshot.products);
    setSuppliers(snapshot.suppliers);
    setCategories(snapshot.categories);
    return snapshot;
  };

  const loadCatalogProductRecord = async (productId: string) => {
    const product = await getCatalogProduct(productId);
    setMode('existing');
    setSelectedProductId(productId);
    setIdentity(product.identity);
    setVariants(product.variants);
    return product;
  };

  useEffect(() => {
    const loadInitialCatalog = async () => {
      try {
        await loadCatalog();
      } catch (error) {
        setValidationMessage(classifyCatalogLoadError(error));
      } finally {
        setIsLoadingCatalog(false);
      }
    };
    void loadInitialCatalog();
  }, []);

  const summary = useMemo(() => summarizeVariants(variants), [variants]);
  const activeVariants = useMemo(() => toActiveVariants(variants), [variants]);
  const archiveVariantIds = useMemo(() => toArchiveVariantIds(variants), [variants]);

  const validate = (): string | undefined => {
    if (!identity.productName.trim()) return 'Product name is required.';
    if (!activeVariants.length && !archiveVariantIds.length) return 'At least one variant row is required.';

    const seen = new Set<string>();
    for (let i = 0; i < activeVariants.length; i += 1) {
      const row = activeVariants[i];
      if (!hasIdentity(row)) return `Variant row ${i + 1} is blank. Fill size, color, or other.`;
      const key = variantIdentityKey(row);
      if (seen.has(key)) return 'Duplicate variant identity found. Size/Color/Other must be unique.';
      seen.add(key);
    }

    if (mode === 'existing' && !selectedProductId) {
      return 'Select an existing product before saving updates.';
    }

    return undefined;
  };

  const resetWorkspace = () => {
    setMode('new');
    setSelectedProductId(null);
    setIdentity(EMPTY_IDENTITY);
    setVariants([]);
    setValidationMessage(undefined);
  };

  const handleSave = async () => {
    const error = validate();
    setValidationMessage(error);
    if (error) return;

    setIsSaving(true);
    try {
      const payload: SaveCatalogPayload = {
        mode,
        identity,
        variants: activeVariants,
        archiveVariantIds,
        selectedProductId: mode === 'existing' ? selectedProductId ?? undefined : undefined,
      };
      const response = await saveCatalogProduct(payload);
      await loadCatalog();
      await loadCatalogProductRecord(response.product_id);
      setValidationMessage(
        mode === 'existing'
          ? 'Catalog updated. Existing variants stayed visible, and any archived rows will be deactivated on save.'
          : 'Catalog saved. The product is now ready for opening stock or purchase entry.',
      );
    } catch (errorSave) {
      setValidationMessage(classifyCatalogSaveError(errorSave));
    } finally {
      setIsSaving(false);
    }
  };

  return (
    <PageShell
      title="Catalog"
      description="Maintain parent products and saleable variants here. Stock is recorded separately in Inventory and Purchases."
    >
      <div className="products-stock-layout" data-mode={mode} data-selected-product={selectedProductId ?? ''}>
        <ProductChooser
          products={toLookup(products)}
          selectedProductId={selectedProductId}
          onSelectExisting={async (productId) => {
            setIsLoadingProduct(true);
            try {
              await loadCatalogProductRecord(productId);
              setValidationMessage(undefined);
            } catch (error) {
              setValidationMessage(
                toErrorMessage(error, 'Unable to load the selected product.'),
              );
            } finally {
              setIsLoadingProduct(false);
            }
          }}
          onCreateNew={(typedName) => {
            setMode('new');
            setSelectedProductId(null);
            setIdentity({ ...EMPTY_IDENTITY, productName: typedName });
            setVariants([]);
            setValidationMessage(undefined);
          }}
        />

        <section className="ps-card">
          <div className="ps-headline-row">
            <h3>{mode === 'existing' ? 'Editing existing product' : 'New product draft'}</h3>
            <span>{mode === 'existing' ? identity.productName || 'Selected product' : 'Unsaved catalog item'}</span>
          </div>
          <p className="muted">
            {mode === 'existing'
              ? 'All active variants load into this editor. You can adjust current details, add new variants, and archive old ones explicitly.'
              : 'Set up the parent product first, then generate or add the child variants your team will actually buy and sell.'}
          </p>
          {isLoadingCatalog ? <p className="muted">Loading product list...</p> : null}
          {isLoadingProduct ? <p className="muted">Loading selected product details...</p> : null}
        </section>

        <ProductIdentityForm
          identity={identity}
          suppliers={suppliers}
          categories={categories}
          onIdentityChange={setIdentity}
          onAddSupplier={(supplier) =>
            setSuppliers((prev) => (prev.includes(supplier) ? prev : [...prev, supplier]))
          }
          onAddCategory={(category) =>
            setCategories((prev) => (prev.includes(category) ? prev : [...prev, category]))
          }
        />

        <VariantGenerator
          onGenerate={({ size, color, other }) =>
            setVariants((current) =>
              mergeCatalogVariants(current, generateVariantsFromInputs({ size, color, other })),
            )
          }
        />

        <VariantGrid
          variants={variants}
          onVariantChange={(tempId, field, value) =>
            setVariants((current) =>
              current.map((variant) =>
                variant.tempId !== tempId
                  ? variant
                  : {
                      ...variant,
                      [field]:
                        field === 'defaultPurchasePrice' ||
                        field === 'defaultSellingPrice' ||
                        field === 'maxDiscountPct'
                          ? Number(value) || 0
                          : value,
                    }
              )
            )
          }
          onAddVariant={() => setVariants((current) => [...current, createEmptyVariant()])}
          onToggleArchiveVariant={(tempId) =>
            setVariants((current) =>
              current.map((variant) =>
                variant.tempId !== tempId
                  ? variant
                  : { ...variant, isArchived: !variant.isArchived }
              )
            )
          }
          onRemoveVariant={(tempId) =>
            setVariants((current) => current.filter((variant) => variant.tempId !== tempId))
          }
        />

        <SaveSummary
          variantCount={summary.variantCount}
          archivedVariants={summary.archivedVariants}
          costedVariants={summary.costedVariants}
          pricedVariants={summary.pricedVariants}
          isSaving={isSaving}
          isSaveDisabled={Boolean(validate())}
          validationMessage={validationMessage}
          onSave={handleSave}
          onReset={resetWorkspace}
        />
      </div>
    </PageShell>
  );
}

export const ProductsStockWorkspace = CatalogWorkspace;
