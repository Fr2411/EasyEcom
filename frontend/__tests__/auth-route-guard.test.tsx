import { cleanup, render, screen, waitFor } from '@testing-library/react';
import { afterEach, describe, expect, test, vi } from 'vitest';
import { AuthRouteGuard } from '@/components/auth/auth-route-guard';

const replaceMock = vi.fn();
const refreshAuthMock = vi.fn(async () => undefined);
const useAuthMock = vi.fn();

vi.mock('next/navigation', () => ({
  useRouter: () => ({ replace: replaceMock })
}));

vi.mock('@/components/auth/auth-provider', () => ({
  useAuth: () => useAuthMock()
}));

afterEach(() => {
  cleanup();
  replaceMock.mockReset();
  refreshAuthMock.mockClear();
  useAuthMock.mockReset();
});

describe('AuthRouteGuard', () => {
  test('public-only mode shows visible redirect state for authenticated users', async () => {
    useAuthMock.mockReturnValue({ user: { id: '1' }, loading: false, bootstrapError: 'none', refreshAuth: refreshAuthMock });

    render(
      <AuthRouteGuard mode="public-only">
        <div>Login Form</div>
      </AuthRouteGuard>
    );

    expect(screen.getByText('You are already signed in. Redirecting to dashboard...')).toBeTruthy();

    await waitFor(() => expect(replaceMock).toHaveBeenCalledWith('/dashboard'));
  });

  test('protected mode shows error state when bootstrap fails and allows retry', () => {
    useAuthMock.mockReturnValue({ user: null, loading: false, bootstrapError: 'server', refreshAuth: refreshAuthMock });

    render(
      <AuthRouteGuard mode="protected">
        <div>Dashboard</div>
      </AuthRouteGuard>
    );

    expect(screen.getByText('We could not verify your session')).toBeTruthy();
    screen.getByRole('button', { name: 'Retry' }).click();
    expect(refreshAuthMock).toHaveBeenCalledTimes(1);
  });

  test('protected mode displays loading then renders dashboard once auth is resolved', () => {
    useAuthMock.mockReturnValueOnce({ user: null, loading: true, bootstrapError: 'none', refreshAuth: refreshAuthMock });
    const { rerender } = render(
      <AuthRouteGuard mode="protected">
        <div>Dashboard Content</div>
      </AuthRouteGuard>
    );

    expect(screen.getByText('Loading your workspace...')).toBeTruthy();

    useAuthMock.mockReturnValue({ user: { id: '1' }, loading: false, bootstrapError: 'none', refreshAuth: refreshAuthMock });
    rerender(
      <AuthRouteGuard mode="protected">
        <div>Dashboard Content</div>
      </AuthRouteGuard>
    );

    expect(screen.getByText('Dashboard Content')).toBeTruthy();
  });
});
