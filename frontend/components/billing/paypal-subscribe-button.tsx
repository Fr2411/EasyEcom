'use client';

import { useEffect, useMemo, useRef, useState } from 'react';
import { useRouter } from 'next/navigation';
import { useAuth } from '@/components/auth/auth-provider';
import { getPublicBillingConfig } from '@/lib/api/billing';
import type { BillingPlan } from '@/types/billing';

declare global {
  interface Window {
    paypal?: {
      Buttons: (config: {
        style?: Record<string, unknown>;
        createSubscription: (data: unknown, actions: { subscription: { create: (payload: Record<string, unknown>) => Promise<string> } }) => Promise<string>;
        onApprove?: () => void;
        onError?: (error: unknown) => void;
      }) => { render: (selector: HTMLElement) => Promise<void> | void };
    };
  }
}

type PaypalConfig = {
  billing_provider: string;
  paypal_client_id: string | null;
  paypal_enabled: boolean;
};

type Props = {
  plan: BillingPlan;
  className?: string;
  onError: (message: string) => void;
};

function loadPaypalSdk(clientId: string) {
  const existing = document.querySelector<HTMLScriptElement>('script[data-paypal-sdk="true"]');
  if (existing) {
    return Promise.resolve();
  }

  return new Promise<void>((resolve, reject) => {
    const script = document.createElement('script');
    script.src = `https://www.paypal.com/sdk/js?client-id=${encodeURIComponent(clientId)}&components=buttons&vault=true&intent=subscription`;
    script.async = true;
    script.dataset.paypalSdk = 'true';
    script.onload = () => resolve();
    script.onerror = () => reject(new Error('Unable to load PayPal right now.'));
    document.head.appendChild(script);
  });
}

export function PaypalSubscribeButton({ plan, className, onError }: Props) {
  const router = useRouter();
  const { user } = useAuth();
  const containerRef = useRef<HTMLDivElement | null>(null);
  const renderedRef = useRef(false);
  const [config, setConfig] = useState<PaypalConfig | null>(null);
  const [loading, setLoading] = useState(true);

  const canRenderButton = useMemo(() => {
    return Boolean(
      user &&
      user.roles.includes('CLIENT_OWNER') &&
      plan.plan_code !== 'free' &&
      plan.provider_plan_id &&
      config?.paypal_enabled &&
      config?.paypal_client_id
    );
  }, [config?.paypal_client_id, config?.paypal_enabled, plan.plan_code, plan.provider_plan_id, user]);

  useEffect(() => {
    let cancelled = false;
    async function loadConfig() {
      try {
        const payload = await getPublicBillingConfig();
        if (!cancelled) setConfig(payload);
      } catch (error) {
        if (!cancelled) {
          onError(error instanceof Error ? error.message : 'Unable to load PayPal billing settings.');
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    }
    void loadConfig();
    return () => {
      cancelled = true;
    };
  }, [onError]);

  useEffect(() => {
    if (!canRenderButton || !containerRef.current || renderedRef.current || !config?.paypal_client_id) {
      return;
    }

    let cancelled = false;
    void loadPaypalSdk(config.paypal_client_id)
      .then(() => {
        if (cancelled || !containerRef.current || !window.paypal) return;
        renderedRef.current = true;
        window.paypal
          .Buttons({
            style: { shape: 'pill', layout: 'vertical', color: 'gold', label: 'subscribe' },
            createSubscription(_data, actions) {
              return actions.subscription.create({
                plan_id: plan.provider_plan_id,
                custom_id: user?.client_id,
              });
            },
            onApprove() {
              router.push('/billing/success');
            },
            onError(error) {
              onError(error instanceof Error ? error.message : 'PayPal approval could not be started.');
            },
          })
          .render(containerRef.current);
      })
      .catch((error) => onError(error instanceof Error ? error.message : 'Unable to load PayPal.'));

    return () => {
      cancelled = true;
    };
  }, [canRenderButton, config?.paypal_client_id, onError, plan.provider_plan_id, router, user?.client_id]);

  if (!user) {
    return (
      <button type="button" className={className ?? 'btn-primary'} onClick={() => router.push('/signup')}>
        Start Free
      </button>
    );
  }

  if (!user.roles.includes('CLIENT_OWNER')) {
    return (
      <button type="button" className={className ?? 'secondary'} onClick={() => router.push('/billing')}>
        Owner approval required
      </button>
    );
  }

  if (loading) {
    return <button type="button" className={className ?? 'btn-primary'} disabled>Loading PayPal…</button>;
  }

  if (!canRenderButton) {
    return <button type="button" className={className ?? 'secondary'} disabled>PayPal unavailable</button>;
  }

  return <div ref={containerRef} className="paypal-subscribe-button" />;
}
