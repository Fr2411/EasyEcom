export type AIAgentFAQEntry = {
  question: string;
  answer: string;
};

export type AIAgentAllowedActions = {
  product_qa: boolean;
  recommendations: boolean;
  cart_building: boolean;
  order_confirmation: boolean;
};

export type AIAgentSettings = {
  profile_id: string;
  channel_id: string;
  widget_key: string;
  ai_runtime: string;
  model_name: string;
  model_configured: boolean;
  channel_status: 'active' | 'inactive';
  is_enabled: boolean;
  display_name: string;
  persona_prompt: string;
  store_policy: string;
  faq_entries: AIAgentFAQEntry[];
  escalation_rules: string[];
  allowed_origins: string[];
  allowed_actions: AIAgentAllowedActions;
  default_location_id: string | null;
  opening_message: string;
  handoff_message: string;
  chat_link: string;
  widget_script: string;
};

export type AIAgentSettingsUpdatePayload = {
  channel_status: 'active' | 'inactive';
  is_enabled: boolean;
  display_name: string;
  persona_prompt: string;
  store_policy: string;
  faq_entries: AIAgentFAQEntry[];
  escalation_rules: string[];
  allowed_origins: string[];
  allowed_actions: AIAgentAllowedActions;
  default_location_id: string | null;
  opening_message: string;
  handoff_message: string;
};

export type AIConversationSummary = {
  conversation_id: string;
  channel_id: string;
  channel_type: string;
  channel_display_name: string;
  status: 'open' | 'handoff' | 'closed' | string;
  customer_name: string;
  customer_phone: string;
  customer_email: string;
  latest_intent: string;
  latest_summary: string;
  handoff_reason: string;
  last_message_preview: string;
  last_message_at: string | null;
  message_count: number;
};

export type AIConversationList = {
  items: AIConversationSummary[];
};
