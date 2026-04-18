'use client';

import Link from 'next/link';
import { FormEvent, useEffect, useState } from 'react';
import { WorkspaceNotice, WorkspacePanel } from '@/components/commerce/workspace-primitives';
import { getChannelIntegrations, getChannelLocations, saveWhatsAppMetaIntegration } from '@/lib/api/integrations';
import { getSettingsWorkspace, updateSettingsWorkspace } from '@/lib/api/settings';
import type { ChannelIntegration, ChannelLocation } from '@/types/integrations';
import type { SettingsWorkspace as SettingsWorkspacePayload } from '@/types/settings';

type ChannelDraft = {
  display_name: string;
  external_account_id: string;
  phone_number_id: string;
  phone_number: string;
  default_location_id: string;
  auto_send_enabled: boolean;
  agent_enabled: boolean;
  model_name: string;
  persona_prompt: string;
};

function SettingsLoadingState() {
  return (
    <div className="settings-layout settings-loading-layout" role="status" aria-live="polite">
      <WorkspacePanel
        title="Tenant settings"
        description="Loading tenant identity, profile defaults, and channel preferences for this workspace."
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

function channelDraftFromIntegration(channel: ChannelIntegration): ChannelDraft {
  return {
    display_name: channel.display_name,
    external_account_id: channel.external_account_id,
    phone_number_id: channel.phone_number_id,
    phone_number: channel.phone_number,
    default_location_id: channel.default_location_id ?? '',
    auto_send_enabled: channel.auto_send_enabled,
    agent_enabled: channel.agent_enabled,
    model_name: channel.model_name,
    persona_prompt: channel.persona_prompt,
  };
}

export function SettingsWorkspace() {
  const [workspace, setWorkspace] = useState<SettingsWorkspacePayload | null>(null);
  const [form, setForm] = useState<SettingsWorkspacePayload | null>(null);
  const [channel, setChannel] = useState<ChannelIntegration | null>(null);
  const [channelDraft, setChannelDraft] = useState<ChannelDraft | null>(null);
  const [locations, setLocations] = useState<ChannelLocation[]>([]);
  const [loading, setLoading] = useState(true);
  const [savingSettings, setSavingSettings] = useState(false);
  const [savingChannel, setSavingChannel] = useState(false);
  const [notice, setNotice] = useState('');
  const [error, setError] = useState('');

  useEffect(() => {
    let active = true;
    setLoading(true);
    void Promise.all([getSettingsWorkspace(), getChannelIntegrations(), getChannelLocations()])
      .then(([settingsPayload, channelsPayload, locationsPayload]) => {
        if (!active) return;
        const whatsapp = channelsPayload.items.find((item) => item.provider === 'whatsapp') ?? null;
        setWorkspace(settingsPayload);
        setForm(settingsPayload);
        setChannel(whatsapp);
        setChannelDraft(whatsapp ? channelDraftFromIntegration(whatsapp) : null);
        setLocations(locationsPayload.items);
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

  const saveChannelPreferences = async () => {
    if (!channelDraft) return;
    setSavingChannel(true);
    try {
      const payload = await saveWhatsAppMetaIntegration({
        ...channelDraft,
        verify_token: '',
        access_token: '',
        app_secret: '',
        default_location_id: channelDraft.default_location_id || null,
      });
      setChannel(payload.channel);
      setChannelDraft(channelDraftFromIntegration(payload.channel));
      setNotice('Channel preferences saved.');
      setError('');
    } catch (saveError) {
      setError(saveError instanceof Error ? saveError.message : 'Unable to save channel preferences.');
    } finally {
      setSavingChannel(false);
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
                WhatsApp number
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

      <WorkspacePanel
        title="Channel preferences"
        description="Tenant-level AI selling behavior stays channel-scoped so it remains aligned with the live WhatsApp integration."
        actions={
          channelDraft ? (
            <button type="button" className="btn-primary settings-save-btn" onClick={saveChannelPreferences} disabled={savingChannel}>
              {savingChannel ? 'Saving…' : 'Save channel preferences'}
            </button>
          ) : null
        }
      >
        {channel && channelDraft ? (
          <div className="settings-grid">
            <label>
              Display name
              <input
                value={channelDraft.display_name}
                onChange={(event) => setChannelDraft({ ...channelDraft, display_name: event.target.value })}
              />
            </label>
            <label>
              Phone number
              <input
                value={channelDraft.phone_number}
                onChange={(event) => setChannelDraft({ ...channelDraft, phone_number: event.target.value })}
              />
            </label>
            <label>
              Meta phone number ID
              <input value={channelDraft.phone_number_id} disabled />
            </label>
            <label>
              Default location
              <select
                value={channelDraft.default_location_id}
                onChange={(event) => setChannelDraft({ ...channelDraft, default_location_id: event.target.value })}
              >
                <option value="">Use tenant default</option>
                {locations.map((location) => (
                  <option key={location.location_id} value={location.location_id}>
                    {location.name}
                  </option>
                ))}
              </select>
            </label>
            <label>
              Model name
              <input
                value={channelDraft.model_name}
                onChange={(event) => setChannelDraft({ ...channelDraft, model_name: event.target.value })}
              />
            </label>
            <label className="admin-checkbox">
              <input
                type="checkbox"
                checked={channelDraft.auto_send_enabled}
                onChange={(event) => setChannelDraft({ ...channelDraft, auto_send_enabled: event.target.checked })}
              />
              Auto-send approved replies
            </label>
            <label className="admin-checkbox">
              <input
                type="checkbox"
                checked={channelDraft.agent_enabled}
                onChange={(event) => setChannelDraft({ ...channelDraft, agent_enabled: event.target.checked })}
              />
              AI agent enabled
            </label>
            <label className="field-span-2">
              Persona prompt
              <textarea
                value={channelDraft.persona_prompt}
                onChange={(event) => setChannelDraft({ ...channelDraft, persona_prompt: event.target.value })}
              />
            </label>
          </div>
        ) : (
          <WorkspaceNotice tone="info">
            No WhatsApp channel is configured for this tenant yet. Configure the live channel in <Link href="/integrations">Integrations</Link>, then return here to manage tenant-level channel preferences.
          </WorkspaceNotice>
        )}
      </WorkspacePanel>
      <div className="mobile-action-safe-spacer" aria-hidden="true" />
    </div>
  );
}
