'use client';

import { useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { useAuth } from '@/components/auth/auth-provider';

type AuthRouteGuardProps = {
  mode: 'protected' | 'public-only';
  children: React.ReactNode;
};

export function AuthRouteGuard({ mode, children }: AuthRouteGuardProps) {
  const router = useRouter();
  const { user, loading, bootstrapError } = useAuth();

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

  if (mode === 'protected' && (loading || bootstrapError === 'unauthorized')) {
    return null;
  }

  if (mode === 'public-only' && user) {
    return null;
  }

  return <>{children}</>;
}
