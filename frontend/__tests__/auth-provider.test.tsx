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
  return <div data-testid="auth-state">{`${auth.loading}|${auth.user ? 'user' : 'none'}|${auth.bootstrapError}`}</div>;
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

    await waitFor(() => expect(screen.getByTestId('auth-state').textContent).toBe('false|none|unauthorized'));
  });

  test('marks 500 as server', async () => {
    vi.mocked(getCurrentUser).mockRejectedValueOnce(new ApiError(500, 'server'));
    render(
      <AuthProvider>
        <AuthConsumer />
      </AuthProvider>
    );

    await waitFor(() => expect(screen.getByTestId('auth-state').textContent).toBe('false|none|server'));
  });

  test('marks network failures distinctly', async () => {
    vi.mocked(getCurrentUser).mockRejectedValueOnce(new ApiNetworkError('network down'));
    render(
      <AuthProvider>
        <AuthConsumer />
      </AuthProvider>
    );

    await waitFor(() => expect(screen.getByTestId('auth-state').textContent).toBe('false|none|network'));
  });
});
