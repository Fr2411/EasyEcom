import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, describe, expect, test, vi } from 'vitest';

const getIntegrationsMock = vi.fn();
const getIntegrationMessagesMock = vi.fn();
const getConversationsMock = vi.fn();
const createIntegrationMock = vi.fn();
const useAuthMock = vi.fn();

vi.mock('@/lib/api/integrations', () => ({
  getIntegrations: (...args: unknown[]) => getIntegrationsMock(...args),
  getIntegrationMessages: (...args: unknown[]) => getIntegrationMessagesMock(...args),
  getConversations: (...args: unknown[]) => getConversationsMock(...args),
  createIntegration: (...args: unknown[]) => createIntegrationMock(...args),
}));

vi.mock('@/components/auth/auth-provider', () => ({
  useAuth: () => useAuthMock(),
}));

import IntegrationsPage from '@/app/(app)/integrations/page';

afterEach(() => {
  cleanup();
  getIntegrationsMock.mockReset();
  getIntegrationMessagesMock.mockReset();
  getConversationsMock.mockReset();
  createIntegrationMock.mockReset();
  useAuthMock.mockReset();
});

describe('IntegrationsPage', () => {
  test('renders access denied state', () => {
    useAuthMock.mockReturnValue({ user: { roles: ['CLIENT_EMPLOYEE'] } });
    render(<IntegrationsPage />);
    expect(screen.getByTestId('integrations-access-denied')).toBeTruthy();
  });

  test('renders empty state', async () => {
    useAuthMock.mockReturnValue({ user: { roles: ['CLIENT_OWNER'] } });
    getIntegrationsMock.mockResolvedValue({ items: [] });
    getIntegrationMessagesMock.mockResolvedValue({ items: [] });
    getConversationsMock.mockResolvedValue({ items: [] });

    render(<IntegrationsPage />);
    await waitFor(() => expect(screen.getByTestId('integrations-empty-state')).toBeTruthy());
  });

  test('submits create integration', async () => {
    useAuthMock.mockReturnValue({ user: { roles: ['CLIENT_MANAGER'] } });
    getIntegrationsMock.mockResolvedValue({ items: [{ channel_id: 'chl-1', provider: 'webhook', display_name: 'Web', status: 'active', external_account_id: '', verify_token_set: true, inbound_secret_set: true, config: {}, created_at: '', updated_at: '', last_inbound_at: null }] });
    getIntegrationMessagesMock.mockResolvedValue({ items: [] });
    getConversationsMock.mockResolvedValue({ items: [] });
    createIntegrationMock.mockResolvedValue({ channel_id: 'chl-2' });

    render(<IntegrationsPage />);
    await waitFor(() => expect(screen.getByText('Channel integrations')).toBeTruthy());

    fireEvent.change(screen.getByLabelText('Display name'), { target: { value: 'WhatsApp Main' } });
    fireEvent.click(screen.getByRole('button', { name: 'Create integration' }));

    await waitFor(() => expect(createIntegrationMock).toHaveBeenCalled());
  });
});
