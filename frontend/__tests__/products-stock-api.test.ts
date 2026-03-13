import { beforeEach, describe, expect, test, vi } from 'vitest';

const apiClientMock = vi.fn();

vi.mock('@/lib/api', () => ({
  apiClient: (...args: unknown[]) => apiClientMock(...args),
}));

import { getCatalogProducts, saveCatalogProduct } from '@/lib/api/catalog';

describe('catalog api mapping', () => {
  beforeEach(() => {
    apiClientMock.mockReset();
  });

  test('maps snapshot variants to frontend tempId + variant_id shape', async () => {
    apiClientMock.mockResolvedValue({
      products: [
        {
          product_id: 'p-1',
          identity: { productName: 'Tee', supplier: 'S', category: 'C', description: '', features: [] },
          variants: [
            {
              variant_id: 'v-1',
              size: 'M',
              color: 'Black',
              other: '',
              defaultPurchasePrice: 11,
              defaultSellingPrice: 20,
              maxDiscountPct: 10,
            },
          ],
        },
      ],
      suppliers: ['S'],
      categories: ['C'],
    });

    const snapshot = await getCatalogProducts();

    expect(snapshot.products[0].variants[0]).toEqual(
      expect.objectContaining({
        variant_id: 'v-1',
        size: 'M',
        color: 'Black',
        defaultPurchasePrice: 11,
      }),
    );
    expect(snapshot.products[0].variants[0].tempId).toBeTruthy();
  });

  test('posts create payload without frontend temp ids or stock fields', async () => {
    apiClientMock.mockResolvedValue({ product_id: 'p-1', variant_count: 2 });

    await saveCatalogProduct({
      mode: 'new',
      identity: {
        productName: 'Tee',
        supplier: 'S',
        category: 'C',
        description: '',
        features: [],
      },
      variants: [
        {
          tempId: 'temp-existing',
          variant_id: 'v-existing',
          size: 'M',
          color: 'Black',
          other: 'Cotton',
          defaultPurchasePrice: 14,
          defaultSellingPrice: 24,
          maxDiscountPct: 10,
        },
        {
          tempId: 'temp-manual',
          size: '',
          color: 'Blue',
          other: '',
          defaultPurchasePrice: 9,
          defaultSellingPrice: 16,
          maxDiscountPct: 10,
        },
      ],
      archiveVariantIds: ['v-archive'],
    });

    expect(apiClientMock).toHaveBeenCalledTimes(1);
    const [path, requestOptions] = apiClientMock.mock.calls[0] as [string, { body: string; method: string }];
    const body = JSON.parse(requestOptions.body);

    expect(path).toBe('/catalog/products');
    expect(requestOptions.method).toBe('POST');
    expect(body.variants).toEqual([
      expect.objectContaining({
        variant_id: 'v-existing',
        size: 'M',
        color: 'Black',
        other: 'Cotton',
        defaultPurchasePrice: 14,
      }),
      expect.objectContaining({
        color: 'Blue',
        defaultPurchasePrice: 9,
        defaultSellingPrice: 16,
      }),
    ]);
    expect(body.archiveVariantIds).toEqual(['v-archive']);
  });
});
