'use client';

import { FormEvent, useEffect, useState } from 'react';
import { WorkspaceNotice, WorkspacePanel } from '@/components/commerce/workspace-primitives';
import { getSettingsWorkspace, updateSettingsWorkspace } from '@/lib/api/settings';
import type { SettingsWorkspace as SettingsWorkspacePayload } from '@/types/settings';

function SettingsLoadingState() {
  return (
    <div className="settings-layout settings-loading-layout" role="status" aria-live="polite">
      <WorkspacePanel
        title="Tenant settings"
        description="Loading tenant identity and profile defaults for this workspace."
      >
        <div className="settings-loading-copy">
          <strong>Loading tenant settings…</strong>
          <p className="settings-muted">Preparing tenant-scoped configuration fields. No stock, sales, or ledger data is modified during loading.</p>
        </div>
        <div className="settings-loading-context">
          <div className="settings-loading-pill" />
          <div className="settings-loading-pill" />
          <div className="settings-loading-pill" />
        </div>
      </WorkspacePanel>

      <WorkspacePanel
        title="Profile, defaults, and document prefixes"
        description="This section loads profile fields, operational defaults, and document prefixes."
      >
        <div className="settings-loading-grid">
          {Array.from({ length: 8 }).map((_, index) => (
            <div key={`settings-loading-profile-${index}`} className="settings-loading-field" />
          ))}
        </div>
      </WorkspacePanel>
    </div>
  );
}

function sectionStatus(completed: number, total: number) {
  if (completed === total) return { label: 'Ready', tone: 'is-ready' as const };
  if (completed > 0) return { label: `${completed}/${total} complete`, tone: 'is-in-progress' as const };
  return { label: 'Needs setup', tone: 'is-empty' as const };
}

