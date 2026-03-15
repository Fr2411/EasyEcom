import { apiClient } from '@/lib/api/client';
import type { SalesOrder } from '@/types/sales';
import type { SalesAgentConversationDetail, SalesAgentConversationRow, SalesAgentDraft } from '@/types/sales-agent';


function buildQuery(params: Record<string, string | undefined>) {
  const search = new URLSearchParams();
  Object.entries(params).forEach(([key, value]) => {
    if (!value) return;
    search.set(key, value);
  });
  const query = search.toString();
  return query ? `?${query}` : '';
}


export async function getSalesAgentConversations(params: { q?: string; status?: string } = {}) {
  return apiClient<{ items: SalesAgentConversationRow[] }>(
    `/sales-agent/conversations${buildQuery({ q: params.q, status: params.status })}`
  );
}


export async function getSalesAgentConversation(conversationId: string) {
  return apiClient<SalesAgentConversationDetail>(`/sales-agent/conversations/${conversationId}`);
}


export async function handoffSalesAgentConversation(conversationId: string, notes = '') {
  return apiClient<SalesAgentConversationRow>(`/sales-agent/conversations/${conversationId}/handoff`, {
    method: 'POST',
    body: JSON.stringify({ notes }),
  });
}


export async function approveSalesAgentDraft(draftId: string, editedText = '') {
  return apiClient<SalesAgentDraft>(`/sales-agent/drafts/${draftId}/approve-send`, {
    method: 'POST',
    body: JSON.stringify({ edited_text: editedText }),
  });
}


export async function rejectSalesAgentDraft(draftId: string, reason = '') {
  return apiClient<SalesAgentDraft>(`/sales-agent/drafts/${draftId}/reject`, {
    method: 'POST',
    body: JSON.stringify({ reason }),
  });
}


export async function getSalesAgentOrders(status?: string) {
  return apiClient<{ items: SalesOrder[] }>(`/sales-agent/orders${buildQuery({ status })}`);
}


export async function confirmSalesAgentOrder(orderId: string) {
  return apiClient<{ order: SalesOrder }>(`/sales-agent/orders/${orderId}/confirm`, {
    method: 'POST',
    body: JSON.stringify({}),
  });
}
