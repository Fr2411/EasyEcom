'use client';

import { useMemo, useState } from 'react';
import type { ProductLookupOption } from '@/types/catalog';

type ProductChooserProps = {
  products: ProductLookupOption[];
  onSelectExisting: (productId: string) => void;
  onCreateNew: (typedName: string) => void;
};

export function ProductChooser({ products, onSelectExisting, onCreateNew }: ProductChooserProps) {
  const [query, setQuery] = useState('');
  const normalizedQuery = query.trim();
  const canSearchProducts = normalizedQuery.length >= 1;

  const filteredProducts = useMemo(() => {
    if (!canSearchProducts) {
      return [];
    }
    const lowered = normalizedQuery.toLowerCase();
    return products.filter((product) => product.name.toLowerCase().includes(lowered));
  }, [canSearchProducts, normalizedQuery, products]);

  return (
    <section className="ps-card">
      <div className="ps-headline-row">
        <h3>Find or create product</h3>
      </div>
      <div className="chooser-control" role="combobox" aria-expanded="true" aria-label="Product chooser">
        <input
          value={query}
          onChange={(event) => setQuery(event.target.value)}
          placeholder="Search products or type a new name"
          aria-label="Product chooser input"
        />
        <ul className="chooser-list">
          {canSearchProducts ? (
            <li>
              <button type="button" onClick={() => onCreateNew(normalizedQuery)}>
                Add new product: "{normalizedQuery}"
              </button>
            </li>
          ) : null}
          {filteredProducts.map((product) => (
            <li key={product.id}>
              <button type="button" onClick={() => onSelectExisting(product.id)}>
                {product.name}
              </button>
            </li>
          ))}
        </ul>
      </div>
    </section>
  );
}
