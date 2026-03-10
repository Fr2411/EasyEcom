'use client';
import { createContext, useCallback, useContext, useEffect, useState } from 'react';
import { getCurrentUser, type SessionUser } from '@/lib/api/auth';
import { ApiError, ApiNetworkError } from '@/lib/api/client';

type AuthBootstrapError = 'none' | 'unauthorized' | 'server' | 'network' | 'unknown';

type AuthContextValue = {
  user: SessionUser | null;
  loading: boolean;
  bootstrapError: AuthBootstrapError;
  refreshAuth: () => Promise<void>;
};

const AuthContext = createContext<AuthContextValue>({
  user: null,
  loading: true,
  bootstrapError: 'none',
  refreshAuth: async () => undefined
});

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<SessionUser | null>(null);
  const [loading, setLoading] = useState(true);
  const [bootstrapError, setBootstrapError] = useState<AuthBootstrapError>('none');

  const refreshAuth = useCallback(async () => {
    setLoading(true);

    try {
      const currentUser = await getCurrentUser();
      setUser(currentUser);
      setBootstrapError('none');
    } catch (error: unknown) {
      if (error instanceof ApiError && error.status === 401) {
        setUser(null);
        setBootstrapError('unauthorized');
        return;
      }

      if (error instanceof ApiError && error.status >= 500) {
        setUser(null);
        setBootstrapError('server');
        console.error('Auth bootstrap failed with server error', error);
        return;
      }

      if (error instanceof ApiNetworkError) {
        setUser(null);
        setBootstrapError('network');
        console.error('Auth bootstrap failed due to network error', error);
        return;
      }

      setUser(null);
      setBootstrapError('unknown');
      console.error('Failed to bootstrap auth session', error);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void refreshAuth();
  }, [refreshAuth]);

  return <AuthContext.Provider value={{ user, loading, bootstrapError, refreshAuth }}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  return useContext(AuthContext);
}
