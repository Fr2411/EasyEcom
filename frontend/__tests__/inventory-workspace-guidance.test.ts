import { describe, expect, test } from 'vitest';
import {
  deriveIntakeRecommendation,
  deriveInventoryProductGroups,
  deriveInventorySearchSuggestions,
  receiveLinesFromPurchaseOrder,
} from '@/components/commerce/inventory-workspace';
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

describe('deriveInventorySearchSuggestions', () => {
  test('returns product, sku, and variant-derived suggestions prioritized by prefix match', () => {
    const suggestions = deriveInventorySearchSuggestions(
      [
        {
          variant_id: 'v1',
          product_id: 'p1',
          product_name: 'Runner Shoe',
          image_url: '',
          image: null,
          label: 'Runner Shoe / 41 / Black',
          sku: 'RUN-41-BLK',
          barcode: '111',
          supplier: 'Sport Hub',
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
      ] as InventoryStockRow[],
      'run',
    );

    expect(suggestions[0]).toBe('RUN-41-BLK');
    expect(suggestions).toContain('Runner Shoe');
    expect(suggestions).toContain('Runner Shoe / 41 / Black');
  });
});

describe('receiveLinesFromPurchaseOrder', () => {
  test('maps purchase-order lines into receive-stock lines with variant id, quantity, and cost', () => {
    const lines = receiveLinesFromPurchaseOrder({
      purchase_id: 'po-1',
      purchase_no: 'PO-1001',
      purchase_date: '2026-04-10',
      supplier_id: 'sup-1',
      supplier_name: 'Supplier',
      reference_no: '',
      subtotal: 100,
      status: 'draft',
      created_at: '2026-04-10T00:00:00Z',
      note: '',
      created_by_user_id: 'user-1',
      lines: [
        {
          line_id: 'line-1',
          variant_id: 'variant-1',
          product_id: 'product-1',
          product_name: 'Runner',
          qty: 5,
          unit_cost: 12.5,
          line_total: 62.5,
        },
      ],
    });

    expect(lines).toHaveLength(1);
    expect(lines[0].variant_id).toBe('variant-1');
    expect(lines[0].quantity).toBe('5');
    expect(lines[0].default_purchase_price).toBe('12.5');
  });
});
