import { apiClient } from '@/lib/api/client';
import type {
  BillingCheckoutRequest,
  BillingCheckoutSessionResponse,
  BillingPlansResponse,
  BillingPortalSessionResponse,
  BillingSubscriptionState,
} from '@/types/billing';

export async function getPublicBillingPlans() {
  return apiClient<BillingPlansResponse>('/public/billing/plans');
}

export async function getBillingSubscription() {
  return apiClient<BillingSubscriptionState>('/billing/subscription');
}

export async function createBillingCheckoutSession(payload: BillingCheckoutRequest) {
  return apiClient<BillingCheckoutSessionResponse>('/billing/checkout-session', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export async function openBillingPortal() {
  return apiClient<BillingPortalSessionResponse>('/billing/customer-portal-session', {
    method: 'POST',
  });
}

export async function changeBillingPlan(payload: BillingCheckoutRequest) {
  return apiClient<BillingPortalSessionResponse>('/billing/change-plan', {
    method: 'POST',
    body: JSON.stringify({ target_plan_code: payload.plan_code }),
  });
}

export async function cancelBillingSubscription() {
  return apiClient<BillingPortalSessionResponse>('/billing/cancel-subscription', {
    method: 'POST',
  });
}
