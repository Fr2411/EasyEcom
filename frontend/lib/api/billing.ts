import { apiClient } from '@/lib/api/client';
import type {
  BillingActionResponse,
  BillingPlanRequest,
  BillingPlansResponse,
  BillingPublicConfig,
  BillingSubscriptionState,
} from '@/types/billing';

export async function getPublicBillingPlans() {
  return apiClient<BillingPlansResponse>('/public/billing/plans');
}

export async function getPublicBillingConfig() {
  return apiClient<BillingPublicConfig>('/public/billing/config');
}

export async function getBillingSubscription() {
  return apiClient<BillingSubscriptionState>('/billing/subscription');
}

export async function changeBillingPlan(payload: BillingPlanRequest) {
  return apiClient<BillingActionResponse>('/billing/change-plan', {
    method: 'POST',
    body: JSON.stringify({ target_plan_code: payload.plan_code }),
  });
}

export async function cancelBillingSubscription() {
  return apiClient<BillingActionResponse>('/billing/cancel-subscription', {
    method: 'POST',
  });
}
