import { apiClient } from '@/lib/api/client';
import type { InventoryAdjustmentPayload, InventoryDetail, InventoryItem, InventoryMovement } from '@/types/inventory';

export async function getInventoryItems(q = ''): Promise<{ items: InventoryItem[] }> {
  const params = new URLSearchParams();
  if (q.trim()) params.set('q', q.trim());
  return apiClient<{ items: InventoryItem[] }>(`/inventory${params.toString() ? `?${params.toString()}` : ''}`);
}

export async function getInventoryMovements(paramsInput: {
  item_id?: string;
  movement_type?: string;
  start_date?: string;
  end_date?: string;
  limit?: number;
} = {}): Promise<{ items: InventoryMovement[] }> {
  const params = new URLSearchParams();
  if (paramsInput.item_id) params.set('item_id', paramsInput.item_id);
  if (paramsInput.movement_type) params.set('movement_type', paramsInput.movement_type);
  if (paramsInput.start_date) params.set('start_date', paramsInput.start_date);
  if (paramsInput.end_date) params.set('end_date', paramsInput.end_date);
  if (paramsInput.limit) params.set('limit', String(paramsInput.limit));
  return apiClient<{ items: InventoryMovement[] }>(`/inventory/movements${params.toString() ? `?${params.toString()}` : ''}`);
}

export async function getInventoryDetail(itemId: string): Promise<InventoryDetail> {
  return apiClient<InventoryDetail>(`/inventory/${itemId}`);
}

export async function createInventoryAdjustment(payload: InventoryAdjustmentPayload): Promise<{ success: boolean }> {
  return apiClient<{ success: boolean }>('/inventory/adjustments', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}


export async function createInboundStock(payload: {
  item_id: string;
  quantity: number;
  expected_unit_cost: number;
  supplier_snapshot?: string;
  note?: string;
  reference?: string;
}): Promise<{ success: boolean; inbound_id: string; item_id: string; pending_incoming_qty: number }> {
  return apiClient('/inventory/inbound', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export async function receiveInboundStock(inboundId: string, payload: {
  quantity?: number;
  unit_cost?: number;
  note?: string;
}): Promise<{ success: boolean; inbound_id: string; item_id: string; received_qty: number; lot_id: string }> {
  return apiClient(`/inventory/inbound/${inboundId}/receive`, {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}
