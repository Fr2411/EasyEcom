import { describe, expect, test } from 'vitest';
import { deriveIntakeRecommendation } from '@/components/commerce/inventory-workspace';
import type { InventoryIntakeLookup } from '@/types/inventory';

function buildLookup(overrides: Partial<InventoryIntakeLookup>): InventoryIntakeLookup {
  return {
    query: 'demo',
    exact_variants: [],
    product_matches: [],
    suggested_new_product: null,
    ...overrides,
  } as InventoryIntakeLookup;
}

describe('deriveIntakeRecommendation', () => {
  test('returns an idle guidance prompt when no lookup has run yet', () => {
    const result = deriveIntakeRecommendation(null);

    expect(result.kind).toBe('idle');
    expect(result.actionLabel).toBe('Review next step');
  });

  test('prefers exact variant matches over product matches', () => {
    const result = deriveIntakeRecommendation(
      buildLookup({
        exact_variants: [
          {
            match_reason: 'sku',
            product: {
              product_id: 'p1',
              name: 'Exact Product',
              variants: [],
            },
            variant: {
              label: 'Exact Variant',
            },
          } as unknown as InventoryIntakeLookup['exact_variants'][number],
        ],
        product_matches: [
          {
            product_id: 'p2',
            name: 'Fallback Product',
            variants: [{}, {}],
          } as unknown as InventoryIntakeLookup['product_matches'][number],
        ],
      })
    );

    expect(result.kind).toBe('exact');
    expect(result.title).toContain('Exact Variant');
    expect(result.actionLabel).toBe('Continue receiving');
  });

  test('uses the best product match when there is no exact variant', () => {
    const result = deriveIntakeRecommendation(
      buildLookup({
        product_matches: [
          {
            product_id: 'p1',
            name: 'Runner',
            variants: [{}, {}, {}],
          } as unknown as InventoryIntakeLookup['product_matches'][number],
        ],
      })
    );

    expect(result.kind).toBe('product');
    expect(result.title).toContain('Runner');
    expect(result.actionLabel).toBe('Review product');
  });

  test('falls back to a new product suggestion when nothing matches', () => {
    const result = deriveIntakeRecommendation(
      buildLookup({
        suggested_new_product: {
          product_name: 'No Match Item',
          sku_root: 'NMI',
        },
      })
    );

    expect(result.kind).toBe('new');
    expect(result.title).toContain('No Match Item');
    expect(result.actionLabel).toBe('Start new product');
  });
});
