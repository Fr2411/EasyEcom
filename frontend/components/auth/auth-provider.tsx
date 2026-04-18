'use client';

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
} from 'react';
import { getCurrentUser, type SessionUser } from '@/lib/api/auth';
import { ApiError, ApiNetworkError } from '@/lib/api/client';

type AuthBootstrapError = 'none' | 'unauthorized' | 'server' | 'network' | 'unknown';

type AuthContextValue = {
  user: SessionUser | null;
  loading: boolean;
  bootstrapError: AuthBootstrapError;
  refreshAuth: () => Promise<void>;
  clearAuth: () => void;
};

const AuthContext = createContext<AuthContextValue>({
  user: null,
  loading: true,
  bootstrapError: 'none',
  refreshAuth: async () => undefined,
  clearAuth: () => undefined,
});

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<SessionUser | null>(null);
  const [loading, setLoading] = useState(true);
  const [bootstrapError, setBootstrapError] =
    useState<AuthBootstrapError>('none');
  const userRef = useRef<SessionUser | null>(null);

  useEffect(() => {
    userRef.current = user;
  }, [user]);

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
      } else {
        const existingUser = userRef.current;
        // Preserve the last verified session for transient failures so active
        // operators are not interrupted mid-workflow by intermittent mobile
        // network instability.
        if (existingUser) {
          setUser(existingUser);
          setBootstrapError('none');
        } else if (error instanceof ApiError && error.status >= 500) {
          setUser(null);
          setBootstrapError('server');
        } else if (error instanceof ApiNetworkError) {
          setUser(null);
          setBootstrapError('network');
        } else {
          setUser(null);
          setBootstrapError('unknown');
        }
      }
    } finally {
      setLoading(false);
    }
  }, []);

  const clearAuth = useCallback(() => {
    setUser(null);
    setBootstrapError('unauthorized');
    setLoading(false);
  }, []);

  useEffect(() => {
    void refreshAuth();
  }, [refreshAuth]);

  const value = useMemo(
    () => ({ user, loading, bootstrapError, refreshAuth, clearAuth }),
    [user, loading, bootstrapError, refreshAuth, clearAuth]
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  return useContext(AuthContext);
}
