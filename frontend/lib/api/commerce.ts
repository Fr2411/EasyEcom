import { apiClient } from '@/lib/api/client';
import type {
  CatalogCreationStep,
  CatalogUpsertPayload,
  CatalogProduct,
  StagedProductMediaUpload,
  CatalogWorkspace,
} from '@/types/catalog';
import type {
  InventoryAdjustmentPayload,
  InventoryInlineUpdatePayload,
  InventoryIntakeLookup,
  InventoryStockRow,
  InventoryWorkspace,
  ReceiveStockPayload,
  ReceiveStockResponse,
} from '@/types/inventory';
import type { ReturnCreatePayload, ReturnEligibleLines, ReturnLookupOrder, ReturnRefundPayload, ReturnRecord } from '@/types/returns';
import type { EmbeddedCustomer, SaleLookupVariant, SalesOrder, SalesOrderPayload, SalesOrderPaymentPayload } from '@/types/sales';


function buildQuery(params: Record<string, string | boolean | undefined>) {
  const search = new URLSearchParams();
  Object.entries(params).forEach(([key, value]) => {
    if (value === undefined || value === '' || value === false) return;
    search.set(key, String(value));
  });
  const text = search.toString();
  return text ? `?${text}` : '';
}


export async function getCatalogWorkspace(params: {
  q?: string;
  locationId?: string;
  includeOos?: boolean;
} = {}) {
  return apiClient<CatalogWorkspace>(
    `/catalog/workspace${buildQuery({
      q: params.q,
      location_id: params.locationId,
      include_oos: params.includeOos,
    })}`
  );
}


export async function saveCatalogProduct(payload: CatalogUpsertPayload) {
  if (payload.product_id) {
    return apiClient<{ product: CatalogProduct }>(`/catalog/products/${payload.product_id}`, {
      method: 'PUT',
      body: JSON.stringify(payload),
    });
  }
  return apiClient<{ product: CatalogProduct }>('/catalog/products', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export async function validateCatalogCreationStep(payload: {
  step: CatalogCreationStep;
  identity: CatalogUpsertPayload['identity'];
  variants: CatalogUpsertPayload['variants'];
}) {
  return apiClient<{ step: CatalogCreationStep; valid: boolean }>('/catalog/products/validate-step', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}


export async function uploadStagedProductMedia(file: File) {
  const form = new FormData();
  form.append('image', file);
  return apiClient<StagedProductMediaUpload>('/catalog/media/staged', {
    method: 'POST',
    body: form,
  });
}


export async function attachCatalogProductMedia(productId: string, uploadId: string) {
  return apiClient<{ product: CatalogProduct }>(`/catalog/products/${productId}/media`, {
    method: 'POST',
    body: JSON.stringify({ upload_id: uploadId }),
  });
}


export async function getInventoryWorkspace(params: { q?: string; locationId?: string } = {}) {
  return apiClient<InventoryWorkspace>(
    `/inventory/workspace${buildQuery({
      q: params.q,
      location_id: params.locationId,
    })}`
  );
}


export async function getInventoryIntakeLookup(params: { q: string; locationId?: string }) {
  return apiClient<InventoryIntakeLookup>(
    `/inventory/intake/lookup${buildQuery({
      q: params.q,
      location_id: params.locationId,
    })}`
  );
}


export async function receiveInventoryStock(payload: ReceiveStockPayload) {
  return apiClient<ReceiveStockResponse>('/inventory/receipts', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}


export async function createInventoryAdjustment(payload: InventoryAdjustmentPayload) {
  return apiClient<InventoryStockRow>('/inventory/adjustments', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export async function updateInventoryInlineFields(payload: InventoryInlineUpdatePayload) {
  return apiClient<InventoryStockRow>('/inventory/inline-update', {
    method: 'PATCH',
    body: JSON.stringify(payload),
  });
}


export async function getSalesOrders(params: { status?: string; q?: string } = {}) {
  return apiClient<{ items: SalesOrder[] }>(
    `/sales/orders${buildQuery({
      status: params.status,
      q: params.q,
    })}`
  );
}


export async function getSalesOrder(orderId: string) {
  return apiClient<SalesOrder>(`/sales/orders/${orderId}`);
}


export async function searchSaleVariants(params: { q: string; locationId?: string }) {
  return apiClient<{ items: SaleLookupVariant[] }>(
    `/sales/variants/search${buildQuery({
      q: params.q,
      location_id: params.locationId,
    })}`
  );
}


export async function searchEmbeddedCustomers(params: { phone?: string; email?: string }) {
  return apiClient<{ items: EmbeddedCustomer[] }>(
    `/sales/customers/search${buildQuery({
      phone: params.phone,
      email: params.email,
    })}`
  );
}


export async function saveSalesOrder(payload: SalesOrderPayload, orderId?: string) {
  const path = orderId ? `/sales/orders/${orderId}` : '/sales/orders';
  return apiClient<{ order: SalesOrder }>(path, {
    method: orderId ? 'PUT' : 'POST',
    body: JSON.stringify(payload),
  });
}


export async function confirmSalesOrder(orderId: string) {
  return apiClient<{ order: SalesOrder }>(`/sales/orders/${orderId}/confirm`, {
    method: 'POST',
    body: JSON.stringify({}),
  });
}


export async function fulfillSalesOrder(orderId: string) {
  return apiClient<{ order: SalesOrder }>(`/sales/orders/${orderId}/fulfill`, {
    method: 'POST',
    body: JSON.stringify({}),
  });
}

export async function recordSalesOrderPayment(orderId: string, payload: SalesOrderPaymentPayload) {
  return apiClient<{ order: SalesOrder }>(`/sales/orders/${orderId}/record-payment`, {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}


export async function cancelSalesOrder(orderId: string, notes = '') {
  return apiClient<{ order: SalesOrder }>(`/sales/orders/${orderId}/cancel`, {
    method: 'POST',
    body: JSON.stringify({ notes }),
  });
}


export async function getReturns(q = '') {
  return apiClient<{ items: ReturnRecord[] }>(`/returns${buildQuery({ q })}`);
}


export async function searchReturnOrders(q: string) {
  return apiClient<{ items: ReturnLookupOrder[] }>(`/returns/orders/search${buildQuery({ q })}`);
}


export async function getEligibleReturnLines(orderId: string) {
  return apiClient<ReturnEligibleLines>(`/returns/orders/${orderId}/eligible-lines`);
}


export async function createSalesReturn(payload: ReturnCreatePayload) {
  return apiClient<ReturnRecord>('/returns', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export async function recordSalesReturnRefund(returnId: string, payload: ReturnRefundPayload) {
  return apiClient<ReturnRecord>(`/returns/${returnId}/record-refund`, {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}
