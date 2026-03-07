'use client';

import { useEffect, useState } from 'react';
import { apiGet, apiPost, SessionUser } from '../../lib/api';

type Product = { product_id: string; product_name: string };

export default function ProductsStockPage() {
  const [user, setUser] = useState<SessionUser | null>(null);
  const [query, setQuery] = useState('');
  const [results, setResults] = useState<Product[]>([]);

  useEffect(() => {
    const raw = localStorage.getItem('easy_ecom_user');
    if (raw) setUser(JSON.parse(raw));
  }, []);

  async function search() {
    if (!user) return;
    const rows = await apiGet<Product[]>(`/products/search?q=${encodeURIComponent(query)}`, user);
    setResults(rows);
  }

  async function createSimpleProduct() {
    if (!user) return;
    await apiPost('/products/upsert', {
      typed_product_name: query || 'New Product',
      variant_entries: [{ variant_label: 'Default', qty: 0, unit_cost: 0, default_selling_price: 0, max_discount_pct: 10 }]
    }, user);
    await search();
  }

  return (
    <div>
      <h1>Catalog & Stock</h1>
      <input value={query} onChange={(e) => setQuery(e.target.value)} placeholder="Search or add product" />
      <button onClick={search}>Search</button>
      <button onClick={createSimpleProduct}>Save</button>
      <ul>{results.map((p) => <li key={p.product_id}>{p.product_name}</li>)}</ul>
    </div>
  );
}
