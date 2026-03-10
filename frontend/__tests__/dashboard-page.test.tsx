import { render, screen } from '@testing-library/react';
import { describe, expect, test } from 'vitest';
import DashboardPage from '@/app/(app)/dashboard/page';

describe('DashboardPage', () => {
  test('renders visible placeholder content', () => {
    render(<DashboardPage />);

    expect(screen.getByRole('heading', { name: 'Dashboard' })).toBeTruthy();
    expect(screen.getByText('KPI and operational summary modules will be implemented next.')).toBeTruthy();
  });
});
