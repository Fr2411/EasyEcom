import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, describe, expect, test, vi } from 'vitest';

const getInventoryItemsMock = vi.fn();
const getInventoryMovementsMock = vi.fn();
const getInventoryDetailMock = vi.fn();
const createInventoryAdjustmentMock = vi.fn();
const createOpeningStockMock = vi.fn();
const getCatalogProductsMock = vi.fn();

vi.mock('@/lib/api/inventory', () => ({
  getInventoryItems: (...args: unknown[]) => getInventoryItemsMock(...args),
  getInventoryMovements: (...args: unknown[]) => getInventoryMovementsMock(...args),
  getInventoryDetail: (...args: unknown[]) => getInventoryDetailMock(...args),
  createInventoryAdjustment: (...args: unknown[]) => createInventoryAdjustmentMock(...args),
  createOpeningStock: (...args: unknown[]) => createOpeningStockMock(...args),
}));

vi.mock('@/lib/api/catalog', () => ({
  getCatalogProducts: (...args: unknown[]) => getCatalogProductsMock(...args),
}));

import InventoryPage from '@/app/(app)/inventory/page';

const EMPTY_INVENTORY = { items: [] };
const EMPTY_CATALOG = { products: [], suppliers: [], categories: [] };

const VARIANT_ITEM = {
  item_id: 'v1',
  item_name: 'Red Tee / Size:M',
  parent_product_id: 'p1',
  parent_product_name: 'Red Tee',
  item_type: 'variant' as const,
  availability_status: 'in_stock' as const,
  on_hand_qty: 8,
  incoming_qty: 0,
  reserved_qty: 0,
  sellable_qty: 8,
  avg_unit_cost: 2,
  stock_value: 16,
  lot_count: 1,
  low_stock: false,
  actionable: true,
};

afterEach(() => {
  cleanup();
  getInventoryItemsMock.mockReset();
  getInventoryMovementsMock.mockReset();
  getInventoryDetailMock.mockReset();
  createInventoryAdjustmentMock.mockReset();
  createOpeningStockMock.mockReset();
  getCatalogProductsMock.mockReset();
});

