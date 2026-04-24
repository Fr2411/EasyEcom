import { apiClient } from '@/lib/api/client';
import type {
  AssistantPlaybook,
  ChannelUpsertPayload,
  CustomerChannel,
  CustomerCommunicationWorkspace,
  CustomerConversationDetail,
  PlaybookUpdatePayload,
} from '@/types/customer-communication';

export async function getCustomerCommunicationWorkspace(conversationId?: string) {
  const query = conversationId ? `?conversation_id=${encodeURIComponent(conversationId)}` : '';
  return apiClient<CustomerCommunicationWorkspace>(`/customer-communication/workspace${query}`);
}

export async function updateAssistantPlaybook(payload: PlaybookUpdatePayload) {
  return apiClient<AssistantPlaybook>('/customer-communication/playbook', {
    method: 'PUT',
    body: JSON.stringify(payload),
  });
}

export async function createCustomerChannel(payload: ChannelUpsertPayload) {
  return apiClient<CustomerChannel>('/customer-communication/channels', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export async function updateCustomerChannel(channelId: string, payload: ChannelUpsertPayload) {
  return apiClient<CustomerChannel>(`/customer-communication/channels/${channelId}`, {
    method: 'PUT',
    body: JSON.stringify(payload),
  });
}

export async function escalateCustomerConversation(conversationId: string, reason: string) {
  return apiClient<CustomerConversationDetail>(
    `/customer-communication/conversations/${conversationId}/escalate?reason=${encodeURIComponent(reason)}`,
    { method: 'POST', body: JSON.stringify({}) },
  );
}
