'use client';

import Link from 'next/link';
import { useEffect, useMemo, useState } from 'react';
import { BadgeCheck } from 'lucide-react';
import {
  billingAccessStateLabel,
  billingStatusLabel,
  billingStatusTone,
  getBillingPresentation,
  sortBillingPlans,
} from '@/lib/billing';
import {
  cancelBillingSubscription,
  changeBillingPlan,
  createBillingCheckoutSession,
  getBillingSubscription,
  getPublicBillingPlans,
  openBillingPortal,
} from '@/lib/api/billing';
import { redirectToExternalUrl } from '@/lib/navigation';
import type { BillingPlan, BillingPlanCode, BillingSubscriptionState } from '@/types/billing';
import { formatDateTime } from '@/lib/commerce-format';
import {
  DraftRecommendationCard,
  StagedActionFooter,
  WorkspaceEmpty,
  WorkspaceNotice,
  WorkspacePanel,
} from '@/components/commerce/workspace-primitives';
import { ApiError, ApiNetworkError } from '@/lib/api/client';

type BillingWorkspaceState = {
  subscription: BillingSubscriptionState;
  plans: BillingPlan[];
};

function actionErrorMessage(error: unknown, fallback: string) {
  if (error instanceof ApiError && error.status === 401) {
    return 'Your session expired while opening billing. Please sign in again.';
  }
  if (error instanceof ApiNetworkError) {
    return fallback;
  }
  return error instanceof Error ? error.message : fallback;
}

function PlanCard({
  plan,
  currentPlanCode,
  disabled,
  busy,
  onSelect,
}: {
  plan: BillingPlan;
  currentPlanCode: BillingPlanCode;
  disabled: boolean;
  busy: boolean;
  onSelect: (planCode: BillingPlanCode) => void;
}) {
  const current = currentPlanCode === plan.plan_code;
  const presentation = getBillingPresentation(plan.plan_code);

  return (
    <article className={current ? 'billing-plan-card active' : 'billing-plan-card'}>
      <div className="billing-plan-card-head">
        <div>
          <p className="eyebrow">{current ? 'Current plan' : 'Plan'}</p>
          <h4>{plan.display_name}</h4>
          <p>{plan.public_description}</p>
        </div>
        {presentation.highlight ? <span className="billing-plan-highlight">Recommended</span> : null}
      </div>
      <strong className="billing-plan-price">{presentation.priceLabel}</strong>
      <ul className="billing-plan-features">
        {presentation.features.map((feature) => (
          <li key={feature}>
            <BadgeCheck size={14} aria-hidden="true" />
            <span>{feature}</span>
          </li>
        ))}
      </ul>
      <button
        type="button"
        className={current ? 'secondary' : 'btn-primary'}
        disabled={disabled || busy || current || plan.plan_code === 'free'}
        onClick={() => onSelect(plan.plan_code)}
      >
        {current ? 'Current plan' : busy ? 'Working…' : presentation.ctaLabel}
      </button>
    </article>
  );
}

