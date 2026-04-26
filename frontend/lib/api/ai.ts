import { apiClient } from '@/lib/api/client';
import type { AIAgentSettings, AIAgentSettingsUpdatePayload } from '@/types/ai';

export async function getAIAgentSettings() {
  return apiClient<AIAgentSettings>('/ai/settings');
}

export async function updateAIAgentSettings(payload: AIAgentSettingsUpdatePayload) {
  return apiClient<AIAgentSettings>('/ai/settings', {
    method: 'PUT',
    body: JSON.stringify(payload),
  });
}
