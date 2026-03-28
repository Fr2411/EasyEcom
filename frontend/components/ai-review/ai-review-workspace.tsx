'use client';

import Link from 'next/link';
import { FormEvent, useEffect, useState, useTransition } from 'react';

import { WorkspaceEmpty, WorkspaceNotice, WorkspacePanel } from '@/components/commerce/workspace-primitives';
import { approveAiReviewDraft, getAiReviewDraft, getAiReviewDrafts, rejectAiReviewDraft } from '@/lib/api/ai-review';
import { formatDateTime } from '@/lib/commerce-format';
import type { AiReviewDetail, AiReviewDraft, AiReviewQueueItem } from '@/types/ai-review';


export function AiReviewWorkspace() {
  const [queue, setQueue] = useState<AiReviewQueueItem[]>([]);
  const [selectedDraftId, setSelectedDraftId] = useState<string | null>(null);
  const [detail, setDetail] = useState<AiReviewDetail | null>(null);
  const [draftEdits, setDraftEdits] = useState<Record<string, string>>({});
  const [query, setQuery] = useState('');
  const [status, setStatus] = useState('needs_review');
  const [notice, setNotice] = useState('');
  const [error, setError] = useState('');
  const [isPending, startTransition] = useTransition();

  const loadQueue = (nextQuery = query, nextStatus = status, preferredDraftId?: string | null) => {
    startTransition(async () => {
      try {
        const payload = await getAiReviewDrafts({ q: nextQuery, status: nextStatus || undefined });
        setQueue(payload.items);
        setError('');
        const fallbackDraftId = preferredDraftId && payload.items.some((item) => item.draft_id === preferredDraftId)
          ? preferredDraftId
          : payload.items[0]?.draft_id ?? null;
        setSelectedDraftId(fallbackDraftId);
        if (fallbackDraftId) {
          await loadDetail(fallbackDraftId);
        } else {
          setDetail(null);
        }
      } catch (loadError) {
        setError(loadError instanceof Error ? loadError.message : 'Unable to load the AI review queue.');
      }
    });
  };

  const loadDetail = async (draftId: string) => {
    const payload = await getAiReviewDraft(draftId);
    setDetail(payload);
    setDraftEdits((current) => ({
      ...current,
      [payload.draft.draft_id]: current[payload.draft.draft_id] ?? payload.draft.final_text ?? payload.draft.ai_draft_text,
    }));
  };

  useEffect(() => {
    loadQueue('', 'needs_review');
  }, []);

  const applyFilters = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    loadQueue(query.trim(), status, selectedDraftId);
  };

  const selectDraft = async (draftId: string) => {
    setSelectedDraftId(draftId);
    try {
      await loadDetail(draftId);
      setError('');
    } catch (detailError) {
      setError(detailError instanceof Error ? detailError.message : 'Unable to load the review detail.');
    }
  };

  const onApprove = async (draft: AiReviewDraft) => {
    try {
      const editedText = draftEdits[draft.draft_id] ?? draft.final_text ?? draft.ai_draft_text;
      await approveAiReviewDraft(draft.draft_id, editedText);
      setNotice('Draft approved and sent.');
      await loadQueue(query, status, draft.draft_id);
    } catch (approveError) {
      setError(approveError instanceof Error ? approveError.message : 'Unable to approve the draft.');
    }
  };

  const onReject = async (draft: AiReviewDraft) => {
    try {
      await rejectAiReviewDraft(draft.draft_id, 'Rejected from AI Review inbox');
      setNotice('Draft rejected and moved to handoff.');
      await loadQueue(query, status, draft.draft_id);
    } catch (rejectError) {
      setError(rejectError instanceof Error ? rejectError.message : 'Unable to reject the draft.');
    }
  };

  const activeDraft = detail?.draft ?? null;

  return (
    <div className="workspace-stack">
      {notice ? <WorkspaceNotice tone="success">{notice}</WorkspaceNotice> : null}
      {error ? <WorkspaceNotice tone="error">{error}</WorkspaceNotice> : null}

      <WorkspacePanel
        title="Pending drafts"
        description="Review risky outbound drafts, confirm the final copy, and approve before any customer-facing send."
        hint="Risky replies stay blocked until a human reviewer explicitly approves them."
        actions={
          <form className="workspace-search" onSubmit={applyFilters}>
            <input
              type="search"
              value={query}
              placeholder="Search customer, phone, or draft"
              onChange={(event) => setQuery(event.target.value)}
            />
            <select value={status} onChange={(event) => setStatus(event.target.value)}>
              <option value="needs_review">Needs review</option>
              <option value="">All statuses</option>
              <option value="sent">Sent</option>
              <option value="rejected">Rejected</option>
            </select>
            <button type="submit">Filter</button>
          </form>
        }
      >
        <div className="ai-review-layout">
          <div>
            {isPending && !queue.length ? <div className="dashboard-loading">Loading AI review queue…</div> : null}
            {queue.length ? (
              <ul className="ai-review-queue">
                {queue.map((item) => (
                  <li key={item.draft_id}>
                    <button
                      type="button"
                      className={selectedDraftId === item.draft_id ? 'active' : ''}
                      onClick={() => selectDraft(item.draft_id)}
                    >
                      <strong>{item.customer_name || item.customer_phone || 'Unknown customer'}</strong>
                      <p className="admin-muted">{item.customer_phone || item.external_sender_id}</p>
                      <p>{item.last_message_preview}</p>
                      <small>
                        {item.last_message_at ? formatDateTime(item.last_message_at) : 'No activity yet'}
                        {' · '}
                        {item.reason_codes.join(', ') || 'Manual review'}
                      </small>
                    </button>
                  </li>
                ))}
              </ul>
            ) : (
              <WorkspaceEmpty
                title="No drafts waiting for review"
                message="Risky outbound replies will appear here before any customer-facing send is allowed."
              />
            )}
          </div>

          <div>
            {detail && activeDraft ? (
              <div className="workspace-stack">
                <WorkspacePanel
                  title="Draft detail"
                  description="Review the latest conversation context, edit the reply if needed, and approve or reject with a full audit trail."
                  actions={<Link className="button-link secondary" href="/sales-agent">Open Sales Agent</Link>}
                >
                  <div className="workspace-stack">
                    <div className="sales-agent-side-card">
                      <div>
                        <strong>{detail.conversation.customer_name || detail.conversation.customer_phone || 'Unknown customer'}</strong>
                        <p className="admin-muted">{detail.conversation.customer_phone || detail.conversation.external_sender_id}</p>
                        <p className="admin-muted">
                          Intent: {detail.conversation.latest_intent || 'Unknown'}
                          {' · '}
                          Conversation: {detail.conversation.conversation_id}
                        </p>
                      </div>
                      <div className="sales-agent-trace-pills">
                        {activeDraft.reason_codes.map((code) => <span key={code}>{code}</span>)}
                      </div>
                      <label>
                        <span>Approved outbound text</span>
                        <textarea
                          rows={6}
                          value={draftEdits[activeDraft.draft_id] ?? activeDraft.final_text ?? activeDraft.ai_draft_text}
                          onChange={(event) =>
                            setDraftEdits((current) => ({ ...current, [activeDraft.draft_id]: event.target.value }))
                          }
                        />
                      </label>
                      <div className="sales-agent-side-actions">
                        <button
                          type="button"
                          onClick={() => onApprove(activeDraft)}
                          disabled={activeDraft.status !== 'needs_review'}
                        >
                          Approve and Send
                        </button>
                        <button
                          type="button"
                          className="secondary"
                          onClick={() => onReject(activeDraft)}
                          disabled={activeDraft.status !== 'needs_review'}
                        >
                          Reject
                        </button>
                      </div>
                      <p className="admin-muted">
                        Requested by {activeDraft.requested_by_name || activeDraft.requested_by_user_id || 'system'}
                        {' · '}
                        Created {formatDateTime(activeDraft.created_at)}
                      </p>
                      {activeDraft.approved_at ? (
                        <p className="admin-muted">
                          Approved by {activeDraft.approved_by_name || activeDraft.approved_by_user_id || 'unknown'}
                          {' · '}
                          {formatDateTime(activeDraft.approved_at)}
                        </p>
                      ) : null}
                      {activeDraft.outbound_message_id ? (
                        <p className="admin-muted">Outbound message ID: {activeDraft.outbound_message_id}</p>
                      ) : null}
                    </div>

                    <div className="workspace-panel">
                      <div className="workspace-panel-body">
                        <h4>Conversation timeline</h4>
                        <div className="sales-agent-timeline">
                          {detail.conversation.messages.map((message) => (
                            <article key={message.message_id} className={`sales-agent-message direction-${message.direction}`}>
                              <header>
                                <strong>{message.direction === 'inbound' ? 'Customer' : 'Outbound'}</strong>
                                <span>{formatDateTime(message.occurred_at)}</span>
                              </header>
                              <p>{message.message_text}</p>
                            </article>
                          ))}
                        </div>
                      </div>
                    </div>

                    <div className="workspace-panel">
                      <div className="workspace-panel-body">
                        <h4>Audit trail</h4>
                        <div className="ai-review-messages">
                          {detail.audit_trail.map((entry) => (
                            <article key={entry.audit_log_id} className="ai-msg">
                              <strong>{entry.action.replaceAll('_', ' ')}</strong>
                              <p>
                                {entry.actor_name || entry.actor_user_id || 'System'}
                                {' · '}
                                {formatDateTime(entry.created_at)}
                              </p>
                            </article>
                          ))}
                        </div>
                      </div>
                    </div>
                  </div>
                </WorkspacePanel>
              </div>
            ) : (
              <WorkspaceEmpty
                title="Select a draft"
                message="Choose a draft from the queue to inspect the conversation, adjust the final reply, and approve the outbound send."
              />
            )}
          </div>
        </div>
      </WorkspacePanel>
    </div>
  );
}
