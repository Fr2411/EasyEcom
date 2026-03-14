import { render, screen } from '@testing-library/react';
import { describe, expect, test, vi } from 'vitest';
import { Sidebar } from '@/components/layout/sidebar';

vi.mock('@/components/auth/auth-provider', () => ({
  useAuth: () => ({
    user: { roles: ['CLIENT_STAFF'] },
    clearAuth: vi.fn(),
  }),
}));

vi.mock('next/navigation', () => ({
  usePathname: () => '/inventory',
  useRouter: () => ({ replace: vi.fn(), refresh: vi.fn() }),
}));

vi.mock('@/lib/api/auth', () => ({
  logout: vi.fn(async () => undefined),
}));

describe('Sidebar role filtering', () => {
  test('hides admin and finance links for non-super-admin operational users', () => {
    render(<Sidebar />);

    expect(screen.getByRole('link', { name: 'Inventory' })).toBeTruthy();
    expect(screen.getByRole('link', { name: 'Customers' })).toBeTruthy();
    expect(screen.queryByRole('link', { name: 'Admin' })).toBeNull();
    expect(screen.queryByRole('link', { name: 'Finance' })).toBeNull();
  });
});
