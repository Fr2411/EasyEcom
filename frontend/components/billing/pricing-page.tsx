'use client';

import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { useEffect, useState } from 'react';
import { BadgeCheck, Sparkles } from 'lucide-react';
import { PublicLayout } from '@/components/layout/public-layout';
import { ApiError } from '@/lib/api/client';
import { createBillingCheckoutSession, getPublicBillingPlans } from '@/lib/api/billing';
import { redirectToExternalUrl } from '@/lib/navigation';
import { getBillingPresentation, sortBillingPlans } from '@/lib/billing';
import type { BillingPlan, BillingPlanCode } from '@/types/billing';

function PricingAction({
  plan,
  busy,
  onClick,
}: {
  plan: BillingPlan;
  busy: boolean;
  onClick: (planCode: BillingPlanCode) => void;
}) {
  const presentation = getBillingPresentation(plan.plan_code);

  return (
    <article className={presentation.highlight ? 'pricing-card highlighted' : 'pricing-card'}>
      <div className="pricing-card-head">
        <div>
          <p className="pricing-card-kicker">{plan.display_name}</p>
          <h3>{presentation.priceLabel}</h3>
          <p>{plan.public_description}</p>
        </div>
        {presentation.highlight ? <span className="pricing-highlight"><Sparkles size={14} aria-hidden="true" />Recommended</span> : null}
      </div>
      <ul className="pricing-feature-list">
        {presentation.features.map((feature) => (
          <li key={feature}>
            <BadgeCheck size={14} aria-hidden="true" />
            <span>{feature}</span>
          </li>
        ))}
      </ul>
      <button
        type="button"
        className={presentation.highlight ? 'btn-primary' : 'secondary'}
        disabled={busy}
        onClick={() => onClick(plan.plan_code)}
      >
        {busy ? 'Opening…' : presentation.ctaLabel}
      </button>
    </article>
  );
}

export function PricingPage() {
  const router = useRouter();
  const [plans, setPlans] = useState<BillingPlan[]>([]);
  const [busyPlan, setBusyPlan] = useState<BillingPlanCode | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    let cancelled = false;

    async function loadPlans() {
      setLoading(true);
      try {
        const response = await getPublicBillingPlans();
        if (!cancelled) {
          setPlans(sortBillingPlans(response.items));
          setError('');
        }
      } catch (loadError) {
        if (!cancelled) {
          setError(loadError instanceof Error ? loadError.message : 'Unable to load public pricing.');
        }
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    }

    void loadPlans();
    return () => {
      cancelled = true;
    };
  }, []);

  const startCheckout = async (planCode: BillingPlanCode) => {
    if (planCode === 'free') {
      router.push('/signup');
      return;
    }

    setBusyPlan(planCode);
    setError('');
    try {
      const { checkout_url } = await createBillingCheckoutSession({ plan_code: planCode });
      redirectToExternalUrl(checkout_url);
    } catch (checkoutError) {
      if (checkoutError instanceof ApiError && checkoutError.status === 401) {
        router.push('/signup');
        return;
      }
      setError(checkoutError instanceof Error ? checkoutError.message : 'Unable to start checkout right now.');
    } finally {
      setBusyPlan(null);
    }
  };

  return (
    <PublicLayout>
      <main className="pricing-page">
        <section className="pricing-hero">
          <p className="pricing-eyebrow">Pricing</p>
          <h1>Simple pricing that grows with you</h1>
          <p className="pricing-lead">
            Start free, upgrade when you grow, and keep billing simple with Stripe-hosted checkout and verified subscription access.
          </p>
          <div className="pricing-hero-actions">
            <Link href="/signup" className="button-link btn-primary">
              Start Free
            </Link>
            <Link href="/login" className="button-link secondary">
              Login
            </Link>
          </div>
          {error ? <p className="pricing-error" role="alert">{error}</p> : null}
        </section>

        {loading ? (
          <section className="pricing-grid" aria-label="Plan comparison">
            <article className="pricing-card">
              <p>Loading plans…</p>
            </article>
          </section>
        ) : (
          <section className="pricing-grid" aria-label="Plan comparison">
            {plans.map((plan) => (
              <PricingAction
                key={plan.plan_code}
                plan={plan}
                busy={busyPlan === plan.plan_code}
                onClick={startCheckout}
              />
            ))}
          </section>
        )}

        <section className="pricing-footnote-card">
          <div>
            <p className="eyebrow">Billing flow</p>
            <h2>EasyEcom unlocks paid access only after verified Stripe webhook events confirm subscription state.</h2>
          </div>
          <div className="pricing-footnote-points">
            <span>Stripe-hosted checkout</span>
            <span>Webhook-driven activation</span>
            <span>No card data stored in EasyEcom</span>
          </div>
        </section>
      </main>
    </PublicLayout>
  );
}
