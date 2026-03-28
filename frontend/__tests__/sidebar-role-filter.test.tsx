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
    expect(screen.getByRole('link', { name: 'Purchases' })).toBeTruthy();
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

  test('shows automation when the session explicitly allows it', () => {
    useAuthMock.mockReturnValue({
      user: {
        roles: ['FINANCE_STAFF'],
        allowed_pages: ['Home', 'Dashboard', 'Automation', 'Finance', 'Reports', 'Settings'],
      },
      clearAuth: vi.fn(),
    });

    render(<Sidebar />);

    expect(screen.getByRole('link', { name: 'Automation' })).toBeTruthy();
    expect(screen.getByRole('link', { name: 'Finance' })).toBeTruthy();
  });

  test('keeps catalog hidden from normal tenant navigation even for owners', () => {
    useAuthMock.mockReturnValue({
      user: {
        roles: ['CLIENT_OWNER'],
        allowed_pages: ['Home', 'Dashboard', 'Catalog', 'Inventory', 'Sales', 'Settings'],
      },
      clearAuth: vi.fn(),
    });

    render(<Sidebar />);

    expect(screen.getByRole('link', { name: 'Inventory' })).toBeTruthy();
    expect(screen.queryByRole('link', { name: 'Catalog' })).toBeNull();
  });

  test('shows workspace identity under the logo when session details are available', () => {
    useAuthMock.mockReturnValue({
      user: {
        roles: ['CLIENT_OWNER'],
        allowed_pages: ['Dashboard', 'Inventory', 'Sales', 'Settings'],
        business_name: 'Codex Footwear',
        name: 'Codex User',
        email: 'codex@example.com',
      },
      clearAuth: vi.fn(),
    });

    render(<Sidebar />);

    expect(screen.getByText('Codex Footwear')).toBeTruthy();
    expect(screen.getByText('Codex User')).toBeTruthy();
    expect(screen.getByText('codex@example.com')).toBeTruthy();
    expect(screen.getByRole('button', { name: 'Minimize sidebar' })).toBeTruthy();
  });

  test('keeps Sales Agent visible for client owners even if an older allowed page list omits it', () => {
    useAuthMock.mockReturnValue({
      user: {
        roles: ['CLIENT_OWNER'],
        allowed_pages: ['Dashboard', 'Inventory', 'Sales', 'Settings'],
      },
      clearAuth: vi.fn(),
    });

    render(<Sidebar />);

    expect(screen.getByRole('link', { name: 'Sales Agent' })).toBeTruthy();
  });
});
