import { describe, expect, test } from 'vitest';
import { deriveIntakeRecommendation, deriveInventoryProductGroups } from '@/components/commerce/inventory-workspace';
import type { InventoryIntakeLookup, InventoryStockRow } from '@/types/inventory';

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

describe('deriveInventoryProductGroups', () => {
  test('groups variant rows under a single product and aggregates quantities', () => {
    const groups = deriveInventoryProductGroups([
      {
        variant_id: 'v1',
        product_id: 'p1',
        product_name: 'Runner',
        image_url: '',
        image: null,
        label: 'Runner / 41 / Black',
        sku: 'RUN-41-BLK',
        barcode: '111',
        supplier: 'Supplier A',
        category: 'Shoes',
        location_id: 'loc-1',
        location_name: 'Main',
        unit_cost: '20',
        unit_price: '40',
        reorder_level: '2',
        on_hand: '3.000',
        reserved: '1.000',
        available_to_sell: '2.000',
        low_stock: false,
      },
      {
        variant_id: 'v2',
        product_id: 'p1',
        product_name: 'Runner',
        image_url: '',
        image: null,
        label: 'Runner / 42 / Black',
        sku: 'RUN-42-BLK',
        barcode: '222',
        supplier: 'Supplier A',
        category: 'Shoes',
        location_id: 'loc-1',
        location_name: 'Main',
        unit_cost: '21',
        unit_price: '41',
        reorder_level: '2',
        on_hand: '5.000',
        reserved: '0.000',
        available_to_sell: '5.000',
        low_stock: true,
      },
    ] as InventoryStockRow[]);

    expect(groups).toHaveLength(1);
    expect(groups[0].product_name).toBe('Runner');
    expect(groups[0].variants).toHaveLength(2);
    expect(groups[0].on_hand).toBe(8);
    expect(groups[0].available_to_sell).toBe(7);
    expect(groups[0].low_stock_count).toBe(1);
  });
});
