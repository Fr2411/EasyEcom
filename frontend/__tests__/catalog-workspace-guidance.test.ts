import { describe, expect, test } from 'vitest';
import { deriveCatalogRecommendation } from '@/components/commerce/catalog-workspace';
import type { CatalogProduct, CatalogWorkspace } from '@/types/catalog';

function buildProduct(overrides: Partial<CatalogProduct> = {}): CatalogProduct {
  return {
    product_id: 'product-1',
    name: 'Runner',
    brand: 'EasyEcom',
    status: 'active',
    supplier: 'Supplier A',
    category: 'Shoes',
    description: '',
    sku_root: 'RUN',
    default_price: '120',
    min_price: '90',
    max_discount_percent: '25',
    variants: [],
    ...overrides,
  };
}

function buildWorkspace(overrides: Partial<CatalogWorkspace>): CatalogWorkspace {
  return {
    query: 'demo',
    has_multiple_locations: false,
    active_location: { location_id: 'loc-1', name: 'Main', is_default: true },
    locations: [{ location_id: 'loc-1', name: 'Main', is_default: true }],
    categories: [],
    suppliers: [],
    items: [],
    ...overrides,
  };
}

describe('deriveCatalogRecommendation', () => {
  test('prompts for a product clue before any lookup runs', () => {
    const result = deriveCatalogRecommendation(null);

    expect(result.kind).toBe('idle');
    expect(result.actionLabel).toBe('Review next step');
  });

  test('prefers an exact product match when the query matches a product name or SKU root', () => {
    const result = deriveCatalogRecommendation(
      buildWorkspace({
        query: 'RUN',
        items: [buildProduct()],
      })
    );

    expect(result.kind).toBe('exact');
    expect(result.title).toContain('Runner');
    expect(result.actionLabel).toBe('Open product');
  });

  test('uses the strongest likely match when no exact match is found', () => {
    const result = deriveCatalogRecommendation(
      buildWorkspace({
        query: 'sho',
        items: [buildProduct({ name: 'Shoes Pro' })],
      })
    );

    expect(result.kind).toBe('likely');
    expect(result.title).toContain('Shoes Pro');
    expect(result.actionLabel).toBe('Review product');
  });

  test('falls back to a new product suggestion when there is no catalog match', () => {
    const result = deriveCatalogRecommendation(
      buildWorkspace({
        query: 'unknown',
        items: [],
      })
    );

    expect(result.kind).toBe('new');
    expect(result.title).toContain('No catalog match');
    expect(result.actionLabel).toBe('Start new product');
  });
});
