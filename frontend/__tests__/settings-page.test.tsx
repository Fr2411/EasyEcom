import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, describe, expect, test, vi } from 'vitest';

const getBusinessProfileMock = vi.fn();
const patchBusinessProfileMock = vi.fn();
const getPreferencesMock = vi.fn();
const patchPreferencesMock = vi.fn();
const getSequencesMock = vi.fn();
const patchSequencesMock = vi.fn();
const getTenantContextMock = vi.fn();
const useAuthMock = vi.fn();

vi.mock('@/lib/api/settings', () => ({
  getBusinessProfile: (...args: unknown[]) => getBusinessProfileMock(...args),
  patchBusinessProfile: (...args: unknown[]) => patchBusinessProfileMock(...args),
  getPreferences: (...args: unknown[]) => getPreferencesMock(...args),
  patchPreferences: (...args: unknown[]) => patchPreferencesMock(...args),
  getSequences: (...args: unknown[]) => getSequencesMock(...args),
  patchSequences: (...args: unknown[]) => patchSequencesMock(...args),
  getTenantContext: (...args: unknown[]) => getTenantContextMock(...args),
}));

vi.mock('@/components/auth/auth-provider', () => ({
  useAuth: () => useAuthMock(),
}));

import SettingsPage from '@/app/(app)/settings/page';

afterEach(() => {
  cleanup();
  getBusinessProfileMock.mockReset();
  patchBusinessProfileMock.mockReset();
  getPreferencesMock.mockReset();
  patchPreferencesMock.mockReset();
  getSequencesMock.mockReset();
  patchSequencesMock.mockReset();
  getTenantContextMock.mockReset();
  useAuthMock.mockReset();
});

function prime() {
  getBusinessProfileMock.mockResolvedValue({ client_id: 'tenant-a', business_name: 'Tenant A', display_name: '', phone: '', email: '', address: '', currency_code: 'USD', timezone: 'UTC', tax_registration_no: '', logo_upload_supported: false, logo_upload_deferred_reason: 'Deferred' });
  getPreferencesMock.mockResolvedValue({ low_stock_threshold: 5, default_sales_note: '', default_inventory_adjustment_reasons: [], default_payment_terms_days: 0, active_usage: { low_stock_threshold: true, default_sales_note: false, default_inventory_adjustment_reasons: false, default_payment_terms_days: false } });
  getSequencesMock.mockResolvedValue({ sales_prefix: 'SAL', returns_prefix: 'RET', active_usage: { sales_prefix: false, returns_prefix: false } });
  getTenantContextMock.mockResolvedValue({ client_id: 'tenant-a', business_name: 'Tenant A', status: 'active', currency_code: 'USD' });
  patchBusinessProfileMock.mockResolvedValue({ client_id: 'tenant-a', business_name: 'Tenant AX', display_name: '', phone: '', email: '', address: '', currency_code: 'USD', timezone: 'UTC', tax_registration_no: '', logo_upload_supported: false, logo_upload_deferred_reason: 'Deferred' });
  patchPreferencesMock.mockResolvedValue({ low_stock_threshold: 6, default_sales_note: '', default_inventory_adjustment_reasons: [], default_payment_terms_days: 0, active_usage: { low_stock_threshold: true, default_sales_note: false, default_inventory_adjustment_reasons: false, default_payment_terms_days: false } });
  patchSequencesMock.mockResolvedValue({ sales_prefix: 'SO', returns_prefix: 'RT', active_usage: { sales_prefix: false, returns_prefix: false } });
}

describe('SettingsPage', () => {
  test('renders access denied state for non-admin write', async () => {
    useAuthMock.mockReturnValue({ user: { roles: ['CLIENT_EMPLOYEE'] } });
    prime();
    render(<SettingsPage />);
    await waitFor(() => expect(screen.getByTestId('settings-access-denied')).toBeTruthy());
  });

  test('renders empty/deferred state on missing payload', async () => {
    useAuthMock.mockReturnValue({ user: { roles: ['CLIENT_OWNER'] } });
    getBusinessProfileMock.mockResolvedValue(null);
    getPreferencesMock.mockResolvedValue(null);
    getSequencesMock.mockResolvedValue(null);
    getTenantContextMock.mockResolvedValue(null);

    render(<SettingsPage />);
    await waitFor(() => expect(screen.getByTestId('settings-empty-state')).toBeTruthy());
  });

  test('loads and saves forms', async () => {
    useAuthMock.mockReturnValue({ user: { roles: ['CLIENT_OWNER'] } });
    prime();

    render(<SettingsPage />);
    await waitFor(() => expect(screen.getByText('Business profile')).toBeTruthy());

    fireEvent.change(screen.getByLabelText('Business name'), { target: { value: 'Tenant AX' } });
    fireEvent.click(screen.getByRole('button', { name: 'Save business profile' }));
    await waitFor(() => expect(patchBusinessProfileMock).toHaveBeenCalled());
  });
});
