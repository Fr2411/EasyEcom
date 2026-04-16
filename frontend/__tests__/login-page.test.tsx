import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { describe, expect, test, vi, beforeEach } from 'vitest';
import LoginPage from '@/app/login/page';

const replaceMock = vi.fn();
const useAuthMock = vi.fn();

vi.mock('next/navigation', () => ({
  useRouter: () => ({ replace: replaceMock }),
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

    expect(screen.getByRole('heading', { name: 'Welcome back' })).toBeTruthy();
    expect(screen.getByRole('link', { name: 'EasyEcom home' })).toBeTruthy();
    expect(screen.getByRole('button', { name: 'Sign In' })).toBeTruthy();
    expect(screen.getByRole('link', { name: 'Create account' }).getAttribute('href')).toBe('/signup');
  });

  test('redirects authenticated users to dashboard', async () => {
    useAuthMock.mockReturnValue({ user: { id: 'user-1' }, loading: false, bootstrapError: 'none', refreshAuth: vi.fn() });

    render(<LoginPage />);

    await waitFor(() => expect(replaceMock).toHaveBeenCalledWith('/dashboard'));
  });

  test('supports show password for accessibility', () => {
    useAuthMock.mockReturnValue({ user: null, loading: false, bootstrapError: 'unauthorized', refreshAuth: vi.fn() });

    render(<LoginPage />);

    fireEvent.click(screen.getAllByRole('button', { name: 'Show password' })[0]);
    expect(screen.getAllByLabelText('Password')[0].getAttribute('type')).toBe('text');
  });
});
