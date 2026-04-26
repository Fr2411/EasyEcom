'use client';

import { FormEvent, useEffect, useState } from 'react';
import { WorkspaceEmpty, WorkspaceNotice, WorkspacePanel } from '@/components/commerce/workspace-primitives';
import { getAIAgentSettings, updateAIAgentSettings } from '@/lib/api/ai';
import { getSettingsWorkspace, updateSettingsWorkspace } from '@/lib/api/settings';
import type { AIAgentAllowedActions, AIAgentFAQEntry, AIAgentSettings as AIAgentSettingsPayload } from '@/types/ai';
import type { SettingsWorkspace as SettingsWorkspacePayload } from '@/types/settings';

function linesToText(items: string[]) {
  return items.join('\n');
}

function textToLines(value: string) {
  return value
    .split('\n')
    .map((item) => item.trim())
    .filter(Boolean);
}

function faqToText(items: AIAgentFAQEntry[]) {
  return items
    .map((item) => `${item.question.trim()} | ${item.answer.trim()}`)
    .join('\n');
}

function textToFaq(value: string) {
  return value
    .split('\n')
    .map((line) => {
      const [question = '', ...answerParts] = line.split('|');
      return {
        question: question.trim(),
        answer: answerParts.join('|').trim(),
      };
    })
    .filter((item) => item.question || item.answer);
}

