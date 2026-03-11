import { render, screen, within } from '@testing-library/react';
import { describe, expect, test, vi } from 'vitest';
import type { ReactNode } from 'react';
import AppLayout from '@/app/(app)/layout';

vi.mock('@/components/auth/auth-route-guard', () => ({
  AuthRouteGuard: ({ children }: { mode: 'protected' | 'public-only'; children: ReactNode }) => (
    <div data-testid="auth-route-guard">{children}</div>
  )
}));

vi.mock('next/navigation', () => ({
  useRouter: () => ({ replace: vi.fn(), refresh: vi.fn() }),
  usePathname: () => '/dashboard'
}));

vi.mock('@/lib/api/auth', () => ({
  logout: vi.fn(async () => undefined)
}));

describe('AppLayout', () => {
  test('renders children inside the app shell wrapper', () => {
    render(
      <AppLayout>
        <div>Dashboard body content</div>
      </AppLayout>
    );

    expect(screen.getByTestId('auth-route-guard')).toBeTruthy();
    expect(screen.getByLabelText('Primary')).toBeTruthy();
    expect(screen.getByText('Operations Workspace')).toBeTruthy();

    const systemSection = screen.getByLabelText('System');
    const settingsLink = within(systemSection).getByRole('link', { name: 'Settings' });
    const logoutButton = within(systemSection).getByRole('button', { name: 'Log out' });

    const settingsListItem = settingsLink.closest('li');
    const logoutListItem = logoutButton.closest('li');

    expect(settingsListItem).toBeTruthy();
    expect(logoutListItem).toBeTruthy();
    expect(settingsListItem?.nextElementSibling).toBe(logoutListItem);

    expect(screen.getByText('Dashboard body content')).toBeTruthy();
  });
});
