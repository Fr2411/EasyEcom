import { render, screen } from '@testing-library/react';
import { describe, expect, test, vi } from 'vitest';
import AdminPage from '@/app/(app)/admin/page';

vi.mock('@/components/admin/admin-workspace', () => ({
  AdminWorkspace: () => <div>Mocked admin workspace</div>,
}));

describe('AdminPage', () => {
  test('renders the super admin page shell and workspace', () => {
    render(<AdminPage />);

    expect(screen.getByText('Super Admin Panel')).toBeTruthy();
    expect(screen.getByText('Mocked admin workspace')).toBeTruthy();
  });
});
