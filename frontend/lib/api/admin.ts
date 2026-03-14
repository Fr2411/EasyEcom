import { apiClient } from '@/lib/api/client';
import type {
  AdminAuditResponse,
  AdminClient,
  AdminClientUpdateInput,
  AdminClientsResponse,
  AdminOnboardClientInput,
  AdminOnboardResponse,
  AdminRolesResponse,
  AdminUserAccess,
  AdminUserAccessUpdateInput,
  AdminUser,
  AdminUserCreateInput,
  AdminUserPasswordSetInput,
  AdminUsersResponse,
  AdminUserUpdateInput,
} from '@/types/admin';

export function listAdminClients(search?: string) {
  const params = new URLSearchParams();
  if (search?.trim()) {
    params.set('q', search.trim());
  }
  const suffix = params.size ? `?${params.toString()}` : '';
  return apiClient<AdminClientsResponse>(`/admin/clients${suffix}`);
}

export function getAdminClient(clientId: string) {
  return apiClient<AdminClient>(`/admin/clients/${clientId}`);
}

export function updateAdminClient(clientId: string, payload: AdminClientUpdateInput) {
  return apiClient<AdminClient>(`/admin/clients/${clientId}`, {
    method: 'PATCH',
    body: JSON.stringify(payload),
  });
}

export function onboardAdminClient(payload: AdminOnboardClientInput) {
  return apiClient<AdminOnboardResponse>('/admin/clients/onboard', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export function listAdminUsers(clientId: string) {
  return apiClient<AdminUsersResponse>(`/admin/clients/${clientId}/users`);
}

export function createAdminUser(clientId: string, payload: AdminUserCreateInput) {
  return apiClient<AdminUser>(`/admin/clients/${clientId}/users`, {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export function updateAdminUser(userId: string, payload: AdminUserUpdateInput) {
  return apiClient<AdminUser>(`/admin/users/${userId}`, {
    method: 'PATCH',
    body: JSON.stringify(payload),
  });
}

export function setAdminUserPassword(userId: string, payload: AdminUserPasswordSetInput) {
  return apiClient<AdminUser>(`/admin/users/${userId}/set-password`, {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export function getAdminUserAccess(userId: string) {
  return apiClient<AdminUserAccess>(`/admin/users/${userId}/access`);
}

export function updateAdminUserAccess(userId: string, payload: AdminUserAccessUpdateInput) {
  return apiClient<AdminUserAccess>(`/admin/users/${userId}/access`, {
    method: 'PUT',
    body: JSON.stringify(payload),
  });
}

export function listAdminRoles() {
  return apiClient<AdminRolesResponse>('/admin/roles');
}

export function listAdminAudit(clientId?: string) {
  const params = new URLSearchParams();
  if (clientId) {
    params.set('client_id', clientId);
  }
  const suffix = params.size ? `?${params.toString()}` : '';
  return apiClient<AdminAuditResponse>(`/admin/audit${suffix}`);
}