export function SettingsWorkspace() {
  const [workspace, setWorkspace] = useState<SettingsWorkspacePayload | null>(null);
  const [form, setForm] = useState<SettingsWorkspacePayload | null>(null);
  const [loading, setLoading] = useState(true);
  const [savingSettings, setSavingSettings] = useState(false);
  const [notice, setNotice] = useState('');
  const [error, setError] = useState('');

  useEffect(() => {
    let active = true;
    setLoading(true);
    void getSettingsWorkspace()
      .then((settingsPayload) => {
        if (!active) return;
        setWorkspace(settingsPayload);
        setForm(settingsPayload);
        setError('');
      })
      .catch((loadError) => {
        if (!active) return;
        setError(loadError instanceof Error ? loadError.message : 'Unable to load tenant settings.');
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
    setSavingSettings(true);
    try {
      const payload = await updateSettingsWorkspace({
        profile: form.profile,
        defaults: form.defaults,
        prefixes: form.prefixes,
      });
      setWorkspace(payload);
      setForm(payload);
      setNotice('Tenant settings saved.');
      setError('');
    } catch (saveError) {
      setError(saveError instanceof Error ? saveError.message : 'Unable to save tenant settings.');
    } finally {
      setSavingSettings(false);
    }
  };

  if (loading) {
    return <SettingsLoadingState />;
  }

  if (error && !form) {
    return <div className="reports-error">{error}</div>;
  }

  if (!form) {
    return null;
  }

  const profileCompleted = [
    form.profile.business_name,
    form.profile.contact_name,
    form.profile.email,
    form.profile.phone,
    form.profile.whatsapp_number,
    form.profile.address,
  ].filter((value) => value.trim().length > 0).length;
  const defaultsCompleted = [
    form.defaults.default_location_name,
    String(form.defaults.low_stock_threshold),
  ].filter((value) => value.trim().length > 0).length;
  const numberingCompleted = [
    form.prefixes.sales_prefix,
    form.prefixes.purchases_prefix,
    form.prefixes.returns_prefix,
  ].filter((value) => value.trim().length > 0).length;
  const profileStatus = sectionStatus(profileCompleted, 6);
  const defaultsStatus = sectionStatus(defaultsCompleted, 2);
  const numberingStatus = sectionStatus(numberingCompleted, 3);

  return (
    <div className="settings-layout">
      {notice ? <WorkspaceNotice tone="success">{notice}</WorkspaceNotice> : null}
      {error ? <WorkspaceNotice tone="error">{error}</WorkspaceNotice> : null}

      <WorkspacePanel title="Tenant settings" description="Confirm the active tenant identity and scope before editing settings.">
        <dl className="settings-context">
          <div>
            <dt>Business</dt>
            <dd>{workspace?.tenant_context.business_name}</dd>
          </div>
          <div>
            <dt>Status</dt>
            <dd>{workspace?.tenant_context.status}</dd>
          </div>
          <div>
            <dt>Currency</dt>
            <dd>{workspace?.tenant_context.currency_code}</dd>
          </div>
        </dl>
        <details className="settings-technical-details">
          <summary>Advanced technical details</summary>
          <dl className="settings-context settings-context-technical">
            <div>
              <dt>Tenant ID</dt>
              <dd>{workspace?.tenant_context.client_id}</dd>
            </div>
          </dl>
        </details>
      </WorkspacePanel>

      <form onSubmit={saveSettings}>
        <WorkspacePanel
          title="Profile, defaults, and document prefixes"
          description="Update business profile fields, operational defaults, and numbering prefixes used by sales, purchases, and returns."
          actions={<button type="submit" className="btn-primary settings-save-btn" disabled={savingSettings}>{savingSettings ? 'Saving…' : 'Save settings'}</button>}
        >
          <section className="settings-section">
            <div className="workspace-subsection-header">
              <h4>Business profile</h4>
              <p>Keep core contact details first for fast routine updates.</p>
              <span className={`settings-section-status ${profileStatus.tone}`}>{profileStatus.label}</span>
            </div>
            <div className="settings-grid">
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
              <label>
                Secondary phone
                <input
                  value={form.profile.whatsapp_number}
                  onChange={(event) => setForm({ ...form, profile: { ...form.profile, whatsapp_number: event.target.value } })}
                />
              </label>
              <label className="field-span-2">
                Address
                <textarea
                  value={form.profile.address}
                  onChange={(event) => setForm({ ...form, profile: { ...form.profile, address: event.target.value } })}
                />
              </label>
            </div>
            <details className="settings-technical-details settings-advanced-profile">
              <summary>Additional profile details</summary>
              <div className="settings-grid settings-grid-advanced">
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
                    value={form.profile.notes}
                    onChange={(event) => setForm({ ...form, profile: { ...form.profile, notes: event.target.value } })}
                  />
                </label>
              </div>
            </details>
          </section>

          <section className="settings-section">
            <div className="workspace-subsection-header">
              <h4>Operational defaults</h4>
              <p>Review default inventory and approval rules that affect day-to-day operations.</p>
              <span className={`settings-section-status ${defaultsStatus.tone}`}>{defaultsStatus.label}</span>
            </div>
            <div className="settings-grid">
              <label>
                Default warehouse name
                <input
                  value={form.defaults.default_location_name}
                  onChange={(event) => setForm({ ...form, defaults: { ...form.defaults, default_location_name: event.target.value } })}
                />
              </label>
              <label>
                Low-stock threshold
                <input
                  type="number"
                  min="0"
                  step="1"
                  value={form.defaults.low_stock_threshold}
                  onChange={(event) => setForm({ ...form, defaults: { ...form.defaults, low_stock_threshold: Number(event.target.value) } })}
                />
              </label>
              <label className="admin-checkbox">
                <input
                  type="checkbox"
                  checked={form.defaults.allow_backorder}
                  onChange={(event) => setForm({ ...form, defaults: { ...form.defaults, allow_backorder: event.target.checked } })}
                />
                Allow backorder
              </label>
              <label className="admin-checkbox">
                <input
                  type="checkbox"
                  checked={form.defaults.require_discount_approval}
                  onChange={(event) => setForm({ ...form, defaults: { ...form.defaults, require_discount_approval: event.target.checked } })}
                />
                Require discount approval
              </label>
            </div>
          </section>

          <section className="settings-section">
            <div className="workspace-subsection-header">
              <h4>Document numbering</h4>
              <p>Keep prefixes consistent so order, purchase, and return IDs stay easy to scan.</p>
              <span className={`settings-section-status ${numberingStatus.tone}`}>{numberingStatus.label}</span>
            </div>
            <div className="settings-grid">
              <label>
                Sales prefix
                <input
                  value={form.prefixes.sales_prefix}
                  onChange={(event) => setForm({ ...form, prefixes: { ...form.prefixes, sales_prefix: event.target.value.toUpperCase() } })}
                />
              </label>
              <label>
                Purchases prefix
                <input
                  value={form.prefixes.purchases_prefix}
                  onChange={(event) => setForm({ ...form, prefixes: { ...form.prefixes, purchases_prefix: event.target.value.toUpperCase() } })}
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
          </section>
        </WorkspacePanel>
      </form>

      <div className="mobile-action-safe-spacer" aria-hidden="true" />
    </div>
  );
}
