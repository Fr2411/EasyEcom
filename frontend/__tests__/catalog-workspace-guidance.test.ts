import { describe, expect, test } from 'vitest';
import { ApiError, ApiNetworkError } from '@/lib/api/client';
import {
  deriveCatalogVariantOperationalScan,
  deriveCatalogInlineErrors,
  deriveCatalogRecommendation,
  deriveCatalogStepBlockedSummary,
  deriveCatalogStepSafeError,
  normalizeFirstVariantForCreateFlow,
} from '@/components/commerce/catalog-workspace';
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
    image_url: '',
    image: null,
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

describe('deriveCatalogVariantOperationalScan', () => {
  test('prioritizes active variants and lowest available stock for operational scanning', () => {
    const rows = deriveCatalogVariantOperationalScan([
      {
        variant_id: 'v-archived',
        product_id: 'p-1',
        product_name: 'Runner',
        title: 'Archived',
        label: 'Archived / Legacy',
        sku: 'RUN-OLD',
        barcode: '',
        status: 'archived',
        options: { size: '40', color: 'Gray', other: '' },
        unit_cost: null,
        unit_price: null,
        min_price: null,
        effective_unit_price: null,
        effective_min_price: null,
        is_price_inherited: false,
        is_min_price_inherited: false,
        reorder_level: '4',
        on_hand: '12',
        reserved: '0',
        available_to_sell: '12',
      },
      {
        variant_id: 'v-active-low',
        product_id: 'p-1',
        product_name: 'Runner',
        title: 'Low',
        label: '41 / Black',
        sku: 'RUN-41-BLK',
        barcode: '',
        status: 'active',
        options: { size: '41', color: 'Black', other: '' },
        unit_cost: null,
        unit_price: null,
        min_price: null,
        effective_unit_price: null,
        effective_min_price: null,
        is_price_inherited: false,
        is_min_price_inherited: false,
        reorder_level: '5',
        on_hand: '2',
        reserved: '0',
        available_to_sell: '2',
      },
      {
        variant_id: 'v-active-high',
        product_id: 'p-1',
        product_name: 'Runner',
        title: 'High',
        label: '42 / Black',
        sku: 'RUN-42-BLK',
        barcode: '',
        status: 'active',
        options: { size: '42', color: 'Black', other: '' },
        unit_cost: null,
        unit_price: null,
        min_price: null,
        effective_unit_price: null,
        effective_min_price: null,
        is_price_inherited: false,
        is_min_price_inherited: false,
        reorder_level: '5',
        on_hand: '15',
        reserved: '0',
        available_to_sell: '15',
      },
    ]);

    expect(rows.map((row) => row.variant_id)).toEqual(['v-active-low', 'v-active-high', 'v-archived']);
  });

  test('limits scan output to the requested number of rows', () => {
    const rows = deriveCatalogVariantOperationalScan(
      [
        {
          variant_id: 'v-1',
          product_id: 'p-1',
          product_name: 'Runner',
          title: 'One',
          label: '41 / Black',
          sku: 'RUN-41-BLK',
          barcode: '',
          status: 'active',
          options: { size: '41', color: 'Black', other: '' },
          unit_cost: null,
          unit_price: null,
          min_price: null,
          effective_unit_price: null,
          effective_min_price: null,
          is_price_inherited: false,
          is_min_price_inherited: false,
          reorder_level: '5',
          on_hand: '2',
          reserved: '0',
          available_to_sell: '2',
        },
        {
          variant_id: 'v-2',
          product_id: 'p-1',
          product_name: 'Runner',
          title: 'Two',
          label: '42 / Black',
          sku: 'RUN-42-BLK',
          barcode: '',
          status: 'active',
          options: { size: '42', color: 'Black', other: '' },
          unit_cost: null,
          unit_price: null,
          min_price: null,
          effective_unit_price: null,
          effective_min_price: null,
          is_price_inherited: false,
          is_min_price_inherited: false,
          reorder_level: '5',
          on_hand: '5',
          reserved: '0',
          available_to_sell: '5',
        },
      ],
      1
    );

    expect(rows).toHaveLength(1);
    expect(rows[0].variant_id).toBe('v-1');
  });
});

