export type ChannelIntegration = {
  channel_id: string;
  provider: 'whatsapp' | 'messenger' | 'webhook';
  display_name: string;
  status: 'inactive' | 'active' | 'disabled';
  external_account_id: string;
  verify_token_set: boolean;
  inbound_secret_set: boolean;
  config: Record<string, string>;
  created_at: string;
  updated_at: string;
  last_inbound_at: string | null;
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
