import { apiClient } from '@/lib/api/client';
import type { AIAgentSettings, AIAgentSettingsUpdatePayload, AIConversationList } from '@/types/ai';

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
