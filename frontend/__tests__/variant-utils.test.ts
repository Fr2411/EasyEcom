import { describe, expect, test } from 'vitest';

import { generateVariantsFromInputs } from '@/lib/products-stock/variant-utils';

describe('generateVariantsFromInputs', () => {
  test('generates distinct size-only variants', () => {
    const rows = generateVariantsFromInputs({
      productName: 'Classic Tee',
      size: 'S,M',
      color: '',
      other: ''
    });

    expect(rows).toHaveLength(2);
    expect(rows.map((row) => row.size)).toEqual(['S', 'M']);
    expect(rows.map((row) => row.color)).toEqual([undefined, undefined]);
    expect(rows.map((row) => row.other)).toEqual([undefined, undefined]);
  });

  test('generates distinct color-only variants', () => {
    const rows = generateVariantsFromInputs({
      productName: 'Classic Tee',
      size: '',
      color: 'Black,White',
      other: ''
    });

    expect(rows).toHaveLength(2);
    expect(rows.map((row) => row.color)).toEqual(['Black', 'White']);
    expect(rows.map((row) => row.size)).toEqual([undefined, undefined]);
    expect(rows.map((row) => row.other)).toEqual([undefined, undefined]);
  });

  test('generates full cross-product when both size and color are provided', () => {
    const rows = generateVariantsFromInputs({
      productName: 'Classic Tee',
      size: 'S,M',
      color: 'Black,White',
      other: ''
    });

    expect(rows).toHaveLength(4);
    expect(rows.map((row) => [row.size, row.color])).toEqual([
      ['S', 'Black'],
      ['S', 'White'],
      ['M', 'Black'],
      ['M', 'White']
    ]);
  });
});
