'use client';

import { Copy, RefreshCw } from 'lucide-react';
import { useCallback, useEffect, useMemo, useState } from 'react';
import Link from 'next/link';
import { WorkspaceEmpty, WorkspaceNotice, WorkspacePanel } from '@/components/commerce/workspace-primitives';
import { getAIAgentSettings, listAIConversations } from '@/lib/api/ai';
import { formatDateTime } from '@/lib/commerce-format';
import type { AIAgentSettings, AIConversationSummary } from '@/types/ai';

function widgetScriptUrl(script: string) {
  return script.match(/src="([^"]+)"/)?.[1] ?? '';
}

function customerLabel(conversation: AIConversationSummary) {
  return (
    conversation.customer_name.trim()
    || conversation.customer_phone.trim()
    || conversation.customer_email.trim()
    || 'Website visitor'
  );
}

function statusLabel(status: string) {
  const normalized = status.trim().toLowerCase();
  if (normalized === 'handoff') return 'Handoff';
  if (normalized === 'closed') return 'Closed';
  return 'Open';
}

function statusClassName(status: string) {
  return status.trim().toLowerCase() === 'open' ? 'status-pill status-pill-active' : 'status-pill';
}

export function AIAssistantWorkspace() {
  const [settings, setSettings] = useState<AIAgentSettings | null>(null);
  const [conversations, setConversations] = useState<AIConversationSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [copied, setCopied] = useState(false);
  const [copiedLink, setCopiedLink] = useState(false);

  const loadWorkspace = useCallback(async () => {
    setLoading(true);
    try {
      const [settingsPayload, conversationsPayload] = await Promise.all([
        getAIAgentSettings(),
        listAIConversations(30),
      ]);
      setSettings(settingsPayload);
      setConversations(conversationsPayload.items);
      setError('');
    } catch (loadError) {
      setError(loadError instanceof Error ? loadError.message : 'Unable to load AI assistant workspace.');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void loadWorkspace();
  }, [loadWorkspace]);

  const metrics = useMemo(() => {
    return conversations.reduce(
      (summary, conversation) => {
        const status = conversation.status.trim().toLowerCase();
        return {
          open: summary.open + (status === 'open' ? 1 : 0),
          handoff: summary.handoff + (status === 'handoff' ? 1 : 0),
          closed: summary.closed + (status === 'closed' ? 1 : 0),
        };
      },
      { open: 0, handoff: 0, closed: 0 },
    );
  }, [conversations]);

  const scriptUrl = settings ? widgetScriptUrl(settings.widget_script) : '';
  const channelReady = Boolean(settings?.is_enabled && settings.channel_status === 'active' && settings.model_configured);
  const channelStatusLabel = settings?.is_enabled && settings.channel_status === 'active'
    ? (settings.model_configured ? 'Ready' : 'Missing model key')
    : 'Disabled';

  const copyScript = async () => {
    if (!settings?.widget_script || typeof navigator === 'undefined' || !navigator.clipboard) {
      return;
    }
    try {
      await navigator.clipboard.writeText(settings.widget_script);
      setCopied(true);
      window.setTimeout(() => setCopied(false), 1800);
    } catch {
      setError('Unable to copy the website chat embed script from this browser.');
    }
  };

  const copyChatLink = async () => {
    if (!settings?.chat_link || typeof navigator === 'undefined' || !navigator.clipboard) {
      return;
    }
    try {
      await navigator.clipboard.writeText(settings.chat_link);
      setCopiedLink(true);
      window.setTimeout(() => setCopiedLink(false), 1800);
    } catch {
      setError('Unable to copy the customer chat link from this browser.');
    }
  };

  return (
    <div className="operations-page ai-assistant-module">
      <div className="operations-toolbar">
        <div>
          <p className="operations-eyebrow">Customer chat</p>
          <h2>AI Assistant</h2>
        </div>
        <div className="operations-toolbar-actions">
          <button type="button" className="secondary" onClick={() => void loadWorkspace()} disabled={loading}>
            <RefreshCw size={16} aria-hidden="true" />
            {loading ? 'Refreshing' : 'Refresh'}
          </button>
          <Link href="/settings" className="button-link secondary">Settings</Link>
        </div>
      </div>

      {error ? <WorkspaceNotice tone="error">{error}</WorkspaceNotice> : null}

      <div className="operations-kpi-grid">
        <article className="operations-kpi-card">
          <span>Latest conversations</span>
          <strong>{conversations.length}</strong>
        </article>
        <article className="operations-kpi-card">
          <span>Open</span>
          <strong>{metrics.open}</strong>
        </article>
        <article className="operations-kpi-card">
          <span>Needs handoff</span>
          <strong>{metrics.handoff}</strong>
        </article>
        <article className="operations-kpi-card">
          <span>Closed</span>
          <strong>{metrics.closed}</strong>
        </article>
      </div>

      <WorkspacePanel title="Website chat" description="Tenant website chat channel details.">
        {settings ? (
          <div className="operations-detail-stack">
            <dl className="operations-definition-grid">
              <div>
                <dt>Assistant</dt>
                <dd>{settings.display_name}</dd>
              </div>
              <div>
                <dt>Status</dt>
                <dd>
                  <span className={channelReady ? 'status-pill status-pill-active' : 'status-pill'}>
                    {channelStatusLabel}
                  </span>
                </dd>
              </div>
              <div>
                <dt>Runtime</dt>
                <dd>EasyEcom backend</dd>
              </div>
              <div>
                <dt>Model</dt>
                <dd>{settings.model_name}</dd>
              </div>
              <div>
                <dt>Widget key</dt>
                <dd className="ai-assistant-code-text">{settings.widget_key}</dd>
              </div>
              <div>
                <dt>Customer chat link</dt>
                <dd className="ai-assistant-code-text">{settings.chat_link}</dd>
              </div>
            </dl>
            <div className="ai-assistant-link-row">
              <input aria-label="Customer chat link" readOnly value={settings.chat_link} />
              <a className="button-link secondary" href={settings.chat_link} target="_blank" rel="noreferrer">
                Open link
              </a>
              <button type="button" className="secondary" onClick={copyChatLink} disabled={!settings.chat_link}>
                <Copy size={16} aria-hidden="true" />
                {copiedLink ? 'Copied' : 'Copy link'}
              </button>
            </div>
            <dl className="operations-definition-grid compact">
              <div>
                <dt>Widget script URL</dt>
                <dd className="ai-assistant-code-text">{scriptUrl || 'Not available'}</dd>
              </div>
            </dl>
            <div className="ai-assistant-script-row">
              <textarea
                aria-label="Website chat embed script"
                rows={3}
                readOnly
                value={settings.widget_script}
              />
              <button type="button" className="secondary" onClick={copyScript} disabled={!settings.widget_script}>
                <Copy size={16} aria-hidden="true" />
                {copied ? 'Copied' : 'Copy embed'}
              </button>
            </div>
          </div>
        ) : loading ? (
          <div className="reports-loading">Loading website chat link...</div>
        ) : (
          <WorkspaceEmpty title="Website chat is unavailable" message="AI assistant settings were not returned for this tenant." />
        )}
      </WorkspacePanel>

      <WorkspacePanel title="Latest customer conversations" description="Recent website chat sessions for this tenant.">
        {loading ? <div className="reports-loading">Loading conversations...</div> : null}
        {!loading && !conversations.length ? (
          <WorkspaceEmpty
            title="No customer conversations yet"
            message="Website chat conversations will appear after customers send messages through the tenant widget."
          />
        ) : null}
        {!loading && conversations.length ? (
          <div className="operations-list-stack">
            {conversations.map((conversation) => (
              <article key={conversation.conversation_id} className="operations-list-card static ai-assistant-conversation-card">
                <div className="operations-list-card-head">
                  <strong>{customerLabel(conversation)}</strong>
                  <span className={statusClassName(conversation.status)}>{statusLabel(conversation.status)}</span>
                </div>
                <p>{conversation.last_message_preview || conversation.latest_summary || 'No message preview saved'}</p>
                <div className="operations-inline-meta compact">
                  <span>{formatDateTime(conversation.last_message_at)}</span>
                  <span>{conversation.message_count} messages</span>
                  <span>{conversation.channel_display_name}</span>
                  {conversation.latest_intent ? <span>{conversation.latest_intent}</span> : null}
                </div>
                {conversation.customer_phone || conversation.customer_email ? (
                  <div className="operations-inline-meta compact">
                    {conversation.customer_phone ? <span>{conversation.customer_phone}</span> : null}
                    {conversation.customer_email ? <span>{conversation.customer_email}</span> : null}
                  </div>
                ) : null}
                {conversation.handoff_reason ? (
                  <div className="workspace-notice info compact">{conversation.handoff_reason}</div>
                ) : null}
              </article>
            ))}
          </div>
        ) : null}
      </WorkspacePanel>

      <div className="mobile-action-safe-spacer" aria-hidden="true" />
    </div>
  );
}
