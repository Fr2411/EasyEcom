import { apiClient } from '@/lib/api/client';
import type {
  ChannelIntegration,
  ChannelLocation,
  WhatsAppMetaIntegrationPayload,
  WhatsAppMetaIntegrationResult,
} from '@/types/integrations';


function buildQuery(clientId?: string) {
  if (!clientId?.trim()) {
    return '';
  }
  const params = new URLSearchParams({ client_id: clientId.trim() });
  return `?${params.toString()}`;
}


export async function getChannelIntegrations(clientId?: string) {
  return apiClient<{ items: ChannelIntegration[] }>(`/integrations/channels${buildQuery(clientId)}`);
}


export async function getChannelLocations(clientId?: string) {
  return apiClient<{ items: ChannelLocation[] }>(`/integrations/channels/locations${buildQuery(clientId)}`);
}


export async function saveWhatsAppMetaIntegration(payload: WhatsAppMetaIntegrationPayload, clientId?: string) {
  return apiClient<WhatsAppMetaIntegrationResult>(`/integrations/channels/whatsapp/meta${buildQuery(clientId)}`, {
    method: 'PUT',
    body: JSON.stringify(payload),
  });
}
