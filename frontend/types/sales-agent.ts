import type { SalesOrder } from '@/types/sales';

export type SalesAgentMention = {
  mention_id: string;
  product_id: string | null;
  variant_id: string | null;
  mention_role: string;
  quantity: string | null;
  unit_price: string | null;
  min_price: string | null;
  available_to_sell: string | null;
};

export type SalesAgentMessage = {
  message_id: string;
  direction: string;
  message_text: string;
  content_summary: string;
  occurred_at: string;
  outbound_status: string;
  provider_status: string;
  mentions: SalesAgentMention[];
};

export type SalesAgentDraft = {
  draft_id: string;
  conversation_id: string;
  linked_sales_order_id: string | null;
  status: string;
  ai_draft_text: string;
  edited_text: string;
  final_text: string;
  intent: string;
  confidence: string | null;
  grounding: Record<string, unknown>;
  reason_codes: string[];
  approved_at: string | null;
  sent_at: string | null;
  failed_reason: string | null;
  human_modified: boolean;
};

export type SalesAgentConversationRow = {
  conversation_id: string;
  channel_id: string;
  customer_id: string | null;
  customer_name: string;
  customer_phone: string;
  customer_email: string;
  external_sender_id: string;
  status: string;
  customer_type: string;
  behavior_tags: string[];
  lifetime_spend: string;
  lifetime_order_count: number;
  latest_intent: string;
  latest_summary: string;
  last_message_preview: string;
  last_message_at: string | null;
  latest_recommended_products_summary: string;
  linked_draft_order_id: string | null;
  linked_draft_order_status: string;
  latest_draft_id: string | null;
  latest_draft_status: string | null;
  latest_trace: Record<string, unknown>;
  linked_order: SalesOrder | null;
};

export type SalesAgentConversationDetail = SalesAgentConversationRow & {
  messages: SalesAgentMessage[];
  latest_draft: SalesAgentDraft | null;
};
