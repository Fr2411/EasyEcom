export type BillingPlanCode = 'free' | 'growth' | 'scale';

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
  currency_code: string;
  interval: string;
  sort_order: number;
  public_description: string;
  feature_flags_json?: Record<string, unknown> | null;
};

export type BillingPlansResponse = {
  items: BillingPlan[];
};

export type BillingSubscriptionState = {
  plan_code: BillingPlanCode;
  plan_name: string;
  billing_status: BillingSubscriptionStatus | string;
  billing_access_state: BillingAccessState;
  cancel_at_period_end: boolean;
  current_period_start: string | null;
  current_period_end: string | null;
  grace_until: string | null;
  stripe_customer_id: string | null;
  stripe_subscription_id: string | null;
  portal_available: boolean;
  can_upgrade: boolean;
  can_manage_subscription: boolean;
  paid_modules_locked: string[];
};

export type BillingCheckoutRequest = {
  plan_code: Extract<BillingPlanCode, 'growth' | 'scale'>;
};

export type BillingCheckoutSessionResponse = {
  checkout_url: string;
};

export type BillingPortalSessionResponse = {
  portal_url: string;
};

export type BillingWebhookProcessResult = {
  accepted: boolean;
  status: string;
  event_id: string | null;
};
