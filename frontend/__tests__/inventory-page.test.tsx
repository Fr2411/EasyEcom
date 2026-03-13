import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, describe, expect, test, vi } from 'vitest';

const getInventoryItemsMock = vi.fn();
const getInventoryMovementsMock = vi.fn();
const getInventoryDetailMock = vi.fn();
const createInventoryAdjustmentMock = vi.fn();
const getProductsStockSnapshotMock = vi.fn();
const saveProductStockMock = vi.fn();

vi.mock('@/lib/api/inventory', () => ({
  getInventoryItems: (...args: unknown[]) => getInventoryItemsMock(...args),
  getInventoryMovements: (...args: unknown[]) => getInventoryMovementsMock(...args),
  getInventoryDetail: (...args: unknown[]) => getInventoryDetailMock(...args),
  createInventoryAdjustment: (...args: unknown[]) => createInventoryAdjustmentMock(...args),
}));

vi.mock('@/lib/api/products-stock', () => ({
  getProductsStockSnapshot: (...args: unknown[]) => getProductsStockSnapshotMock(...args),
  saveProductStock: (...args: unknown[]) => saveProductStockMock(...args),
}));

import InventoryPage from '@/app/(app)/inventory/page';

const EMPTY_INVENTORY = { items: [] };
const EMPTY_CATALOG = { products: [], suppliers: [], categories: [] };

afterEach(() => {
  cleanup();
  getInventoryItemsMock.mockReset();
  getInventoryMovementsMock.mockReset();
  getInventoryDetailMock.mockReset();
  createInventoryAdjustmentMock.mockReset();
  getProductsStockSnapshotMock.mockReset();
  saveProductStockMock.mockReset();
});

