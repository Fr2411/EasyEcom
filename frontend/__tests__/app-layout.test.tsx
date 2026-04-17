import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, test, vi } from 'vitest';
import type { ReactNode } from 'react';
import AppLayout from '@/app/(app)/layout';

vi.mock('@/components/auth/auth-route-guard', () => ({
  AuthRouteGuard: ({ children }: { mode: 'protected' | 'public-only'; children: ReactNode }) => (
    <div data-testid="auth-route-guard">{children}</div>
  )
}));

vi.mock('@/components/auth/auth-provider', () => ({
  useAuth: () => ({
    user: { roles: ['SUPER_ADMIN'] },
  }),
}));

vi.mock('@/components/ui/nav-item', () => ({
  NavItem: ({ item }: { item: { label: string; href: string } }) => <a href={item.href}>{item.label}</a>
}));

vi.mock('@/components/theme/theme-toggle', () => ({
  ThemeToggle: () => <div>Theme toggle</div>,
}));

vi.mock('next/navigation', () => ({
  useRouter: () => ({ replace: vi.fn() }),
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
    expect(screen.getByRole('img', { name: 'Easy-Ecom' })).toBeTruthy();
    expect(screen.getByRole('button', { name: 'Show workspace details' })).toBeTruthy();
    fireEvent.click(screen.getByRole('button', { name: 'Show workspace details' }));
    expect(screen.getByText('Easy-Ecom Internal')).toBeTruthy();
    expect(screen.getByRole('button', { name: 'Reports' })).toBeTruthy();
    expect(screen.getByRole('link', { name: 'Admin' })).toBeTruthy();
    expect(screen.getByRole('link', { name: 'Customers' })).toBeTruthy();
    expect(screen.getByRole('link', { name: 'Purchases' })).toBeTruthy();
    expect(screen.getByRole('button', { name: 'Log out' })).toBeTruthy();
    expect(screen.getByText('Dashboard body content')).toBeTruthy();
  });
});
