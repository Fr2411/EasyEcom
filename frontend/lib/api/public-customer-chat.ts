import { apiClient } from '@/lib/api/client';
import type { PublicCustomerChatRequest, PublicCustomerChatResponse } from '@/types/customer-communication';

export async function sendPublicCustomerChatMessage(channelKey: string, payload: PublicCustomerChatRequest) {
  return apiClient<PublicCustomerChatResponse>(
    `/public/customer-communication/chat/${encodeURIComponent(channelKey)}`,
    {
      method: 'POST',
      body: JSON.stringify(payload),
      timeoutMs: 180000,
    },
  );
}
