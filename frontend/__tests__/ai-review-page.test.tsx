import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, describe, expect, test, vi } from 'vitest';

const getAiReviewConversationsMock = vi.fn();
const getAiReviewConversationMock = vi.fn();
const createAiReviewDraftMock = vi.fn();
const approveAiReviewDraftMock = vi.fn();
const sendAiReviewDraftMock = vi.fn();
const useAuthMock = vi.fn();

vi.mock('@/lib/api/ai-review', () => ({
  getAiReviewConversations: (...args: unknown[]) => getAiReviewConversationsMock(...args),
  getAiReviewConversation: (...args: unknown[]) => getAiReviewConversationMock(...args),
  createAiReviewDraft: (...args: unknown[]) => createAiReviewDraftMock(...args),
  editAiReviewDraft: vi.fn(),
  approveAiReviewDraft: (...args: unknown[]) => approveAiReviewDraftMock(...args),
  rejectAiReviewDraft: vi.fn(),
  sendAiReviewDraft: (...args: unknown[]) => sendAiReviewDraftMock(...args),
}));

vi.mock('@/components/auth/auth-provider', () => ({
  useAuth: () => useAuthMock(),
}));

import AiReviewPage from '@/app/(app)/ai-review/page';

afterEach(() => {
  cleanup();
  getAiReviewConversationsMock.mockReset();
  getAiReviewConversationMock.mockReset();
  createAiReviewDraftMock.mockReset();
  approveAiReviewDraftMock.mockReset();
  sendAiReviewDraftMock.mockReset();
  useAuthMock.mockReset();
});

describe('AiReviewPage', () => {
  test('renders access denied state', () => {
    useAuthMock.mockReturnValue({ user: { roles: ['CLIENT_EMPLOYEE'] } });
    render(<AiReviewPage />);
    expect(screen.getByTestId('ai-review-access-denied')).toBeTruthy();
  });

  test('renders empty state', async () => {
    useAuthMock.mockReturnValue({ user: { roles: ['CLIENT_OWNER'] } });
    getAiReviewConversationsMock.mockResolvedValue({ items: [] });

    render(<AiReviewPage />);
    await waitFor(() => expect(screen.getByTestId('ai-review-empty-state')).toBeTruthy());
  });

  test('generate approve send flow', async () => {
    useAuthMock.mockReturnValue({ user: { roles: ['CLIENT_MANAGER'] } });
    getAiReviewConversationsMock.mockResolvedValue({ items: [{ conversation_id: 'conv-1', channel_id: 'chl-1', external_sender_id: 'wa-1', customer_id: null, status: 'new', last_message_at: '', preview_message_id: 'msg-in-1', preview_text: 'stock?' }] });
    getAiReviewConversationMock.mockResolvedValue({ conversation_id: 'conv-1', channel_id: 'chl-1', external_sender_id: 'wa-1', status: 'open', messages: [{ message_id: 'msg-in-1', direction: 'inbound', message_text: 'stock?', content_summary: 'stock?', occurred_at: '', outbound_status: 'received' }], latest_draft: null });
    createAiReviewDraftMock.mockResolvedValue({ draft_id: 'd-1', conversation_id: 'conv-1', inbound_message_id: 'msg-in-1', status: 'draft_created', ai_draft_text: 'We have stock', edited_text: '', final_text: '', intent: 'stock_check', confidence: 'grounded', grounding: {}, requested_by_user_id: 'u1', approved_by_user_id: null, sent_by_user_id: null, created_at: '', updated_at: '', approved_at: null, sent_at: null, failed_reason: null, send_result: {}, human_modified: false });
    approveAiReviewDraftMock.mockResolvedValue({ draft_id: 'd-1', conversation_id: 'conv-1', inbound_message_id: 'msg-in-1', status: 'approved', ai_draft_text: 'We have stock', edited_text: '', final_text: 'We have stock', intent: 'stock_check', confidence: 'grounded', grounding: {}, requested_by_user_id: 'u1', approved_by_user_id: 'u1', sent_by_user_id: null, created_at: '', updated_at: '', approved_at: '', sent_at: null, failed_reason: null, send_result: {}, human_modified: false });
    sendAiReviewDraftMock.mockResolvedValue({ draft_id: 'd-1', conversation_id: 'conv-1', inbound_message_id: 'msg-in-1', status: 'sent', ai_draft_text: 'We have stock', edited_text: '', final_text: 'We have stock', intent: 'stock_check', confidence: 'grounded', grounding: {}, requested_by_user_id: 'u1', approved_by_user_id: 'u1', sent_by_user_id: 'u1', created_at: '', updated_at: '', approved_at: '', sent_at: '', failed_reason: null, send_result: { status: 'prepared' }, human_modified: false });

    render(<AiReviewPage />);
    await waitFor(() => expect(screen.getByText('Inbox / Review queue')).toBeTruthy());

    await waitFor(() => expect(screen.getByRole('button', { name: 'Generate AI draft' })).toBeTruthy());
    fireEvent.click(screen.getByRole('button', { name: 'Generate AI draft' }));
    await waitFor(() => expect(createAiReviewDraftMock).toHaveBeenCalled());

    fireEvent.click(screen.getByRole('button', { name: 'Approve' }));
    await waitFor(() => expect(approveAiReviewDraftMock).toHaveBeenCalled());

    fireEvent.click(screen.getByRole('button', { name: 'Send' }));
    await waitFor(() => expect(sendAiReviewDraftMock).toHaveBeenCalled());
  });
});
