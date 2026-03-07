'use client';

import { useEffect, useMemo, useState } from 'react';
import { PageShell } from '@/components/ui/page-shell';
import { ProductChooser } from '@/components/products-stock/product-chooser';
import { ProductIdentityForm } from '@/components/products-stock/product-identity';
import { VariantGenerator } from '@/components/products-stock/variant-generator';
import { VariantGrid } from '@/components/products-stock/variant-grid';
import { SaveSummary } from '@/components/products-stock/save-summary';
import { getProductsStockSnapshot, saveProductStock } from '@/lib/api/products-stock';
import {
  createEmptyVariant,
  generateVariantsFromInputs,
  summarizeVariants
} from '@/lib/products-stock/variant-utils';
import type { ProductIdentity, ProductRecord, Variant, VariantMode } from '@/types/products-stock';

const EMPTY_IDENTITY: ProductIdentity = {
  productName: '',
  supplier: '',
  category: '',
  description: '',
  features: []
};

function toLookup(products: ProductRecord[]) {
  return products.map((product) => ({ id: product.id, name: product.identity.productName }));
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

  useEffect(() => {
    getProductsStockSnapshot().then((snapshot) => {
      setProducts(snapshot.products);
      setSuppliers(snapshot.suppliers);
      setCategories(snapshot.categories);
    });
  }, []);

  const summary = useMemo(() => summarizeVariants(variants), [variants]);

  const resetWorkspace = () => {
    setMode('new');
    setSelectedProductId(null);
    setIdentity(EMPTY_IDENTITY);
    setVariants([]);
    setValidationMessage(undefined);
    setSameCostEnabled(false);
    setSharedCost('');
  };

  const loadExistingProduct = (productId: string) => {
    const existing = products.find((product) => product.id === productId);
    if (!existing) {
      return;
    }

    setMode('existing');
    setSelectedProductId(productId);
    setIdentity(existing.identity);
    setVariants(existing.variants);
    setValidationMessage(undefined);
  };

  const startNewProduct = (typedName: string) => {
    setMode('new');
    setSelectedProductId(null);
    setIdentity({ ...EMPTY_IDENTITY, productName: typedName });
    setVariants([]);
    setValidationMessage(undefined);
  };

  const handleVariantChange = (id: string, field: keyof Variant, value: string) => {
    setVariants((current) =>
      current.map((variant) => {
        if (variant.id !== id) {
          return variant;
        }

        if (field === 'qty' || field === 'cost' || field === 'defaultSellingPrice' || field === 'maxDiscountPct') {
          return { ...variant, [field]: Number(value) || 0 };
        }

        return { ...variant, [field]: value };
      })
    );
  };

  const validate = (): string | undefined => {
    if (!identity.productName.trim()) {
      return 'Product name is required.';
    }

    if (variants.length === 0) {
      return 'At least one variant is required.';
    }

    return undefined;
  };

  const handleSave = async () => {
    const error = validate();
    setValidationMessage(error);
    if (error) {
      return;
    }

    setIsSaving(true);
    await saveProductStock({
      mode,
      identity,
      variants
    });
    setIsSaving(false);
    setValidationMessage('Saved successfully.');
  };

  return (
    <PageShell
      title="Products & Stock"
      description="Manage product identity, variants, and stock economics from one compact workspace."
    >
      <div className="products-stock-layout" data-mode={mode} data-selected-product={selectedProductId ?? ''}>
        <ProductChooser products={toLookup(products)} onSelectExisting={loadExistingProduct} onCreateNew={startNewProduct} />

        <ProductIdentityForm
          identity={identity}
          suppliers={suppliers}
          categories={categories}
          onIdentityChange={setIdentity}
          onAddSupplier={(supplier) => setSuppliers((prev) => (prev.includes(supplier) ? prev : [...prev, supplier]))}
          onAddCategory={(category) => setCategories((prev) => (prev.includes(category) ? prev : [...prev, category]))}
        />

        {mode === 'new' ? (
          <VariantGenerator
            onGenerate={({ size, color, other }) => setVariants(generateVariantsFromInputs(size, color, other))}
          />
        ) : null}

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
          onVariantChange={handleVariantChange}
          onAddVariant={() => setVariants((current) => [...current, createEmptyVariant()])}
          onRemoveVariant={(id) => setVariants((current) => current.filter((variant) => variant.id !== id))}
        />

        <SaveSummary
          variantCount={summary.variantCount}
          totalQty={summary.totalQty}
          estimatedStockCost={summary.estimatedStockCost}
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
