'use client';

import { useEffect, useMemo, useState } from 'react';
import { PageShell } from '@/components/ui/page-shell';
import { ProductChooser } from '@/components/products-stock/product-chooser';
import { ProductIdentityForm } from '@/components/products-stock/product-identity';
import { VariantGenerator } from '@/components/products-stock/variant-generator';
import { VariantGrid } from '@/components/products-stock/variant-grid';
import { SaveSummary } from '@/components/products-stock/save-summary';
import { getProductsStockSnapshot, saveProductStock } from '@/lib/api/products-stock';
import { createEmptyVariant, generateVariantsFromInputs, hasIdentity, summarizeVariants, variantIdentityKey } from '@/lib/products-stock/variant-utils';
import type { ProductIdentity, ProductRecord, SaveProductPayload, Variant, VariantMode } from '@/types/products-stock';

const EMPTY_IDENTITY: ProductIdentity = { productName: '', supplier: '', category: '', description: '', features: [] };

const toLookup = (products: ProductRecord[]) => products.map((product) => ({ id: product.id, name: product.identity.productName }));

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

export function ProductsStockWorkspace() {
  const [products, setProducts] = useState<ProductRecord[]>([]);
  const [suppliers, setSuppliers] = useState<string[]>([]);
  const [categories, setCategories] = useState<string[]>([]);
  const [mode, setMode] = useState<VariantMode>('new');
  const [selectedProductId, setSelectedProductId] = useState<string | null>(null);
  const [identity, setIdentity] = useState<ProductIdentity>(EMPTY_IDENTITY);
  const [variants, setVariants] = useState<Variant[]>([]);
  const [sameCostEnabled, setSameCostEnabled] = useState(false);
  const [sharedCost, setSharedCost] = useState('');
  const [isSaving, setIsSaving] = useState(false);
  const [validationMessage, setValidationMessage] = useState<string>();

  const loadSnapshot = async () => {
    const snapshot = await getProductsStockSnapshot();
    setProducts(snapshot.products);
    setSuppliers(snapshot.suppliers);
    setCategories(snapshot.categories);
  };

  useEffect(() => {
    loadSnapshot().catch((error) => setValidationMessage(toErrorMessage(error, 'Unable to load products and stock snapshot. Check backend connectivity.')));
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
    return undefined;
  };

  const handleSave = async () => {
    const error = validate();
    setValidationMessage(error);
    if (error) return;
    setIsSaving(true);
    try {
      const payload: SaveProductPayload = {
        mode,
        identity,
        variants,
        selectedProductId: mode === 'existing' ? selectedProductId ?? undefined : undefined,
      };
      await saveProductStock(payload);
      await loadSnapshot();
      setValidationMessage('Saved successfully.');
    } catch (errorSave) {
      setValidationMessage(toErrorMessage(errorSave, 'Save failed due to server or network error.'));
    } finally {
      setIsSaving(false);
    }
  };

  return (
    <PageShell title="Products & Stock" description="Variant-first catalog and opening stock workspace.">
      <div className="products-stock-layout" data-mode={mode} data-selected-product={selectedProductId ?? ''}>
        <ProductChooser
          products={toLookup(products)}
          onSelectExisting={(productId) => {
            const existing = products.find((product) => product.id === productId);
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
          onAddSupplier={(supplier) => setSuppliers((prev) => (prev.includes(supplier) ? prev : [...prev, supplier]))}
          onAddCategory={(category) => setCategories((prev) => (prev.includes(category) ? prev : [...prev, category]))}
        />

        {mode === 'new' ? <VariantGenerator onGenerate={({ size, color, other }) => setVariants(generateVariantsFromInputs({ size, color, other }))} /> : null}

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
          onVariantChange={(id, field, value) =>
            setVariants((current) =>
              current.map((variant) =>
                variant.rowId !== id
                  ? variant
                  : {
                      ...variant,
                      [field]: field === 'qty' || field === 'cost' || field === 'defaultSellingPrice' || field === 'maxDiscountPct' ? Number(value) || 0 : value
                    }
              )
            )
          }
          onAddVariant={() => setVariants((current) => [...current, createEmptyVariant()])}
          onRemoveVariant={(id) => setVariants((current) => current.filter((variant) => variant.rowId !== id))}
        />

        <SaveSummary
          variantCount={summary.variantCount}
          totalQty={summary.totalQty}
          estimatedStockCost={summary.estimatedStockCost}
          isSaving={isSaving}
          isSaveDisabled={Boolean(validate())}
          validationMessage={validationMessage}
          onSave={handleSave}
          onReset={() => {
            setMode('new');
            setSelectedProductId(null);
            setIdentity(EMPTY_IDENTITY);
            setVariants([]);
            setSameCostEnabled(false);
            setSharedCost('');
            setValidationMessage(undefined);
          }}
        />
      </div>
    </PageShell>
  );
}
