'use client';

import { useEffect, useMemo, useState } from 'react';
import { PageShell } from '@/components/ui/page-shell';
import { ProductChooser } from '@/components/products-stock/product-chooser';
import { ProductIdentityForm } from '@/components/products-stock/product-identity';
import { VariantGenerator } from '@/components/products-stock/variant-generator';
import { VariantGrid } from '@/components/products-stock/variant-grid';
import { SaveSummary } from '@/components/products-stock/save-summary';
import { getCatalogProducts, saveCatalogProduct } from '@/lib/api/catalog';
import {
  createEmptyVariant,
  generateVariantsFromInputs,
  hasIdentity,
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

export function CatalogWorkspace() {
  const [products, setProducts] = useState<CatalogProductRecord[]>([]);
  const [suppliers, setSuppliers] = useState<string[]>([]);
  const [categories, setCategories] = useState<string[]>([]);
  const [mode, setMode] = useState<CatalogMode>('new');
  const [selectedProductId, setSelectedProductId] = useState<string | null>(null);
  const [identity, setIdentity] = useState<ProductIdentity>(EMPTY_IDENTITY);
  const [variants, setVariants] = useState<CatalogVariant[]>([]);
  const [isSaving, setIsSaving] = useState(false);
  const [validationMessage, setValidationMessage] = useState<string>();

  const loadCatalog = async () => {
    const snapshot = await getCatalogProducts();
    setProducts(snapshot.products);
    setSuppliers(snapshot.suppliers);
    setCategories(snapshot.categories);
  };

  useEffect(() => {
    loadCatalog().catch((error) => {
      setValidationMessage(toErrorMessage(error, 'Unable to load catalog right now.'));
    });
  }, []);

  const summary = useMemo(() => summarizeVariants(variants), [variants]);

  const validate = (): string | undefined => {
    if (!identity.productName.trim()) return 'Product name is required.';
    if (!variants.length) return 'At least one variant row is required.';

    const seen = new Set<string>();
    for (let i = 0; i < variants.length; i += 1) {
      const row = variants[i];
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
        variants,
        selectedProductId: mode === 'existing' ? selectedProductId ?? undefined : undefined,
      };
      await saveCatalogProduct(payload);
      await loadCatalog();
      setValidationMessage('Catalog saved. Add opening stock from Inventory when you are ready to receive stock.');
    } catch (errorSave) {
      setValidationMessage(toErrorMessage(errorSave, 'Save failed due to server or network error.'));
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
          onSelectExisting={(productId) => {
            const existing = products.find((product) => product.product_id === productId);
            if (!existing) return;
            setMode('existing');
            setSelectedProductId(productId);
            setIdentity(existing.identity);
            setVariants(existing.variants);
            setValidationMessage(undefined);
          }}
          onCreateNew={(typedName) => {
            setMode('new');
            setSelectedProductId(null);
            setIdentity({ ...EMPTY_IDENTITY, productName: typedName });
            setVariants([]);
            setValidationMessage(undefined);
          }}
        />

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

        {mode === 'new' ? (
          <VariantGenerator
            onGenerate={({ size, color, other }) =>
              setVariants(generateVariantsFromInputs({ size, color, other }))
            }
          />
        ) : null}

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
                        field === 'defaultSellingPrice' || field === 'maxDiscountPct'
                          ? Number(value) || 0
                          : value,
                    }
              )
            )
          }
          onAddVariant={() => setVariants((current) => [...current, createEmptyVariant()])}
          onRemoveVariant={(tempId) =>
            setVariants((current) => current.filter((variant) => variant.tempId !== tempId))
          }
        />

        <SaveSummary
          variantCount={summary.variantCount}
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
