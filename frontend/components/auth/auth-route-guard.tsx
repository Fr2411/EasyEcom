'use client';

import { useEffect } from 'react';
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

  if (mode === 'protected') {
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
