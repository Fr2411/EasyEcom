import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, describe, expect, test, vi } from 'vitest';

const getSalesMock = vi.fn();
const getSalesFormOptionsMock = vi.fn();
const createSaleMock = vi.fn();
const getSaleDetailMock = vi.fn();
const createCustomerMock = vi.fn();

vi.mock('@/lib/api/sales', () => ({
  getSales: (...args: unknown[]) => getSalesMock(...args),
  getSalesFormOptions: (...args: unknown[]) => getSalesFormOptionsMock(...args),
  createSale: (...args: unknown[]) => createSaleMock(...args),
  getSaleDetail: (...args: unknown[]) => getSaleDetailMock(...args),
}));

vi.mock('@/lib/api/customers', () => ({
  createCustomer: (...args: unknown[]) => createCustomerMock(...args),
}));

import SalesPage from '@/app/(app)/sales/page';

afterEach(() => {
  cleanup();
  getSalesMock.mockReset();
  getSalesFormOptionsMock.mockReset();
  createSaleMock.mockReset();
  getSaleDetailMock.mockReset();
  createCustomerMock.mockReset();
});

describe('SalesPage', () => {
  test('renders empty state', async () => {
    getSalesMock.mockResolvedValue({ items: [] });
    getSalesFormOptionsMock.mockResolvedValue({ customers: [], products: [] });

    render(<SalesPage />);

    expect(screen.getByRole('heading', { name: 'Sales' })).toBeTruthy();
    await waitFor(() => expect(screen.getByText('No sales yet')).toBeTruthy());
  });

  test('creates sale and shows totals', async () => {
    getSalesMock.mockResolvedValue({ items: [] });
    getSalesFormOptionsMock
      .mockResolvedValueOnce({
        customers: [{ customer_id: 'cust-a', full_name: 'Alice', phone: '01700', email: 'a@x.com' }],
        products: [{ product_id: 'prd-1', label: 'T-Shirt', default_unit_price: 100, available_qty: 10 }],
      })
      .mockResolvedValueOnce({
        customers: [{ customer_id: 'cust-a', full_name: 'Alice', phone: '01700', email: 'a@x.com' }],
        products: [{ product_id: 'prd-1', label: 'T-Shirt', default_unit_price: 100, available_qty: 10 }],
      });
    createSaleMock.mockResolvedValue({ sale_id: 'sale-new' });

    render(<SalesPage />);

    await waitFor(() => expect(screen.getByText('Create Sale')).toBeTruthy());
    fireEvent.change(screen.getByPlaceholderText('Enter phone number'), { target: { value: '01700' } });
    fireEvent.blur(screen.getByPlaceholderText('Enter phone number'));

    const selects = screen.getAllByRole('combobox');
    fireEvent.change(selects[0], { target: { value: 'prd-1' } });
    fireEvent.change(screen.getByLabelText('Quantity 1'), { target: { value: '2' } });

    await waitFor(() => expect(screen.getByText('Subtotal: 200.00')).toBeTruthy());
    fireEvent.click(screen.getByRole('button', { name: 'Submit Sale' }));
    await waitFor(() => expect(createSaleMock).toHaveBeenCalled());
  });

  test('creates a customer when phone does not exist', async () => {
    getSalesMock.mockResolvedValue({ items: [] });
    getSalesFormOptionsMock.mockResolvedValue({
      customers: [],
      products: [{ product_id: 'prd-1', label: 'T-Shirt', default_unit_price: 100, available_qty: 10 }],
    });
    createCustomerMock.mockResolvedValue({ customer: { customer_id: 'new-c', full_name: 'Bob', phone: '01800', email: '' } });
    createSaleMock.mockResolvedValue({ sale_id: 'sale-new' });

    render(<SalesPage />);
    await waitFor(() => expect(screen.getByText('Create Sale')).toBeTruthy());

    fireEvent.change(screen.getByPlaceholderText('Enter phone number'), { target: { value: '01800' } });
    fireEvent.change(screen.getByPlaceholderText('Auto-filled for existing customer'), { target: { value: 'Bob' } });
    fireEvent.change(screen.getAllByRole('combobox')[0], { target: { value: 'prd-1' } });
    fireEvent.click(screen.getByRole('button', { name: 'Submit Sale' }));

    await waitFor(() => expect(createCustomerMock).toHaveBeenCalled());
    await waitFor(() => expect(createSaleMock).toHaveBeenCalled());
  });
});
