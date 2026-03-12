import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, describe, expect, test, vi } from 'vitest';

const getAdminUsersMock = vi.fn();
const getAdminRolesMock = vi.fn();
const getAdminAuditMock = vi.fn();
const createAdminTenantMock = vi.fn();
const createAdminUserMock = vi.fn();
const updateAdminUserMock = vi.fn();
const setAdminUserRolesMock = vi.fn();
const useAuthMock = vi.fn();

vi.mock('@/lib/api/admin', () => ({
  getAdminUsers: (...args: unknown[]) => getAdminUsersMock(...args),
  getAdminRoles: (...args: unknown[]) => getAdminRolesMock(...args),
  getAdminAudit: (...args: unknown[]) => getAdminAuditMock(...args),
  createAdminTenant: (...args: unknown[]) => createAdminTenantMock(...args),
  createAdminUser: (...args: unknown[]) => createAdminUserMock(...args),
  updateAdminUser: (...args: unknown[]) => updateAdminUserMock(...args),
  setAdminUserRoles: (...args: unknown[]) => setAdminUserRolesMock(...args),
}));

vi.mock('@/components/auth/auth-provider', () => ({
  useAuth: () => useAuthMock(),
}));

import AdminPage from '@/app/(app)/admin/page';

afterEach(() => {
  cleanup();
  getAdminUsersMock.mockReset();
  getAdminRolesMock.mockReset();
  getAdminAuditMock.mockReset();
  createAdminTenantMock.mockReset();
  createAdminUserMock.mockReset();
  updateAdminUserMock.mockReset();
  setAdminUserRolesMock.mockReset();
  useAuthMock.mockReset();
});

describe('AdminPage', () => {
  test('renders access denied state', async () => {
    useAuthMock.mockReturnValue({ user: { roles: ['CLIENT_EMPLOYEE'] } });

    render(<AdminPage />);

    expect(screen.getByTestId('admin-access-denied')).toBeTruthy();
  });

  test('renders empty state', async () => {
    useAuthMock.mockReturnValue({ user: { roles: ['CLIENT_OWNER'] } });
    getAdminUsersMock.mockResolvedValue({ items: [] });
    getAdminRolesMock.mockResolvedValue({ roles: ['CLIENT_OWNER'] });
    getAdminAuditMock.mockResolvedValue({ supported: false, deferred_reason: 'Deferred', items: [] });

    render(<AdminPage />);

    await waitFor(() => expect(screen.getByTestId('admin-empty-state')).toBeTruthy());
  });

  test('submits create user and supports role interactions', async () => {
    useAuthMock.mockReturnValue({ user: { roles: ['SUPER_ADMIN'] } });
    getAdminUsersMock.mockResolvedValue({ items: [{ user_id: 'u-1', client_id: 'c-1', name: 'A', email: 'a@x.com', is_active: true, created_at: '', roles: ['CLIENT_OWNER'] }] });
    getAdminRolesMock.mockResolvedValue({ roles: ['SUPER_ADMIN', 'CLIENT_OWNER'] });
    getAdminAuditMock.mockResolvedValue({ supported: false, deferred_reason: 'Deferred', items: [] });
    createAdminTenantMock.mockResolvedValue({ client_id: "c-2", business_name: "Biz", owner_user: { user_id: "u-9" } });
    createAdminUserMock.mockResolvedValue({ user: { user_id: 'u-2' } });
    updateAdminUserMock.mockResolvedValue({ user: { user_id: 'u-1' } });
    setAdminUserRolesMock.mockResolvedValue({ user: { user_id: 'u-1' } });

    render(<AdminPage />);

    await waitFor(() => expect(screen.getByText('Tenant users')).toBeTruthy());

    fireEvent.change(screen.getByLabelText('Client ID'), { target: { value: 'c-1' } });
    fireEvent.change(screen.getByLabelText('Full name'), { target: { value: 'New User' } });
    fireEvent.change(screen.getByLabelText('Email'), { target: { value: 'new@x.com' } });
    fireEvent.change(screen.getByLabelText('Password'), { target: { value: 'Password!1' } });
    fireEvent.click(screen.getByRole('button', { name: 'Add User' }));

    await waitFor(() => expect(createAdminUserMock).toHaveBeenCalled());

    fireEvent.click(screen.getByRole('button', { name: 'Deactivate' }));
    await waitFor(() => expect(updateAdminUserMock).toHaveBeenCalled());

    const roleCheck = screen.getByLabelText('SUPER_ADMIN');
    fireEvent.click(roleCheck);
    await waitFor(() => expect(setAdminUserRolesMock).toHaveBeenCalled());
  });
});
