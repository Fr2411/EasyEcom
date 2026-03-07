'use client';

import type { ProductIdentity } from '@/types/products-stock';
import { featureListToInput, toFeatureList } from '@/lib/products-stock/variant-utils';

type ProductIdentityProps = {
  identity: ProductIdentity;
  suppliers: string[];
  categories: string[];
  onIdentityChange: (next: ProductIdentity) => void;
  onAddSupplier: (supplier: string) => void;
  onAddCategory: (category: string) => void;
};

export function ProductIdentityForm({
  identity,
  suppliers,
  categories,
  onIdentityChange,
  onAddSupplier,
  onAddCategory
}: ProductIdentityProps) {
  const setField = <K extends keyof ProductIdentity>(field: K, value: ProductIdentity[K]) => {
    onIdentityChange({ ...identity, [field]: value });
  };

  return (
    <section className="ps-card">
      <div className="ps-headline-row">
        <h3>Product identity</h3>
      </div>
      <div className="identity-grid">
        <label>
          Product Name
          <input value={identity.productName} onChange={(e) => setField('productName', e.target.value)} />
        </label>

        <label>
          Supplier
          <div className="inline-add-row">
            <input
              list="supplier-options"
              value={identity.supplier}
              onChange={(e) => setField('supplier', e.target.value)}
              placeholder="Select or type supplier"
            />
            <button type="button" onClick={() => identity.supplier.trim() && onAddSupplier(identity.supplier.trim())}>
              Add
            </button>
          </div>
          <datalist id="supplier-options">
            {suppliers.map((supplier) => (
              <option key={supplier} value={supplier} />
            ))}
          </datalist>
        </label>

        <label>
          Category
          <div className="inline-add-row">
            <input
              list="category-options"
              value={identity.category}
              onChange={(e) => setField('category', e.target.value)}
              placeholder="Select or type category"
            />
            <button type="button" onClick={() => identity.category.trim() && onAddCategory(identity.category.trim())}>
              Add
            </button>
          </div>
          <datalist id="category-options">
            {categories.map((category) => (
              <option key={category} value={category} />
            ))}
          </datalist>
        </label>

        <label className="field-span-2">
          Description
          <input value={identity.description} onChange={(e) => setField('description', e.target.value)} />
        </label>

        <label className="field-span-2">
          Features (comma-separated)
          <input
            value={featureListToInput(identity.features)}
            onChange={(e) => setField('features', toFeatureList(e.target.value))}
            placeholder="Breathable, Durable, Quick-dry"
          />
        </label>
      </div>
    </section>
  );
}
