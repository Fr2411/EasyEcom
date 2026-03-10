import { render, screen, waitFor } from '@testing-library/react';
import { describe, expect, test, vi, beforeEach } from 'vitest';
import LoginPage from '@/app/login/page';

const replaceMock = vi.fn();
const useAuthMock = vi.fn();

vi.mock('next/navigation', () => ({
  useRouter: () => ({ replace: replaceMock })
}));

vi.mock('@/lib/api/auth', () => ({
  login: vi.fn(async () => undefined)
}));

vi.mock('@/components/auth/auth-provider', () => ({
  useAuth: () => useAuthMock()
}));

describe('LoginPage', () => {
  beforeEach(() => {
    replaceMock.mockReset();
    useAuthMock.mockReset();
  });

  test('shows login form for unauthenticated users', () => {
    useAuthMock.mockReturnValue({ user: null, loading: false, bootstrapError: 'unauthorized', refreshAuth: vi.fn() });

    render(<LoginPage />);

    expect(screen.getByRole('heading', { name: 'EasyEcom Login' })).toBeTruthy();
    expect(screen.getByRole('button', { name: 'Sign in' })).toBeTruthy();
  });

  test('redirects authenticated users to dashboard with visible transition state', async () => {
    useAuthMock.mockReturnValue({ user: { id: 'user-1' }, loading: false, bootstrapError: 'none', refreshAuth: vi.fn() });

    render(<LoginPage />);

    expect(screen.getByText('You are already signed in. Redirecting to dashboard...')).toBeTruthy();
    await waitFor(() => expect(replaceMock).toHaveBeenCalledWith('/dashboard'));
  });
});
