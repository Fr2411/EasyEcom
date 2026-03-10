import { apiClient } from '@/lib/api/client';
import type { AdminAuditResponse, AdminRolesResponse, AdminUser, AdminUsersResponse } from '@/types/admin';

export async function getAdminUsers() {
  return apiClient<AdminUsersResponse>('/admin/users');
}

export async function createAdminUser(payload: {
  name: string;
  email: string;
  password: string;
  role_codes: string[];
  is_active: boolean;
}) {
  return apiClient<{ user: AdminUser }>('/admin/users', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export async function updateAdminUser(userId: string, payload: { name?: string; email?: string; is_active?: boolean }) {
  return apiClient<{ user: AdminUser }>(`/admin/users/${userId}`, {
    method: 'PATCH',
    body: JSON.stringify(payload),
  });
}

export async function setAdminUserRoles(userId: string, roleCodes: string[]) {
  return apiClient<{ user: AdminUser }>(`/admin/users/${userId}/roles`, {
    method: 'PATCH',
    body: JSON.stringify({ role_codes: roleCodes }),
  });
}

export async function getAdminRoles() {
  return apiClient<AdminRolesResponse>('/admin/roles');
}

export async function getAdminAudit() {
  return apiClient<AdminAuditResponse>('/admin/audit');
}
