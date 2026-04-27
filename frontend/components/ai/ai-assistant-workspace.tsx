'use client';

import { Copy, RefreshCw } from 'lucide-react';
import { useCallback, useEffect, useMemo, useState } from 'react';
import Link from 'next/link';
import { WorkspaceEmpty, WorkspaceNotice, WorkspacePanel } from '@/components/commerce/workspace-primitives';
import { getAIAgentSettings, getAIConversationDetail, listAIConversations, updateAIConversationStatus } from '@/lib/api/ai';
import { formatDateTime } from '@/lib/commerce-format';
import type { AIAgentSettings, AIConversationDetail, AIConversationSummary } from '@/types/ai';

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
  const [selectedConversationId, setSelectedConversationId] = useState('');
  const [selectedConversation, setSelectedConversation] = useState<AIConversationDetail | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);
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
      setSelectedConversationId((current) => current || conversationsPayload.items[0]?.conversation_id || '');
      setError('');
    } catch (loadError) {
      setError(loadError instanceof Error ? loadError.message : 'Unable to load AI assistant workspace.');
    } finally {
      setLoading(false);
    }
  }, []);

  const loadConversationDetail = useCallback(async (conversationId: string) => {
    setDetailLoading(true);
    try {
      const detail = await getAIConversationDetail(conversationId, 50);
      setSelectedConversation(detail);
      setError('');
    } catch (detailError) {
      setSelectedConversation(null);
      setError(detailError instanceof Error ? detailError.message : 'Unable to load the conversation transcript.');
    } finally {
      setDetailLoading(false);
    }
  }, []);

  useEffect(() => {
    void loadWorkspace();
  }, [loadWorkspace]);

  useEffect(() => {
    if (!selectedConversationId) {
      setSelectedConversation(null);
      return;
    }
    void loadConversationDetail(selectedConversationId);
  }, [loadConversationDetail, selectedConversationId]);

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

  const changeConversationStatus = async (status: 'open' | 'handoff' | 'closed') => {
    if (!selectedConversationId) {
      return;
    }
    try {
      const detail = await updateAIConversationStatus(selectedConversationId, {
        status,
        handoff_reason: status === 'handoff'
          ? (selectedConversation?.handoff_reason || 'Conversation requires a human follow-up')
          : '',
      });
      setSelectedConversation(detail);
      setConversations((current) => current.map((item) => item.conversation_id === detail.conversation_id ? {
        ...item,
        status: detail.status,
        handoff_reason: detail.handoff_reason,
        latest_intent: detail.latest_intent,
        latest_summary: detail.latest_summary,
        last_message_preview: detail.last_message_preview,
        last_message_at: detail.last_message_at,
      } : item));
      setError('');
    } catch (statusError) {
      setError(statusError instanceof Error ? statusError.message : 'Unable to update the conversation status.');
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
              <article
                key={conversation.conversation_id}
                className="operations-list-card static ai-assistant-conversation-card"
                aria-current={selectedConversationId === conversation.conversation_id ? 'true' : undefined}
              >
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
                <div className="operations-toolbar-actions">
                  <button
                    type="button"
                    className="secondary"
                    onClick={() => setSelectedConversationId(conversation.conversation_id)}
                  >
                    {selectedConversationId === conversation.conversation_id ? 'Viewing transcript' : 'Open transcript'}
                  </button>
                </div>
              </article>
            ))}
          </div>
        ) : null}
      </WorkspacePanel>

      <WorkspacePanel title="Conversation transcript" description="Inspect the actual customer and assistant messages for the selected conversation.">
        {!selectedConversationId && !conversations.length ? (
          <WorkspaceEmpty
            title="No conversation selected"
            message="Choose a conversation after customers begin chatting through the tenant widget."
          />
        ) : null}
        {detailLoading ? <div className="reports-loading">Loading transcript...</div> : null}
        {!detailLoading && selectedConversation ? (
          <div className="operations-detail-stack">
            <div className="operations-inline-meta compact">
              <span>{selectedConversation.channel_display_name}</span>
              <span>{statusLabel(selectedConversation.status)}</span>
              {selectedConversation.latest_intent ? <span>{selectedConversation.latest_intent}</span> : null}
              <span>{formatDateTime(selectedConversation.last_message_at)}</span>
            </div>
            {selectedConversation.customer_phone || selectedConversation.customer_email || selectedConversation.customer_address ? (
              <div className="operations-inline-meta compact">
                {selectedConversation.customer_phone ? <span>{selectedConversation.customer_phone}</span> : null}
                {selectedConversation.customer_email ? <span>{selectedConversation.customer_email}</span> : null}
                {selectedConversation.customer_address ? <span>{selectedConversation.customer_address}</span> : null}
              </div>
            ) : null}
            {selectedConversation.handoff_reason ? (
              <WorkspaceNotice tone="info">{selectedConversation.handoff_reason}</WorkspaceNotice>
            ) : null}
            <div className="operations-toolbar-actions">
              {selectedConversation.status !== 'open' ? (
                <button type="button" className="secondary" onClick={() => void changeConversationStatus('open')}>
                  Reopen for AI
                </button>
              ) : null}
              {selectedConversation.status !== 'handoff' ? (
                <button type="button" className="secondary" onClick={() => void changeConversationStatus('handoff')}>
                  Mark handoff
                </button>
              ) : null}
              {selectedConversation.status !== 'closed' ? (
                <button type="button" className="secondary" onClick={() => void changeConversationStatus('closed')}>
                  Close conversation
                </button>
              ) : null}
            </div>
            {!selectedConversation.messages.length ? (
              <WorkspaceEmpty
                title="Transcript is empty"
                message="This conversation has no stored messages yet."
              />
            ) : (
              <div className="operations-list-stack">
                {selectedConversation.messages.map((message) => (
                  <article key={message.message_id} className="operations-list-card static ai-assistant-conversation-card">
                    <div className="operations-list-card-head">
                      <strong>{message.direction === 'outbound' ? settings?.display_name || 'Assistant' : selectedConversation.customer_name || 'Customer'}</strong>
                      <span className={message.direction === 'outbound' ? 'status-pill status-pill-active' : 'status-pill'}>
                        {message.direction === 'outbound' ? 'Assistant' : 'Customer'}
                      </span>
                    </div>
                    <p>{message.text}</p>
                    <div className="operations-inline-meta compact">
                      <span>{formatDateTime(message.occurred_at)}</span>
                    </div>
                  </article>
                ))}
              </div>
            )}
          </div>
        ) : null}
      </WorkspacePanel>

      <div className="mobile-action-safe-spacer" aria-hidden="true" />
    </div>
  );
}
