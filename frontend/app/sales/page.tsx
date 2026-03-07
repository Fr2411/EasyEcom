'use client';

import { FormEvent, useEffect, useState } from 'react';
import { apiPost, SessionUser } from '../../lib/api';

export default function SalesPage() {
  const [user, setUser] = useState<SessionUser | null>(null);
  const [customerId, setCustomerId] = useState('');
  const [productId, setProductId] = useState('');
  const [qty, setQty] = useState(1);
  const [unitPrice, setUnitPrice] = useState(1);
  const [message, setMessage] = useState('');

  useEffect(() => {
    const raw = localStorage.getItem('easy_ecom_user');
    if (raw) setUser(JSON.parse(raw));
  }, []);

  async function submit(e: FormEvent) {
    e.preventDefault();
    if (!user) return;
    const result = await apiPost<{ order_id: string }>('/sales/create', {
      customer_id: customerId,
      items: [{ product_id: productId, qty, unit_selling_price: unitPrice }]
    }, user);
    setMessage(`Confirmed ${result.order_id}`);
  }

  return (
    <form onSubmit={submit}>
      <h1>Sales Order Workspace</h1>
      <input placeholder="Customer ID" value={customerId} onChange={(e) => setCustomerId(e.target.value)} />
      <input placeholder="Product ID" value={productId} onChange={(e) => setProductId(e.target.value)} />
      <input type="number" value={qty} onChange={(e) => setQty(Number(e.target.value))} />
      <input type="number" value={unitPrice} onChange={(e) => setUnitPrice(Number(e.target.value))} />
      <button type="submit">Confirm Sale</button>
      {message ? <p>{message}</p> : null}
    </form>
  );
}
