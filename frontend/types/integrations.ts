export type ChannelIntegration = {
  channel_id: string;
  provider: 'whatsapp' | 'messenger' | 'webhook';
  display_name: string;
  status: 'inactive' | 'active' | 'disabled';
  config_saved: boolean;
  webhook_key?: string;
  external_account_id: string;
  phone_number_id: string;
  phone_number: string;
  verify_token_set: boolean;
  inbound_secret_set: boolean;
  access_token_set: boolean;
  webhook_verified_at: string | null;
  last_webhook_post_at: string | null;
  signature_validation_ok: boolean | null;
  graph_auth_ok: boolean | null;
  outbound_send_ok: boolean | null;
  openai_ready?: boolean;
  openai_probe_ok: boolean | null;
  last_error_code: string | null;
  last_error_message: string | null;
  last_provider_status_code: number | null;
  last_provider_response_excerpt: string | null;
  last_diagnostic_at: string | null;
  next_action: string;
  default_location_id: string | null;
  auto_send_enabled: boolean;
  agent_enabled: boolean;
  model_name: string;
  persona_prompt: string;
  config: Record<string, string>;
  created_at: string;
  updated_at: string;
  last_inbound_at: string | null;
  last_outbound_at: string | null;
};

export type ChannelMessage = {
  message_id: string;
  conversation_id: string;
  channel_id: string;
  direction: 'inbound' | 'outbound';
  external_sender_id: string;
  provider_event_id: string;
  message_text: string;
  content_summary: string;
  occurred_at: string;
  outbound_status: string;
};

export type ChannelConversation = {
  conversation_id: string;
  channel_id: string;
  external_sender_id: string;
  status: string;
  customer_id: string | null;
  linked_sale_id: string | null;
  last_message_at: string;
  updated_at: string;
};

export type WhatsAppMetaIntegrationPayload = {
  display_name: string;
  external_account_id: string;
  phone_number_id: string;
  phone_number: string;
  verify_token: string;
  access_token: string;
  app_secret: string;
  default_location_id?: string | null;
  auto_send_enabled: boolean;
  agent_enabled: boolean;
  model_name: string;
  persona_prompt: string;
};

export type WhatsAppMetaIntegrationResult = {
  channel: ChannelIntegration;
  setup_verify_token: string | null;
};

export type ChannelDiagnostics = {
  config_saved: boolean;
  verify_token_set: boolean;
  webhook_verified_at: string | null;
  last_webhook_post_at: string | null;
  signature_validation_ok: boolean | null;
  graph_auth_ok: boolean | null;
  outbound_send_ok: boolean | null;
  openai_ready: boolean;
  openai_probe_ok: boolean | null;
  last_error_code: string | null;
  last_error_message: string | null;
  last_provider_status_code: number | null;
  last_provider_response_excerpt: string | null;
  last_diagnostic_at: string | null;
  next_action: string;
};

export type ChannelDiagnosticsEnvelope = {
  diagnostics: ChannelDiagnostics;
  provider_details: Record<string, string | number | null>;
};

export type ChannelSmokePayload = {
  recipient: string;
  text: string;
};

export type ChannelSmokeResult = {
  ok: boolean;
  provider_event_id: string | null;
  message: string;
  diagnostics: ChannelDiagnostics;
  provider_details: Record<string, string | number | null>;
};

export type ChannelRunDiagnosticsResult = {
  channel: ChannelIntegration;
  diagnostics: ChannelDiagnostics;
  provider_details: Record<string, string | number | null>;
};

export type ChannelLocation = {
  location_id: string;
  name: string;
  is_default: boolean;
};
