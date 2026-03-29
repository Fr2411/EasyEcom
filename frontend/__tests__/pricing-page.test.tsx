import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, describe, expect, test, vi } from 'vitest';
import { PricingPage } from '@/components/billing/pricing-page';

const {
  pushMock,
  mockGetPublicBillingPlans,
  mockCreateBillingCheckoutSession,
  mockRedirectToExternalUrl,
} = vi.hoisted(() => ({
  pushMock: vi.fn(),
  mockGetPublicBillingPlans: vi.fn(),
  mockCreateBillingCheckoutSession: vi.fn(),
  mockRedirectToExternalUrl: vi.fn(),
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
  createBillingCheckoutSession: mockCreateBillingCheckoutSession,
}));

vi.mock('@/lib/navigation', () => ({
  redirectToExternalUrl: mockRedirectToExternalUrl,
}));

afterEach(() => {
  cleanup();
  pushMock.mockReset();
  mockGetPublicBillingPlans.mockReset();
  mockCreateBillingCheckoutSession.mockReset();
  mockRedirectToExternalUrl.mockReset();
});

describe('PricingPage', () => {
  test('routes the free plan to signup and paid plans to checkout sessions', async () => {
    mockGetPublicBillingPlans.mockResolvedValue({
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
      ],
    });
    mockCreateBillingCheckoutSession.mockResolvedValue({ checkout_url: 'https://checkout.stripe.test/session' });

    render(<PricingPage />);

    await waitFor(() => expect(screen.getByRole('button', { name: 'Start free' })).toBeTruthy());

    fireEvent.click(screen.getByRole('button', { name: 'Start free' }));
    expect(pushMock).toHaveBeenCalledWith('/signup');

    fireEvent.click(screen.getByRole('button', { name: 'Start Growth' }));

    await waitFor(() =>
      expect(mockCreateBillingCheckoutSession).toHaveBeenCalledWith({ plan_code: 'growth' })
    );
    expect(mockRedirectToExternalUrl).toHaveBeenCalledWith('https://checkout.stripe.test/session');
  });
});
