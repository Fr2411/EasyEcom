'use client';

import { FormEvent, useEffect, useState } from 'react';
import { WorkspaceEmpty, WorkspaceNotice, WorkspacePanel } from '@/components/commerce/workspace-primitives';
import { getSettingsWorkspace, updateSettingsWorkspace } from '@/lib/api/settings';
import type { SettingsWorkspace as SettingsWorkspacePayload } from '@/types/settings';

export function SettingsWorkspace() {
  const [workspace, setWorkspace] = useState<SettingsWorkspacePayload | null>(null);
  const [form, setForm] = useState<SettingsWorkspacePayload | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [notice, setNotice] = useState('');
  const [error, setError] = useState('');

  useEffect(() => {
    let active = true;
    setLoading(true);
    void getSettingsWorkspace()
      .then((payload) => {
        if (!active) return;
        setWorkspace(payload);
        setForm(payload);
        setError('');
      })
      .catch((loadError) => {
        if (!active) return;
        setError(loadError instanceof Error ? loadError.message : 'Unable to load settings.');
      })
      .finally(() => {
        if (active) setLoading(false);
      });

    return () => {
      active = false;
    };
  }, []);

  const saveSettings = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!form) return;

    setSaving(true);
    try {
      const payload = await updateSettingsWorkspace({
        profile: form.profile,
        defaults: form.defaults,
        prefixes: form.prefixes,
      });
      setWorkspace(payload);
      setForm(payload);
      setNotice('Settings saved.');
      setError('');
    } catch (saveError) {
      setError(saveError instanceof Error ? saveError.message : 'Unable to save settings.');
    } finally {
      setSaving(false);
    }
  };

  if (loading) {
    return <div className="reports-loading">Loading settings…</div>;
  }

  if (error && !form) {
    return <div className="reports-error">{error}</div>;
  }

  if (!form || !workspace) {
    return <WorkspaceEmpty title="Settings unavailable" message="No tenant settings were returned for this workspace." />;
  }

  return (
    <div className="operations-page settings-module">
      <form className="operations-form-stack" onSubmit={saveSettings}>
        <div className="operations-toolbar">
          <div>
            <p className="operations-eyebrow">Business setup</p>
            <h2>Business profile, defaults, and document numbers</h2>
            <p>Keep core business details current. Technical metadata stays collapsed unless you need it.</p>
          </div>
          <div className="operations-toolbar-actions">
            <button type="submit" className="btn-primary" disabled={saving}>{saving ? 'Saving…' : 'Save Settings'}</button>
          </div>
        </div>

        {notice ? <WorkspaceNotice tone="success">{notice}</WorkspaceNotice> : null}
        {error ? <WorkspaceNotice tone="error">{error}</WorkspaceNotice> : null}

        <WorkspacePanel title="Workspace context" description="Confirm the active tenant before editing business settings.">
          <dl className="operations-definition-grid">
            <div>
              <dt>Business</dt>
              <dd>{workspace.tenant_context.business_name}</dd>
            </div>
            <div>
              <dt>Status</dt>
              <dd>{workspace.tenant_context.status}</dd>
            </div>
            <div>
              <dt>Currency</dt>
              <dd>{workspace.tenant_context.currency_code}</dd>
            </div>
          </dl>
          <details className="operations-advanced-block">
            <summary>Advanced</summary>
            <dl className="operations-definition-grid compact">
              <div>
                <dt>Tenant ID</dt>
                <dd>{workspace.tenant_context.client_id}</dd>
              </div>
            </dl>
          </details>
        </WorkspacePanel>

        <WorkspacePanel title="Business profile" description="Daily-use contact and identity details for the live workspace.">
          <div className="operations-form-grid">
            <label>
              Business name
              <input
                value={form.profile.business_name}
                onChange={(event) => setForm({ ...form, profile: { ...form.profile, business_name: event.target.value } })}
              />
            </label>
            <label>
              Contact name
              <input
                value={form.profile.contact_name}
                onChange={(event) => setForm({ ...form, profile: { ...form.profile, contact_name: event.target.value } })}
              />
            </label>
            <label>
              Email
              <input
                value={form.profile.email}
                onChange={(event) => setForm({ ...form, profile: { ...form.profile, email: event.target.value } })}
              />
            </label>
            <label>
              Phone
              <input
                value={form.profile.phone}
                onChange={(event) => setForm({ ...form, profile: { ...form.profile, phone: event.target.value } })}
              />
            </label>
            <label className="field-span-2">
              Address
              <textarea
                rows={3}
                value={form.profile.address}
                onChange={(event) => setForm({ ...form, profile: { ...form.profile, address: event.target.value } })}
              />
            </label>
          </div>

          <details className="operations-advanced-block">
            <summary>Advanced</summary>
            <div className="operations-form-grid compact">
              <label>
                Owner name
                <input
                  value={form.profile.owner_name}
                  onChange={(event) => setForm({ ...form, profile: { ...form.profile, owner_name: event.target.value } })}
                />
              </label>
              <label>
                Website URL
                <input
                  value={form.profile.website_url}
                  onChange={(event) => setForm({ ...form, profile: { ...form.profile, website_url: event.target.value } })}
                />
              </label>
              <label>
                Timezone
                <input
                  value={form.profile.timezone}
                  onChange={(event) => setForm({ ...form, profile: { ...form.profile, timezone: event.target.value } })}
                />
              </label>
              <label>
                Currency code
                <input
                  value={form.profile.currency_code}
                  onChange={(event) => setForm({ ...form, profile: { ...form.profile, currency_code: event.target.value } })}
                />
              </label>
              <label>
                Currency symbol
                <input
                  value={form.profile.currency_symbol}
                  onChange={(event) => setForm({ ...form, profile: { ...form.profile, currency_symbol: event.target.value } })}
                />
              </label>
              <label className="field-span-2">
                Notes
                <textarea
                  rows={3}
                  value={form.profile.notes}
                  onChange={(event) => setForm({ ...form, profile: { ...form.profile, notes: event.target.value } })}
                />
              </label>
            </div>
          </details>
        </WorkspacePanel>

        <WorkspacePanel title="Defaults" description="Operational defaults used across catalog, inventory, and sales.">
          <div className="operations-form-grid compact">
            <label>
              Default location name
              <input
                value={form.defaults.default_location_name}
                onChange={(event) => setForm({ ...form, defaults: { ...form.defaults, default_location_name: event.target.value } })}
              />
            </label>
            <label>
              Low stock threshold
              <input
                inputMode="decimal"
                value={String(form.defaults.low_stock_threshold)}
                onChange={(event) => setForm({ ...form, defaults: { ...form.defaults, low_stock_threshold: Number(event.target.value || '0') } })}
              />
            </label>
          </div>
          <div className="operations-toggle-grid">
            <label className="operations-toggle-card">
              <input
                type="checkbox"
                checked={form.defaults.allow_backorder}
                onChange={(event) => setForm({ ...form, defaults: { ...form.defaults, allow_backorder: event.target.checked } })}
              />
              <div>
                <strong>Allow backorders</strong>
                <span>Keep selling even when stock is not available.</span>
              </div>
            </label>
            <label className="operations-toggle-card">
              <input
                type="checkbox"
                checked={form.defaults.require_discount_approval}
                onChange={(event) => setForm({ ...form, defaults: { ...form.defaults, require_discount_approval: event.target.checked } })}
              />
              <div>
                <strong>Require discount approval</strong>
                <span>Protect minimum-price rules during sales entry.</span>
              </div>
            </label>
          </div>
        </WorkspacePanel>

        <WorkspacePanel title="Document numbers" description="Prefixes shown in live sales and return records.">
          <div className="operations-form-grid compact">
            <label>
              Sales prefix
              <input
                value={form.prefixes.sales_prefix}
                onChange={(event) => setForm({ ...form, prefixes: { ...form.prefixes, sales_prefix: event.target.value.toUpperCase() } })}
              />
            </label>
            <label>
              Returns prefix
              <input
                value={form.prefixes.returns_prefix}
                onChange={(event) => setForm({ ...form, prefixes: { ...form.prefixes, returns_prefix: event.target.value.toUpperCase() } })}
              />
            </label>
          </div>
        </WorkspacePanel>
      </form>
      <div className="mobile-action-safe-spacer" aria-hidden="true" />
    </div>
  );
}
