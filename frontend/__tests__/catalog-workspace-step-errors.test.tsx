import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, test, vi } from 'vitest';

import { CatalogWorkspace } from '@/components/commerce/catalog-workspace';
import { ApiError } from '@/lib/api/client';

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
    fireEvent.click(screen.getByRole('tab', { name: 'Start New Product' }));

    const productNameInput = await screen.findByLabelText('Product name');
    fireEvent.change(productNameInput, { target: { value: 'A' } });

    fireEvent.click(screen.getByRole('button', { name: 'Next: First Variant' }));

    await waitFor(() => expect(screen.getByText('Product name must be at least 2 characters.')).toBeTruthy());
    expect(screen.getByRole('alert').textContent).toContain('Cannot continue: complete the required Product fields.');
  });
});
