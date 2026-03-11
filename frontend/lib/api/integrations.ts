import { apiClient } from '@/lib/api/client';
import type { ChannelConversation, ChannelIntegration, ChannelMessage } from '@/types/integrations';

export function getIntegrations() {
  return apiClient<{ items: ChannelIntegration[] }>('/integrations/channels');
}

export function createIntegration(payload: {
  provider: string;
  display_name: string;
  external_account_id?: string;
  status?: string;
  verify_token?: string;
  inbound_secret?: string;
  config?: Record<string, string>;
}) {
  return apiClient<ChannelIntegration>('/integrations/channels', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export function getIntegrationMessages() {
  return apiClient<{ items: ChannelMessage[] }>('/integrations/messages');
}

export function getConversations() {
  return apiClient<{ items: ChannelConversation[] }>('/integrations/conversations');
}
