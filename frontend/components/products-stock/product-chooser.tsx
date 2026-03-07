'use client';

import { useMemo, useState } from 'react';
import type { ProductLookupOption } from '@/types/products-stock';

type ProductChooserProps = {
  products: ProductLookupOption[];
  onSelectExisting: (productId: string) => void;
  onCreateNew: (typedName: string) => void;
};

export function ProductChooser({ products, onSelectExisting, onCreateNew }: ProductChooserProps) {
  const [query, setQuery] = useState('');

  const filteredProducts = useMemo(() => {
    const lowered = query.toLowerCase();
    return products.filter((product) => product.name.toLowerCase().includes(lowered));
  }, [products, query]);

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
          {query.trim() ? (
            <li>
              <button type="button" onClick={() => onCreateNew(query.trim())}>
                Add new product: "{query.trim()}"
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
