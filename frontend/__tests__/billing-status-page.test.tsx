import { cleanup, render, screen, waitFor } from '@testing-library/react';
import { afterEach, describe, expect, test, vi } from 'vitest';
import { BillingStatusPage } from '@/components/billing/billing-status-page';

const { mockGetBillingSubscription } = vi.hoisted(() => ({
  mockGetBillingSubscription: vi.fn(),
}));

vi.mock('@/lib/api/billing', () => ({
  getBillingSubscription: mockGetBillingSubscription,
}));

afterEach(() => {
  cleanup();
  mockGetBillingSubscription.mockReset();
});

describe('BillingStatusPage', () => {
  test('renders backend trust state on the success page', async () => {
    mockGetBillingSubscription.mockResolvedValue({
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
    });

    render(<BillingStatusPage mode="success" />);

    await waitFor(() => expect(screen.getByText('Billing success')).toBeTruthy());
    expect(screen.getAllByText('Growth').length).toBeGreaterThan(0);
    expect(screen.getByRole('link', { name: 'Open billing workspace' })).toBeTruthy();
  });

  test('shows grace/locked state on the cancel page without assuming outcome', async () => {
    mockGetBillingSubscription.mockResolvedValue({
      plan_code: 'growth',
      plan_name: 'Growth',
      billing_status: 'past_due',
      billing_access_state: 'read_only_grace',
      cancel_at_period_end: true,
      cancel_effective_at: '2026-04-01T00:00:00+00:00',
      current_period_start: '2026-03-01T00:00:00+00:00',
      current_period_end: '2026-04-01T00:00:00+00:00',
      grace_until: '2026-04-08T00:00:00+00:00',
      billing_provider: 'paypal',
      provider_customer_id: 'payer_123',
      provider_subscription_id: 'I-123',
      can_upgrade: false,
      can_manage_subscription: true,
      paid_modules_locked: ['Finance', 'Reports'],
    });

    render(<BillingStatusPage mode="cancel" />);

    await waitFor(() => expect(screen.getByText('Billing cancelled')).toBeTruthy());
    expect(screen.getAllByText('Read-only grace').length).toBeGreaterThan(0);
    expect(screen.getByText('2 paid modules are currently locked.')).toBeTruthy();
  });
});
