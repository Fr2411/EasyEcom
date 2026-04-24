'use client';

import { FormEvent, useEffect, useMemo, useState } from 'react';
import { Bot, MessageSquareText, ShieldAlert } from 'lucide-react';
import { WorkspaceEmpty, WorkspaceNotice, WorkspacePanel } from '@/components/commerce/workspace-primitives';
import {
  createCustomerChannel,
  escalateCustomerConversation,
  getCustomerCommunicationWorkspace,
  updateAssistantPlaybook,
} from '@/lib/api/customer-communication';
import type {
  ChannelUpsertPayload,
  CustomerCommunicationWorkspace as CustomerCommunicationWorkspacePayload,
  CustomerConversationSummary,
  PlaybookUpdatePayload,
} from '@/types/customer-communication';

const BUSINESS_TYPES = [
  { value: 'general_retail', label: 'General retail' },
  { value: 'pet_food', label: 'Pet food' },
  { value: 'fashion', label: 'Fashion' },
  { value: 'shoe_store', label: 'Shoe store' },
  { value: 'electronics', label: 'Electronics' },
  { value: 'cosmetics', label: 'Cosmetics' },
  { value: 'grocery', label: 'Grocery' },
];

const PERSONALITIES = ['friendly', 'expert', 'premium', 'casual', 'concise'];
const CHANNELS = ['website', 'whatsapp', 'instagram', 'facebook', 'messenger', 'other'];

type PlaybookForm = {
  business_type: string;
  brand_personality: string;
  custom_instructions: string;
  forbidden_claims: string;
  delivery_policy: string;
  returns_policy: string;
  payment_policy: string;
  warranty_policy: string;
  discount_policy: string;
  upsell: boolean;
  cross_sell: boolean;
  promote_slow_stock: boolean;
  protect_premium_positioning: boolean;
  angry_customer: boolean;
  medical_or_health: boolean;
  legal_or_safety: boolean;
  refund_dispute: boolean;
  high_value_order: boolean;
  unavailable_product: boolean;
};

function buildPlaybookForm(workspace: CustomerCommunicationWorkspacePayload): PlaybookForm {
  const policies = workspace.playbook.policies;
  const goals = workspace.playbook.sales_goals;
  const escalation = workspace.playbook.escalation_rules;
  return {
    business_type: workspace.playbook.business_type,
    brand_personality: workspace.playbook.brand_personality,
    custom_instructions: workspace.playbook.custom_instructions,
    forbidden_claims: workspace.playbook.forbidden_claims,
    delivery_policy: String(policies.delivery ?? ''),
    returns_policy: String(policies.returns ?? ''),
    payment_policy: String(policies.payment ?? ''),
    warranty_policy: String(policies.warranty ?? ''),
    discount_policy: String(policies.discounts ?? ''),
    upsell: Boolean(goals.upsell),
    cross_sell: Boolean(goals.cross_sell),
    promote_slow_stock: Boolean(goals.promote_slow_stock),
    protect_premium_positioning: Boolean(goals.protect_premium_positioning),
    angry_customer: escalation.angry_customer !== false,
    medical_or_health: escalation.medical_or_health !== false,
    legal_or_safety: escalation.legal_or_safety !== false,
    refund_dispute: escalation.refund_dispute !== false,
    high_value_order: escalation.high_value_order !== false,
    unavailable_product: escalation.unavailable_product !== false,
  };
}

function playbookPayload(form: PlaybookForm): PlaybookUpdatePayload {
  return {
    business_type: form.business_type,
    brand_personality: form.brand_personality,
    custom_instructions: form.custom_instructions,
    forbidden_claims: form.forbidden_claims,
    policies: {
      delivery: form.delivery_policy,
      returns: form.returns_policy,
      payment: form.payment_policy,
      warranty: form.warranty_policy,
      discounts: form.discount_policy,
    },
    sales_goals: {
      upsell: form.upsell,
      cross_sell: form.cross_sell,
      promote_slow_stock: form.promote_slow_stock,
      protect_premium_positioning: form.protect_premium_positioning,
    },
    escalation_rules: {
      angry_customer: form.angry_customer,
      medical_or_health: form.medical_or_health,
      legal_or_safety: form.legal_or_safety,
      refund_dispute: form.refund_dispute,
      high_value_order: form.high_value_order,
      unavailable_product: form.unavailable_product,
    },
  };
}

function initialChannelForm(): ChannelUpsertPayload {
  return {
    provider: 'website',
    display_name: 'Website chat',
    status: 'active',
    external_account_id: '',
    default_location_id: null,
    auto_send_enabled: true,
    config: {},
  };
}

function formatDateTime(value?: string | null) {
  if (!value) return 'No activity';
  return new Intl.DateTimeFormat(undefined, {
    dateStyle: 'medium',
    timeStyle: 'short',
  }).format(new Date(value));
}

