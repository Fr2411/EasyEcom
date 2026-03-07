import React from 'react';
import { cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { afterEach, describe, expect, test } from 'vitest';
import { ProductsStockWorkspace } from '@/components/products-stock/products-stock-workspace';

afterEach(() => {
  cleanup();
});

describe('ProductsStockWorkspace', () => {
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
      expect(screen.getByDisplayValue('S / Black')).toBeTruthy();
      expect(screen.getByDisplayValue('M / White')).toBeTruthy();
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
