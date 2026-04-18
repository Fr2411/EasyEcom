import { cleanup, render, screen, waitFor } from '@testing-library/react';
import { afterEach, describe, expect, test, vi } from 'vitest';
import { AuthProvider, useAuth } from '@/components/auth/auth-provider';
import { ApiError, ApiNetworkError } from '@/lib/api/client';

vi.mock('@/lib/api/auth', () => ({
  getCurrentUser: vi.fn()
}));

import { getCurrentUser } from '@/lib/api/auth';

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

function AuthConsumer() {
  const auth = useAuth();
  return <div data-testid="auth-state">{`${auth.loading}|${auth.user ? 'user' : 'none'}|${auth.bootstrapError}|${auth.hasVerifiedSession ? 'verified' : 'unverified'}`}</div>;
}

describe('AuthProvider bootstrap states', () => {
  test('renders children through the auth context provider', async () => {
    vi.mocked(getCurrentUser).mockResolvedValueOnce({
      user_id: 'user-1',
      email: 'user@example.com',
      name: 'User',
      role: 'SUPER_ADMIN',
      client_id: 'client-1',
      roles: ['SUPER_ADMIN'],
      allowed_pages: ['Home', 'Dashboard'],
      is_authenticated: true,
    });

    render(
      <AuthProvider>
        <div data-testid="provider-child">Child content</div>
      </AuthProvider>
    );

    expect(screen.getByTestId('provider-child').textContent).toBe('Child content');
    await waitFor(() => expect(screen.getByTestId('provider-child')).toBeTruthy());
  });

  test('marks 401 as unauthorized', async () => {
    vi.mocked(getCurrentUser).mockRejectedValueOnce(new ApiError(401, 'unauthorized'));
    render(
      <AuthProvider>
        <AuthConsumer />
      </AuthProvider>
    );

    await waitFor(() => expect(screen.getByTestId('auth-state').textContent).toBe('false|none|unauthorized|unverified'));
  });

  test('marks 500 as server', async () => {
    vi.mocked(getCurrentUser).mockRejectedValueOnce(new ApiError(500, 'server'));
    render(
      <AuthProvider>
        <AuthConsumer />
      </AuthProvider>
    );

    await waitFor(() => expect(screen.getByTestId('auth-state').textContent).toBe('false|none|server|unverified'));
  });

  test('marks network failures distinctly', async () => {
    vi.mocked(getCurrentUser).mockRejectedValueOnce(new ApiNetworkError('network down'));
    render(
      <AuthProvider>
        <AuthConsumer />
      </AuthProvider>
    );

    await waitFor(() => expect(screen.getByTestId('auth-state').textContent).toBe('false|none|network|unverified'));
  });

  test('keeps existing authenticated user when a later bootstrap refresh hits transient network failure', async () => {
    vi.mocked(getCurrentUser)
      .mockResolvedValueOnce({
        user_id: 'user-1',
        email: 'user@example.com',
        name: 'User',
        role: 'SUPER_ADMIN',
        client_id: 'client-1',
        roles: ['SUPER_ADMIN'],
        allowed_pages: ['Home', 'Dashboard'],
        is_authenticated: true,
      })
      .mockRejectedValueOnce(new ApiNetworkError('network down'));

    function RefreshButton() {
      const auth = useAuth();
      return (
        <button type="button" onClick={() => void auth.refreshAuth()}>
          Refresh auth
        </button>
      );
    }

    render(
      <AuthProvider>
        <AuthConsumer />
        <RefreshButton />
      </AuthProvider>
    );

    await waitFor(() => expect(screen.getByTestId('auth-state').textContent).toBe('false|user|none|verified'));

    screen.getByRole('button', { name: 'Refresh auth' }).click();

    await waitFor(() => expect(screen.getByTestId('auth-state').textContent).toBe('false|user|none|verified'));
  });

  test('hydrates verified-session grace from sessionStorage and keeps it during transient server failures', async () => {
    window.sessionStorage.setItem('easyecom.auth.verified_session', '1');
    vi.mocked(getCurrentUser).mockRejectedValueOnce(new ApiError(503, 'server'));

    render(
      <AuthProvider>
        <AuthConsumer />
      </AuthProvider>
    );

    await waitFor(() => expect(screen.getByTestId('auth-state').textContent).toBe('false|none|server|verified'));
  });

  test('clears verified-session grace marker on 401 unauthorized', async () => {
    window.sessionStorage.setItem('easyecom.auth.verified_session', '1');
    vi.mocked(getCurrentUser).mockRejectedValueOnce(new ApiError(401, 'unauthorized'));

    render(
      <AuthProvider>
        <AuthConsumer />
      </AuthProvider>
    );

    await waitFor(() => expect(screen.getByTestId('auth-state').textContent).toBe('false|none|unauthorized|unverified'));
    expect(window.sessionStorage.getItem('easyecom.auth.verified_session')).toBeNull();
  });
});
