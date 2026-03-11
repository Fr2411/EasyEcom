export type AutomationPolicy = {
  policy_id: string;
  client_id: string;
  automation_enabled: boolean;
  auto_send_enabled: boolean;
  emergency_disabled: boolean;
  categories: Record<string, boolean>;
  updated_by_user_id: string;
  created_at: string;
  updated_at: string;
};

export type AutomationEvaluation = {
  conversation_id: string;
  inbound_message_id: string;
  category: string;
  classification_rule: string;
  automation_eligible: boolean;
  recommended_action: string;
  reason: string;
  candidate_reply?: string;
  intent?: string;
  confidence?: string;
};

export type AutomationDecision = {
  decision_id: string;
  conversation_id: string;
  inbound_message_id: string;
  policy_id: string;
  category: string;
  classification_rule: string;
  recommended_action: string;
  outcome: string;
  reason: string;
  confidence: string;
  candidate_reply: string;
  run_by_user_id: string;
  created_at: string;
  updated_at: string;
};
