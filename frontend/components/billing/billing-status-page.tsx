'use client';

import Link from 'next/link';
import { useEffect, useState } from 'react';
import { AlertTriangle, BadgeCheck } from 'lucide-react';
import {
  billingAccessStateLabel,
  billingStatusLabel,
  billingStatusTone,
} from '@/lib/billing';
import { getBillingSubscription } from '@/lib/api/billing';
import type { BillingSubscriptionState } from '@/types/billing';
import { formatDateTime } from '@/lib/commerce-format';
import {
  DraftRecommendationCard,
  StagedActionFooter,
  WorkspaceEmpty,
  WorkspaceNotice,
  WorkspacePanel,
} from '@/components/commerce/workspace-primitives';

type BillingStatusPageMode = 'success' | 'cancel';

export function BillingStatusPage({ mode }: { mode: BillingStatusPageMode }) {
  const [subscription, setSubscription] = useState<BillingSubscriptionState | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    let cancelled = false;

    async function loadSubscription() {
      setLoading(true);
      try {
        const payload = await getBillingSubscription();
        if (!cancelled) {
          setSubscription(payload);
          setError('');
        }
      } catch (loadError) {
        if (!cancelled) {
          setError(loadError instanceof Error ? loadError.message : 'Unable to load billing state.');
        }
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    }

    void loadSubscription();
    return () => {
      cancelled = true;
    };
  }, []);

  const currentTone = billingStatusTone(subscription?.billing_status);
  const heading = mode === 'success' ? 'Billing success' : 'Billing cancelled';
  const description =
    mode === 'success'
      ? 'Stripe has returned you to the app, but EasyEcom waits for verified backend subscription state before granting paid access.'
      : 'Checkout or portal flow was exited. This page shows the live backend subscription state rather than assuming anything changed.';

  if (loading && !subscription) {
    return <div className="reports-loading">Loading billing state…</div>;
  }
  if (error && !subscription) {
    return <div className="reports-error">{error}</div>;
  }
  if (!subscription) {
    return <WorkspaceEmpty title="Billing state unavailable" message="No billing state was returned for this tenant." />;
  }

  return (
    <div className="billing-status-page">
      <WorkspaceNotice tone={currentTone}>
        {mode === 'success' ? 'Stripe checkout returned successfully.' : 'Stripe flow was cancelled.'} Backend subscription state remains the source of truth.
      </WorkspaceNotice>
      {error ? <WorkspaceNotice tone="error">{error}</WorkspaceNotice> : null}

      <div className="billing-status-grid">
        <WorkspacePanel title={heading} description={description}>
          <DraftRecommendationCard
            title={subscription.plan_name}
            summary={`Status: ${billingStatusLabel(subscription.billing_status)}. ${subscription.cancel_at_period_end ? 'Cancellation is scheduled at period end.' : 'No cancellation is scheduled.'}`}
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

          <StagedActionFooter summary="This page never upgrades the tenant by itself. It only reflects the verified backend view after Stripe redirects back.">
            <Link href="/billing" className="button-link secondary">
              Open billing workspace
            </Link>
            <Link href="/dashboard" className="button-link btn-primary">
              Return to dashboard
            </Link>
          </StagedActionFooter>
        </WorkspacePanel>

        <WorkspacePanel title="Status checks" description="These cards reflect what the backend currently believes about billing access.">
          <div className="billing-summary-list">
            <article className="billing-summary-card">
              <BadgeCheck size={16} aria-hidden="true" />
              <strong>{billingStatusLabel(subscription.billing_status)}</strong>
              <p>{subscription.plan_name}</p>
            </article>
            <article className="billing-summary-card">
              <AlertTriangle size={16} aria-hidden="true" />
              <strong>{billingAccessStateLabel(subscription.billing_access_state)}</strong>
              <p>
                {subscription.paid_modules_locked.length
                  ? `${subscription.paid_modules_locked.length} paid modules are currently locked.`
                  : 'No paid modules are currently locked.'}
              </p>
            </article>
          </div>
        </WorkspacePanel>
      </div>
    </div>
  );
}
