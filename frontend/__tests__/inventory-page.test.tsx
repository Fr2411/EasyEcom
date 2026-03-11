import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, describe, expect, test, vi } from 'vitest';

const getInventoryItemsMock = vi.fn();
const getInventoryMovementsMock = vi.fn();
const getInventoryDetailMock = vi.fn();
const createInventoryAdjustmentMock = vi.fn();
const createInboundStockMock = vi.fn();
const receiveInboundStockMock = vi.fn();

vi.mock('@/lib/api/inventory', () => ({
  getInventoryItems: (...args: unknown[]) => getInventoryItemsMock(...args),
  getInventoryMovements: (...args: unknown[]) => getInventoryMovementsMock(...args),
  getInventoryDetail: (...args: unknown[]) => getInventoryDetailMock(...args),
  createInventoryAdjustment: (...args: unknown[]) => createInventoryAdjustmentMock(...args),
  createInboundStock: (...args: unknown[]) => createInboundStockMock(...args),
  receiveInboundStock: (...args: unknown[]) => receiveInboundStockMock(...args),
}));

import InventoryPage from '@/app/(app)/inventory/page';

afterEach(() => {
  cleanup();
  getInventoryItemsMock.mockReset();
  getInventoryMovementsMock.mockReset();
  getInventoryDetailMock.mockReset();
  createInventoryAdjustmentMock.mockReset();
  createInboundStockMock.mockReset();
  receiveInboundStockMock.mockReset();
});

describe('InventoryPage', () => {
  test('renders inventory empty state', async () => {
    getInventoryItemsMock.mockResolvedValue({ items: [] });
    getInventoryMovementsMock.mockResolvedValue({ items: [] });

    render(<InventoryPage />);

    expect(screen.getByRole('heading', { name: 'Inventory' })).toBeTruthy();
    await waitFor(() => expect(screen.getByText('No inventory yet')).toBeTruthy());
  });

  test('renders stock and submits adjustment', async () => {
    getInventoryItemsMock.mockResolvedValue({
      items: [{ item_id: 'v1', item_name: 'Red Tee / Size:M', parent_product_id: 'p1', parent_product_name: 'Red Tee', item_type: 'variant', on_hand_qty: 8, incoming_qty: 0, reserved_qty: 0, sellable_qty: 8, avg_unit_cost: 2, stock_value: 16, lot_count: 1, low_stock: false }],
    });
    getInventoryMovementsMock.mockResolvedValue({ items: [] });
    getInventoryDetailMock.mockResolvedValue({ item: { item_id: 'v1', item_name: 'Red Tee / Size:M', parent_product_id: 'p1', parent_product_name: 'Red Tee', item_type: 'variant', on_hand_qty: 8, incoming_qty: 0, reserved_qty: 0, sellable_qty: 8, avg_unit_cost: 2, stock_value: 16, lot_count: 1, low_stock: false }, recent_movements: [] });
    createInventoryAdjustmentMock.mockResolvedValue({ success: true });

    render(<InventoryPage />);

    await waitFor(() => expect(screen.getByText('Current Stock')).toBeTruthy());
    fireEvent.change(screen.getByLabelText('Reason'), { target: { value: 'Cycle count' } });
    fireEvent.click(screen.getByRole('button', { name: 'Apply Adjustment' }));

    await waitFor(() => expect(createInventoryAdjustmentMock).toHaveBeenCalled());
  });
});
