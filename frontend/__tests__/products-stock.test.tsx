import React from 'react';
import { cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { afterEach, describe, expect, test, vi } from 'vitest';

vi.mock('@/lib/api/products-stock', () => ({
  getProductsStockSnapshot: vi.fn(async () => ({
    products: [
      {
        id: 'p-100',
        identity: {
          productName: 'Urban Fit Tee',
          supplier: 'Nova Textiles',
          category: 'Apparel',
          description: 'Premium cotton crew-neck t-shirt.',
          features: ['180 GSM', 'Bio-washed', 'Regular fit']
        },
        variants: [
          {
            id: 'v-1001',
            label: 'S / Black',
            size: 'S',
            color: 'Black',
            qty: 42,
            cost: 8.75,
            defaultSellingPrice: 16.5,
            maxDiscountPct: 10
          },
          {
            id: 'v-1002',
            label: 'M / White',
            size: 'M',
            color: 'White',
            qty: 33,
            cost: 8.75,
            defaultSellingPrice: 16.5,
            maxDiscountPct: 10
          }
        ]
      }
    ],
    suppliers: ['Nova Textiles', 'HydroWorks', 'Peak Source'],
    categories: ['Apparel', 'Lifestyle', 'Accessories']
  })),
  saveProductStock: vi.fn(async () => ({ success: true as const }))
}));

import { ProductsStockWorkspace } from '@/components/products-stock/products-stock-workspace';
import { getProductsStockSnapshot, saveProductStock } from '@/lib/api/products-stock';

afterEach(() => {
  cleanup();
});

describe('ProductsStockWorkspace', () => {

  test('chooser keeps results hidden until at least one character is typed and clears when emptied', async () => {
    render(<ProductsStockWorkspace />);

    expect(screen.queryByText('Urban Fit Tee')).toBeNull();

    const chooserInput = screen.getByLabelText('Product chooser input');
    fireEvent.change(chooserInput, { target: { value: 'Urban' } });
    expect(await screen.findByText('Urban Fit Tee')).toBeTruthy();

    fireEvent.change(chooserInput, { target: { value: '' } });
    await waitFor(() => {
      expect(screen.queryByText('Urban Fit Tee')).toBeNull();
      expect(screen.queryByText('Add new product: "Urban"')).toBeNull();
    });
  });
  test('smart chooser shows add-new option while typing', async () => {
    render(<ProductsStockWorkspace />);

    const chooserInput = screen.getByLabelText('Product chooser input');
    fireEvent.change(chooserInput, { target: { value: 'Night Runner' } });

    expect(screen.getByText('Add new product: "Night Runner"')).toBeTruthy();
  });

  test('selecting existing product loads existing-product mode', async () => {
    render(<ProductsStockWorkspace />);

    const chooserInput = screen.getByLabelText('Product chooser input');
    fireEvent.change(chooserInput, { target: { value: 'Urban Fit Tee' } });

    const productOption = await screen.findByText('Urban Fit Tee');
    fireEvent.click(productOption);

    await waitFor(() => {
      expect(screen.queryByText('Generate combinations')).toBeNull();
      expect(screen.getByDisplayValue('S / Black')).toBeTruthy();
    });
  });

  test('new product mode generates variants from comma-separated inputs', async () => {
    render(<ProductsStockWorkspace />);

    fireEvent.change(screen.getByLabelText('Product chooser input'), { target: { value: 'Fresh Tee' } });
    fireEvent.click(screen.getByText('Add new product: "Fresh Tee"'));

    fireEvent.change(screen.getByPlaceholderText('S, M, L'), { target: { value: 'S, M' } });
    fireEvent.change(screen.getByPlaceholderText('Black, White'), { target: { value: 'Black, White' } });
    fireEvent.click(screen.getByText('Generate combinations'));

    await waitFor(() => {
      expect(screen.getByDisplayValue('Fresh Tee / S / Black')).toBeTruthy();
      expect(screen.getByDisplayValue('Fresh Tee / M / White')).toBeTruthy();
      expect(screen.getByText('Variants: 4')).toBeTruthy();
    });
  });

  test('same-cost helper populates all row costs', async () => {
    render(<ProductsStockWorkspace />);

    fireEvent.change(screen.getByLabelText('Product chooser input'), { target: { value: 'Fresh Tee' } });
    fireEvent.click(screen.getByText('Add new product: "Fresh Tee"'));
    fireEvent.change(screen.getByPlaceholderText('S, M, L'), { target: { value: 'S, M' } });
    fireEvent.click(screen.getByText('Generate combinations'));

    fireEvent.click(screen.getByLabelText('Same cost for all variants'));
    fireEvent.change(screen.getByLabelText('Shared cost'), { target: { value: '12.5' } });
    fireEvent.click(screen.getByText('Apply shared cost'));

    await waitFor(() => {
      const table = screen.getByRole('table');
      const costInputs = within(table).getAllByDisplayValue('12.5');
      expect(costInputs.length).toBe(2);
    });
  });


  test('features input keeps trailing comma so users can enter multiple features naturally', async () => {
    render(<ProductsStockWorkspace />);

    fireEvent.change(screen.getByLabelText('Product chooser input'), { target: { value: 'Fresh Tee' } });
    fireEvent.click(screen.getByText('Add new product: "Fresh Tee"'));

    const featuresInput = screen.getByPlaceholderText('Breathable, Durable, Quick-dry') as HTMLInputElement;

    fireEvent.change(featuresInput, { target: { value: 'Breathable,' } });
    await waitFor(() => {
      expect(featuresInput.value).toBe('Breathable,');
    });

    fireEvent.change(featuresInput, { target: { value: 'Breathable, Durable' } });
    await waitFor(() => {
      expect(featuresInput.value).toBe('Breathable, Durable');
    });
  });


  test('shows explicit reload error when save succeeds but snapshot refresh fails', async () => {
    vi.mocked(saveProductStock).mockResolvedValueOnce({ success: true });
    vi.mocked(getProductsStockSnapshot)
      .mockResolvedValueOnce({
        products: [],
        suppliers: [],
        categories: []
      })
      .mockRejectedValueOnce(new Error('Snapshot refresh failed'));

    render(<ProductsStockWorkspace />);

    fireEvent.change(screen.getByLabelText('Product chooser input'), { target: { value: 'Fresh Tee' } });
    fireEvent.click(screen.getByText('Add new product: "Fresh Tee"'));
    fireEvent.change(screen.getByPlaceholderText('S, M, L'), { target: { value: 'S, M' } });
    fireEvent.click(screen.getByText('Generate combinations'));

    fireEvent.click(screen.getByText('Save'));

    expect(await screen.findByText(/Saved successfully, but refresh failed:/)).toBeTruthy();
    expect(screen.getByText(/Snapshot refresh failed/)).toBeTruthy();
  });

  test('summary values update based on variant edits', async () => {
    render(<ProductsStockWorkspace />);

    fireEvent.change(screen.getByLabelText('Product chooser input'), { target: { value: 'Urban Fit Tee' } });
    fireEvent.click(await screen.findByText('Urban Fit Tee'));

    const qtyInputs = screen.getAllByDisplayValue(/^(42|33)$/) as HTMLInputElement[];
    fireEvent.change(qtyInputs[0], { target: { value: '10' } });

    await waitFor(() => {
      expect(screen.getByText('Total Qty: 43')).toBeTruthy();
      expect(screen.getByText('Estimated Stock Cost: $376.25')).toBeTruthy();
    });
  });
});