describe('InventoryPage', () => {
  test('renders inventory empty state', async () => {
    getInventoryItemsMock.mockResolvedValue({ items: [] });
    getInventoryMovementsMock.mockResolvedValue({ items: [] });
    getCatalogProductsMock.mockResolvedValue(EMPTY_CATALOG);

    render(<InventoryPage />);

    expect(screen.getByRole('heading', { name: 'Inventory' })).toBeTruthy();
    await waitFor(() => expect(screen.getByText('No variants found')).toBeTruthy());
  });

  test('renders stock and submits adjustment', async () => {
    getInventoryItemsMock.mockResolvedValue({ items: [VARIANT_ITEM] });
    getInventoryMovementsMock.mockResolvedValue({ items: [] });
    getInventoryDetailMock.mockResolvedValue({ item: VARIANT_ITEM, recent_movements: [] });
    getCatalogProductsMock.mockResolvedValue(EMPTY_CATALOG);
    createInventoryAdjustmentMock.mockResolvedValue({ success: true });

    render(<InventoryPage />);

    await waitFor(() => expect(screen.getByText('Inventory by Variant')).toBeTruthy());
    fireEvent.change(screen.getByLabelText('Reason'), { target: { value: 'Cycle count' } });
    fireEvent.click(screen.getByRole('button', { name: 'Apply Adjustment' }));

    await waitFor(() => expect(createInventoryAdjustmentMock).toHaveBeenCalled());
  });

  test('hides legacy product rows from adjustment selector', async () => {
    getInventoryItemsMock.mockResolvedValue({
      items: [
        {
          item_id: 'legacy-p1',
          item_name: 'Legacy Parent',
          parent_product_id: 'legacy-p1',
          parent_product_name: 'Legacy Parent',
          item_type: 'product',
          availability_status: 'in_stock',
          on_hand_qty: 3,
          incoming_qty: 0,
          reserved_qty: 0,
          sellable_qty: 3,
          avg_unit_cost: 2,
          stock_value: 6,
          lot_count: 1,
          low_stock: false,
          actionable: false,
        },
        {
          ...VARIANT_ITEM,
          item_id: 'v3',
          item_name: 'Green Tee / Size:S',
          parent_product_id: 'p3',
          parent_product_name: 'Green Tee',
        },
      ],
    });
    getInventoryMovementsMock.mockResolvedValue({ items: [] });
    getCatalogProductsMock.mockResolvedValue(EMPTY_CATALOG);

    render(<InventoryPage />);

    await waitFor(() => expect(screen.getByRole('heading', { name: 'Adjust Stock' })).toBeTruthy());
    expect(screen.queryByRole('option', { name: 'Legacy Parent' })).toBeNull();
    expect(screen.getByRole('option', { name: 'Green Tee / Green Tee / Size:S' })).toBeTruthy();
  });

  test('renders safely when stock numbers are nullish', async () => {
    const nullishItem = {
      ...VARIANT_ITEM,
      item_id: 'v2',
      item_name: 'Blue Tee / Size:L',
      parent_product_id: 'p2',
      parent_product_name: 'Blue Tee',
      on_hand_qty: null,
      incoming_qty: undefined,
      sellable_qty: '1',
      avg_unit_cost: null,
      stock_value: undefined,
      lot_count: 0,
    };
    getInventoryItemsMock.mockResolvedValue({ items: [nullishItem] });
    getInventoryMovementsMock.mockResolvedValue({
      items: [
        {
          txn_id: 't1',
          timestamp: '2025-01-01',
          item_id: 'v2',
          item_name: 'Blue Tee / Size:L',
          parent_product_id: 'p2',
          parent_product_name: 'Blue Tee',
          movement_type: 'ADJUST',
          qty_delta: null,
          source_type: 'manual',
          source_id: '',
          note: '',
          lot_id: '',
          resulting_balance: null,
        },
      ],
    });
    getInventoryDetailMock.mockResolvedValue({
      item: nullishItem,
      recent_movements: [
        {
          txn_id: 't2',
          timestamp: '2025-01-02',
          item_id: 'v2',
          item_name: 'Blue Tee / Size:L',
          parent_product_id: 'p2',
          parent_product_name: 'Blue Tee',
          movement_type: 'ADJUST',
          qty_delta: undefined,
          source_type: 'manual',
          source_id: '',
          note: '',
          lot_id: '',
          resulting_balance: undefined,
        },
      ],
    });
    getCatalogProductsMock.mockResolvedValue(EMPTY_CATALOG);

    render(<InventoryPage />);

    await waitFor(() => expect(screen.getByText('Inventory by Variant')).toBeTruthy());
    fireEvent.click(screen.getByText('v2'));
    await waitFor(() => expect(screen.getByText(/Inventory Detail/)).toBeTruthy());

    expect(screen.getAllByText('0.00').length).toBeGreaterThan(0);
  });

  test('posts opening stock for a catalog product', async () => {
    getInventoryItemsMock.mockResolvedValue({ items: [VARIANT_ITEM] });
    getInventoryMovementsMock.mockResolvedValue({ items: [] });
    getCatalogProductsMock.mockResolvedValue({
      products: [
        {
          product_id: 'p1',
          identity: {
            productName: 'Red Tee',
            supplier: 'Nova',
            category: 'Apparel',
            description: '',
            features: [],
          },
          variants: [
            {
              tempId: 'temp-v1',
              variant_id: 'v1',
              size: 'M',
              color: 'Red',
              other: '',
              defaultPurchasePrice: 11,
              defaultSellingPrice: 20,
              maxDiscountPct: 10,
            },
          ],
        },
      ],
      suppliers: ['Nova'],
      categories: ['Apparel'],
    });
    createOpeningStockMock.mockResolvedValue({ success: true, product_id: 'p1', lot_ids: ['lot-1'] });

    render(<InventoryPage />);

    await waitFor(() => expect(screen.getByRole('heading', { name: 'Opening Stock' })).toBeTruthy());
    const unitCostInputs = screen.getAllByLabelText('Unit Cost');
    const openingUnitCost = unitCostInputs[0] as HTMLInputElement;
    expect(openingUnitCost.value).toBe('11');
    fireEvent.change(openingUnitCost, { target: { value: '12' } });
    fireEvent.click(screen.getByRole('button', { name: 'Post Opening Stock' }));

    await waitFor(() => expect(createOpeningStockMock).toHaveBeenCalledWith({
      product_id: 'p1',
      lines: [
        {
          variant_id: 'v1',
          qty: 1,
          unit_cost: 12,
          reference: '',
          note: '',
        },
      ],
    }));
  });
});
