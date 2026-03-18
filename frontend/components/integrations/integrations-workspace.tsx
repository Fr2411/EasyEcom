'use client';

import { FormEvent, useEffect, useState, useTransition } from 'react';

import { useAuth } from '@/components/auth/auth-provider';
import { WorkspaceNotice, WorkspacePanel } from '@/components/commerce/workspace-primitives';
import { ApiNetworkError } from '@/lib/api/client';
import { getPublicEnv } from '@/lib/env';
import { listAdminClients } from '@/lib/api/admin';
import {
  getChannelIntegrations,
  getChannelLocations,
  runChannelDiagnostics,
  saveWhatsAppMetaIntegration,
  sendChannelSmoke,
  validateWhatsAppMetaIntegration,
} from '@/lib/api/integrations';
import { formatDateTime } from '@/lib/commerce-format';
import type { AdminClient } from '@/types/admin';
import type {
  ChannelDiagnostics,
  ChannelDiagnosticsEnvelope,
  ChannelIntegration,
  ChannelLocation,
  WhatsAppMetaIntegrationPayload,
} from '@/types/integrations';


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

type DiagnosticStep = {
  label: string;
  status: 'pass' | 'fail' | 'pending';
  detail: string;
};

function stepClassName(status: DiagnosticStep['status']) {
  return `integration-step integration-step-${status}`;
}

function diagnosticsFromChannel(channel: ChannelIntegration): ChannelDiagnostics {
  return {
    config_saved: channel.config_saved,
    verify_token_set: channel.verify_token_set,
    webhook_verified_at: channel.webhook_verified_at,
    last_webhook_post_at: channel.last_webhook_post_at,
    signature_validation_ok: channel.signature_validation_ok,
    graph_auth_ok: channel.graph_auth_ok,
    outbound_send_ok: channel.outbound_send_ok,
    openai_ready: channel.openai_ready ?? false,
    openai_probe_ok: channel.openai_probe_ok,
    last_error_code: channel.last_error_code,
    last_error_message: channel.last_error_message,
    last_provider_status_code: channel.last_provider_status_code,
    last_provider_response_excerpt: channel.last_provider_response_excerpt,
    last_diagnostic_at: channel.last_diagnostic_at,
    next_action: channel.next_action,
  };
}

function mergeChannelDiagnostics(channel: ChannelIntegration, diagnostics: ChannelDiagnostics): ChannelIntegration {
  return { ...channel, ...diagnostics };
}

function buildDiagnosticSteps(diagnostics: ChannelDiagnostics, autoSendEnabled: boolean): DiagnosticStep[] {
  return [
    {
      label: 'Saved',
      status: diagnostics.config_saved ? 'pass' : 'fail',
      detail: diagnostics.config_saved
        ? 'Core WhatsApp credentials are saved for this tenant.'
        : 'Phone number ID, verify token, access token, or app secret is missing.',
    },
    {
      label: 'Verified',
      status: diagnostics.webhook_verified_at ? 'pass' : 'pending',
      detail: diagnostics.webhook_verified_at
        ? `Webhook verified at ${formatDateTime(diagnostics.webhook_verified_at)}.`
        : 'Meta callback verification has not been completed yet.',
    },
    {
      label: 'Receiving webhooks',
      status: diagnostics.last_webhook_post_at ? 'pass' : diagnostics.signature_validation_ok === false ? 'fail' : 'pending',
      detail: diagnostics.last_webhook_post_at
        ? `Meta last posted at ${formatDateTime(diagnostics.last_webhook_post_at)}.`
        : diagnostics.signature_validation_ok === false
          ? 'Webhook POSTs are reaching EasyEcom, but signature validation is failing.'
          : 'No signed webhook POST has been observed yet.',
    },
    {
      label: 'Can send WhatsApp',
      status: diagnostics.outbound_send_ok === true ? 'pass' : diagnostics.outbound_send_ok === false ? 'fail' : 'pending',
      detail: diagnostics.outbound_send_ok === true
        ? 'WhatsApp outbound send passed.'
        : diagnostics.outbound_send_ok === false
          ? 'Outbound send failed. Review the last provider error below.'
          : 'Run diagnostics and a smoke send to confirm outbound delivery.',
    },
    {
      label: 'OpenAI ready',
      status: diagnostics.openai_probe_ok === true ? 'pass' : diagnostics.openai_ready ? 'pending' : 'fail',
      detail: diagnostics.openai_probe_ok === true
        ? 'OpenAI probe passed with the configured model.'
        : diagnostics.openai_ready
          ? 'Backend key is present, but the probe has not passed yet.'
          : 'The backend process does not currently expose OPENAI_API_KEY.',
    },
    {
      label: 'Auto-send enabled',
      status: autoSendEnabled ? 'pass' : 'pending',
      detail: autoSendEnabled
        ? 'Guarded auto-send is enabled for this tenant.'
        : 'Replies will be routed to review until auto-send is turned on.',
    },
  ];
}

