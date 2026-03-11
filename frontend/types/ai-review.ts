export type AiReviewQueueItem = {
  conversation_id: string;
  channel_id: string;
  external_sender_id: string;
  customer_id: string | null;
  status: 'new' | 'needs_review' | 'approved' | 'sent' | 'failed';
  last_message_at: string;
  preview_message_id: string;
  preview_text: string;
};

export type AiReviewMessage = {
  message_id: string;
  direction: 'inbound' | 'outbound';
  message_text: string;
  content_summary: string;
  occurred_at: string;
  outbound_status: string;
};

export type AiReviewDraft = {
  draft_id: string;
  conversation_id: string;
  inbound_message_id: string;
  status: string;
  ai_draft_text: string;
  edited_text: string;
  final_text: string;
  intent: string;
  confidence: string;
  grounding: Record<string, unknown>;
  requested_by_user_id: string;
  approved_by_user_id: string | null;
  sent_by_user_id: string | null;
  created_at: string;
  updated_at: string;
  approved_at: string | null;
  sent_at: string | null;
  failed_reason: string | null;
  send_result: Record<string, unknown>;
  human_modified: boolean;
};

export type AiReviewConversationDetail = {
  conversation_id: string;
  channel_id: string;
  external_sender_id: string;
  status: string;
  messages: AiReviewMessage[];
  latest_draft: AiReviewDraft | null;
};
