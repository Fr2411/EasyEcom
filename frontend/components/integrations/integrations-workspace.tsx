'use client';

import { useEffect, useMemo, useState } from 'react';
import { ApiError } from '@/lib/api/client';
import { createIntegration, getConversations, getIntegrationMessages, getIntegrations } from '@/lib/api/integrations';
import { useAuth } from '@/components/auth/auth-provider';
import type { ChannelConversation, ChannelIntegration, ChannelMessage } from '@/types/integrations';

const ADMIN_ROLES = new Set(['SUPER_ADMIN', 'CLIENT_OWNER', 'CLIENT_MANAGER']);

export function IntegrationsWorkspace() {
  const { user } = useAuth();
  const canAccess = useMemo(() => Boolean(user?.roles?.some((role) => ADMIN_ROLES.has(role))), [user?.roles]);
  const [items, setItems] = useState<ChannelIntegration[]>([]);
  const [messages, setMessages] = useState<ChannelMessage[]>([]);
  const [conversations, setConversations] = useState<ChannelConversation[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [saving, setSaving] = useState(false);
  const [form, setForm] = useState({ provider: 'webhook', display_name: '', external_account_id: '', status: 'inactive', verify_token: '', inbound_secret: '' });

  async function loadData() {
    setLoading(true);
    setError('');
    try {
      const [channels, recentMessages, recentConversations] = await Promise.all([getIntegrations(), getIntegrationMessages(), getConversations()]);
      setItems(channels.items);
      setMessages(recentMessages.items.slice(0, 5));
      setConversations(recentConversations.items.slice(0, 5));
    } catch (err) {
      if (err instanceof ApiError && err.status === 403) setError('Access denied. Only tenant admins/managers can configure channels.');
      else setError('Unable to load channel integrations.');
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    if (!canAccess) {
      setLoading(false);
      return;
    }
    void loadData();
  }, [canAccess]);

  async function onCreate(event: React.FormEvent) {
    event.preventDefault();
    setSaving(true);
    setError('');
    try {
      await createIntegration(form);
      setForm({ provider: 'webhook', display_name: '', external_account_id: '', status: 'inactive', verify_token: '', inbound_secret: '' });
      await loadData();
    } catch (err) {
      setError(err instanceof ApiError ? `Create failed: ${err.message}` : 'Create failed');
    } finally {
      setSaving(false);
    }
  }

  if (!canAccess) return <div className="admin-card" data-testid="integrations-access-denied"><h3>Integrations access denied</h3><p>Only tenant owner/manager roles can configure channels.</p></div>;
  if (loading) return <div className="admin-card" data-testid="integrations-loading"><h3>Loading integrations…</h3></div>;

  return <div className="integrations-layout">
    <section className="admin-card">
      <h3>Channel integrations</h3>
      {error ? <p className="admin-error">{error}</p> : null}
      {items.length === 0 ? <p data-testid="integrations-empty-state">No channel integrations configured yet.</p> : (
        <table className="admin-table"><thead><tr><th>Name</th><th>Provider</th><th>Status</th><th>Last inbound</th></tr></thead><tbody>{items.map((item) => <tr key={item.channel_id}><td>{item.display_name}</td><td>{item.provider}</td><td><span className={`int-status int-${item.status}`}>{item.status}</span></td><td>{item.last_inbound_at ?? '—'}</td></tr>)}</tbody></table>
      )}
    </section>

    <section className="admin-card">
      <h3>Add integration</h3>
      <form className="admin-form" onSubmit={onCreate}>
        <label>Provider<select value={form.provider} onChange={(e) => setForm((p) => ({ ...p, provider: e.target.value }))}><option value="webhook">Webhook</option><option value="whatsapp">WhatsApp</option><option value="messenger">Messenger</option></select></label>
        <label>Display name<input required value={form.display_name} onChange={(e) => setForm((p) => ({ ...p, display_name: e.target.value }))} /></label>
        <label>External account/page id<input value={form.external_account_id} onChange={(e) => setForm((p) => ({ ...p, external_account_id: e.target.value }))} /></label>
        <label>Status<select value={form.status} onChange={(e) => setForm((p) => ({ ...p, status: e.target.value }))}><option value="inactive">Inactive</option><option value="active">Active</option><option value="disabled">Disabled</option></select></label>
        <label>Verification token<input value={form.verify_token} onChange={(e) => setForm((p) => ({ ...p, verify_token: e.target.value }))} /></label>
        <label>Inbound secret<input value={form.inbound_secret} onChange={(e) => setForm((p) => ({ ...p, inbound_secret: e.target.value }))} /></label>
        <button type="submit" disabled={saving}>{saving ? 'Saving…' : 'Create integration'}</button>
      </form>
    </section>

    <section className="admin-card">
      <h3>Recent communication events</h3>
      {messages.length === 0 ? <p>No inbound/outbound events yet.</p> : <ul className="integrations-events">{messages.map((row) => <li key={row.message_id}><strong>{row.direction}</strong> · {row.content_summary || 'No text'}<br /><span>{row.occurred_at}</span></li>)}</ul>}
    </section>

    <section className="admin-card">
      <h3>Recent conversations</h3>
      {conversations.length === 0 ? <p>No conversations recorded yet.</p> : <ul className="integrations-events">{conversations.map((row) => <li key={row.conversation_id}><strong>{row.external_sender_id}</strong> via {row.channel_id}<br /><span>{row.last_message_at}</span></li>)}</ul>}
    </section>
  </div>;
}
