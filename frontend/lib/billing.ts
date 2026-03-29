import type {
  BillingAccessState,
  BillingPlan,
  BillingPlanCode,
  BillingSubscriptionStatus,
} from '@/types/billing';

type BillingPresentation = {
  priceLabel: string;
  ctaLabel: string;
  highlight?: boolean;
  features: string[];
};

const BILLING_PRESENTATION: Record<BillingPlanCode, BillingPresentation> = {
  free: {
    priceLabel: 'AED 0 / month',
    ctaLabel: 'Start free',
    features: [
      'Catalog, inventory, sales, and returns',
      'Owner-managed setup',
      'Core dashboards',
      'Upgrade only when paid modules matter',
    ],
  },
  growth: {
    priceLabel: 'Growth monthly',
    ctaLabel: 'Start Growth',
    highlight: true,
    features: [
      'Finance, reports, customers, and purchases',
      'Integrations, AI review, and automation',
      'Stripe-hosted owner billing controls',
      'Full paid workspace access',
    ],
  },
  scale: {
    priceLabel: 'Scale monthly',
    ctaLabel: 'Start Scale',
    features: [
      'Everything in Growth',
      'Best fit for larger operational teams',
      'Ready for future limit expansion',
      'Same paid access in v1, stronger commercial tiering',
    ],
  },
};

export function getBillingPresentation(planCode: BillingPlanCode): BillingPresentation {
  return BILLING_PRESENTATION[planCode];
}

export function billingStatusTone(status: string | null | undefined) {
  if (!status) return 'info';
  if (status === 'active' || status === 'trialing') return 'success';
  if (status === 'past_due' || status === 'incomplete' || status === 'unpaid') return 'error';
  return 'info';
}

export function billingStatusLabel(status: BillingSubscriptionStatus | string | null | undefined) {
  if (!status) return 'Unknown';
  return status.replaceAll('_', ' ');
}

export function billingAccessStateLabel(accessState: BillingAccessState) {
  switch (accessState) {
    case 'free_active':
      return 'Free access';
    case 'paid_active':
      return 'Paid access';
    case 'read_only_grace':
      return 'Read-only grace';
    case 'blocked':
      return 'Blocked';
    default:
      return 'Unknown';
  }
}

export function sortBillingPlans(plans: BillingPlan[]) {
  return [...plans].sort((left, right) => left.sort_order - right.sort_order);
}
