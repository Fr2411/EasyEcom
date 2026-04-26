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
  channel_status: 'active' | 'inactive';
  is_enabled: boolean;
  display_name: string;
  n8n_webhook_url: string;
  persona_prompt: string;
  store_policy: string;
  faq_entries: AIAgentFAQEntry[];
  escalation_rules: string[];
  allowed_origins: string[];
  allowed_actions: AIAgentAllowedActions;
  default_location_id: string | null;
  opening_message: string;
  handoff_message: string;
  widget_script: string;
};

export type AIAgentSettingsUpdatePayload = {
  channel_status: 'active' | 'inactive';
  is_enabled: boolean;
  display_name: string;
  n8n_webhook_url: string;
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
