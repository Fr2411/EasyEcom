'use client';

import { useMemo, useState } from 'react';
import type { ProductLookupOption } from '@/types/catalog';

type ProductChooserProps = {
  products: ProductLookupOption[];
  selectedProductId?: string | null;
  onSelectExisting: (productId: string) => void;
  onCreateNew: (typedName: string) => void;
};

export function ProductChooser({
  products,
  selectedProductId,
  onSelectExisting,
  onCreateNew,
}: ProductChooserProps) {
  const [query, setQuery] = useState('');
  const normalizedQuery = query.trim();
  const canCreateNew = normalizedQuery.length >= 1;

  const visibleProducts = useMemo(() => {
    if (!normalizedQuery) {
      return products.slice(0, 8);
    }
    const lowered = normalizedQuery.toLowerCase();
    return products.filter((product) => product.name.toLowerCase().includes(lowered));
  }, [normalizedQuery, products]);

  const hasExactMatch = useMemo(
    () => products.some((product) => product.name.trim().toLowerCase() === normalizedQuery.toLowerCase()),
    [normalizedQuery, products],
  );

  return (
    <section className="ps-card">
      <div className="ps-headline-row">
        <h3>Find or create product</h3>
      </div>
      <p className="muted">
        Load an existing product with its saved variants, or type a new name to start a fresh catalog item.
      </p>
      <div className="chooser-control" role="combobox" aria-expanded="true" aria-label="Product chooser">
        <input
          value={query}
          onChange={(event) => setQuery(event.target.value)}
          placeholder="Search products or type a new name"
          aria-label="Product chooser input"
        />
        <ul className="chooser-list">
          {canCreateNew && !hasExactMatch ? (
            <li>
              <button type="button" onClick={() => onCreateNew(normalizedQuery)}>
                Add new product: "{normalizedQuery}"
              </button>
            </li>
          ) : null}
          {visibleProducts.map((product) => (
            <li key={product.id}>
              <button
                type="button"
                aria-pressed={selectedProductId === product.id}
                onClick={() => onSelectExisting(product.id)}
              >
                {selectedProductId === product.id ? 'Editing: ' : 'Open: '}
                {product.name}
              </button>
            </li>
          ))}
          {visibleProducts.length === 0 && !canCreateNew ? (
            <li>
              <span className="muted">No catalog products loaded yet.</span>
            </li>
          ) : null}
        </ul>
      </div>
    </section>
  );
}
