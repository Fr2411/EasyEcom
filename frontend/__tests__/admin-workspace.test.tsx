import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, test, vi } from 'vitest';

import { AdminWorkspace } from '@/components/admin/admin-workspace';

const useAuthMock = vi.fn();
const listAdminClientsMock = vi.fn();
const getAdminClientMock = vi.fn();
const listAdminUsersMock = vi.fn();
const listAdminAuditMock = vi.fn();
const getAdminUserAccessMock = vi.fn();
let searchParamsValue = new URLSearchParams();

vi.mock('@/components/auth/auth-provider', () => ({
  useAuth: () => useAuthMock(),
}));

vi.mock('next/navigation', () => ({
  useSearchParams: () => searchParamsValue,
}));

vi.mock('@/lib/api/admin', () => ({
  createAdminUser: vi.fn(),
  getAdminClient: (...args: unknown[]) => getAdminClientMock(...args),
  getAdminUserAccess: (...args: unknown[]) => getAdminUserAccessMock(...args),
  listAdminAudit: (...args: unknown[]) => listAdminAuditMock(...args),
  listAdminClients: (...args: unknown[]) => listAdminClientsMock(...args),
  listAdminUsers: (...args: unknown[]) => listAdminUsersMock(...args),
  onboardAdminClient: vi.fn(),
  setAdminUserPassword: vi.fn(),
  updateAdminClient: vi.fn(),
  updateAdminUser: vi.fn(),
  updateAdminUserAccess: vi.fn(),
}));

describe('AdminWorkspace', () => {
  afterEach(() => {
    cleanup();
  });

  beforeEach(() => {
    vi.clearAllMocks();
    searchParamsValue = new URLSearchParams();
    useAuthMock.mockReturnValue({
      user: { roles: ['SUPER_ADMIN'], allowed_pages: ['Admin'] },
      loading: false,
    });
    listAdminClientsMock.mockResolvedValue({
      items: [
        {
          client_id: 'client-1',
          client_code: 'acme',
          business_name: 'Acme',
          contact_name: 'Asha',
          owner_name: 'Owner',
          email: 'owner@acme.test',
          phone: '+9715000000',
          address: '',
          website_url: '',
          facebook_url: '',
          instagram_url: '',
          whatsapp_number: '',
          status: 'active',
          notes: '',
          timezone: 'UTC',
          currency_code: 'USD',
          currency_symbol: '$',
          default_location_name: 'Main Warehouse',
          created_at: new Date().toISOString(),
          updated_at: new Date().toISOString(),
        },
      ],
    });
    getAdminClientMock.mockResolvedValue({
      client_id: 'client-1',
      client_code: 'acme',
      business_name: 'Acme',
      contact_name: 'Asha',
      owner_name: 'Owner',
      email: 'owner@acme.test',
      phone: '+9715000000',
      address: '',
      website_url: '',
      facebook_url: '',
      instagram_url: '',
      whatsapp_number: '',
      status: 'active',
      notes: '',
      timezone: 'UTC',
      currency_code: 'USD',
      currency_symbol: '$',
      default_location_name: 'Main Warehouse',
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString(),
    });
    listAdminUsersMock.mockResolvedValue({
      items: [
        {
          user_id: 'user-1',
          user_code: 'acme-client-staff-staff',
          client_id: 'client-1',
          client_code: 'acme',
          name: 'Staff User',
          email: 'staff@acme.test',
          role_code: 'CLIENT_STAFF',
          role_name: 'Client Staff',
          is_active: true,
          created_at: new Date().toISOString(),
          last_login_at: null,
        },
      ],
    });
    listAdminAuditMock.mockResolvedValue({ items: [] });
    getAdminUserAccessMock.mockResolvedValue({
      user_id: 'user-1',
      role_code: 'CLIENT_STAFF',
      default_pages: ['CATALOG', 'INVENTORY'],
      effective_pages: ['CATALOG', 'INVENTORY'],
      overrides: [],
    });
  });

  test('opens create mode from the guided onboarding route', async () => {
    searchParamsValue = new URLSearchParams('mode=create');
    render(<AdminWorkspace />);

    await waitFor(() => expect(screen.getByText('Find or stage a tenant')).toBeTruthy());

    expect(screen.getByText('Stage new tenant')).toBeTruthy();
    expect(screen.getAllByRole('button', { name: 'Review before creating' }).length).toBeGreaterThan(0);
    expect(screen.getByText('Tenant shell preview')).toBeTruthy();
  });

  test('opens inline access details for an existing tenant user', async () => {
    render(<AdminWorkspace />);

    await waitFor(() => expect(screen.getByText('User management')).toBeTruthy());
    fireEvent.click(screen.getAllByRole('button', { name: 'Access Details' })[0]);

    await waitFor(() => expect(screen.getByText('Access details for Staff User')).toBeTruthy());
    expect(screen.getByText('Default pages')).toBeTruthy();
    expect(screen.getAllByDisplayValue('Use default').length).toBeGreaterThan(0);
  });
});
