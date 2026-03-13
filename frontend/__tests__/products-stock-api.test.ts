import { beforeEach, describe, expect, test, vi } from 'vitest';

const apiClientMock = vi.fn();

vi.mock('@/lib/api', () => ({
  apiClient: (...args: unknown[]) => apiClientMock(...args),
}));

import { getProductsStockSnapshot, saveProductStock } from '@/lib/api/products-stock';

describe('products-stock api mapping', () => {
  beforeEach(() => {
    apiClientMock.mockReset();
  });

  test('maps snapshot variants from id to variant_id and generates stable rowId', async () => {
    apiClientMock.mockResolvedValue({
      products: [
        {
          id: 'p-1',
          identity: { productName: 'Tee', supplier: 'S', category: 'C', description: '', features: [] },
          variants: [
            {
              id: 'v-1',
              size: 'M',
              color: 'Black',
              other: '',
              qty: 2,
              cost: 10,
              defaultSellingPrice: 20,
              maxDiscountPct: 10,
            },
          ],
        },
      ],
      suppliers: ['S'],
      categories: ['C'],
    });

    const snapshot = await getProductsStockSnapshot();

    expect(snapshot.products[0].variants[0]).toEqual(
      expect.objectContaining({
        variant_id: 'v-1',
        size: 'M',
        color: 'Black',
      }),
    );
    expect(snapshot.products[0].variants[0].rowId).toBeTruthy();
  });

  test('maps save payload variants to variant_id and deterministic variant_name', async () => {
    apiClientMock.mockResolvedValue({ success: true });

    await saveProductStock({
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
          rowId: 'row-existing',
          variant_id: 'v-existing',
          size: 'M',
          color: 'Black',
          other: 'Cotton',
          qty: 4,
          cost: 12,
          defaultSellingPrice: 24,
          maxDiscountPct: 10,
        },
        {
          rowId: 'row-manual',
          variant_id: 'v-manual',
          size: '',
          color: 'Blue',
          other: '',
          qty: 1,
          cost: 8,
          defaultSellingPrice: 16,
          maxDiscountPct: 10,
        },
      ],
    });

    expect(apiClientMock).toHaveBeenCalledTimes(1);
    const [, requestOptions] = apiClientMock.mock.calls[0] as [string, { body: string }];
    const body = JSON.parse(requestOptions.body);

    expect(body.mode).toBe('new');
    expect(body.variants).toEqual([
      expect.objectContaining({ variant_id: 'v-existing', variant_name: 'M / Black / Cotton' }),
      expect.objectContaining({ variant_id: 'v-manual', variant_name: 'Blue' }),
    ]);
  });
});
