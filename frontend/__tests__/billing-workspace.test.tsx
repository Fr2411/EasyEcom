import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, describe, expect, test, vi } from 'vitest';
import { BillingWorkspace } from '@/components/billing/billing-workspace';

const {
  mockGetBillingSubscription,
  mockGetPublicBillingPlans,
  mockChangeBillingPlan,
  mockCancelBillingSubscription,
  mockRedirectToExternalUrl,
} = vi.hoisted(() => ({
  mockGetBillingSubscription: vi.fn(),
  mockGetPublicBillingPlans: vi.fn(),
  mockChangeBillingPlan: vi.fn(),
  mockCancelBillingSubscription: vi.fn(),
  mockRedirectToExternalUrl: vi.fn(),
}));

vi.mock('@/lib/api/billing', () => ({
  getBillingSubscription: mockGetBillingSubscription,
  getPublicBillingPlans: mockGetPublicBillingPlans,
  changeBillingPlan: mockChangeBillingPlan,
  cancelBillingSubscription: mockCancelBillingSubscription,
}));

vi.mock('@/lib/navigation', () => ({
  redirectToExternalUrl: mockRedirectToExternalUrl,
}));

vi.mock('@/components/auth/auth-provider', () => ({
  useAuth: () => ({
    user: { client_id: 'client-1', roles: ['CLIENT_OWNER'] },
    loading: false,
    bootstrapError: 'none',
    refreshAuth: vi.fn(),
    clearAuth: vi.fn(),
  }),
}));

vi.mock('@/components/billing/paypal-subscribe-button', () => ({
  PaypalSubscribeButton: ({ plan }: { plan: { display_name: string } }) => <button type="button">Start {plan.display_name}</button>,
}));

function plansFixture() {
  return {
    items: [
      {
        plan_code: 'free',
        display_name: 'Free',
        is_paid: false,
        billing_provider: 'paypal',
        provider_plan_id: null,
        currency_code: 'AED',
        interval: 'monthly',
        sort_order: 10,
        public_description: 'Start small',
      },
      {
        plan_code: 'growth',
        display_name: 'Growth',
        is_paid: true,
        billing_provider: 'paypal',
        provider_plan_id: 'P-growth',
        currency_code: 'AED',
        interval: 'monthly',
        sort_order: 20,
        public_description: 'Scale with finance',
      },
      {
        plan_code: 'scale',
        display_name: 'Scale',
        is_paid: true,
        billing_provider: 'paypal',
        provider_plan_id: 'P-scale',
        currency_code: 'AED',
        interval: 'monthly',
        sort_order: 30,
        public_description: 'Multi-location',
      },
    ],
  };
}

function subscriptionFixture(overrides?: Record<string, unknown>) {
  return {
    plan_code: 'growth',
    plan_name: 'Growth',
    billing_status: 'active',
    billing_access_state: 'paid_active',
    cancel_at_period_end: false,
    cancel_effective_at: null,
    current_period_start: '2026-03-01T00:00:00+00:00',
    current_period_end: '2026-04-01T00:00:00+00:00',
    grace_until: null,
    billing_provider: 'paypal',
    provider_customer_id: 'payer_123',
    provider_subscription_id: 'I-123',
    can_upgrade: false,
    can_manage_subscription: true,
    paid_modules_locked: [],
    ...overrides,
  };
}

afterEach(() => {
  cleanup();
  mockGetBillingSubscription.mockReset();
  mockGetPublicBillingPlans.mockReset();
  mockChangeBillingPlan.mockReset();
  mockCancelBillingSubscription.mockReset();
  mockRedirectToExternalUrl.mockReset();
});

describe('BillingWorkspace', () => {
  test('opens hosted billing redirects for plan changes and keeps cancellation local to the cycle end', async () => {
    mockGetBillingSubscription.mockResolvedValue(subscriptionFixture());
    mockGetPublicBillingPlans.mockResolvedValue(plansFixture());
    mockChangeBillingPlan.mockResolvedValue({ action_url: 'https://billing.paypal.test/change', status: 'plan_change_requested' });
    mockCancelBillingSubscription.mockResolvedValue({ action_url: null, status: 'cancellation_scheduled' });

    render(<BillingWorkspace />);

    await waitFor(() => expect(screen.getByRole('button', { name: 'Start Scale' })).toBeTruthy());

    fireEvent.click(screen.getByRole('button', { name: 'Start Scale' }));
    await waitFor(() => expect(mockChangeBillingPlan).toHaveBeenCalledWith({ plan_code: 'scale' }));
    expect(mockRedirectToExternalUrl).toHaveBeenCalledWith('https://billing.paypal.test/change');

    fireEvent.click(screen.getByRole('button', { name: 'Cancel at period end' }));
    await waitFor(() => expect(mockCancelBillingSubscription).toHaveBeenCalledTimes(1));
  });

  test('renders PayPal CTA for a free tenant upgrading into a paid plan', async () => {
    mockGetBillingSubscription.mockResolvedValue(subscriptionFixture({ plan_code: 'free', plan_name: 'Free', billing_status: 'free', billing_access_state: 'free_active', provider_customer_id: null, provider_subscription_id: null, can_upgrade: true, can_manage_subscription: false, paid_modules_locked: ['Reports'] }));
    mockGetPublicBillingPlans.mockResolvedValue(plansFixture());

    render(<BillingWorkspace />);

    await waitFor(() => expect(screen.getByRole('button', { name: 'Start Growth' })).toBeTruthy());
    expect(screen.getByText('Reports')).toBeTruthy();
  });
});
