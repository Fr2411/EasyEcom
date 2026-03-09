'use client';
import { createContext, useContext, useEffect, useState } from 'react';
import { getCurrentUser, type SessionUser } from '@/lib/api/auth';
import { ApiError, ApiNetworkError } from '@/lib/api/client';

type AuthBootstrapError = 'none' | 'unauthorized' | 'server' | 'network' | 'unknown';

const AuthContext = createContext<{ user: SessionUser | null; loading: boolean; bootstrapError: AuthBootstrapError }>({
  user: null,
  loading: true,
  bootstrapError: 'none'
});

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<SessionUser | null>(null);
  const [loading, setLoading] = useState(true);
  const [bootstrapError, setBootstrapError] = useState<AuthBootstrapError>('none');

  useEffect(() => {
    getCurrentUser()
      .then((currentUser) => {
        setUser(currentUser);
        setBootstrapError('none');
      })
      .catch((error: unknown) => {
        if (error instanceof ApiError && error.status === 401) {
          setUser(null);
          setBootstrapError('unauthorized');
          return;
        }

        if (error instanceof ApiError && error.status >= 500) {
          setBootstrapError('server');
          console.error('Auth bootstrap failed with server error', error);
          return;
        }

        if (error instanceof ApiNetworkError) {
          setBootstrapError('network');
          console.error('Auth bootstrap failed due to network error', error);
          return;
        }

        setBootstrapError('unknown');
        console.error('Failed to bootstrap auth session', error);
      })
      .finally(() => setLoading(false));
  }, []);

  return <AuthContext.Provider value={{ user, loading, bootstrapError }}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  return useContext(AuthContext);
}
