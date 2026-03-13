import { cleanup, render } from '@testing-library/react';
import { afterEach, describe, expect, test, vi } from 'vitest';

const redirectMock = vi.fn();

vi.mock('next/navigation', () => ({
  redirect: (...args: unknown[]) => redirectMock(...args),
}));

import CustomersPage from '@/app/(app)/customers/page';

afterEach(() => {
  cleanup();
  redirectMock.mockReset();
});

describe('CustomersPage', () => {
  test('redirects customers route to sales', () => {
    render(<CustomersPage />);
    expect(redirectMock).toHaveBeenCalledWith('/sales');
  });
});
