import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, describe, expect, test, vi } from 'vitest';

const getReturnsMock = vi.fn();
const getReturnSalesLookupMock = vi.fn();
const getReturnableSaleMock = vi.fn();
const createReturnMock = vi.fn();
const getReturnDetailMock = vi.fn();

vi.mock('@/lib/api/returns', () => ({
  getReturns: (...args: unknown[]) => getReturnsMock(...args),
  getReturnSalesLookup: (...args: unknown[]) => getReturnSalesLookupMock(...args),
  getReturnableSale: (...args: unknown[]) => getReturnableSaleMock(...args),
  createReturn: (...args: unknown[]) => createReturnMock(...args),
  getReturnDetail: (...args: unknown[]) => getReturnDetailMock(...args),
}));

import ReturnsPage from '@/app/(app)/returns/page';

afterEach(() => {
  cleanup();
  getReturnsMock.mockReset();
  getReturnSalesLookupMock.mockReset();
  getReturnableSaleMock.mockReset();
  createReturnMock.mockReset();
  getReturnDetailMock.mockReset();
});

describe('ReturnsPage', () => {
  test('renders empty state', async () => {
    getReturnsMock.mockResolvedValue({ items: [] });
    getReturnSalesLookupMock.mockResolvedValue({ items: [] });

    render(<ReturnsPage />);

    expect(screen.getByRole('heading', { name: 'Returns' })).toBeTruthy();
    await waitFor(() => expect(screen.getByText('No returns yet')).toBeTruthy());
  });

  test('validates return qty and submits', async () => {
    getReturnsMock.mockResolvedValue({ items: [] });
    getReturnSalesLookupMock.mockResolvedValue({ items: [{ sale_id: 'sale-1', sale_no: 'SAL-1', customer_id: 'c1', customer_name: 'Alice', sale_date: '2026-03-10', total: 100, status: 'confirmed' }] });
    getReturnableSaleMock.mockResolvedValue({ sale_id: 'sale-1', sale_no: 'SAL-1', customer_id: 'c1', customer_name: 'Alice', sale_date: '2026-03-10', lines: [{ sale_item_id: 'si-1', product_id: 'p1', product_name: 'Tee', sold_qty: 2, already_returned_qty: 0, eligible_qty: 1, unit_price: 50 }] });
    createReturnMock.mockResolvedValue({ return_id: 'ret-new', return_no: 'RET-1' });

    render(<ReturnsPage />);
    await waitFor(() => expect(screen.getByText('Create Return')).toBeTruthy());

    fireEvent.change(screen.getByLabelText('Sale'), { target: { value: 'sale-1' } });
    await waitFor(() => expect(screen.getByText(/Return Total/)).toBeTruthy());

    fireEvent.change(screen.getByLabelText('Return qty si-1'), { target: { value: '2' } });
    await waitFor(() => expect(screen.getByText(/exceeds eligible/)).toBeTruthy());

    fireEvent.change(screen.getByLabelText('Return qty si-1'), { target: { value: '1' } });
    fireEvent.click(screen.getByRole('button', { name: 'Submit Return' }));
    await waitFor(() => expect(createReturnMock).toHaveBeenCalled());
  });
});
