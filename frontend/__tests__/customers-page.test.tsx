import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, describe, expect, test, vi } from 'vitest';

import type { Customer } from '@/types/customers';

const getCustomersMock = vi.fn();
const createCustomerMock = vi.fn();
const updateCustomerMock = vi.fn();

vi.mock('@/lib/api/customers', () => ({
  getCustomers: (...args: unknown[]) => getCustomersMock(...args),
  createCustomer: (...args: unknown[]) => createCustomerMock(...args),
  updateCustomer: (...args: unknown[]) => updateCustomerMock(...args),
}));

import CustomersPage from '@/app/(app)/customers/page';

const baseCustomer: Customer = {
  customer_id: 'cust-1',
  full_name: 'Alice Retail',
  phone: '12345',
  email: 'alice@example.com',
  address_line1: 'Main Street',
  city: 'Austin',
  notes: '',
  is_active: true,
  created_at: '2026-01-01T00:00:00Z',
  updated_at: '2026-01-01T00:00:00Z',
};

afterEach(() => {
  cleanup();
  getCustomersMock.mockReset();
  createCustomerMock.mockReset();
  updateCustomerMock.mockReset();
});

describe('CustomersPage', () => {
  test('renders customer module empty state', async () => {
    getCustomersMock.mockResolvedValue({ items: [] });
    render(<CustomersPage />);

    expect(screen.getByRole('heading', { name: 'Customers' })).toBeTruthy();
    await waitFor(() => expect(screen.getByText('No customers yet')).toBeTruthy());
  });

  test('renders customer list and update action', async () => {
    getCustomersMock.mockResolvedValue({ items: [baseCustomer] });
    updateCustomerMock.mockResolvedValue({ customer: { ...baseCustomer, city: 'Dallas' } });

    render(<CustomersPage />);

    await waitFor(() => expect(screen.getByText('Alice Retail')).toBeTruthy());
    fireEvent.click(screen.getByText('Alice Retail'));
    const cityInputs = screen.getAllByLabelText('City');
    fireEvent.change(cityInputs[cityInputs.length - 1], { target: { value: 'Dallas' } });
    fireEvent.click(screen.getByRole('button', { name: 'Update Customer' }));

    await waitFor(() => expect(updateCustomerMock).toHaveBeenCalled());
  });
});
