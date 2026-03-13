import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, test, vi } from 'vitest';

const getPurchasesMock = vi.fn();
const getPurchaseDetailMock = vi.fn();
const getPurchaseFormOptionsMock = vi.fn();
const createPurchaseMock = vi.fn();

vi.mock('@/lib/api/purchases', () => ({
  getPurchases: (...args: unknown[]) => getPurchasesMock(...args),
  getPurchaseDetail: (...args: unknown[]) => getPurchaseDetailMock(...args),
  getPurchaseFormOptions: (...args: unknown[]) => getPurchaseFormOptionsMock(...args),
  createPurchase: (...args: unknown[]) => createPurchaseMock(...args),
}));

import { PurchasesWorkspace } from '@/components/purchases/purchases-workspace';

describe('PurchasesWorkspace', () => {
  afterEach(() => cleanup());

  beforeEach(() => {
    vi.resetAllMocks();
    getPurchasesMock.mockResolvedValue({ items: [] });
    getPurchaseDetailMock.mockResolvedValue(null);
    getPurchaseFormOptionsMock.mockResolvedValue({
      products: [
        {
          variant_id: 'v-1',
          product_id: 'p-1',
          label: 'Tee / Size:M / TEE-001',
          current_stock: 4,
          default_purchase_price: 14,
          sku: 'TEE-001',
          barcode: '',
        },
      ],
      suppliers: [],
    });
    createPurchaseMock.mockResolvedValue({ purchase_id: 'pur-1' });
  });

  test('prefills unit cost from the catalog default purchase price when a variant is selected', async () => {
    const { container } = render(<PurchasesWorkspace />);

    await waitFor(() => expect(screen.getByText('Create Purchase / Stock-In')).toBeTruthy());

    const lineSelect = container.querySelector('.sale-line-row select') as HTMLSelectElement;
    fireEvent.change(lineSelect, { target: { value: 'v-1' } });

    const unitCostInput = screen.getByLabelText('Unit cost 1') as HTMLInputElement;
    expect(unitCostInput.value).toBe('14');
  });
});
