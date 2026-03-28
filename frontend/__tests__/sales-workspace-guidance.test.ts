import { describe, expect, test } from 'vitest';
import { deriveSalesIntentSuggestion } from '@/components/commerce/sales-workspace';
import type { LookupOutcome } from '@/types/guided-workflow';
import type { EmbeddedCustomer, SaleLookupVariant } from '@/types/sales';

function buildVariant(overrides: Partial<SaleLookupVariant> = {}): SaleLookupVariant {
  return {
    variant_id: 'variant-1',
    product_id: 'product-1',
    product_name: 'Runner',
    label: 'Runner / Black / 42',
    sku: 'RUN-BLK-42',
    barcode: '12345',
    available_to_sell: '5',
    unit_price: '120',
    min_price: '95',
    ...overrides,
  };
}

function buildCustomer(overrides: Partial<EmbeddedCustomer> = {}): EmbeddedCustomer {
  return {
    customer_id: 'customer-1',
    name: 'Rabby',
    phone: '+971500000000',
    email: 'rabby@example.com',
    ...overrides,
  };
}

describe('deriveSalesIntentSuggestion', () => {
  test('returns an idle prompt before any lookup runs', () => {
    const result = deriveSalesIntentSuggestion(null);

    expect(result.kind).toBe('manual');
    expect(result.actionLabel).toBe('Stage manual customer');
  });

  test('prefers exact variants when one is found', () => {
    const result = deriveSalesIntentSuggestion({
      state: 'exact',
      query: 'RUN-BLK-42',
      exact: [buildVariant()],
      likely: [],
      suggestedNew: null,
    });

    expect(result.kind).toBe('variant');
    expect(result.title).toContain('Exact variant found');
    expect(result.actionLabel).toBe('Add one more');
  });

  test('returns a likely-match prompt when exact results are absent', () => {
    const result = deriveSalesIntentSuggestion({
      state: 'likely',
      query: 'rab',
      exact: [],
      likely: [buildCustomer(), buildVariant()],
      suggestedNew: null,
    } as LookupOutcome<SaleLookupVariant, SaleLookupVariant | EmbeddedCustomer, { name: string; phone: string; email: string }>);

    expect(result.kind).toBe('customer');
    expect(result.title).toContain('2 likely matches');
    expect(result.actionLabel).toBe('Stage manual customer');
  });

  test('falls back to manual staging when no matches exist', () => {
    const result = deriveSalesIntentSuggestion({
      state: 'new',
      query: 'unknown',
      exact: [],
      likely: [],
      suggestedNew: { name: '', phone: 'unknown', email: '' },
    });

    expect(result.kind).toBe('manual');
    expect(result.title).toContain('No direct match found');
  });
});
