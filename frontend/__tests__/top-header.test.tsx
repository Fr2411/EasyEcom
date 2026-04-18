import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, test, vi } from 'vitest';

const pushMock = vi.fn();
let pathname = '/dashboard';

vi.mock('next/navigation', () => ({
  usePathname: () => pathname,
  useRouter: () => ({ push: pushMock }),
}));

vi.mock('@/components/theme/theme-toggle', () => ({
  ThemeToggle: () => <div>Theme toggle</div>,
}));

import { TopHeader } from '@/components/layout/top-header';

describe('TopHeader', () => {
  beforeEach(() => {
    pushMock.mockReset();
    pathname = '/dashboard';
  });

  afterEach(() => {
    cleanup();
  });

  test('submits scoped search query to the expected route', () => {
    render(<TopHeader />);

    fireEvent.change(screen.getByLabelText('Global search scope'), { target: { value: 'inventory' } });
    fireEvent.change(screen.getByLabelText('Global search query'), { target: { value: 'Blue Tee' } });
    fireEvent.click(screen.getByRole('button', { name: 'Search all' }));

    expect(pushMock).toHaveBeenCalledWith('/inventory?q=Blue+Tee');
  });

  test('keeps search in catalog context when submitting from catalog route', () => {
    pathname = '/catalog';
    render(<TopHeader />);

    fireEvent.change(screen.getByLabelText('Global search query'), { target: { value: 'shirt' } });
    fireEvent.click(screen.getByRole('button', { name: 'Global search' }));

    expect(pushMock).toHaveBeenCalledWith('/catalog?q=shirt');
  });

  test('does not navigate for empty search values', () => {
    render(<TopHeader />);

    fireEvent.change(screen.getByLabelText('Global search query'), { target: { value: '   ' } });
    fireEvent.click(screen.getByRole('button', { name: 'Search all' }));

    expect(pushMock).not.toHaveBeenCalled();
  });

  test('shows a guided admin action on the admin route', () => {
    pathname = '/admin';

    render(<TopHeader />);

    expect(screen.getByRole('button', { name: 'Start onboarding' })).toBeTruthy();
    fireEvent.click(screen.getByRole('button', { name: 'Start onboarding' }));
    expect(pushMock).toHaveBeenCalledWith('/admin?mode=create');
  });

  test('shows a billing action on the billing route', () => {
    pathname = '/billing';

    render(<TopHeader />);

    expect(screen.getByRole('button', { name: 'View pricing' })).toBeTruthy();
    fireEvent.click(screen.getByRole('button', { name: 'View pricing' }));
    expect(pushMock).toHaveBeenCalledWith('/pricing');
  });

  test('renders cross-module action as secondary by default so page-level actions remain primary', () => {
    render(<TopHeader />);

    const action = screen.getByRole('button', { name: 'Reports' });
    expect(action.className).toContain('header-btn-secondary');
    expect(action.className).toContain('header-btn-quiet');
    expect(action.className).toContain('header-cross-module-action');
  });
});
