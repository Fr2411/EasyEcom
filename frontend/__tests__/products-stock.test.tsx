import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, test, vi } from 'vitest';
import { ProductsStockWorkspace } from '@/components/products-stock/products-stock-workspace';
import { getProductsStockSnapshot, saveProductStock } from '@/lib/api/products-stock';

vi.mock('@/lib/api/products-stock', () => ({
  getProductsStockSnapshot: vi.fn(),
  saveProductStock: vi.fn()
}));

describe('ProductsStockWorkspace', () => {
  afterEach(() => cleanup());

  beforeEach(() => {
    vi.resetAllMocks();
    vi.mocked(getProductsStockSnapshot).mockResolvedValue({ products: [], suppliers: [], categories: [] });
    vi.mocked(saveProductStock).mockResolvedValue({ success: true });
  });

  test('blank identity rows cannot be saved', async () => {
    render(<ProductsStockWorkspace />);
    fireEvent.change(screen.getByLabelText('Product chooser input'), { target: { value: 'New Tee' } });
    fireEvent.click(screen.getByText('Add new product: "New Tee"'));
    fireEvent.click(screen.getByText('Add row'));

    await waitFor(() => {
      expect((screen.getByText('Save') as HTMLButtonElement).disabled).toBe(true);
    });
    expect(saveProductStock).not.toHaveBeenCalled();
  });

  test('duplicate identity rows cannot be saved', async () => {
    render(<ProductsStockWorkspace />);
    fireEvent.change(screen.getByLabelText('Product chooser input'), { target: { value: 'New Tee' } });
    fireEvent.click(screen.getByText('Add new product: "New Tee"'));
    fireEvent.change(screen.getByPlaceholderText('S, M, L'), { target: { value: 'S' } });
    fireEvent.click(screen.getByText('Generate combinations'));
    fireEvent.click(screen.getByText('Add row'));

    const sizeInputs = screen.getAllByRole('cell').flatMap((cell) => Array.from(cell.querySelectorAll('input'))).slice(0, 8);
    fireEvent.change(sizeInputs[3], { target: { value: 'S' } });

    await waitFor(() => {
      expect((screen.getByText('Save') as HTMLButtonElement).disabled).toBe(true);
    });
  });

  test('shows clear network/api error message', async () => {
    vi.mocked(saveProductStock).mockRejectedValue(new Error('{"detail":"API timeout while saving product"}'));
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
