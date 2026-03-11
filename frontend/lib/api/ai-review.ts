import { apiClient } from '@/lib/api/client';
import type { AiReviewConversationDetail, AiReviewDraft, AiReviewQueueItem } from '@/types/ai-review';

export function getAiReviewConversations() {
  return apiClient<{ items: AiReviewQueueItem[] }>('/ai/review/conversations');
}

export function getAiReviewConversation(conversationId: string) {
  return apiClient<AiReviewConversationDetail>(`/ai/review/conversations/${conversationId}`);
}

export function createAiReviewDraft(payload: { conversation_id: string; inbound_message_id: string }) {
  return apiClient<AiReviewDraft>('/ai/review/draft', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export function editAiReviewDraft(draftId: string, payload: { edited_text: string }) {
  return apiClient<AiReviewDraft>(`/ai/review/${draftId}/edit`, {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export function approveAiReviewDraft(draftId: string) {
  return apiClient<AiReviewDraft>(`/ai/review/${draftId}/approve`, { method: 'POST' });
}

export function rejectAiReviewDraft(draftId: string) {
  return apiClient<AiReviewDraft>(`/ai/review/${draftId}/reject`, { method: 'POST' });
}

export function sendAiReviewDraft(draftId: string) {
  return apiClient<AiReviewDraft>(`/ai/review/${draftId}/send`, { method: 'POST' });
}