export function BillingWorkspace() {
  const [workspace, setWorkspace] = useState<BillingWorkspaceState | null>(null);
  const [loading, setLoading] = useState(true);
  const [busyAction, setBusyAction] = useState<string | null>(null);
  const [error, setError] = useState('');

  async function loadWorkspace() {
    setLoading(true);
    try {
      const [subscription, plansResponse] = await Promise.all([
        getBillingSubscription(),
        getPublicBillingPlans(),
      ]);
      setWorkspace({
        subscription,
        plans: sortBillingPlans(plansResponse.items),
      });
      setError('');
    } catch (loadError) {
      setError(actionErrorMessage(loadError, 'Unable to load billing workspace.'));
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void loadWorkspace();
  }, []);

  const subscription = workspace?.subscription ?? null;
  const plans = workspace?.plans ?? [];
  const currentPlanCode = subscription?.plan_code ?? 'free';
  const currentPlanPresentation = getBillingPresentation(currentPlanCode);
  const currentStatusTone = billingStatusTone(subscription?.billing_status);
  const currentStatusLabel = billingStatusLabel(subscription?.billing_status);

  const setBusyAndRedirect = async (
    actionLabel: string,
    request: () => Promise<{ checkout_url?: string; portal_url?: string }>
  ) => {
    setBusyAction(actionLabel);
    setError('');
    try {
      const payload = await request();
      const url = payload.checkout_url ?? payload.portal_url;
      if (!url) {
        throw new Error('Billing redirect URL was not returned by the backend.');
      }
      redirectToExternalUrl(url);
    } catch (actionError) {
      setError(actionErrorMessage(actionError, 'Unable to open billing action right now.'));
    } finally {
      setBusyAction(null);
    }
  };

  const handlePlanSelect = async (planCode: BillingPlanCode) => {
    if (planCode === 'free') {
      return;
    }
    if (planCode === subscription?.plan_code) {
      return;
    }
    if (subscription?.plan_code === 'free') {
      await setBusyAndRedirect(`plan-${planCode}`, () => createBillingCheckoutSession({ plan_code: planCode }));
      return;
    }
    await setBusyAndRedirect(`plan-${planCode}`, () => changeBillingPlan({ plan_code: planCode }));
  };

  const handleOpenPortal = async () => {
    await setBusyAndRedirect('portal', openBillingPortal);
  };

  const handleCancel = async () => {
    await setBusyAndRedirect('cancel', cancelBillingSubscription);
  };

  const overviewCards = useMemo(
    () => [
      { label: 'Plan', value: subscription?.plan_name ?? 'Free', note: currentStatusLabel },
      { label: 'Access', value: billingAccessStateLabel(subscription?.billing_access_state ?? 'free_active'), note: subscription?.grace_until ? `Grace until ${formatDateTime(subscription.grace_until)}` : 'Derived from verified webhook state' },
      { label: 'Current period', value: subscription?.current_period_end ? formatDateTime(subscription.current_period_end) : 'Not set', note: subscription?.cancel_at_period_end ? 'Cancellation scheduled at period end' : 'Renews until changed' },
      { label: 'Portal', value: subscription?.portal_available ? 'Available' : 'Unavailable', note: subscription?.stripe_customer_id ? 'Stripe customer linked' : 'No Stripe customer yet' },
    ],
    [currentStatusLabel, subscription?.billing_access_state, subscription?.cancel_at_period_end, subscription?.current_period_end, subscription?.grace_until, subscription?.plan_name, subscription?.portal_available, subscription?.stripe_customer_id]
  );

  if (loading && !workspace) {
    return <div className="reports-loading">Loading billing workspace…</div>;
  }
  if (error && !workspace) {
    return <div className="reports-error">{error}</div>;
  }
  if (!workspace || !subscription) {
    return <WorkspaceEmpty title="Billing workspace unavailable" message="No billing data was returned for this tenant." />;
  }

  return (
    <div className="billing-module">
      {error ? <WorkspaceNotice tone="error">{error}</WorkspaceNotice> : null}

      <WorkspaceNotice tone={currentStatusTone}>
        {currentStatusLabel}. The workspace uses verified backend subscription state, not the Stripe redirect alone.
      </WorkspaceNotice>

      <div className="finance-cards billing-summary-grid">
        {overviewCards.map((card) => (
          <article key={card.label} className="ps-card">
            <p>{card.label}</p>
            <strong>{card.value}</strong>
            <span>{card.note}</span>
          </article>
        ))}
      </div>

      <div className="billing-layout">
        <WorkspacePanel
          title="Current subscription"
          description="Billing is owner-managed and Stripe-hosted. Paid access only activates after verified payment webhooks."
        >
          <DraftRecommendationCard
            title={subscription.plan_name}
            summary={`Status: ${currentStatusLabel}. ${subscription.cancel_at_period_end ? 'Cancellation is already scheduled.' : 'Manage the current subscription through Stripe-hosted actions.'}`}
            actions={
              <Link href="/pricing" className="button-link secondary">
                View public pricing
              </Link>
            }
          >
            <div className="settings-context billing-context">
              <div>
                <dt>Access state</dt>
                <dd>{billingAccessStateLabel(subscription.billing_access_state)}</dd>
              </div>
              <div>
                <dt>Period start</dt>
                <dd>{subscription.current_period_start ? formatDateTime(subscription.current_period_start) : 'Not set'}</dd>
              </div>
              <div>
                <dt>Period end</dt>
                <dd>{subscription.current_period_end ? formatDateTime(subscription.current_period_end) : 'Not set'}</dd>
              </div>
              <div>
                <dt>Grace until</dt>
                <dd>{subscription.grace_until ? formatDateTime(subscription.grace_until) : 'Not in grace'}</dd>
              </div>
            </div>
          </DraftRecommendationCard>

          <StagedActionFooter summary="Use Stripe portal for subscription management. EasyEcom never stores card data and never assumes the redirect proves payment.">
            <button
              type="button"
              className="secondary"
              onClick={handleCancel}
              disabled={busyAction === 'cancel' || !subscription.can_manage_subscription}
            >
              {busyAction === 'cancel' ? 'Opening…' : 'Cancel subscription'}
            </button>
            <button
              type="button"
              className="btn-primary"
              onClick={handleOpenPortal}
              disabled={busyAction === 'portal' || !subscription.portal_available}
            >
              {busyAction === 'portal' ? 'Opening…' : 'Open billing portal'}
            </button>
          </StagedActionFooter>
        </WorkspacePanel>

        <WorkspacePanel
          title="Plan comparison"
          description="Paid plan changes go through Stripe Checkout or the Stripe customer portal depending on current state."
        >
          <div className="billing-plan-grid">
            {plans.map((plan) => (
              <PlanCard
                key={plan.plan_code}
                plan={plan}
                currentPlanCode={currentPlanCode}
                disabled={busyAction !== null}
                busy={busyAction === `plan-${plan.plan_code}`}
                onSelect={handlePlanSelect}
              />
            ))}
          </div>
        </WorkspacePanel>
      </div>

      <WorkspacePanel
        title="Locked paid modules"
        description="Free or grace tenants lose paid entitlements, but the owner can still recover billing from this workspace."
      >
        {subscription.paid_modules_locked.length ? (
          <div className="billing-summary-list">
            {subscription.paid_modules_locked.map((moduleName) => (
              <article key={moduleName} className="billing-summary-card">
                <strong>{moduleName}</strong>
                <p>{subscription.billing_access_state === 'read_only_grace' ? 'Locked while payment recovery is pending.' : 'Requires a paid plan.'}</p>
              </article>
            ))}
          </div>
        ) : (
          <WorkspaceEmpty
            title="No paid modules locked"
            message={`${currentPlanPresentation.ctaLabel === 'Start free' ? 'Upgrade to a paid plan to unlock advanced modules.' : 'This tenant currently has paid module access.'}`}
          />
        )}
      </WorkspacePanel>
    </div>
  );
}
