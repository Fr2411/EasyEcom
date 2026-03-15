import { apiClient } from '@/lib/api/client';
import type {
  ChannelIntegration,
  WhatsAppMetaIntegrationPayload,
  WhatsAppMetaIntegrationResult,
} from '@/types/integrations';


export async function getChannelIntegrations() {
  return apiClient<{ items: ChannelIntegration[] }>('/integrations/channels');
}


export async function saveWhatsAppMetaIntegration(payload: WhatsAppMetaIntegrationPayload) {
  return apiClient<WhatsAppMetaIntegrationResult>('/integrations/channels/whatsapp/meta', {
    method: 'PUT',
    body: JSON.stringify(payload),
  });
}
