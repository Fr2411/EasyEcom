import { describe, expect, test } from 'vitest';
import { safePurchaseWorkspaceErrorMessage } from '@/components/purchases/purchases-workspace';
import { ApiError, ApiNetworkError } from '@/lib/api/client';

describe('safePurchaseWorkspaceErrorMessage', () => {
  test('returns a safe message for purchase-order network failures', () => {
    const result = safePurchaseWorkspaceErrorMessage(
      new ApiNetworkError('fetch failed (https://api.easy-ecom.online/purchases/orders)')
    );
    expect(result).toBe('Unable to load purchase orders right now. Check your connection and try again.');
  });

  test('returns a permission-safe message for 403 responses', () => {
    const result = safePurchaseWorkspaceErrorMessage(
      new ApiError(403, 'Forbidden (https://api.easy-ecom.online/purchases/orders)')
    );
    expect(result).toBe('You do not have permission to view purchase orders.');
  });

  test('returns a service-safe message for backend 5xx responses', () => {
    const result = safePurchaseWorkspaceErrorMessage(
      new ApiError(500, 'Internal Server Error (https://api.easy-ecom.online/purchases/orders)')
    );
    expect(result).toBe('Purchase orders are temporarily unavailable. Please try again in a moment.');
  });

  test('strips request URLs from generic error messages', () => {
    const result = safePurchaseWorkspaceErrorMessage(
      new Error('Failed to fetch purchase orders (https://api.easy-ecom.online/purchases/orders?status=draft)')
    );
    expect(result).toBe('Failed to fetch purchase orders');
  });
});
