import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, test, vi } from 'vitest';

import { CatalogWorkspace } from '@/components/commerce/catalog-workspace';
import { ApiError, ApiNetworkError } from '@/lib/api/client';

const mockGetCatalogWorkspace = vi.fn();
const mockSaveCatalogProduct = vi.fn();
const mockValidateCatalogCreationStep = vi.fn();
const mockRouterPush = vi.fn();
let searchParamsValue = new URLSearchParams();

vi.mock('next/navigation', () => ({
  useRouter: () => ({ push: mockRouterPush }),
  useSearchParams: () => searchParamsValue,
}));

vi.mock('@/lib/api/commerce', () => ({
  getCatalogWorkspace: (...args: unknown[]) => mockGetCatalogWorkspace(...args),
  saveCatalogProduct: (...args: unknown[]) => mockSaveCatalogProduct(...args),
  validateCatalogCreationStep: (...args: unknown[]) => mockValidateCatalogCreationStep(...args),
}));

describe('CatalogWorkspace step errors', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    searchParamsValue = new URLSearchParams();
    mockGetCatalogWorkspace.mockResolvedValue({
      query: '',
      has_multiple_locations: false,
      active_location: { location_id: 'loc-1', name: 'Main', is_default: true },
      locations: [{ location_id: 'loc-1', name: 'Main', is_default: true }],
      categories: [],
      suppliers: [],
      items: [],
    });
  });

  afterEach(() => {
    cleanup();
  });

  test('shows field-level and CTA-level guidance when Product step Next is blocked', async () => {
    mockValidateCatalogCreationStep.mockRejectedValue(
      new ApiError(
        422,
        '{"detail":[{"loc":["body","identity","product_name"],"msg":"String should have at least 2 characters","type":"string_too_short"}]} (https://example.com/catalog/products/validate-step)'
      )
    );

    render(<CatalogWorkspace />);

    await waitFor(() => expect(screen.getByText('No catalog items staged')).toBeTruthy());
    expect(screen.queryByTestId('catalog-top-start-new-product')).toBeNull();
    fireEvent.click(screen.getByRole('tab', { name: 'Start New Product' }));

    const productNameInput = await screen.findByLabelText('Product name');
    fireEvent.change(productNameInput, { target: { value: 'A' } });

    fireEvent.click(screen.getByRole('button', { name: 'Next: First Variant' }));

    await waitFor(() => expect(screen.getByText('Product name must be at least 2 characters.')).toBeTruthy());
    const summaryAlert = screen.getByRole('alert');
    expect(summaryAlert.textContent).toContain('Cannot continue: Product name needs attention.');
    expect(summaryAlert.textContent).toContain('Product name must be at least 2 characters.');
  });

  test('advances deterministically to First Variant when Product name is valid', async () => {
    mockValidateCatalogCreationStep.mockResolvedValue({ ok: true });

    render(<CatalogWorkspace />);

    await waitFor(() => expect(screen.getByText('No catalog items staged')).toBeTruthy());
    fireEvent.click(screen.getByRole('tab', { name: 'Start New Product' }));

    const productNameInput = await screen.findByLabelText('Product name');
    fireEvent.change(productNameInput, { target: { value: 'Runner Shoe' } });

    fireEvent.click(screen.getByRole('button', { name: 'Next: First Variant' }));

    await waitFor(() => {
      expect(screen.getByRole('button', { name: /2\. First Variant \(Current\)/ })).toBeTruthy();
    });
    expect(screen.getByRole('button', { name: '1. Product (Completed)' })).toBeTruthy();
    expect(screen.getByRole('button', { name: '3. Confirm (Locked)' })).toBeTruthy();
  });

  test('shows explicit final confirm and completion-state messaging after create', async () => {
    mockValidateCatalogCreationStep.mockResolvedValue({ ok: true });
    mockSaveCatalogProduct.mockResolvedValue({
      product: {
        product_id: 'prod-1',
        name: 'Runner Shoe',
      },
    });

    render(<CatalogWorkspace />);

    await waitFor(() => expect(screen.getByText('No catalog items staged')).toBeTruthy());
    fireEvent.click(screen.getByRole('tab', { name: 'Start New Product' }));

    const productNameInput = await screen.findByLabelText('Product name');
    fireEvent.change(productNameInput, { target: { value: 'Runner Shoe' } });

    fireEvent.click(screen.getByRole('button', { name: 'Next: First Variant' }));
    await waitFor(() => expect(screen.getByRole('button', { name: '2. First Variant (Current)' })).toBeTruthy());

    fireEvent.change(screen.getByLabelText('Size'), { target: { value: '42' } });
    fireEvent.click(screen.getByRole('button', { name: 'Next: Confirm' }));

    await waitFor(() => expect(screen.getByRole('button', { name: '3. Confirm (Current)' })).toBeTruthy());
    expect(screen.getByText(/Final confirm: select Create product to complete this flow\./)).toBeTruthy();

    fireEvent.click(screen.getByRole('button', { name: 'Create product' }));

    await waitFor(() => expect(screen.getByText('Product created: Runner Shoe')).toBeTruthy());
    expect(screen.getByText('Create flow complete. Product parent and first saleable variant are saved.')).toBeTruthy();
    expect(screen.getByText('Next: continue with variant-level operations.')).toBeTruthy();
  });

  test('shows plain-language workspace fallback with retry and secondary recovery path', async () => {
    mockGetCatalogWorkspace.mockRejectedValue(new ApiNetworkError('request timeout'));

    render(<CatalogWorkspace />);

    await waitFor(() => expect(screen.getByText('Catalog is taking longer than expected to load.')).toBeTruthy());
    expect(screen.getByText('Retry catalog load first. If it still fails, use Go to Dashboard to refresh your session.')).toBeTruthy();
    expect(screen.getByText('Your network or session may have timed out. Retry once to continue.')).toBeTruthy();
    expect(screen.getByText('Last search: all catalog products.')).toBeTruthy();
    expect(screen.queryByTestId('catalog-top-start-new-product')).toBeNull();

    fireEvent.click(screen.getByRole('button', { name: 'Retry catalog load' }));
    await waitFor(() => expect(mockGetCatalogWorkspace).toHaveBeenCalledTimes(2));
    await waitFor(() => expect(screen.getByText('Repeated failures: open Dashboard to refresh your session, wait a moment, then return to Catalog.')).toBeTruthy());

    fireEvent.click(screen.getByRole('button', { name: 'Go to Dashboard' }));
    expect(mockRouterPush).toHaveBeenCalledWith('/dashboard');
  });

  test('prioritizes catalog finder controls in keyboard tab sequence', async () => {
    render(<CatalogWorkspace />);

    const finderInput = await screen.findByPlaceholderText('Search product name, SKU, barcode, or variant');
    const finderSubmit = screen.getByRole('button', { name: 'Search catalog' });

    expect(finderInput.getAttribute('tabindex')).toBe('2');
    expect(finderSubmit.getAttribute('tabindex')).toBe('3');
  });
});
