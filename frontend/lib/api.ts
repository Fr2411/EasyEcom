export const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost:8000';

export type SessionUser = {
  user_id: string;
  client_id: string;
  roles: string;
  name: string;
  email: string;
};

function authHeaders(user: SessionUser | null): HeadersInit {
  if (!user) return {};
  return {
    'X-User-Id': user.user_id,
    'X-Client-Id': user.client_id,
    'X-Roles': user.roles
  };
}

export async function apiGet<T>(path: string, user: SessionUser | null): Promise<T> {
  const res = await fetch(`${API_BASE_URL}${path}`, { headers: authHeaders(user), cache: 'no-store' });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export async function apiPost<T>(path: string, body: unknown, user: SessionUser | null): Promise<T> {
  const res = await fetch(`${API_BASE_URL}${path}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', ...authHeaders(user) },
    body: JSON.stringify(body)
  });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}
