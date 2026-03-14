import { cleanup, render, screen } from '@testing-library/react';
import { beforeEach, describe, expect, test, vi } from 'vitest';
import { Sidebar } from '@/components/layout/sidebar';

const useAuthMock = vi.fn();

vi.mock('@/components/auth/auth-provider', () => ({
  useAuth: () => useAuthMock(),
}));

vi.mock('next/navigation', () => ({
  usePathname: () => '/inventory',
  useRouter: () => ({ replace: vi.fn(), refresh: vi.fn() }),
}));

vi.mock('@/lib/api/auth', () => ({
  logout: vi.fn(async () => undefined),
}));

describe('Sidebar role filtering', () => {
  beforeEach(() => {
    cleanup();
    useAuthMock.mockReset();
  });

  test('hides admin and finance links for non-super-admin operational users', () => {
    useAuthMock.mockReturnValue({
      user: { roles: ['CLIENT_STAFF'] },
      clearAuth: vi.fn(),
    });
    render(<Sidebar />);

    expect(screen.getByRole('link', { name: 'Inventory' })).toBeTruthy();
    expect(screen.queryByRole('link', { name: 'Customers' })).toBeNull();
    expect(screen.queryByRole('link', { name: 'Purchases' })).toBeNull();
    expect(screen.queryByRole('link', { name: 'Admin' })).toBeNull();
    expect(screen.queryByRole('link', { name: 'Finance' })).toBeNull();
  });

  test('prefers allowed pages from auth context when overrides are present', () => {
    useAuthMock.mockReturnValue({
      user: {
        roles: ['CLIENT_STAFF'],
        allowed_pages: ['Home', 'Dashboard', 'Finance', 'Returns', 'Settings'],
      },
      clearAuth: vi.fn(),
    });

    render(<Sidebar />);

    expect(screen.getByRole('link', { name: 'Finance' })).toBeTruthy();
    expect(screen.queryByRole('link', { name: 'Catalog' })).toBeNull();
  });
});
