import { describe, expect, test } from 'vitest';

import { generateVariantsFromInputs, mergeCatalogVariants } from '@/lib/products-stock/variant-utils';

describe('generateVariantsFromInputs', () => {
  test('generates distinct size-only variants', () => {
    const rows = generateVariantsFromInputs({
      size: 'S,M',
      color: '',
      other: ''
    });

    expect(rows).toHaveLength(2);
    expect(rows.map((row) => row.size)).toEqual(['S', 'M']);
    expect(rows.map((row) => row.color)).toEqual(['', '']);
    expect(rows.map((row) => row.other)).toEqual(['', '']);
  });

  test('generates distinct color-only variants', () => {
    const rows = generateVariantsFromInputs({
      size: '',
      color: 'Black,White',
      other: ''
    });

    expect(rows).toHaveLength(2);
    expect(rows.map((row) => row.color)).toEqual(['Black', 'White']);
    expect(rows.map((row) => row.size)).toEqual(['', '']);
    expect(rows.map((row) => row.other)).toEqual(['', '']);
  });



  test('deduplicates repeated size values ignoring spacing and casing while preserving first display casing', () => {
    const rows = generateVariantsFromInputs({
      size: 'S, s , S',
      color: '',
      other: ''
    });

    expect(rows).toHaveLength(1);
    expect(rows[0]?.size).toBe('S');
  });

  test('deduplicates each input dimension before building cross-product combinations', () => {
    const rows = generateVariantsFromInputs({
      size: 'S, s',
      color: 'Black, black ,BLACK',
      other: 'Cotton, cotton'
    });

    expect(rows).toHaveLength(1);
    expect(rows.map((row) => [row.size, row.color, row.other])).toEqual([['S', 'Black', 'Cotton']]);
  });
  test('generates full cross-product when both size and color are provided', () => {
    const rows = generateVariantsFromInputs({
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

  test('merges generated variants into existing rows instead of replacing them', () => {
    const current = [
      {
        tempId: 'existing',
        variant_id: 'v-1',
        size: 'M',
        color: 'Black',
        other: '',
        defaultPurchasePrice: 10,
        defaultSellingPrice: 20,
        maxDiscountPct: 10,
        isArchived: false,
      },
    ];

    const incoming = generateVariantsFromInputs({
      size: 'L',
      color: 'Black',
      other: '',
    });

    const merged = mergeCatalogVariants(current, incoming);

    expect(merged).toHaveLength(2);
    expect(merged.map((row) => row.size)).toEqual(['M', 'L']);
  });
});
