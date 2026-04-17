'use client';

import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { useAuth } from '@/components/auth/auth-provider';

type AuthRouteGuardProps = {
  mode: 'protected' | 'public-only';
  children: React.ReactNode;
};

function AuthLoadingState({ message }: { message: string }) {
  return (
    <main className="auth-feedback" role="status" aria-live="polite">
      <div className="auth-feedback-card">
        <h1>Checking your session…</h1>
        <p>{message}</p>
      </div>
    </main>
  );
}

function AuthErrorState({ message, onRetry }: { message: string; onRetry: () => void }) {
  return (
    <main className="auth-feedback" role="alert" aria-live="assertive">
      <div className="auth-feedback-card auth-feedback-card-error">
        <h1>We could not verify your session</h1>
        <p>{message}</p>
        <button type="button" onClick={onRetry}>
          Retry
        </button>
      </div>
    </main>
  );
}

export function AuthRouteGuard({ mode, children }: AuthRouteGuardProps) {
  const router = useRouter();
  const { user, loading, bootstrapError, refreshAuth } = useAuth();
  const [loadingExceededThreshold, setLoadingExceededThreshold] = useState(false);

  useEffect(() => {
    if (loading) {
      return;
    }

    if (mode === 'protected' && bootstrapError === 'unauthorized') {
      router.replace('/login');
      return;
    }

    if (mode === 'public-only' && user) {
      router.replace('/dashboard');
    }
  }, [bootstrapError, loading, mode, router, user]);

  useEffect(() => {
    if (mode !== 'protected' || !loading) {
      setLoadingExceededThreshold(false);
      return undefined;
    }
    const timeoutId = window.setTimeout(() => setLoadingExceededThreshold(true), 12000);
    return () => window.clearTimeout(timeoutId);
  }, [loading, mode]);

  if (mode === 'protected') {
    if (loadingExceededThreshold) {
      return (
        <AuthErrorState
          message="Session check is taking longer than expected. Retry once. If it keeps failing, check network quality and backend session health."
          onRetry={refreshAuth}
        />
      );
    }

    if (loading) {
      return <AuthLoadingState message="Loading your workspace..." />;
    }

    if (bootstrapError === 'unauthorized') {
      return <AuthLoadingState message="Redirecting to login..." />;
    }

    if (bootstrapError !== 'none') {
      return (
        <AuthErrorState
          message="Please retry. If this persists, your network or backend session endpoint may be unavailable."
          onRetry={refreshAuth}
        />
      );
    }
  }

  if (mode === 'public-only' && user) {
    return <AuthLoadingState message="You are already signed in. Redirecting to dashboard..." />;
  }

  return <>{children}</>;
}