function formatProviderDetails(details: Record<string, string | number | null>) {
  return Object.entries(details).filter(([, value]) => value !== null && `${value}`.trim() !== '');
}

export function IntegrationsWorkspace() {
  const { user } = useAuth();
  const isSuperAdmin = user?.roles?.includes('SUPER_ADMIN') ?? false;
  const { apiBaseUrl } = getPublicEnv();
  const [integrations, setIntegrations] = useState<ChannelIntegration[]>([]);
  const [locations, setLocations] = useState<ChannelLocation[]>([]);
  const [clients, setClients] = useState<AdminClient[]>([]);
  const [selectedClientId, setSelectedClientId] = useState('');
  const [draft, setDraft] = useState<WhatsAppMetaIntegrationPayload>(EMPTY_FORM);
  const [notice, setNotice] = useState('');
  const [error, setError] = useState('');
  const [latestVerifyToken, setLatestVerifyToken] = useState('');
  const [draftDiagnostics, setDraftDiagnostics] = useState<ChannelDiagnosticsEnvelope | null>(null);
  const [currentProviderDetails, setCurrentProviderDetails] = useState<Record<string, string | number | null>>({});
  const [smokeRecipient, setSmokeRecipient] = useState('');
  const [smokeText, setSmokeText] = useState('EasyEcom smoke test. Reply path is working.');
  const [isPending, startTransition] = useTransition();

  const applyCurrentChannel = (current: ChannelIntegration | undefined) => {
    if (!current) {
      setDraft(EMPTY_FORM);
      return;
    }
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
      verify_token: '',
      access_token: '',
      app_secret: '',
    }));
  };

  const loadWorkspace = (targetClientId = selectedClientId) => {
    startTransition(async () => {
      if (isSuperAdmin && !targetClientId) {
        setIntegrations([]);
        setLocations([]);
        setDraft(EMPTY_FORM);
        setError('');
        return;
      }
      try {
        const [integrationPayload, locationPayload] = await Promise.all([
          getChannelIntegrations(targetClientId || undefined),
          getChannelLocations(targetClientId || undefined),
        ]);
        setIntegrations(integrationPayload.items);
        setLocations(locationPayload.items);
        applyCurrentChannel(integrationPayload.items[0]);
        setDraftDiagnostics(null);
        setCurrentProviderDetails({});
        setNotice('');
        setError('');
      } catch (loadError) {
        setError(loadError instanceof Error ? loadError.message : 'Unable to load channel integrations.');
      }
    });
  };

  useEffect(() => {
    if (!isSuperAdmin) {
      loadWorkspace('');
      return;
    }
    startTransition(async () => {
      try {
        const adminClients = await listAdminClients();
        setClients(adminClients.items);
      } catch (loadError) {
        setError(loadError instanceof Error ? loadError.message : 'Unable to load tenants.');
      }
    });
  }, [isSuperAdmin]);

  useEffect(() => {
    if (isSuperAdmin) {
      loadWorkspace(selectedClientId);
    }
  }, [selectedClientId]);

  const onSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setNotice('');
    setError('');
    try {
      const response = await saveWhatsAppMetaIntegration({
        ...draft,
        default_location_id: draft.default_location_id || null,
      }, selectedClientId || undefined);
      setIntegrations([response.channel]);
      applyCurrentChannel(response.channel);
      if (response.setup_verify_token) {
        setLatestVerifyToken(response.setup_verify_token);
        setNotice(`Integration saved. Verify token: ${response.setup_verify_token}`);
      } else {
        setLatestVerifyToken('');
        setNotice('Integration saved.');
      }
      setDraft((existing) => ({ ...existing, verify_token: '', access_token: '', app_secret: '' }));
      setDraftDiagnostics(null);
      setCurrentProviderDetails({});
    } catch (submitError) {
      if (submitError instanceof ApiNetworkError) {
        setError(
          `The API did not return a usable response while saving. Re-login once, then retry. If it still fails, check the backend deploy, CORS/session settings, and that the Sales Agent migration is applied. (${submitError.message})`
        );
        return;
      }
      setError(submitError instanceof Error ? submitError.message : 'Unable to save the WhatsApp integration.');
    }
  };

  const onValidateDraft = async () => {
    setNotice('');
    setError('');
    try {
      const response = await validateWhatsAppMetaIntegration({
        ...draft,
        default_location_id: draft.default_location_id || null,
      }, selectedClientId || undefined);
      setDraftDiagnostics(response);
      setNotice(response.diagnostics.last_error_message ? response.diagnostics.last_error_message : 'Draft validation completed.');
    } catch (submitError) {
      setError(submitError instanceof Error ? submitError.message : 'Unable to validate the WhatsApp integration draft.');
    }
  };

  const onRunDiagnostics = async () => {
    if (!current) {
      return;
    }
    setNotice('');
    setError('');
    try {
      const response = await runChannelDiagnostics(current.channel_id);
      setIntegrations([response.channel]);
      setCurrentProviderDetails(response.provider_details);
      setNotice(response.diagnostics.last_error_message ? response.diagnostics.last_error_message : 'Channel diagnostics completed.');
    } catch (submitError) {
      setError(submitError instanceof Error ? submitError.message : 'Unable to run channel diagnostics.');
    }
  };

  const onSendSmoke = async () => {
    if (!current) {
      return;
    }
    setNotice('');
    setError('');
    try {
      const response = await sendChannelSmoke(current.channel_id, { recipient: smokeRecipient, text: smokeText });
      setIntegrations((items) =>
        items.map((item) => (item.channel_id === current.channel_id ? mergeChannelDiagnostics(item, response.diagnostics) : item)),
      );
      setCurrentProviderDetails(response.provider_details);
      setNotice(response.message);
    } catch (submitError) {
      setError(submitError instanceof Error ? submitError.message : 'Unable to send a WhatsApp smoke message.');
    }
  };

  const current = integrations[0] ?? null;
  const selectedClient = clients.find((item) => item.client_id === selectedClientId) ?? null;
  const tenantSelectionRequired = isSuperAdmin && !selectedClientId;
  const webhookUrl = current?.webhook_key ? `${apiBaseUrl}/public/webhooks/whatsapp/${current.webhook_key}` : '';
  const currentDiagnostics = current ? diagnosticsFromChannel(current) : null;
  const currentSteps = currentDiagnostics ? buildDiagnosticSteps(currentDiagnostics, current.auto_send_enabled) : [];
  const draftSteps = draftDiagnostics ? buildDiagnosticSteps(draftDiagnostics.diagnostics, draft.auto_send_enabled) : [];

  return (
    <div className="workspace-stack sales-agent-stack">
      {notice ? <WorkspaceNotice tone="success">{notice}</WorkspaceNotice> : null}
      {error ? <WorkspaceNotice tone="error">{error}</WorkspaceNotice> : null}

      {isSuperAdmin ? (
        <WorkspacePanel
          title="Tenant target"
          description="Super admin can configure one tenant channel at a time. Select the tenant first, then save the WhatsApp credentials for that business."
        >
          <div className="sales-agent-form-grid">
            <label className="sales-agent-form-wide">
              <span>Tenant</span>
              <select value={selectedClientId} onChange={(event) => setSelectedClientId(event.target.value)}>
                <option value="">Select a tenant</option>
                {clients.map((client) => (
                  <option key={client.client_id} value={client.client_id}>
                    {client.business_name} ({client.client_code})
                  </option>
                ))}
              </select>
            </label>
          </div>
          {selectedClient ? (
            <p className="workspace-field-note">
              Editing the live channel settings for <strong>{selectedClient.business_name}</strong>.
            </p>
          ) : null}
        </WorkspacePanel>
      ) : null}

      <WorkspacePanel
        title="WhatsApp Meta channel"
        description="Store tenant channel details, webhook verification, and sales-agent behavior in one place."
        hint="This config enables inbound persistence, guarded reply generation, and draft-order creation for the tenant."
      >
        {tenantSelectionRequired ? (
          <div className="workspace-empty">
            <h4>Select a tenant first</h4>
            <p>Once a tenant is selected above, this form will load that business account’s WhatsApp channel details.</p>
          </div>
        ) : null}
        <form className="sales-agent-form" onSubmit={onSubmit} aria-disabled={tenantSelectionRequired}>
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
                placeholder={current?.verify_token_set ? 'Leave blank to keep the saved token' : 'Leave blank to auto-generate'}
              />
              <small className="workspace-field-note">
                Leave blank to preserve the existing saved token. If this is a new channel and you leave it blank,
                EasyEcom generates one during save and shows it after the save succeeds.
              </small>
            </label>
            <label>
              <span>OpenAI model</span>
              <input
                value={draft.model_name}
                onChange={(event) => setDraft({ ...draft, model_name: event.target.value })}
                placeholder="gpt-5-mini"
              />
              <small className="workspace-field-note">
                The OpenAI API key is configured on the backend with <code>OPENAI_API_KEY</code>. This form only selects
                the tenant model and persona.
              </small>
            </label>
            <label>
              <span>Access token</span>
              <input
                type="password"
                value={draft.access_token}
                onChange={(event) => setDraft({ ...draft, access_token: event.target.value })}
                placeholder={current?.access_token_set ? 'Saved. Enter a new value to rotate.' : 'Meta permanent access token'}
              />
              <small className="workspace-field-note">Leave blank to keep the currently saved access token.</small>
            </label>
            <label>
              <span>App secret</span>
              <input
                type="password"
                value={draft.app_secret}
                onChange={(event) => setDraft({ ...draft, app_secret: event.target.value })}
                placeholder={current?.inbound_secret_set ? 'Saved. Enter a new value to rotate.' : 'Webhook app secret'}
              />
              <small className="workspace-field-note">Leave blank to keep the currently saved app secret.</small>
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
            <button
              type="button"
              onClick={onValidateDraft}
              disabled={tenantSelectionRequired || isPending || !draft.phone_number_id.trim()}
            >
              Validate details
            </button>
            <button type="submit" disabled={tenantSelectionRequired || isPending || !draft.phone_number_id.trim()}>
              Save integration
            </button>
          </div>
        </form>

        {draftDiagnostics ? (
          <div className="workspace-stack">
            <div className="integration-step-grid">
              {draftSteps.map((step) => (
                <article key={step.label} className={stepClassName(step.status)}>
                  <span>{step.label}</span>
                  <strong>{step.status === 'pass' ? 'Pass' : step.status === 'fail' ? 'Fail' : 'Pending'}</strong>
                  <p>{step.detail}</p>
                </article>
              ))}
            </div>
            <div className="integration-detail-card">
              <div className="integration-detail-head">
                <strong>Draft validation</strong>
                <span>{draftDiagnostics.diagnostics.last_diagnostic_at ? formatDateTime(draftDiagnostics.diagnostics.last_diagnostic_at) : 'Just now'}</span>
              </div>
              <p>{draftDiagnostics.diagnostics.next_action}</p>
              {draftDiagnostics.diagnostics.last_error_message ? (
                <p className="integration-detail-error">
                  {draftDiagnostics.diagnostics.last_error_code ? `${draftDiagnostics.diagnostics.last_error_code}: ` : ''}
                  {draftDiagnostics.diagnostics.last_error_message}
                </p>
              ) : null}
              {formatProviderDetails(draftDiagnostics.provider_details).length ? (
                <dl className="integration-detail-grid">
                  {formatProviderDetails(draftDiagnostics.provider_details).map(([key, value]) => (
                    <div key={key}>
                      <dt>{key.replace(/_/g, ' ')}</dt>
                      <dd>{String(value)}</dd>
                    </div>
                  ))}
                </dl>
              ) : null}
            </div>
          </div>
        ) : null}
      </WorkspacePanel>

      <WorkspacePanel
        title="Current channel"
        description="Non-secret channel state is shown here so operators can verify the tenant is connected correctly."
      >
        {tenantSelectionRequired ? (
          <div className="workspace-empty">
            <h4>No tenant selected</h4>
            <p>Choose a tenant above to inspect its current channel status and secrets readiness.</p>
          </div>
        ) : current ? (
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

        {current ? (
          <div className="workspace-stack">
            <div className="sales-agent-form-grid">
              <label className="sales-agent-form-wide">
                <span>Webhook callback URL</span>
                <input value={webhookUrl} readOnly />
                <small className="workspace-field-note">
                  Use this exact callback URL in Meta webhook configuration for the WhatsApp app.
                </small>
              </label>
              <label>
                <span>Webhook key</span>
                <input value={current.webhook_key ?? ''} readOnly />
              </label>
              <label>
                <span>Latest generated verify token</span>
                <input
                  value={latestVerifyToken}
                  readOnly
                  placeholder="Use a manual token before saving if you want a stable value here"
                />
                <small className="workspace-field-note">
                  This is only available when EasyEcom auto-generated the token in this browser session. Meta's verify
                  token field cannot be blank.
                </small>
              </label>
            </div>

            <div className="integration-step-grid">
              {currentSteps.map((step) => (
                <article key={step.label} className={stepClassName(step.status)}>
                  <span>{step.label}</span>
                  <strong>{step.status === 'pass' ? 'Pass' : step.status === 'fail' ? 'Fail' : 'Pending'}</strong>
                  <p>{step.detail}</p>
                </article>
              ))}
            </div>

            <div className="integration-detail-card">
              <div className="integration-detail-head">
                <strong>Next action</strong>
                <span>{current.last_diagnostic_at ? formatDateTime(current.last_diagnostic_at) : 'Not run yet'}</span>
              </div>
              <p>{current.next_action}</p>
              {current.last_error_message ? (
                <p className="integration-detail-error">
                  {current.last_error_code ? `${current.last_error_code}: ` : ''}
                  {current.last_error_message}
                </p>
              ) : null}
              {current.last_provider_status_code || current.last_provider_response_excerpt ? (
                <dl className="integration-detail-grid">
                  {current.last_provider_status_code ? (
                    <div>
                      <dt>Provider status</dt>
                      <dd>{current.last_provider_status_code}</dd>
                    </div>
                  ) : null}
                  {current.last_provider_response_excerpt ? (
                    <div className="integration-detail-grid-wide">
                      <dt>Provider response</dt>
                      <dd>{current.last_provider_response_excerpt}</dd>
                    </div>
                  ) : null}
                </dl>
              ) : null}
            </div>

            {formatProviderDetails(currentProviderDetails).length ? (
              <div className="integration-detail-card">
                <div className="integration-detail-head">
                  <strong>Provider diagnostics</strong>
                  <span>Latest run</span>
                </div>
                <dl className="integration-detail-grid">
                  {formatProviderDetails(currentProviderDetails).map(([key, value]) => (
                    <div key={key}>
                      <dt>{key.replace(/_/g, ' ')}</dt>
                      <dd>{String(value)}</dd>
                    </div>
                  ))}
                </dl>
              </div>
            ) : null}

            <div className="sales-agent-form-actions integration-actions">
              <button type="button" onClick={onRunDiagnostics} disabled={isPending}>
                Run diagnostics
              </button>
            </div>

            <div className="integration-detail-card">
              <div className="integration-detail-head">
                <strong>Smoke send</strong>
                <span>Operator-triggered only</span>
              </div>
              <p>
                Send a single WhatsApp test message to an approved recipient before enabling live tenant traffic. Use a
                human test number here, not the business test number itself.
              </p>
              <div className="sales-agent-form-grid">
                <label>
                  <span>Approved recipient</span>
                  <input
                    value={smokeRecipient}
                    onChange={(event) => setSmokeRecipient(event.target.value)}
                    placeholder="+971..."
                  />
                </label>
                <label className="sales-agent-form-wide">
                  <span>Smoke message</span>
                  <textarea rows={3} value={smokeText} onChange={(event) => setSmokeText(event.target.value)} />
                </label>
              </div>
              <div className="sales-agent-form-actions integration-actions">
                <button type="button" onClick={onSendSmoke} disabled={isPending || !smokeRecipient.trim()}>
                  Send smoke message
                </button>
              </div>
            </div>

            <WorkspaceNotice tone="info">
              Backend and frontend deploy separately. If diagnostics change on the API but this screen still looks old,
              confirm the backend deploy first, then wait for the Amplify frontend deploy to finish.
            </WorkspaceNotice>
          </div>
        ) : (
          null
        )}
      </WorkspacePanel>
    </div>
  );
}
