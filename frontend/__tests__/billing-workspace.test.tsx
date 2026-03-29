import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, describe, expect, test, vi } from 'vitest';
import { BillingWorkspace } from '@/components/billing/billing-workspace';

const {
  mockGetBillingSubscription,
  mockGetPublicBillingPlans,
  mockCreateBillingCheckoutSession,
  mockChangeBillingPlan,
  mockCancelBillingSubscription,
  mockOpenBillingPortal,
  mockRedirectToExternalUrl,
} = vi.hoisted(() => ({
  mockGetBillingSubscription: vi.fn(),
  mockGetPublicBillingPlans: vi.fn(),
  mockCreateBillingCheckoutSession: vi.fn(),
  mockChangeBillingPlan: vi.fn(),
  mockCancelBillingSubscription: vi.fn(),
  mockOpenBillingPortal: vi.fn(),
  mockRedirectToExternalUrl: vi.fn(),
}));

vi.mock('@/lib/api/billing', () => ({
  getBillingSubscription: mockGetBillingSubscription,
  getPublicBillingPlans: mockGetPublicBillingPlans,
  createBillingCheckoutSession: mockCreateBillingCheckoutSession,
  changeBillingPlan: mockChangeBillingPlan,
  cancelBillingSubscription: mockCancelBillingSubscription,
  openBillingPortal: mockOpenBillingPortal,
}));

vi.mock('@/lib/navigation', () => ({
  redirectToExternalUrl: mockRedirectToExternalUrl,
}));

function plansFixture() {
  return {
    items: [
      {
        plan_code: 'free',
        display_name: 'Free',
        is_paid: false,
        currency_code: 'AED',
        interval: 'monthly',
        sort_order: 10,
        public_description: 'Start small',
      },
      {
        plan_code: 'growth',
        display_name: 'Growth',
        is_paid: true,
        currency_code: 'AED',
        interval: 'monthly',
        sort_order: 20,
        public_description: 'Scale with finance',
      },
      {
        plan_code: 'scale',
        display_name: 'Scale',
        is_paid: true,
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
    current_period_start: '2026-03-01T00:00:00+00:00',
    current_period_end: '2026-04-01T00:00:00+00:00',
    grace_until: null,
    stripe_customer_id: 'cus_123',
    stripe_subscription_id: 'sub_123',
    portal_available: true,
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
  mockCreateBillingCheckoutSession.mockReset();
  mockChangeBillingPlan.mockReset();
  mockCancelBillingSubscription.mockReset();
  mockOpenBillingPortal.mockReset();
  mockRedirectToExternalUrl.mockReset();
});

describe('BillingWorkspace', () => {
  test('opens Stripe redirects for portal, plan changes, and cancel actions', async () => {
    mockGetBillingSubscription.mockResolvedValue(subscriptionFixture());
    mockGetPublicBillingPlans.mockResolvedValue(plansFixture());
    mockOpenBillingPortal.mockResolvedValue({ portal_url: 'https://portal.stripe.test/session' });
    mockChangeBillingPlan.mockResolvedValue({ portal_url: 'https://billing.stripe.test/change' });
    mockCancelBillingSubscription.mockResolvedValue({ portal_url: 'https://billing.stripe.test/cancel' });

    render(<BillingWorkspace />);

    await waitFor(() => expect(screen.getByRole('button', { name: 'Open billing portal' })).toBeTruthy());

    fireEvent.click(screen.getByRole('button', { name: 'Open billing portal' }));
    await waitFor(() => expect(mockOpenBillingPortal).toHaveBeenCalledTimes(1));
    expect(mockRedirectToExternalUrl).toHaveBeenCalledWith('https://portal.stripe.test/session');

    fireEvent.click(screen.getByRole('button', { name: 'Start Scale' }));
    await waitFor(() => expect(mockChangeBillingPlan).toHaveBeenCalledWith({ plan_code: 'scale' }));
    expect(mockRedirectToExternalUrl).toHaveBeenCalledWith('https://billing.stripe.test/change');

    fireEvent.click(screen.getByRole('button', { name: 'Cancel subscription' }));
    await waitFor(() => expect(mockCancelBillingSubscription).toHaveBeenCalledTimes(1));
    expect(mockRedirectToExternalUrl).toHaveBeenCalledWith('https://billing.stripe.test/cancel');
  });

  test('uses checkout for a free tenant upgrading into a paid plan', async () => {
    mockGetBillingSubscription.mockResolvedValue(subscriptionFixture({ plan_code: 'free', plan_name: 'Free', billing_status: 'free', billing_access_state: 'free_active', stripe_customer_id: null, stripe_subscription_id: null, portal_available: false, can_upgrade: true, can_manage_subscription: false, paid_modules_locked: ['Finance', 'Reports'] }));
    mockGetPublicBillingPlans.mockResolvedValue(plansFixture());
    mockCreateBillingCheckoutSession.mockResolvedValue({ checkout_url: 'https://checkout.stripe.test/session' });

    render(<BillingWorkspace />);

    await waitFor(() => expect(screen.getByRole('button', { name: 'Start Growth' })).toBeTruthy());
    fireEvent.click(screen.getByRole('button', { name: 'Start Growth' }));

    await waitFor(() => expect(mockCreateBillingCheckoutSession).toHaveBeenCalledWith({ plan_code: 'growth' }));
    expect(mockRedirectToExternalUrl).toHaveBeenCalledWith('https://checkout.stripe.test/session');
    expect(screen.getByText('Finance')).toBeTruthy();
  });
});