describe('normalizeFirstVariantForCreateFlow', () => {
  test('promotes the first active detailed variant to index 0 for create-flow validation', () => {
    const payload = normalizeFirstVariantForCreateFlow({
      identity: {
        product_name: 'Runner',
        supplier: 'Supplier A',
        category: 'Shoes',
        brand: '',
        description: '',
        image_url: '',
        pending_primary_media_upload_id: '',
        remove_primary_image: false,
        sku_root: 'RUN',
        default_selling_price: '',
        min_selling_price: '',
        max_discount_percent: '',
        status: 'active',
      },
      variants: [
        { sku: '', barcode: '', size: '', color: '', other: '', default_purchase_price: '', default_selling_price: '', min_selling_price: '', reorder_level: '', status: 'active' },
        { sku: '', barcode: '', size: '42', color: '', other: '', default_purchase_price: '', default_selling_price: '', min_selling_price: '', reorder_level: '', status: 'active' },
      ],
    });

    expect(payload.variants[0].size).toBe('42');
    expect(payload.variants).toHaveLength(2);
  });
});

describe('deriveCatalogInlineErrors', () => {
  test('maps product-name validation failures to a safe inline message', () => {
    const errors = deriveCatalogInlineErrors(
      new ApiError(
        422,
        '{"detail":[{"loc":["body","identity","product_name"],"msg":"String should have at least 2 characters","type":"string_too_short"}]} (https://example.com/catalog/products)'
      )
    );

    expect(errors.product_name).toBe('Product name must be at least 2 characters.');
  });

  test('maps legacy product-name required errors to the same safe inline message', () => {
    const errors = deriveCatalogInlineErrors(
      new ApiError(
        400,
        'Product name is required (https://example.com/catalog/products/validate-step)'
      )
    );

    expect(errors.product_name).toBe('Product name must be at least 2 characters.');
  });

  test('maps first-variant validation failures to inline variant guidance', () => {
    const errors = deriveCatalogInlineErrors(
      new ApiError(
        400,
        'First variant details are required (add at least one option or barcode) (https://example.com/catalog/products/validate-step)'
      )
    );

    expect(errors.first_variant).toBe('First variant details are required (add at least one option or barcode)');
  });

  test('maps generic first-variant required errors to inline variant guidance', () => {
    const errors = deriveCatalogInlineErrors(
      new ApiError(
        400,
        'At least one variant is required (https://example.com/catalog/products/validate-step)'
      )
    );

    expect(errors.first_variant).toBe('At least one variant is required');
  });
});

describe('deriveCatalogStepSafeError', () => {
  test('returns a user-safe backend upgrade hint when step validation route is missing', () => {
    const message = deriveCatalogStepSafeError(
      new ApiError(404, 'Not Found (https://example.com/catalog/products/validate-step)')
    );

    expect(message).toContain('Deploy the latest backend');
    expect(message).not.toContain('https://');
  });

  test('returns a generic network-safe message for transport failures', () => {
    const message = deriveCatalogStepSafeError(new ApiNetworkError('failed (https://example.com/catalog/products/validate-step)'));

    expect(message).toBe('Network connection failed while validating this step. Please retry.');
  });
});

describe('deriveCatalogStepBlockedSummary', () => {
  test('returns product-step summary for blocked required product fields', () => {
    const summary = deriveCatalogStepBlockedSummary('product', {
      product_name: 'Product name must be at least 2 characters.',
    });

    expect(summary).toBe('Cannot continue: Product name needs attention. Product name must be at least 2 characters.');
  });

  test('returns first-variant summary for blocked required first variant fields', () => {
    const summary = deriveCatalogStepBlockedSummary('first_variant', {
      first_variant: 'First variant details are required (add at least one option or barcode)',
    });

    expect(summary).toBe('Cannot continue: complete the required First Variant fields.');
  });
});
