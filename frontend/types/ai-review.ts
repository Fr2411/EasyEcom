import type { SalesAgentConversationDetail, SalesAgentDraft, SalesAgentMessage } from '@/types/sales-agent';

export type AiReviewQueueItem = {
  draft_id: string;
  conversation_id: string;
  linked_sales_order_id: string | null;
  customer_name: string;
  customer_phone: string;
  external_sender_id: string;
  conversation_status: string;
  draft_status: string;
  latest_intent: string;
  last_message_preview: string;
  last_message_at: string | null;
  reason_codes: string[];
  confidence: string | null;
  created_at: string;
  updated_at: string;
  approved_at: string | null;
  sent_at: string | null;
  outbound_message_id: string | null;
};

export type AiReviewAuditEntry = {
  audit_log_id: string;
  entity_type: string;
  entity_id: string;
  action: string;
  actor_user_id: string | null;
  actor_name: string | null;
  created_at: string;
  metadata: Record<string, unknown>;
};

export type AiReviewDraft = SalesAgentDraft;
export type AiReviewMessage = SalesAgentMessage;

export type AiReviewDetail = {
  draft: SalesAgentDraft;
  conversation: SalesAgentConversationDetail;
  audit_trail: AiReviewAuditEntry[];
  outbound_message: SalesAgentMessage | null;
};