describe('InventoryPage', () => {
  test('renders inventory empty state', async () => {
    getInventoryItemsMock.mockResolvedValue({ items: [] });
    getInventoryMovementsMock.mockResolvedValue({ items: [] });
    getProductsStockSnapshotMock.mockResolvedValue({ products: [], suppliers: [], categories: [] });

    render(<InventoryPage />);

    expect(screen.getByRole('heading', { name: 'Inventory' })).toBeTruthy();
    await waitFor(() => expect(screen.getByText('No inventory yet')).toBeTruthy());
  });

  test('renders stock and submits adjustment', async () => {
    getInventoryItemsMock.mockResolvedValue({
      items: [{ item_id: 'v1', item_name: 'Red Tee / Size:M', parent_product_id: 'p1', parent_product_name: 'Red Tee', item_type: 'variant', on_hand_qty: 8, incoming_qty: 0, reserved_qty: 0, sellable_qty: 8, avg_unit_cost: 2, stock_value: 16, lot_count: 1, low_stock: false, actionable: true }],
    });
    getInventoryMovementsMock.mockResolvedValue({ items: [] });
    getInventoryDetailMock.mockResolvedValue({ item: { item_id: 'v1', item_name: 'Red Tee / Size:M', parent_product_id: 'p1', parent_product_name: 'Red Tee', item_type: 'variant', on_hand_qty: 8, incoming_qty: 0, reserved_qty: 0, sellable_qty: 8, avg_unit_cost: 2, stock_value: 16, lot_count: 1, low_stock: false, actionable: true }, recent_movements: [] });
    getProductsStockSnapshotMock.mockResolvedValue({ products: [], suppliers: [], categories: [] });
    createInventoryAdjustmentMock.mockResolvedValue({ success: true });

    render(<InventoryPage />);

    await waitFor(() => expect(screen.getByText('Current Stock (Available Items)')).toBeTruthy());
    fireEvent.change(screen.getByLabelText('Reason'), { target: { value: 'Cycle count' } });
    fireEvent.click(screen.getByRole('button', { name: 'Apply Adjustment' }));

    await waitFor(() => expect(createInventoryAdjustmentMock).toHaveBeenCalled());
  });

  test('hides legacy product rows from adjustment selector', async () => {
    getInventoryItemsMock.mockResolvedValue({
      items: [
        { item_id: 'legacy-p1', item_name: 'Legacy Parent', parent_product_id: 'legacy-p1', parent_product_name: 'Legacy Parent', item_type: 'product', on_hand_qty: 3, incoming_qty: 0, reserved_qty: 0, sellable_qty: 3, avg_unit_cost: 2, stock_value: 6, lot_count: 1, low_stock: false, actionable: false },
        { item_id: 'v3', item_name: 'Green Tee / Size:S', parent_product_id: 'p3', parent_product_name: 'Green Tee', item_type: 'variant', on_hand_qty: 3, incoming_qty: 0, reserved_qty: 0, sellable_qty: 3, avg_unit_cost: 2, stock_value: 6, lot_count: 1, low_stock: false, actionable: true },
      ],
    });
    getInventoryMovementsMock.mockResolvedValue({ items: [] });
    getProductsStockSnapshotMock.mockResolvedValue({ products: [], suppliers: [], categories: [] });

    render(<InventoryPage />);

    await waitFor(() => expect(screen.getByRole('heading', { name: 'Adjust Stock (Variant Only)' })).toBeTruthy());
    expect(screen.queryByRole('option', { name: 'Legacy Parent' })).toBeNull();
    expect(screen.getByRole('option', { name: 'Green Tee / Size:S' })).toBeTruthy();
  });

  test('renders safely when stock numbers are nullish', async () => {
    getInventoryItemsMock.mockResolvedValue({
      items: [{ item_id: 'v2', item_name: 'Blue Tee / Size:L', parent_product_id: 'p2', parent_product_name: 'Blue Tee', item_type: 'variant', on_hand_qty: null, incoming_qty: undefined, reserved_qty: 0, sellable_qty: '1', avg_unit_cost: null, stock_value: undefined, lot_count: 0, low_stock: false, actionable: true }],
    });
    getInventoryMovementsMock.mockResolvedValue({ items: [{ txn_id: 't1', timestamp: '2025-01-01', item_id: 'v2', item_name: 'Blue Tee / Size:L', parent_product_id: 'p2', parent_product_name: 'Blue Tee', movement_type: 'ADJUST', qty_delta: null, source_type: 'manual', source_id: '', note: '', lot_id: '', resulting_balance: null }] });
    getInventoryDetailMock.mockResolvedValue({ item: { item_id: 'v2', item_name: 'Blue Tee / Size:L', parent_product_id: 'p2', parent_product_name: 'Blue Tee', item_type: 'variant', on_hand_qty: null, incoming_qty: undefined, reserved_qty: 0, sellable_qty: '1', avg_unit_cost: null, stock_value: undefined, lot_count: 0, low_stock: false, actionable: true }, recent_movements: [{ txn_id: 't2', timestamp: '2025-01-02', item_id: 'v2', item_name: 'Blue Tee / Size:L', parent_product_id: 'p2', parent_product_name: 'Blue Tee', movement_type: 'ADJUST', qty_delta: undefined, source_type: 'manual', source_id: '', note: '', lot_id: '', resulting_balance: undefined }] });
    getProductsStockSnapshotMock.mockResolvedValue({ products: [], suppliers: [], categories: [] });

    render(<InventoryPage />);

    await waitFor(() => expect(screen.getByText('Current Stock (Available Items)')).toBeTruthy());
    fireEvent.click(screen.getByText('v2'));
    await waitFor(() => expect(screen.getByText(/Inventory Detail/)).toBeTruthy());

    expect(screen.getAllByText('0.00').length).toBeGreaterThan(0);
  });

  test('new product with generated variants persists all generated variants', async () => {
    getInventoryItemsMock.mockResolvedValue(EMPTY_INVENTORY);
    getInventoryMovementsMock.mockResolvedValue(EMPTY_INVENTORY);
    getProductsStockSnapshotMock.mockResolvedValue(EMPTY_CATALOG);
    saveProductStockMock.mockResolvedValue({ success: true });

    render(<InventoryPage />);

    await waitFor(() => expect(screen.getByRole('heading', { name: 'Find or create product' })).toBeTruthy());
    fireEvent.change(screen.getByLabelText('Product chooser input'), { target: { value: 'Cotton Tee' } });
    fireEvent.click(screen.getByText('Add new product: "Cotton Tee"'));

    fireEvent.change(screen.getByPlaceholderText('S, M, L'), { target: { value: 'S,M' } });
    fireEvent.change(screen.getByPlaceholderText('Black, White'), { target: { value: 'Red,Blue' } });
    fireEvent.click(screen.getByText('Generate combinations'));
    fireEvent.click(screen.getByRole('button', { name: 'Save' }));

    await waitFor(() => expect(saveProductStockMock).toHaveBeenCalledTimes(1));
    expect(saveProductStockMock).toHaveBeenCalledWith(
      expect.objectContaining({
        mode: 'new',
        identity: expect.objectContaining({ productName: 'Cotton Tee' }),
        selectedProductId: undefined,
      }),
    );
    const payload = saveProductStockMock.mock.calls[0][0] as { variants: unknown[] };
    expect(payload.variants).toHaveLength(4);
  });

  test('existing product update persists added variants with selectedProductId', async () => {
    getInventoryItemsMock.mockResolvedValue(EMPTY_INVENTORY);
    getInventoryMovementsMock.mockResolvedValue(EMPTY_INVENTORY);
    getProductsStockSnapshotMock.mockResolvedValue({
      products: [
        {
          id: 'p-101',
          identity: {
            productName: 'Urban Tee',
            supplier: 'Nova',
            category: 'Apparel',
            description: '',
            features: [],
          },
          variants: [
            {
              id: 'v-101',
              size: 'M',
              color: 'Red',
              other: '',
              qty: 2,
              cost: 10,
              defaultSellingPrice: 20,
              maxDiscountPct: 10,
            },
          ],
        },
      ],
      suppliers: ['Nova'],
      categories: ['Apparel'],
    });
    saveProductStockMock.mockResolvedValue({ success: true });

    render(<InventoryPage />);

    await waitFor(() => expect(screen.getByRole('heading', { name: 'Find or create product' })).toBeTruthy());
    fireEvent.change(screen.getByLabelText('Product chooser input'), { target: { value: 'Urban Tee' } });
    fireEvent.click(screen.getByRole('button', { name: 'Urban Tee' }));
    fireEvent.click(screen.getByRole('button', { name: 'Add row' }));

    const table = screen.getByRole('table');
    const rows = Array.from(table.querySelectorAll('tbody tr'));
    const newRowInputs = Array.from(rows[rows.length - 1].querySelectorAll('input'));
    fireEvent.change(newRowInputs[0], { target: { value: 'L' } });
    fireEvent.change(newRowInputs[1], { target: { value: 'Blue' } });
    fireEvent.change(newRowInputs[3], { target: { value: '5' } });
    fireEvent.change(newRowInputs[4], { target: { value: '12' } });
    fireEvent.change(newRowInputs[5], { target: { value: '24' } });

    fireEvent.click(screen.getByRole('button', { name: 'Save' }));

    await waitFor(() => expect(saveProductStockMock).toHaveBeenCalledTimes(1));
    expect(saveProductStockMock).toHaveBeenCalledWith(
      expect.objectContaining({
        mode: 'existing',
        selectedProductId: 'p-101',
      }),
    );
    const payload = saveProductStockMock.mock.calls[0][0] as { variants: Array<{ size: string; color: string }> };
    expect(payload.variants).toHaveLength(2);
    expect(payload.variants).toEqual(expect.arrayContaining([expect.objectContaining({ size: 'L', color: 'Blue' })]));
  });

  test('blank manual rows with business values are blocked before save', async () => {
    getInventoryItemsMock.mockResolvedValue(EMPTY_INVENTORY);
    getInventoryMovementsMock.mockResolvedValue(EMPTY_INVENTORY);
    getProductsStockSnapshotMock.mockResolvedValue(EMPTY_CATALOG);

    render(<InventoryPage />);

    await waitFor(() => expect(screen.getByRole('heading', { name: 'Find or create product' })).toBeTruthy());
    fireEvent.change(screen.getByLabelText('Product chooser input'), { target: { value: 'Basic Tee' } });
    fireEvent.click(screen.getByText('Add new product: "Basic Tee"'));
    fireEvent.click(screen.getByRole('button', { name: 'Add row' }));

    const table = screen.getByRole('table');
    const firstRowInputs = Array.from(table.querySelectorAll('tbody tr')[0].querySelectorAll('input'));
    fireEvent.change(firstRowInputs[3], { target: { value: '3' } });

    await waitFor(() => {
      const saveButton = screen.getByRole('button', { name: 'Save' }) as HTMLButtonElement;
      expect(saveButton.disabled).toBe(true);
    });
    expect(saveProductStockMock).not.toHaveBeenCalled();
  });
});
