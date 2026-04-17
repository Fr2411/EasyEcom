import { apiClient } from '@/lib/api/client';

export type SessionUser = {
  user_id: string;
  email: string;
  name: string;
  business_name?: string | null;
  role: string;
  client_id: string | null;
  roles: string[];
  allowed_pages: string[];
  billing_plan_code?: string | null;
  billing_status?: string | null;
  billing_access_state?: string | null;
  billing_grace_until?: string | null;
  is_authenticated: boolean;
};

export async function login(email: string, password: string) {
  return apiClient('/auth/login', {
    method: 'POST',
    body: JSON.stringify({ email, password })
  });
}

export async function logout() {
  return apiClient<{ success: boolean }>('/auth/logout', {
    method: 'POST'
  });
}

export async function getCurrentUser() {
  return apiClient<SessionUser>('/auth/me', {
    timeoutMs: 12000,
  });
}