export function CustomerCommunicationWorkspace() {
  const [workspace, setWorkspace] = useState<CustomerCommunicationWorkspacePayload | null>(null);
  const [playbookForm, setPlaybookForm] = useState<PlaybookForm | null>(null);
  const [channelForm, setChannelForm] = useState<ChannelUpsertPayload>(initialChannelForm);
  const [activeConversationId, setActiveConversationId] = useState<string | undefined>();
  const [loading, setLoading] = useState(true);
  const [savingPlaybook, setSavingPlaybook] = useState(false);
  const [savingChannel, setSavingChannel] = useState(false);
  const [notice, setNotice] = useState('');
  const [error, setError] = useState('');

  const activeConversation = workspace?.active_conversation ?? null;
  const playbookQuestions = workspace?.playbook.industry_template.questions ?? [];
  const playbookSafety = workspace?.playbook.industry_template.safety ?? [];

  const escalatedConversations = useMemo(
    () => workspace?.conversations.filter((conversation) => conversation.status === 'escalated').length ?? 0,
    [workspace],
  );

  async function loadWorkspace(conversationId?: string) {
    setLoading(true);
    try {
      const payload = await getCustomerCommunicationWorkspace(conversationId);
      setWorkspace(payload);
      setPlaybookForm(buildPlaybookForm(payload));
      setActiveConversationId(payload.active_conversation?.conversation_id);
      setError('');
    } catch (loadError) {
      setError(loadError instanceof Error ? loadError.message : 'Unable to load customer communication.');
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void loadWorkspace();
  }, []);

  async function savePlaybook(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!playbookForm) return;
    setSavingPlaybook(true);
    try {
      const playbook = await updateAssistantPlaybook(playbookPayload(playbookForm));
      const nextWorkspace = workspace ? { ...workspace, playbook } : null;
      setWorkspace(nextWorkspace);
      if (nextWorkspace) setPlaybookForm(buildPlaybookForm(nextWorkspace));
      setNotice('Assistant playbook saved.');
      setError('');
    } catch (saveError) {
      setError(saveError instanceof Error ? saveError.message : 'Unable to save assistant playbook.');
    } finally {
      setSavingPlaybook(false);
    }
  }

  async function createChannel(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSavingChannel(true);
    try {
      await createCustomerChannel(channelForm);
      setChannelForm(initialChannelForm());
      await loadWorkspace(activeConversationId);
      setNotice('Channel saved.');
    } catch (saveError) {
      setError(saveError instanceof Error ? saveError.message : 'Unable to save channel.');
    } finally {
      setSavingChannel(false);
    }
  }

  async function openConversation(conversation: CustomerConversationSummary) {
    setActiveConversationId(conversation.conversation_id);
    await loadWorkspace(conversation.conversation_id);
  }

  async function escalateActiveConversation() {
    if (!activeConversation) return;
    try {
      await escalateCustomerConversation(activeConversation.conversation_id, 'Manual tenant escalation');
      await loadWorkspace(activeConversation.conversation_id);
      setNotice('Conversation escalated.');
    } catch (escalationError) {
      setError(escalationError instanceof Error ? escalationError.message : 'Unable to escalate conversation.');
    }
  }

  if (loading && !workspace) {
    return <div className="reports-loading">Loading customer communication…</div>;
  }

  if (error && !workspace) {
    return <div className="reports-error">{error}</div>;
  }

  if (!workspace || !playbookForm) {
    return <WorkspaceEmpty title="Customer communication unavailable" message="No assistant workspace was returned." />;
  }

  return (
    <div className="operations-page customer-communication-module">
      {notice ? <WorkspaceNotice tone="success">{notice}</WorkspaceNotice> : null}
      {error ? <WorkspaceNotice tone="error">{error}</WorkspaceNotice> : null}

      <div className="reports-grid customer-communication-metrics">
        <article className="ps-card">
          <p>Channels</p>
          <strong>{workspace.channels.length}</strong>
        </article>
        <article className="ps-card">
          <p>Conversations</p>
          <strong>{workspace.conversations.length}</strong>
        </article>
        <article className="ps-card">
          <p>Escalations</p>
          <strong>{escalatedConversations}</strong>
        </article>
      </div>

      <div className="customer-communication-grid">
        <form className="operations-form-stack" onSubmit={savePlaybook}>
          <WorkspacePanel
            title="Assistant Playbook"
            description="Tenant-specific business context, personality, policies, and risk rules."
            actions={<button type="submit" className="btn-primary" disabled={savingPlaybook}>{savingPlaybook ? 'Saving…' : 'Save Playbook'}</button>}
          >
            <div className="operations-form-grid compact">
              <label>
                Business type
                <select
                  value={playbookForm.business_type}
                  onChange={(event) => setPlaybookForm({ ...playbookForm, business_type: event.target.value })}
                >
                  {BUSINESS_TYPES.map((item) => (
                    <option key={item.value} value={item.value}>{item.label}</option>
                  ))}
                </select>
              </label>
              <label>
                Personality
                <select
                  value={playbookForm.brand_personality}
                  onChange={(event) => setPlaybookForm({ ...playbookForm, brand_personality: event.target.value })}
                >
                  {PERSONALITIES.map((item) => (
                    <option key={item} value={item}>{item}</option>
                  ))}
                </select>
              </label>
              <label className="field-span-2">
                Custom instructions
                <textarea
                  rows={4}
                  value={playbookForm.custom_instructions}
                  onChange={(event) => setPlaybookForm({ ...playbookForm, custom_instructions: event.target.value })}
                />
              </label>
              <label className="field-span-2">
                Forbidden claims
                <textarea
                  rows={3}
                  value={playbookForm.forbidden_claims}
                  onChange={(event) => setPlaybookForm({ ...playbookForm, forbidden_claims: event.target.value })}
                />
              </label>
            </div>

            <div className="assistant-template-strip">
              <div>
                <strong>Ask for</strong>
                <span>{playbookQuestions.length ? playbookQuestions.join(', ') : 'Tenant context first'}</span>
              </div>
              <div>
                <strong>Safety</strong>
                <span>{playbookSafety.length ? playbookSafety.join(' ') : 'Escalate uncertain answers.'}</span>
              </div>
            </div>
          </WorkspacePanel>

          <WorkspacePanel title="Policies" description="Facts the assistant can use when customers ask operational questions.">
            <div className="operations-form-grid compact">
              <label>
                Delivery
                <textarea rows={2} value={playbookForm.delivery_policy} onChange={(event) => setPlaybookForm({ ...playbookForm, delivery_policy: event.target.value })} />
              </label>
              <label>
                Returns
                <textarea rows={2} value={playbookForm.returns_policy} onChange={(event) => setPlaybookForm({ ...playbookForm, returns_policy: event.target.value })} />
              </label>
              <label>
                Payment
                <textarea rows={2} value={playbookForm.payment_policy} onChange={(event) => setPlaybookForm({ ...playbookForm, payment_policy: event.target.value })} />
              </label>
              <label>
                Discounts
                <textarea rows={2} value={playbookForm.discount_policy} onChange={(event) => setPlaybookForm({ ...playbookForm, discount_policy: event.target.value })} />
              </label>
            </div>
          </WorkspacePanel>

          <WorkspacePanel title="Sales And Escalation" description="Commercial priorities and hard handoff triggers.">
            <div className="operations-toggle-grid">
              {[
                ['upsell', 'Upsell'],
                ['cross_sell', 'Cross-sell'],
                ['promote_slow_stock', 'Promote slow stock'],
                ['protect_premium_positioning', 'Protect premium'],
              ].map(([key, label]) => (
                <label className="operations-toggle-card" key={key}>
                  <input
                    type="checkbox"
                    checked={Boolean(playbookForm[key as keyof PlaybookForm])}
                    onChange={(event) => setPlaybookForm({ ...playbookForm, [key]: event.target.checked })}
                  />
                  <div><strong>{label}</strong></div>
                </label>
              ))}
            </div>
            <div className="operations-toggle-grid">
              {[
                ['angry_customer', 'Angry customer'],
                ['medical_or_health', 'Medical or health'],
                ['legal_or_safety', 'Legal or safety'],
                ['refund_dispute', 'Refund dispute'],
                ['high_value_order', 'High-value order'],
                ['unavailable_product', 'Unavailable product'],
              ].map(([key, label]) => (
                <label className="operations-toggle-card" key={key}>
                  <input
                    type="checkbox"
                    checked={Boolean(playbookForm[key as keyof PlaybookForm])}
                    onChange={(event) => setPlaybookForm({ ...playbookForm, [key]: event.target.checked })}
                  />
                  <div><strong>{label}</strong></div>
                </label>
              ))}
            </div>
          </WorkspacePanel>
        </form>

        <div className="operations-form-stack">
          <WorkspacePanel title="Channels" description="Shared entry points for website, WhatsApp, Instagram, Facebook, and future adapters.">
            <form className="operations-form-grid compact" onSubmit={createChannel}>
              <label>
                Provider
                <select value={channelForm.provider} onChange={(event) => setChannelForm({ ...channelForm, provider: event.target.value })}>
                  {CHANNELS.map((provider) => <option key={provider} value={provider}>{provider}</option>)}
                </select>
              </label>
              <label>
                Name
                <input value={channelForm.display_name} onChange={(event) => setChannelForm({ ...channelForm, display_name: event.target.value })} />
              </label>
              <label>
                Account ID
                <input value={channelForm.external_account_id} onChange={(event) => setChannelForm({ ...channelForm, external_account_id: event.target.value })} />
              </label>
              <label className="operations-toggle-card">
                <input type="checkbox" checked={channelForm.auto_send_enabled} onChange={(event) => setChannelForm({ ...channelForm, auto_send_enabled: event.target.checked })} />
                <div><strong>Auto-send</strong></div>
              </label>
              <div className="field-span-2 operations-toolbar-actions">
                <button type="submit" className="btn-primary" disabled={savingChannel}>{savingChannel ? 'Saving…' : 'Add Channel'}</button>
              </div>
            </form>

            {workspace.channels.length ? (
              <ul className="assistant-channel-list">
                {workspace.channels.map((channel) => (
                  <li key={channel.channel_id}>
                    <div>
                      <strong>{channel.display_name}</strong>
                      <span>{channel.provider} • {channel.status} • {channel.auto_send_enabled ? 'Auto-send' : 'Manual'}</span>
                    </div>
                    <code>{channel.webhook_key}</code>
                  </li>
                ))}
              </ul>
            ) : (
              <WorkspaceEmpty title="No channels" message="Add a channel before receiving customer messages." />
            )}
          </WorkspacePanel>

          <WorkspacePanel title="Inbox" description="Recent customer conversations and AI handoffs.">
            {workspace.conversations.length ? (
              <div className="assistant-inbox">
                {workspace.conversations.map((conversation) => (
                  <button
                    key={conversation.conversation_id}
                    type="button"
                    className={conversation.conversation_id === activeConversationId ? 'assistant-inbox-row active' : 'assistant-inbox-row'}
                    onClick={() => void openConversation(conversation)}
                  >
                    <span>
                      <MessageSquareText size={15} aria-hidden="true" />
                      <strong>{conversation.external_sender_name || conversation.external_sender_id}</strong>
                    </span>
                    <small>{conversation.channel_provider} • {formatDateTime(conversation.last_message_at)}</small>
                    <em>{conversation.last_message_preview || 'No message preview'}</em>
                    {conversation.status === 'escalated' ? <b>Escalated</b> : null}
                  </button>
                ))}
              </div>
            ) : (
              <WorkspaceEmpty title="No conversations" message="Customer conversations will appear after a channel receives messages." />
            )}
          </WorkspacePanel>
        </div>
      </div>

      <WorkspacePanel
        title="Conversation"
        description="Grounded transcript, assistant runs, and tool calls."
        actions={activeConversation ? <button type="button" className="secondary" onClick={() => void escalateActiveConversation()}>Escalate</button> : null}
      >
        {activeConversation ? (
          <div className="assistant-conversation-layout">
            <div className="assistant-transcript">
              {activeConversation.messages.map((message) => (
                <article key={message.message_id} className={`assistant-message ${message.sender_role}`}>
                  <span>{message.sender_role}</span>
                  <p>{message.message_text}</p>
                  <small>{formatDateTime(message.occurred_at)}</small>
                </article>
              ))}
            </div>
            <aside className="assistant-run-panel">
              <div className="assistant-status-block">
                <Bot size={18} aria-hidden="true" />
                <div>
                  <strong>{activeConversation.status}</strong>
                  <span>{activeConversation.draft_order_id ? `Draft order ${activeConversation.draft_order_id}` : 'No draft order linked'}</span>
                </div>
              </div>
              {activeConversation.escalation_reason ? (
                <div className="assistant-status-block warning">
                  <ShieldAlert size={18} aria-hidden="true" />
                  <div>
                    <strong>Escalation</strong>
                    <span>{activeConversation.escalation_reason}</span>
                  </div>
                </div>
              ) : null}
              {activeConversation.runs.map((run) => (
                <details key={run.run_id} className="operations-advanced-block" open={run.escalation_required}>
                  <summary>{run.model_provider} • {run.validation_status}</summary>
                  <div className="assistant-run-detail">
                    <p>{run.response_text}</p>
                    {run.tool_calls.length ? (
                      <ul>
                        {run.tool_calls.map((tool) => (
                          <li key={tool.tool_call_id}>
                            <strong>{tool.tool_name}</strong>
                            <code>{JSON.stringify(tool.tool_result).slice(0, 240)}</code>
                          </li>
                        ))}
                      </ul>
                    ) : (
                      <span className="muted">No tool calls recorded.</span>
                    )}
                  </div>
                </details>
              ))}
            </aside>
          </div>
        ) : (
          <WorkspaceEmpty title="No active conversation" message="Select a conversation to review the transcript." />
        )}
      </WorkspacePanel>
    </div>
  );
}
