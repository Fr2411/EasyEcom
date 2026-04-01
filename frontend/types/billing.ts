export type BillingPlanCode = 'free' | 'growth' | 'scale';

export type BillingProvider = 'paypal' | 'stripe' | string;

export type BillingAccessState =
  | 'free_active'
  | 'paid_active'
  | 'read_only_grace'
  | 'blocked';

export type BillingSubscriptionStatus =
  | 'free'
  | 'trialing'
  | 'active'
  | 'past_due'
  | 'canceled'
  | 'unpaid'
  | 'incomplete'
  | 'incomplete_expired';

export type BillingPlan = {
  plan_code: BillingPlanCode;
  display_name: string;
  is_paid: boolean;
  billing_provider?: BillingProvider | null;
  provider_plan_id?: string | null;
  currency_code: string;
  interval: string;
  sort_order: number;
  public_description: string;
  feature_flags_json?: Record<string, unknown> | null;
};

export type BillingPlansResponse = {
  items: BillingPlan[];
};

export type BillingPublicConfig = {
  billing_provider: BillingProvider;
  paypal_client_id: string | null;
  paypal_enabled: boolean;
};

export type BillingSubscriptionState = {
  plan_code: BillingPlanCode;
  plan_name: string;
  billing_provider?: BillingProvider | null;
  billing_status: BillingSubscriptionStatus | string;
  billing_access_state: BillingAccessState;
  cancel_at_period_end: boolean;
  cancel_effective_at?: string | null;
  current_period_start: string | null;
  current_period_end: string | null;
  grace_until: string | null;
  provider_customer_id?: string | null;
  provider_subscription_id?: string | null;
  provider_plan_id?: string | null;
  can_upgrade: boolean;
  can_manage_subscription: boolean;
  paid_modules_locked: string[];
  pending_plan_code?: BillingPlanCode | null;
};

export type BillingPlanRequest = {
  plan_code: Extract<BillingPlanCode, 'growth' | 'scale'>;
};

export type BillingActionResponse = {
  action_url: string | null;
  status: string;
};

export type BillingWebhookProcessResult = {
  accepted: boolean;
  status: string;
  event_id: string | null;
  provider: BillingProvider;
};
