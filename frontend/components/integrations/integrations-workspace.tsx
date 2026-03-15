'use client';

import { FormEvent, useEffect, useState, useTransition } from 'react';

import { getInventoryWorkspace } from '@/lib/api/commerce';
import { getChannelIntegrations, saveWhatsAppMetaIntegration } from '@/lib/api/integrations';
import { WorkspaceNotice, WorkspacePanel } from '@/components/commerce/workspace-primitives';
import type { ChannelIntegration, WhatsAppMetaIntegrationPayload } from '@/types/integrations';
import { formatDateTime } from '@/lib/commerce-format';


const EMPTY_FORM: WhatsAppMetaIntegrationPayload = {
  display_name: 'WhatsApp Sales Agent',
  external_account_id: '',
  phone_number_id: '',
  phone_number: '',
  verify_token: '',
  access_token: '',
  app_secret: '',
  default_location_id: '',
  auto_send_enabled: false,
  agent_enabled: true,
  model_name: 'gpt-5-mini',
  persona_prompt:
    'You are an aggressive but honest sales agent. Increase revenue through smart upsell and slow-moving stock suggestions, but never promise unavailable stock or unauthorized discounts.',
};


type LocationOption = {
  location_id: string;
  name: string;
};


export function IntegrationsWorkspace() {
  const [integrations, setIntegrations] = useState<ChannelIntegration[]>([]);
  const [locations, setLocations] = useState<LocationOption[]>([]);
  const [draft, setDraft] = useState<WhatsAppMetaIntegrationPayload>(EMPTY_FORM);
  const [notice, setNotice] = useState('');
  const [error, setError] = useState('');
  const [isPending, startTransition] = useTransition();

  useEffect(() => {
    startTransition(async () => {
      try {
        const [integrationPayload, inventoryPayload] = await Promise.all([
          getChannelIntegrations(),
          getInventoryWorkspace(),
        ]);
        setIntegrations(integrationPayload.items);
        setLocations(inventoryPayload.locations);
        const current = integrationPayload.items[0];
        if (current) {
          setDraft((existing) => ({
            ...existing,
            display_name: current.display_name,
            external_account_id: current.external_account_id,
            phone_number_id: current.phone_number_id,
            phone_number: current.phone_number,
            default_location_id: current.default_location_id ?? '',
            auto_send_enabled: current.auto_send_enabled,
            agent_enabled: current.agent_enabled,
            model_name: current.model_name,
            persona_prompt: current.persona_prompt,
          }));
        }
      } catch (loadError) {
        setError(loadError instanceof Error ? loadError.message : 'Unable to load channel integrations.');
      }
    });
  }, []);

  const onSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setNotice('');
    setError('');
    try {
      const response = await saveWhatsAppMetaIntegration({
        ...draft,
        default_location_id: draft.default_location_id || null,
      });
      setIntegrations([response.channel]);
      if (response.setup_verify_token) {
        setNotice(`Integration saved. Verify token: ${response.setup_verify_token}`);
      } else {
        setNotice('Integration saved.');
      }
      setDraft((existing) => ({ ...existing, verify_token: '' }));
    } catch (submitError) {
      setError(submitError instanceof Error ? submitError.message : 'Unable to save the WhatsApp integration.');
    }
  };

  const current = integrations[0] ?? null;

  return (
    <div className="workspace-stack sales-agent-stack">
      {notice ? <WorkspaceNotice tone="success">{notice}</WorkspaceNotice> : null}
      {error ? <WorkspaceNotice tone="error">{error}</WorkspaceNotice> : null}

      <WorkspacePanel
        title="WhatsApp Meta channel"
        description="Store tenant channel details, webhook verification, and sales-agent behavior in one place."
        hint="This config enables inbound persistence, guarded reply generation, and draft-order creation for the tenant."
      >
        <form className="sales-agent-form" onSubmit={onSubmit}>
          <div className="sales-agent-form-grid">
            <label>
              <span>Display name</span>
              <input
                value={draft.display_name}
                onChange={(event) => setDraft({ ...draft, display_name: event.target.value })}
                placeholder="WhatsApp Sales Agent"
              />
            </label>
            <label>
              <span>Business account id</span>
              <input
                value={draft.external_account_id}
                onChange={(event) => setDraft({ ...draft, external_account_id: event.target.value })}
                placeholder="Meta business account id"
              />
            </label>
            <label>
              <span>Phone number id</span>
              <input
                value={draft.phone_number_id}
                onChange={(event) => setDraft({ ...draft, phone_number_id: event.target.value })}
                placeholder="Meta phone number id"
                required
              />
            </label>
            <label>
              <span>WhatsApp number</span>
              <input
                value={draft.phone_number}
                onChange={(event) => setDraft({ ...draft, phone_number: event.target.value })}
                placeholder="+971..."
              />
            </label>
            <label>
              <span>Verify token</span>
              <input
                value={draft.verify_token}
                onChange={(event) => setDraft({ ...draft, verify_token: event.target.value })}
                placeholder="Leave blank to auto-generate"
              />
            </label>
            <label>
              <span>OpenAI model</span>
              <input
                value={draft.model_name}
                onChange={(event) => setDraft({ ...draft, model_name: event.target.value })}
                placeholder="gpt-5-mini"
              />
            </label>
            <label>
              <span>Access token</span>
              <input
                type="password"
                value={draft.access_token}
                onChange={(event) => setDraft({ ...draft, access_token: event.target.value })}
                placeholder={current?.access_token_set ? 'Saved. Enter a new value to rotate.' : 'Meta permanent access token'}
              />
            </label>
            <label>
              <span>App secret</span>
              <input
                type="password"
                value={draft.app_secret}
                onChange={(event) => setDraft({ ...draft, app_secret: event.target.value })}
                placeholder={current?.inbound_secret_set ? 'Saved. Enter a new value to rotate.' : 'Webhook app secret'}
              />
            </label>
            <label>
              <span>Default location</span>
              <select
                value={draft.default_location_id ?? ''}
                onChange={(event) => setDraft({ ...draft, default_location_id: event.target.value })}
              >
                <option value="">Auto-select default</option>
                {locations.map((location) => (
                  <option key={location.location_id} value={location.location_id}>
                    {location.name}
                  </option>
                ))}
              </select>
            </label>
            <label className="sales-agent-checkbox">
              <input
                type="checkbox"
                checked={draft.auto_send_enabled}
                onChange={(event) => setDraft({ ...draft, auto_send_enabled: event.target.checked })}
              />
              <span>Enable guarded auto-send</span>
            </label>
            <label className="sales-agent-checkbox">
              <input
                type="checkbox"
                checked={draft.agent_enabled}
                onChange={(event) => setDraft({ ...draft, agent_enabled: event.target.checked })}
              />
              <span>Enable sales agent orchestration</span>
            </label>
            <label className="sales-agent-form-wide">
              <span>Persona prompt</span>
              <textarea
                rows={5}
                value={draft.persona_prompt}
                onChange={(event) => setDraft({ ...draft, persona_prompt: event.target.value })}
              />
            </label>
          </div>
          <div className="sales-agent-form-actions">
            <button type="submit" disabled={isPending || !draft.phone_number_id.trim()}>
              Save integration
            </button>
          </div>
        </form>
      </WorkspacePanel>

      <WorkspacePanel
        title="Current channel"
        description="Non-secret channel state is shown here so operators can verify the tenant is connected correctly."
      >
        {current ? (
          <div className="sales-agent-status-grid">
            <article className="sales-agent-stat-card">
              <span>Status</span>
              <strong>{current.status}</strong>
              <p>{current.phone_number || current.phone_number_id}</p>
            </article>
            <article className="sales-agent-stat-card">
              <span>Secrets</span>
              <strong>{current.access_token_set ? 'Ready' : 'Missing token'}</strong>
              <p>{current.inbound_secret_set ? 'App secret saved' : 'App secret missing'}</p>
            </article>
            <article className="sales-agent-stat-card">
              <span>Delivery mode</span>
              <strong>{current.auto_send_enabled ? 'Guarded auto-send' : 'Review first'}</strong>
              <p>{current.agent_enabled ? current.model_name : 'Agent disabled'}</p>
            </article>
            <article className="sales-agent-stat-card">
              <span>Traffic</span>
              <strong>Inbound {current.last_inbound_at ? formatDateTime(current.last_inbound_at) : 'Not yet'}</strong>
              <p>Outbound {current.last_outbound_at ? formatDateTime(current.last_outbound_at) : 'Not yet'}</p>
            </article>
          </div>
        ) : (
          <div className="workspace-empty">
            <h4>No tenant channel configured yet</h4>
            <p>Save the Meta WhatsApp details above to activate the Sales Agent pipeline for this tenant.</p>
          </div>
        )}
      </WorkspacePanel>
    </div>
  );
}
