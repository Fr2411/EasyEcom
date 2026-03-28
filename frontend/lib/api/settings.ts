import { apiClient } from '@/lib/api/client';
import type { SettingsWorkspace, SettingsWorkspaceUpdatePayload } from '@/types/settings';

export async function getSettingsWorkspace() {
  return apiClient<SettingsWorkspace>('/settings/workspace');
}

export async function updateSettingsWorkspace(payload: SettingsWorkspaceUpdatePayload) {
  return apiClient<SettingsWorkspace>('/settings/workspace', {
    method: 'PUT',
    body: JSON.stringify(payload),
  });
}