export function SettingsWorkspace() {
  const [workspace, setWorkspace] = useState<SettingsWorkspacePayload | null>(null);
  const [form, setForm] = useState<SettingsWorkspacePayload | null>(null);
  const [aiSettings, setAiSettings] = useState<AIAgentSettingsPayload | null>(null);
  const [aiForm, setAiForm] = useState<AIAgentSettingsPayload | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [notice, setNotice] = useState('');
  const [error, setError] = useState('');

  useEffect(() => {
    let active = true;
    setLoading(true);
    void Promise.all([getSettingsWorkspace(), getAIAgentSettings()])
      .then(([payload, aiPayload]) => {
        if (!active) return;
        setWorkspace(payload);
        setForm(payload);
        setAiSettings(aiPayload);
        setAiForm(aiPayload);
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
    if (!form || !aiForm) return;

    setSaving(true);
    try {
      const [payload, aiPayload] = await Promise.all([
        updateSettingsWorkspace({
          profile: form.profile,
          defaults: form.defaults,
          prefixes: form.prefixes,
        }),
        updateAIAgentSettings({
          channel_status: aiForm.channel_status,
          is_enabled: aiForm.is_enabled,
          display_name: aiForm.display_name,
          n8n_webhook_url: aiForm.n8n_webhook_url,
          persona_prompt: aiForm.persona_prompt,
          store_policy: aiForm.store_policy,
          faq_entries: aiForm.faq_entries,
          escalation_rules: aiForm.escalation_rules,
          allowed_origins: aiForm.allowed_origins,
          allowed_actions: aiForm.allowed_actions,
          default_location_id: aiForm.default_location_id,
          opening_message: aiForm.opening_message,
          handoff_message: aiForm.handoff_message,
        }),
      ]);
      setWorkspace(payload);
      setForm(payload);
      setAiSettings(aiPayload);
      setAiForm(aiPayload);
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

  if (!form || !workspace || !aiForm || !aiSettings) {
    return <WorkspaceEmpty title="Settings unavailable" message="No tenant settings were returned for this workspace." />;
  }

  const setAllowedAction = (key: keyof AIAgentAllowedActions, value: boolean) => {
    setAiForm({
      ...aiForm,
      allowed_actions: {
        ...aiForm.allowed_actions,
        [key]: value,
      },
    });
  };

  return (
    <div className="operations-page settings-module">
      <form className="operations-form-stack" onSubmit={saveSettings}>
        <div className="operations-toolbar">
          <div>
            <h2>Business profile, defaults, and document numbers</h2>
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
              </div>
            </label>
          </div>
        </WorkspacePanel>

        <WorkspacePanel title="AI sales assistant" description="Tenant-owned controls for the website chatbot and n8n workflow.">
          <div className="operations-toggle-grid">
            <label className="operations-toggle-card">
              <input
                type="checkbox"
                checked={aiForm.is_enabled}
                onChange={(event) => setAiForm({ ...aiForm, is_enabled: event.target.checked })}
              />
              <div>
                <strong>Enable assistant</strong>
              </div>
            </label>
            <label className="operations-toggle-card">
              <input
                type="checkbox"
                checked={aiForm.channel_status === 'active'}
                onChange={(event) => setAiForm({ ...aiForm, channel_status: event.target.checked ? 'active' : 'inactive' })}
              />
              <div>
                <strong>Website channel active</strong>
              </div>
            </label>
          </div>
          <div className="operations-form-grid">
            <label>
              Assistant name
              <input
                value={aiForm.display_name}
                onChange={(event) => setAiForm({ ...aiForm, display_name: event.target.value })}
              />
            </label>
            <label>
              n8n webhook URL
              <input
                value={aiForm.n8n_webhook_url}
                onChange={(event) => setAiForm({ ...aiForm, n8n_webhook_url: event.target.value })}
              />
            </label>
            <label className="field-span-2">
              Allowed website origins
              <textarea
                rows={3}
                value={linesToText(aiForm.allowed_origins)}
                onChange={(event) => setAiForm({ ...aiForm, allowed_origins: textToLines(event.target.value) })}
              />
            </label>
          </div>
        </WorkspacePanel>

        <WorkspacePanel title="AI behavior" description="Policy and tone that n8n receives before it answers customers.">
          <div className="operations-form-grid">
            <label className="field-span-2">
              Brand voice and persona
              <textarea
                rows={4}
                value={aiForm.persona_prompt}
                onChange={(event) => setAiForm({ ...aiForm, persona_prompt: event.target.value })}
              />
            </label>
            <label className="field-span-2">
              Store policy
              <textarea
                rows={5}
                value={aiForm.store_policy}
                onChange={(event) => setAiForm({ ...aiForm, store_policy: event.target.value })}
              />
            </label>
            <label className="field-span-2">
              FAQ entries
              <textarea
                rows={4}
                value={faqToText(aiForm.faq_entries)}
                onChange={(event) => setAiForm({ ...aiForm, faq_entries: textToFaq(event.target.value) })}
              />
            </label>
            <label className="field-span-2">
              Escalation rules
              <textarea
                rows={4}
                value={linesToText(aiForm.escalation_rules)}
                onChange={(event) => setAiForm({ ...aiForm, escalation_rules: textToLines(event.target.value) })}
              />
            </label>
            <label className="field-span-2">
              Handoff message
              <textarea
                rows={2}
                value={aiForm.handoff_message}
                onChange={(event) => setAiForm({ ...aiForm, handoff_message: event.target.value })}
              />
            </label>
          </div>
        </WorkspacePanel>

        <WorkspacePanel title="AI permissions" description="Allowed actions still run through EasyEcom's tenant-safe backend tools.">
          <div className="operations-toggle-grid">
            <label className="operations-toggle-card">
              <input
                type="checkbox"
                checked={aiForm.allowed_actions.product_qa}
                onChange={(event) => setAllowedAction('product_qa', event.target.checked)}
              />
              <div>
                <strong>Product Q&amp;A</strong>
              </div>
            </label>
            <label className="operations-toggle-card">
              <input
                type="checkbox"
                checked={aiForm.allowed_actions.recommendations}
                onChange={(event) => setAllowedAction('recommendations', event.target.checked)}
              />
              <div>
                <strong>Recommendations</strong>
              </div>
            </label>
            <label className="operations-toggle-card">
              <input
                type="checkbox"
                checked={aiForm.allowed_actions.cart_building}
                onChange={(event) => setAllowedAction('cart_building', event.target.checked)}
              />
              <div>
                <strong>Cart building</strong>
              </div>
            </label>
            <label className="operations-toggle-card">
              <input
                type="checkbox"
                checked={aiForm.allowed_actions.order_confirmation}
                onChange={(event) => setAllowedAction('order_confirmation', event.target.checked)}
              />
              <div>
                <strong>Order confirmation</strong>
              </div>
            </label>
          </div>
        </WorkspacePanel>

        <WorkspacePanel title="Website widget" description="Embed script for the public website chat surface.">
          <dl className="operations-definition-grid">
            <div>
              <dt>Widget key</dt>
              <dd>{aiSettings.widget_key}</dd>
            </div>
            <div>
              <dt>Channel</dt>
              <dd>{aiSettings.channel_status}</dd>
            </div>
          </dl>
          <textarea rows={3} readOnly value={aiSettings.widget_script} />
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
