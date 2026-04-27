import { apiClient } from '@/lib/api/client';
import type { AIAgentSettings, AIAgentSettingsUpdatePayload, AIConversationDetail, AIConversationList } from '@/types/ai';

export async function getAIAgentSettings() {
  return apiClient<AIAgentSettings>('/ai/settings');
}

export async function updateAIAgentSettings(payload: AIAgentSettingsUpdatePayload) {
  return apiClient<AIAgentSettings>('/ai/settings', {
    method: 'PUT',
    body: JSON.stringify(payload),
  });
}

export async function listAIConversations(limit = 20) {
  const params = new URLSearchParams({ limit: String(limit) });
  return apiClient<AIConversationList>(`/ai/conversations?${params.toString()}`);
}

export async function getAIConversationDetail(conversationId: string, messageLimit = 50) {
  const params = new URLSearchParams({ message_limit: String(messageLimit) });
  return apiClient<AIConversationDetail>(`/ai/conversations/${encodeURIComponent(conversationId)}?${params.toString()}`);
}

export async function updateAIConversationStatus(
  conversationId: string,
  payload: { status: 'open' | 'handoff' | 'closed'; handoff_reason?: string },
) {
  return apiClient<AIConversationDetail>(`/ai/conversations/${encodeURIComponent(conversationId)}`, {
    method: 'PATCH',
    body: JSON.stringify(payload),
  });
}
