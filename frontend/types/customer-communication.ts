export type AssistantPlaybook = {
  playbook_id: string;
  status: string;
  business_type: 'general_retail' | 'pet_food' | 'fashion' | 'shoe_store' | 'electronics' | 'cosmetics' | 'grocery' | string;
  brand_personality: 'friendly' | 'expert' | 'premium' | 'casual' | 'concise' | string;
  custom_instructions: string;
  forbidden_claims: string;
  sales_goals: Record<string, unknown>;
  policies: Record<string, unknown>;
  escalation_rules: Record<string, unknown>;
  industry_template: {
    questions?: string[];
    safety?: string[];
    [key: string]: unknown;
  };
};

export type CustomerChannel = {
  channel_id: string;
  provider: 'website' | 'whatsapp' | 'instagram' | 'facebook' | 'messenger' | 'other' | string;
  display_name: string;
  status: 'active' | 'inactive' | string;
  external_account_id: string;
  webhook_key: string;
  default_location_id?: string | null;
  auto_send_enabled: boolean;
  config: Record<string, unknown>;
  last_inbound_at?: string | null;
  last_outbound_at?: string | null;
};

export type CustomerMessage = {
  message_id: string;
  conversation_id: string;
  channel_id: string;
  direction: 'inbound' | 'outbound' | string;
  sender_role: 'customer' | 'assistant' | 'staff' | string;
  provider_event_id: string;
  message_text: string;
  outbound_status: string;
  metadata: Record<string, unknown>;
  occurred_at?: string | null;
};

export type AssistantToolCall = {
  tool_call_id: string;
  run_id: string;
  tool_name: string;
  tool_arguments: Record<string, unknown>;
  tool_result: Record<string, unknown>;
  validation_status: string;
  created_at?: string | null;
};

export type AssistantRun = {
  run_id: string;
  conversation_id: string;
  inbound_message_id: string;
  status: string;
  model_provider: string;
  model_name: string;
  response_text: string;
  validation_status: string;
  escalation_required: boolean;
  escalation_reason: string;
  total_tokens?: number | null;
  created_at?: string | null;
  tool_calls: AssistantToolCall[];
};

export type CustomerConversationSummary = {
  conversation_id: string;
  channel_id: string;
  channel_provider: string;
  channel_display_name: string;
  customer_id?: string | null;
  draft_order_id?: string | null;
  external_sender_id: string;
  external_sender_name: string;
  external_sender_phone: string;
  external_sender_email: string;
  status: string;
  latest_intent: string;
  latest_summary: string;
  escalation_reason: string;
  last_message_preview: string;
  last_message_at?: string | null;
};

export type CustomerConversationDetail = CustomerConversationSummary & {
  memory: Record<string, unknown>;
  messages: CustomerMessage[];
  runs: AssistantRun[];
};

export type CustomerCommunicationWorkspace = {
  playbook: AssistantPlaybook;
  channels: CustomerChannel[];
  conversations: CustomerConversationSummary[];
  active_conversation?: CustomerConversationDetail | null;
};

export type PlaybookUpdatePayload = {
  business_type: string;
  brand_personality: string;
  custom_instructions: string;
  forbidden_claims: string;
  sales_goals: Record<string, unknown>;
  policies: Record<string, unknown>;
  escalation_rules: Record<string, unknown>;
};

export type ChannelUpsertPayload = {
  provider: string;
  display_name: string;
  status: string;
  external_account_id: string;
  default_location_id?: string | null;
  auto_send_enabled: boolean;
  config: Record<string, unknown>;
};
