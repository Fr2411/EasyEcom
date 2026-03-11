import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, describe, expect, test, vi } from 'vitest';

const getAutomationPolicyMock = vi.fn();
const getAutomationHistoryMock = vi.fn();
const getAutomationQueueMock = vi.fn();
const enableAutomationMock = vi.fn();
const disableAutomationMock = vi.fn();
const patchAutomationPolicyMock = vi.fn();
const useAuthMock = vi.fn();

vi.mock('@/lib/api/automation', () => ({
  getAutomationPolicy: (...args: unknown[]) => getAutomationPolicyMock(...args),
  getAutomationHistory: (...args: unknown[]) => getAutomationHistoryMock(...args),
  getAutomationQueue: (...args: unknown[]) => getAutomationQueueMock(...args),
  enableAutomation: (...args: unknown[]) => enableAutomationMock(...args),
  disableAutomation: (...args: unknown[]) => disableAutomationMock(...args),
  patchAutomationPolicy: (...args: unknown[]) => patchAutomationPolicyMock(...args),
}));

vi.mock('@/components/auth/auth-provider', () => ({ useAuth: () => useAuthMock() }));

import AutomationPage from '@/app/(app)/automation/page';

afterEach(() => {
  cleanup();
  getAutomationPolicyMock.mockReset();
  getAutomationHistoryMock.mockReset();
  getAutomationQueueMock.mockReset();
  enableAutomationMock.mockReset();
  disableAutomationMock.mockReset();
  patchAutomationPolicyMock.mockReset();
  useAuthMock.mockReset();
});

describe('AutomationPage', () => {
  test('renders access denied state', () => {
    useAuthMock.mockReturnValue({ user: { roles: ['CLIENT_EMPLOYEE'] } });
    render(<AutomationPage />);
    expect(screen.getByTestId('automation-access-denied')).toBeTruthy();
  });

  test('renders policy and history empty state', async () => {
    useAuthMock.mockReturnValue({ user: { roles: ['CLIENT_OWNER'] } });
    getAutomationPolicyMock.mockResolvedValue({ policy_id: 'p1', client_id: 'tenant-a', automation_enabled: false, auto_send_enabled: false, emergency_disabled: false, categories: { product_availability: true, stock_availability: true, simple_price_inquiry: true, business_hours_basic_info: false }, updated_by_user_id: 'u1', created_at: '', updated_at: '' });
    getAutomationHistoryMock.mockResolvedValue({ items: [] });
    getAutomationQueueMock.mockResolvedValue({ items: [] });

    render(<AutomationPage />);
    await waitFor(() => expect(screen.getByText('Automation governance')).toBeTruthy());
    expect(screen.getByTestId('automation-history-empty')).toBeTruthy();
  });

  test('toggles policy controls', async () => {
    useAuthMock.mockReturnValue({ user: { roles: ['CLIENT_MANAGER'] } });
    const basePolicy = { policy_id: 'p1', client_id: 'tenant-a', automation_enabled: false, auto_send_enabled: false, emergency_disabled: false, categories: { product_availability: true, stock_availability: true, simple_price_inquiry: true, business_hours_basic_info: false }, updated_by_user_id: 'u1', created_at: '', updated_at: '' };
    getAutomationPolicyMock.mockResolvedValue(basePolicy);
    getAutomationHistoryMock.mockResolvedValue({ items: [{ decision_id: 'd1', conversation_id: 'conv-1', inbound_message_id: 'msg-1', policy_id: 'p1', category: 'simple_price_inquiry', classification_rule: 'keyword_price', recommended_action: 'draft_for_review', outcome: 'drafted', reason: 'eligible_low_risk', confidence: 'insufficient_context', candidate_reply: 'reply', run_by_user_id: 'u1', created_at: '', updated_at: '' }] });
    getAutomationQueueMock.mockResolvedValue({ items: [] });
    enableAutomationMock.mockResolvedValue({ ...basePolicy, automation_enabled: true });
    disableAutomationMock.mockResolvedValue({ ...basePolicy, automation_enabled: false });
    patchAutomationPolicyMock.mockResolvedValue({ ...basePolicy, auto_send_enabled: true });

    render(<AutomationPage />);
    await waitFor(() => expect(screen.getByText('Decision history')).toBeTruthy());

    fireEvent.click(screen.getByRole('button', { name: 'Enable' }));
    await waitFor(() => expect(enableAutomationMock).toHaveBeenCalled());

    fireEvent.click(screen.getByLabelText('Allow auto-send for grounded low-risk replies'));
    await waitFor(() => expect(patchAutomationPolicyMock).toHaveBeenCalled());
  });
});
