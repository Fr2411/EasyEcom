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
  hasVerifiedSession: boolean;
  refreshAuth: () => Promise<void>;
  clearAuth: () => void;
};

const VERIFIED_SESSION_STORAGE_KEY = 'easyecom.auth.verified_session';

const AuthContext = createContext<AuthContextValue>({
  user: null,
  loading: true,
  bootstrapError: 'none',
  hasVerifiedSession: false,
  refreshAuth: async () => undefined,
  clearAuth: () => undefined,
});

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<SessionUser | null>(null);
  const [loading, setLoading] = useState(true);
  const [bootstrapError, setBootstrapError] =
    useState<AuthBootstrapError>('none');
  const [hasVerifiedSession, setHasVerifiedSession] = useState(() => {
    if (typeof window === 'undefined') {
      return false;
    }
    return window.sessionStorage.getItem(VERIFIED_SESSION_STORAGE_KEY) === '1';
  });
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
      setHasVerifiedSession(true);
      if (typeof window !== 'undefined') {
        window.sessionStorage.setItem(VERIFIED_SESSION_STORAGE_KEY, '1');
      }
    } catch (error: unknown) {
      if (error instanceof ApiError && error.status === 401) {
        setUser(null);
        setBootstrapError('unauthorized');
        setHasVerifiedSession(false);
        if (typeof window !== 'undefined') {
          window.sessionStorage.removeItem(VERIFIED_SESSION_STORAGE_KEY);
        }
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
    setHasVerifiedSession(false);
    if (typeof window !== 'undefined') {
      window.sessionStorage.removeItem(VERIFIED_SESSION_STORAGE_KEY);
    }
    setLoading(false);
  }, []);

  useEffect(() => {
    void refreshAuth();
  }, [refreshAuth]);

  const value = useMemo(
    () => ({
      user,
      loading,
      bootstrapError,
      hasVerifiedSession,
      refreshAuth,
      clearAuth,
    }),
    [user, loading, bootstrapError, hasVerifiedSession, refreshAuth, clearAuth]
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  return useContext(AuthContext);
}
