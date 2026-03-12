import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, test, vi } from 'vitest';

const pushMock = vi.fn();

vi.mock('next/navigation', () => ({
  usePathname: () => '/dashboard',
  useRouter: () => ({ push: pushMock }),
}));

import { TopHeader } from '@/components/layout/top-header';

describe('TopHeader', () => {
  beforeEach(() => {
    pushMock.mockReset();
  });

  afterEach(() => {
    cleanup();
  });

  test('submits scoped search query to the expected route', () => {
    render(<TopHeader />);

    fireEvent.change(screen.getByLabelText('Search scope'), { target: { value: 'inventory' } });
    fireEvent.change(screen.getByLabelText('Search query'), { target: { value: 'Blue Tee' } });
    fireEvent.click(screen.getByRole('button', { name: 'Search' }));

    expect(pushMock).toHaveBeenCalledWith('/inventory?q=Blue+Tee');
  });

  test('does not navigate for empty search values', () => {
    render(<TopHeader />);

    fireEvent.change(screen.getByLabelText('Search query'), { target: { value: '   ' } });
    fireEvent.click(screen.getByRole('button', { name: 'Search' }));

    expect(pushMock).not.toHaveBeenCalled();
  });
});
