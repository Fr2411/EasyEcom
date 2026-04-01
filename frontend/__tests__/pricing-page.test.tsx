import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, describe, expect, test, vi } from 'vitest';
import { PricingPage } from '@/components/billing/pricing-page';

const {
  pushMock,
  mockGetPublicBillingPlans,
} = vi.hoisted(() => ({
  pushMock: vi.fn(),
  mockGetPublicBillingPlans: vi.fn(),
}));

vi.mock('next/navigation', () => ({
  useRouter: () => ({ push: pushMock }),
}));

vi.mock('@/components/theme/theme-toggle', () => ({
  ThemeToggle: () => <div>Theme toggle</div>,
}));

vi.mock('@/components/branding/easy-ecom-logo', () => ({
  EasyEcomLogo: () => <div>EasyEcom Logo</div>,
}));

vi.mock('@/lib/api/billing', () => ({
  getPublicBillingPlans: mockGetPublicBillingPlans,
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

afterEach(() => {
  cleanup();
  pushMock.mockReset();
  mockGetPublicBillingPlans.mockReset();
});

describe('PricingPage', () => {
  test('routes the free plan to signup and renders PayPal CTA for paid plans', async () => {
    mockGetPublicBillingPlans.mockResolvedValue({
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
      ],
    });

    render(<PricingPage />);

    await waitFor(() => expect(screen.getByRole('button', { name: 'Start free' })).toBeTruthy());

    fireEvent.click(screen.getByRole('button', { name: 'Start free' }));
    expect(pushMock).toHaveBeenCalledWith('/signup');
    expect(screen.getByRole('button', { name: 'Start Growth' })).toBeTruthy();
  });
});
