import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, describe, expect, test, vi } from 'vitest';

const getPurchasesMock = vi.fn();
const getPurchaseFormOptionsMock = vi.fn();
const createPurchaseMock = vi.fn();
const getPurchaseDetailMock = vi.fn();

vi.mock('@/lib/api/purchases', () => ({
  getPurchases: (...args: unknown[]) => getPurchasesMock(...args),
  getPurchaseFormOptions: (...args: unknown[]) => getPurchaseFormOptionsMock(...args),
  createPurchase: (...args: unknown[]) => createPurchaseMock(...args),
  getPurchaseDetail: (...args: unknown[]) => getPurchaseDetailMock(...args),
}));

import PurchasesPage from '@/app/(app)/purchases/page';

afterEach(() => {
  cleanup();
  getPurchasesMock.mockReset();
  getPurchaseFormOptionsMock.mockReset();
  createPurchaseMock.mockReset();
  getPurchaseDetailMock.mockReset();
});

describe('PurchasesPage', () => {
  test('renders purchases empty state', async () => {
    getPurchasesMock.mockResolvedValue({ items: [] });
    getPurchaseFormOptionsMock.mockResolvedValue({ products: [], suppliers: [] });

    render(<PurchasesPage />);

    expect(screen.getByRole('heading', { name: 'Purchases' })).toBeTruthy();
    await waitFor(() => expect(screen.getByText('No purchases yet')).toBeTruthy());
  });

  test('creates purchase and computes totals', async () => {
    getPurchasesMock.mockResolvedValue({ items: [] });
    getPurchaseFormOptionsMock.mockResolvedValue({
      products: [{ product_id: 'prd-1', label: 'Paper', current_stock: 5 }],
      suppliers: [{ supplier_id: 'sup-1', name: 'Main Supplier' }],
    });
    createPurchaseMock.mockResolvedValue({ purchase_id: 'pur-new' });

    render(<PurchasesPage />);

    await waitFor(() => expect(screen.getByText('Create Purchase / Stock-In')).toBeTruthy());
    fireEvent.change(screen.getByDisplayValue('Select product/variant'), { target: { value: 'prd-1' } });
    fireEvent.change(screen.getByLabelText('Purchase quantity 1'), { target: { value: '2' } });
    fireEvent.change(screen.getByLabelText('Unit cost 1'), { target: { value: '10' } });

    await waitFor(() => expect(screen.getByText('Purchase Total: 20.00')).toBeTruthy());
    fireEvent.click(screen.getByRole('button', { name: 'Submit Purchase' }));
    await waitFor(() => expect(createPurchaseMock).toHaveBeenCalled());
  });
});
