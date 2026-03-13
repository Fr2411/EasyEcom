import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, test, vi } from 'vitest';
import { ProductsStockWorkspace } from '@/components/products-stock/products-stock-workspace';
import { getCatalogProducts, saveCatalogProduct } from '@/lib/api/catalog';

vi.mock('@/lib/api/catalog', () => ({
  getCatalogProducts: vi.fn(),
  saveCatalogProduct: vi.fn(),
}));

describe('ProductsStockWorkspace', () => {
  afterEach(() => cleanup());

  beforeEach(() => {
    vi.resetAllMocks();
    vi.mocked(getCatalogProducts).mockResolvedValue({ products: [], suppliers: [], categories: [] });
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
