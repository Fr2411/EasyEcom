import { describe, expect, test } from 'vitest';
import { deriveReturnSuggestion } from '@/components/commerce/returns-workspace';
import type { ReturnLookupOrder } from '@/types/returns';

function buildOrder(overrides: Partial<ReturnLookupOrder> = {}): ReturnLookupOrder {
  return {
    sales_order_id: 'order-1',
    order_number: 'SO-1001',
    customer_name: 'Rabby',
    customer_phone: '+971500000000',
    customer_email: 'rabby@example.com',
    ordered_at: '2026-03-15T10:00:00+00:00',
    status: 'completed',
    total_amount: '150',
    shipment_status: 'completed',
    ...overrides,
  } as ReturnLookupOrder;
}

describe('deriveReturnSuggestion', () => {
  test('prompts for a completed order clue when nothing has been entered', () => {
    const result = deriveReturnSuggestion('', [], null);

    expect(result.kind).toBe('idle');
    expect(result.actionLabel).toBe('Interpret order clue');
  });

  test('returns exact when the order number matches directly', () => {
    const result = deriveReturnSuggestion('SO-1001', [buildOrder()], null);

    expect(result.kind).toBe('exact');
    expect(result.title).toContain('Exact order found');
    expect(result.actionLabel).toBe('Open eligible lines');
  });

  test('returns likely when a single order is found', () => {
    const result = deriveReturnSuggestion('Rabby', [buildOrder()], null);

    expect(result.kind).toBe('likely');
    expect(result.title).toContain('One likely completed order found');
  });

  test('returns a staged draft recommendation once eligible lines are loaded', () => {
    const result = deriveReturnSuggestion('SO-1001', [], {
      order_number: 'SO-1001',
      customer_name: 'Rabby',
      customer_phone: '+971500000000',
      customer_email: 'rabby@example.com',
      ordered_at: null,
      total_amount: '150',
      status: 'completed',
      shipment_status: 'completed',
      lines: [],
    } as ReturnLookupOrder & { lines: [] });

    expect(result.kind).toBe('draft');
    expect(result.actionLabel).toBe('Review before creating return');
  });
});
