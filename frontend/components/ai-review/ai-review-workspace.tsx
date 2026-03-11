'use client';

import { useEffect, useMemo, useState } from 'react';
import { useAuth } from '@/components/auth/auth-provider';
import { ApiError } from '@/lib/api/client';
import {
  approveAiReviewDraft,
  createAiReviewDraft,
  editAiReviewDraft,
  getAiReviewConversation,
  getAiReviewConversations,
  rejectAiReviewDraft,
  sendAiReviewDraft,
} from '@/lib/api/ai-review';
import type { AiReviewConversationDetail, AiReviewDraft, AiReviewQueueItem } from '@/types/ai-review';

const ADMIN_ROLES = new Set(['SUPER_ADMIN', 'CLIENT_OWNER', 'CLIENT_MANAGER']);

export function AiReviewWorkspace() {
  const { user } = useAuth();
  const canAccess = useMemo(() => Boolean(user?.roles?.some((role) => ADMIN_ROLES.has(role))), [user?.roles]);
  const [items, setItems] = useState<AiReviewQueueItem[]>([]);
  const [selectedId, setSelectedId] = useState('');
  const [detail, setDetail] = useState<AiReviewConversationDetail | null>(null);
  const [composer, setComposer] = useState('');
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');

  async function loadQueue() {
    setLoading(true);
    setError('');
    try {
      const response = await getAiReviewConversations();
      setItems(response.items);
      const first = response.items[0]?.conversation_id ?? '';
      setSelectedId((prev) => prev || first);
    } catch {
      setError('Unable to load AI review queue.');
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    if (!canAccess) {
      setLoading(false);
      return;
    }
    void loadQueue();
  }, [canAccess]);

  useEffect(() => {
    if (!selectedId || !canAccess) return;
    void (async () => {
      try {
        const row = await getAiReviewConversation(selectedId);
        setDetail(row);
        const latest = row.latest_draft;
        setComposer(latest?.final_text || latest?.edited_text || latest?.ai_draft_text || '');
      } catch {
        setError('Unable to load selected conversation.');
      }
    })();
  }, [selectedId, canAccess]);

  async function onGenerateDraft() {
    if (!detail) return;
    const inbound = detail.messages.filter((m) => m.direction === 'inbound').at(-1);
    if (!inbound) return;
    setBusy(true);
    try {
      const draft = await createAiReviewDraft({ conversation_id: detail.conversation_id, inbound_message_id: inbound.message_id });
      const refreshed = await getAiReviewConversation(detail.conversation_id);
      setDetail({ ...refreshed, latest_draft: draft });
      setComposer(draft.ai_draft_text);
      await loadQueue();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Failed to generate draft');
    } finally {
      setBusy(false);
    }
  }

  async function updateDraft(action: 'edit' | 'approve' | 'reject' | 'send') {
    if (!detail?.latest_draft) return;
    setBusy(true);
    setError('');
    try {
      let draft: AiReviewDraft;
      if (action === 'edit') draft = await editAiReviewDraft(detail.latest_draft.draft_id, { edited_text: composer });
      else if (action === 'approve') draft = await approveAiReviewDraft(detail.latest_draft.draft_id);
      else if (action === 'reject') draft = await rejectAiReviewDraft(detail.latest_draft.draft_id);
      else draft = await sendAiReviewDraft(detail.latest_draft.draft_id);
      setDetail((prev) => (prev ? { ...prev, latest_draft: draft } : prev));
      await loadQueue();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Action failed');
    } finally {
      setBusy(false);
    }
  }

  if (!canAccess) return <div className="admin-card" data-testid="ai-review-access-denied"><h3>AI review access denied</h3><p>Only tenant owner/manager roles can review AI responses.</p></div>;
  if (loading) return <div className="admin-card" data-testid="ai-review-loading"><h3>Loading AI review queue…</h3></div>;

  return <div className="ai-review-layout">
    <aside className="admin-card">
      <h3>Inbox / Review queue</h3>
      {items.length === 0 ? <p data-testid="ai-review-empty-state">No inbound conversations are waiting for AI review.</p> : <ul className="ai-review-queue">{items.map((item) => <li key={item.conversation_id}><button className={item.conversation_id === selectedId ? 'active' : ''} onClick={() => setSelectedId(item.conversation_id)}>{item.external_sender_id}<br /><small>{item.preview_text}</small><span className={`int-status int-${item.status}`}>{item.status}</span></button></li>)}</ul>}
    </aside>

    <section className="admin-card">
      <h3>Conversation detail</h3>
      {!detail ? <p>Select a conversation from the queue.</p> : <>
        <p><strong>Channel:</strong> {detail.channel_id} · <strong>Sender:</strong> {detail.external_sender_id}</p>
        <div className="ai-review-messages">{detail.messages.map((message) => <div key={message.message_id} className={`ai-msg ai-${message.direction}`}><strong>{message.direction}</strong><p>{message.message_text || message.content_summary}</p></div>)}</div>

        <div className="ai-review-draft-block">
          <h4>AI suggested reply</h4>
          {detail.latest_draft ? <>
            <p><strong>Intent:</strong> {detail.latest_draft.intent} · <strong>Status:</strong> {detail.latest_draft.status}</p>
            <textarea aria-label="Final response" value={composer} onChange={(e) => setComposer(e.target.value)} rows={5} />
            <div className="ai-review-actions">
              <button onClick={() => updateDraft('edit')} disabled={busy || !composer.trim()}>Save edit</button>
              <button onClick={() => updateDraft('approve')} disabled={busy}>Approve</button>
              <button onClick={() => updateDraft('send')} disabled={busy || detail.latest_draft.status !== 'approved'}>Send</button>
              <button onClick={() => updateDraft('reject')} disabled={busy}>Reject</button>
            </div>
          </> : <button onClick={onGenerateDraft} disabled={busy}>Generate AI draft</button>}
        </div>
      </>}
      {error ? <p className="admin-error">{error}</p> : null}
    </section>
  </div>;
}
