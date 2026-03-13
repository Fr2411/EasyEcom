import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, test, vi } from 'vitest';
import { ProductsStockWorkspace } from '@/components/products-stock/products-stock-workspace';
import { ApiNetworkError } from '@/lib/api/client';
import { getCatalogProduct, getCatalogProducts, saveCatalogProduct } from '@/lib/api/catalog';

vi.mock('@/lib/api/catalog', () => ({
  getCatalogProducts: vi.fn(),
  getCatalogProduct: vi.fn(),
  saveCatalogProduct: vi.fn(),
}));

vi.mock('@/lib/env', () => ({
  getPublicEnv: () => ({ apiBaseUrl: 'https://api.easy-ecom.test' }),
}));

describe('ProductsStockWorkspace', () => {
  afterEach(() => cleanup());

  beforeEach(() => {
    vi.resetAllMocks();
    vi.mocked(getCatalogProducts).mockResolvedValue({ products: [], suppliers: [], categories: [] });
    vi.mocked(getCatalogProduct).mockResolvedValue({
      product_id: 'p-existing',
      identity: {
        productName: 'Existing Tee',
        supplier: 'Nova',
        category: 'Apparel',
        description: '',
        features: [],
      },
      variants: [
        {
          tempId: 'temp-existing',
          variant_id: 'v-existing',
          size: 'M',
          color: 'Black',
          other: '',
          defaultPurchasePrice: 11,
          defaultSellingPrice: 22,
          maxDiscountPct: 10,
          isArchived: false,
        },
      ],
    });
    vi.mocked(saveCatalogProduct).mockResolvedValue({ product_id: 'p-1', variant_count: 1 });
  });

  test('blank identity rows cannot be saved', async () => {
    render(<ProductsStockWorkspace />);
    fireEvent.change(screen.getByLabelText('Product chooser input'), { target: { value: 'New Tee' } });
    fireEvent.click(screen.getByText('Add new product: "New Tee"'));
    fireEvent.click(screen.getByText('Add row'));

    await waitFor(() => {
      expect((screen.getByText('Save') as HTMLButtonElement).disabled).toBe(true);
    });
    expect(saveCatalogProduct).not.toHaveBeenCalled();
  });

  test('duplicate identity rows cannot be saved', async () => {
    render(<ProductsStockWorkspace />);
    fireEvent.change(screen.getByLabelText('Product chooser input'), { target: { value: 'New Tee' } });
    fireEvent.click(screen.getByText('Add new product: "New Tee"'));
    fireEvent.change(screen.getByPlaceholderText('S, M, L'), { target: { value: 'S' } });
    fireEvent.click(screen.getByText('Generate combinations'));
    fireEvent.click(screen.getByText('Add row'));

    const table = screen.getByRole('table');
    const rows = Array.from(table.querySelectorAll('tbody tr'));
    const newRowInputs = Array.from(rows[rows.length - 1].querySelectorAll('input'));
    fireEvent.change(newRowInputs[0], { target: { value: 'S' } });

    await waitFor(() => {
      expect((screen.getByText('Save') as HTMLButtonElement).disabled).toBe(true);
    });
  });

  test('loads an existing product and appends generated variants without dropping current rows', async () => {
    vi.mocked(getCatalogProducts).mockResolvedValue({
      products: [
        {
          product_id: 'p-existing',
          identity: {
            productName: 'Existing Tee',
            supplier: 'Nova',
            category: 'Apparel',
            description: '',
            features: [],
          },
          variants: [],
        },
      ],
      suppliers: ['Nova'],
      categories: ['Apparel'],
    });

    render(<ProductsStockWorkspace />);

    await waitFor(() => {
      expect(screen.getByRole('button', { name: 'Open: Existing Tee' })).toBeTruthy();
    });
    fireEvent.click(screen.getByRole('button', { name: 'Open: Existing Tee' }));

    await waitFor(() => {
      expect(getCatalogProduct).toHaveBeenCalledWith('p-existing');
      expect(screen.getByText('Editing existing product')).toBeTruthy();
    });

    fireEvent.change(screen.getByPlaceholderText('S, M, L'), { target: { value: 'L' } });
    fireEvent.click(screen.getByText('Generate combinations'));

    await waitFor(() => {
      const table = screen.getByRole('table');
      expect(table.querySelectorAll('tbody tr').length).toBe(2);
      expect(screen.getByDisplayValue('M')).toBeTruthy();
      expect(screen.getAllByDisplayValue('L').length).toBeGreaterThanOrEqual(1);
    });
  });

  test('includes purchase price defaults in save payload', async () => {
    render(<ProductsStockWorkspace />);

    fireEvent.change(screen.getByLabelText('Product chooser input'), { target: { value: 'New Tee' } });
    fireEvent.click(screen.getByText('Add new product: "New Tee"'));
    fireEvent.click(screen.getByText('Add row'));

    const table = screen.getByRole('table');
    const rowInputs = Array.from(table.querySelectorAll('tbody tr:first-child input'));
    fireEvent.change(rowInputs[0] as HTMLInputElement, { target: { value: 'S' } });
    fireEvent.change(rowInputs[3] as HTMLInputElement, { target: { value: '12' } });
    fireEvent.change(rowInputs[4] as HTMLInputElement, { target: { value: '24' } });
    fireEvent.click(screen.getByText('Save'));

    await waitFor(() => {
      expect(saveCatalogProduct).toHaveBeenCalledWith(
        expect.objectContaining({
          variants: [
            expect.objectContaining({
              size: 'S',
              defaultPurchasePrice: 12,
              defaultSellingPrice: 24,
            }),
          ],
        }),
      );
    });
  });

  test('shows a specific catalog load message for API reachability failures', async () => {
    vi.mocked(getCatalogProducts).mockRejectedValue(new ApiNetworkError('Load failed'));

    render(<ProductsStockWorkspace />);

    await waitFor(() => {
      expect(
        screen.getByText(
          'Catalog cannot reach the API. Check NEXT_PUBLIC_API_BASE_URL, HTTPS, and whether the backend is running.',
        ),
      ).toBeTruthy();
    });
  });

  test('shows clear network/api error message', async () => {
    vi.mocked(saveCatalogProduct).mockRejectedValue(new Error('{"detail":"API timeout while saving product"}'));
    render(<ProductsStockWorkspace />);

    fireEvent.change(screen.getByLabelText('Product chooser input'), { target: { value: 'New Tee' } });
    fireEvent.click(screen.getByText('Add new product: "New Tee"'));
    fireEvent.change(screen.getByPlaceholderText('S, M, L'), { target: { value: 'S' } });
    fireEvent.click(screen.getByText('Generate combinations'));
    fireEvent.click(screen.getByText('Save'));

    await waitFor(() => {
      expect(screen.getByText('API timeout while saving product')).toBeTruthy();
    });
  });
});
