'use client';

import { useEffect, useMemo, useState } from 'react';
import { ApiError, ApiNetworkError } from '@/lib/api/client';
import { createCustomer, getCustomers, updateCustomer } from '@/lib/api/customers';
import type { Customer, CustomerPayload } from '@/types/customers';

const INITIAL_FORM: CustomerPayload = { full_name: '', phone: '', email: '', address_line1: '', city: '', notes: '' };

export function CustomersWorkspace() {
  const [items, setItems] = useState<Customer[]>([]);
  const [selected, setSelected] = useState<Customer | null>(null);
  const [query, setQuery] = useState('');
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [form, setForm] = useState<CustomerPayload>(INITIAL_FORM);
  const isEditMode = Boolean(selected?.customer_id);

  const load = async (q = query) => {
    try {
      setLoading(true); setError(null);
      const data = await getCustomers(q);
      setItems(data.items);
    } catch (err) {
      if (err instanceof ApiNetworkError) setError('Unable to connect to customer service.');
      else if (err instanceof ApiError && err.status === 401) setError('Session expired. Sign in again.');
      else setError('Unable to load customers right now.');
    } finally { setLoading(false); }
  };

  useEffect(() => { load(''); }, []);
  useEffect(() => {
    if (!selected) return setForm(INITIAL_FORM);
    setForm({ full_name: selected.full_name, phone: selected.phone, email: selected.email, address_line1: selected.address_line1, city: selected.city, notes: selected.notes });
  }, [selected]);

  const canSubmit = useMemo(() => form.full_name.trim().length > 0 && !saving, [form.full_name, saving]);

  const submit = async () => {
    if (!canSubmit) return;
    try {
      setSaving(true); setError(null);
      const res = selected ? await updateCustomer(selected.customer_id, form) : await createCustomer(form);
      setSelected(res.customer);
      await load(query);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to save customer.');
    } finally { setSaving(false); }
  };

  return (
    <section className="customers-module">
      <div className="customers-toolbar">
        <input aria-label="Search customers" placeholder="Search name, phone, or email" value={query} onChange={(e) => setQuery(e.target.value)} />
        <button type="button" onClick={() => load(query)}>Search</button>
        <button type="button" onClick={() => setSelected(null)}>Add Customer</button>
      </div>
      {error ? <p className="customers-error">{error}</p> : null}
      {loading ? <p className="customers-loading">Loading customers...</p> : null}
      {!loading && items.length === 0 ? <div className="customers-empty"><h3>No customers yet</h3><p>Add your first customer to start creating sales orders faster.</p></div> : null}
      <div className="customers-grid">
        <div className="customers-list">
          <table><thead><tr><th>Name</th><th>Phone</th><th>Email</th><th>City</th></tr></thead><tbody>
            {items.map((item) => <tr key={item.customer_id} onClick={() => setSelected(item)} className={selected?.customer_id === item.customer_id ? 'active' : ''}><td>{item.full_name}</td><td>{item.phone || '—'}</td><td>{item.email || '—'}</td><td>{item.city || '—'}</td></tr>)}
          </tbody></table>
        </div>
        <aside className="customer-detail">
          <h3>{isEditMode ? 'Customer Details' : 'Create Customer'}</h3>
          <label>Name<input value={form.full_name} onChange={(e) => setForm((prev) => ({ ...prev, full_name: e.target.value }))} /></label>
          <label>Phone<input value={form.phone} onChange={(e) => setForm((prev) => ({ ...prev, phone: e.target.value }))} /></label>
          <label>Email<input value={form.email} onChange={(e) => setForm((prev) => ({ ...prev, email: e.target.value }))} /></label>
          <label>Address<input value={form.address_line1} onChange={(e) => setForm((prev) => ({ ...prev, address_line1: e.target.value }))} /></label>
          <label>City<input value={form.city} onChange={(e) => setForm((prev) => ({ ...prev, city: e.target.value }))} /></label>
          <label>Notes<textarea value={form.notes} onChange={(e) => setForm((prev) => ({ ...prev, notes: e.target.value }))} /></label>
          {selected ? <p className="customers-meta">Created: {selected.created_at || '—'} · Updated: {selected.updated_at || '—'}</p> : null}
          <button type="button" disabled={!canSubmit} onClick={submit}>{saving ? 'Saving…' : isEditMode ? 'Update Customer' : 'Create Customer'}</button>
        </aside>
      </div>
    </section>
  );
}
