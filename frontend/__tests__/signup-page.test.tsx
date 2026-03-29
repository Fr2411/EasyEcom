import { render, screen } from '@testing-library/react';
import { describe, expect, test, vi } from 'vitest';
import SignupPage from '@/app/signup/page';

const useAuthMock = vi.fn();

vi.mock('next/navigation', () => ({
  useRouter: () => ({ replace: vi.fn() }),
}));

vi.mock('@/components/auth/auth-provider', () => ({
  useAuth: () => useAuthMock(),
}));

describe('SignupPage', () => {
  test('renders the dedicated signup form', () => {
    useAuthMock.mockReturnValue({ user: null, loading: false, refreshAuth: vi.fn() });

    render(<SignupPage />);

    expect(screen.getByRole('heading', { name: 'Create your EasyEcom account' })).toBeTruthy();
    expect(screen.getByLabelText('Full name')).toBeTruthy();
    expect(screen.getByLabelText('Business name')).toBeTruthy();
    expect(screen.getByLabelText('Email')).toBeTruthy();
    expect(screen.getByLabelText('Password')).toBeTruthy();
  });
});
