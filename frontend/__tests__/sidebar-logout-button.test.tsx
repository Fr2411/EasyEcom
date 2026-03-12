import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, test, vi } from 'vitest';
import { SidebarLogoutButton } from '@/components/layout/sidebar-logout-button';

const replaceMock = vi.fn();
const refreshMock = vi.fn();
const clearAuthMock = vi.fn();

vi.mock('next/navigation', () => ({
  useRouter: () => ({ replace: replaceMock, refresh: refreshMock })
}));

vi.mock('@/lib/api/auth', () => ({
  logout: vi.fn(async () => undefined)
}));

vi.mock('@/components/auth/auth-provider', () => ({
  useAuth: () => ({ clearAuth: clearAuthMock })
}));

import { logout } from '@/lib/api/auth';

describe('SidebarLogoutButton', () => {
  beforeEach(() => {
    replaceMock.mockReset();
    refreshMock.mockReset();
    clearAuthMock.mockReset();
    vi.mocked(logout).mockClear();
  });

  test('clears local auth state and redirects to login after logout', async () => {
    render(<SidebarLogoutButton />);

    fireEvent.click(screen.getByRole('button', { name: 'Log out' }));

    await waitFor(() => expect(logout).toHaveBeenCalledTimes(1));
    expect(clearAuthMock).toHaveBeenCalledTimes(1);
    expect(replaceMock).toHaveBeenCalledWith('/login');
    expect(refreshMock).toHaveBeenCalledTimes(1);
  });
});
