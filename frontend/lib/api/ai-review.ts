import { apiClient } from '@/lib/api/client';
import type { AiReviewDetail, AiReviewDraft, AiReviewQueueItem } from '@/types/ai-review';


function buildQuery(params: Record<string, string | undefined>) {
  const search = new URLSearchParams();
  Object.entries(params).forEach(([key, value]) => {
    if (!value) return;
    search.set(key, value);
  });
  const query = search.toString();
  return query ? `?${query}` : '';
}


export async function getAiReviewDrafts(params: { q?: string; status?: string } = {}) {
  return apiClient<{ items: AiReviewQueueItem[] }>(
    `/ai-review/drafts${buildQuery({ q: params.q, status: params.status })}`,
  );
}


export async function getAiReviewDraft(draftId: string) {
  return apiClient<AiReviewDetail>(`/ai-review/drafts/${draftId}`);
}


export async function approveAiReviewDraft(draftId: string, editedText = '') {
  return apiClient<AiReviewDraft>(`/ai-review/drafts/${draftId}/approve-send`, {
    method: 'POST',
    body: JSON.stringify({ edited_text: editedText }),
  });
}


export async function rejectAiReviewDraft(draftId: string, reason = '') {
  return apiClient<AiReviewDraft>(`/ai-review/drafts/${draftId}/reject`, {
    method: 'POST',
    body: JSON.stringify({ reason }),
  });
}
