import { getPublicEnv } from '@/lib/env';

export class ApiError extends Error {
  constructor(
    message: string,
    public readonly status: number
  ) {
    super(message);
    this.name = 'ApiError';
  }
}

export async function apiClient<T>(path: string, init?: RequestInit): Promise<T> {
  const { apiBaseUrl } = getPublicEnv();
  const response = await fetch(`${apiBaseUrl}${path}`, {
    ...init,
    headers: {
      'Content-Type': 'application/json',
      ...(init?.headers ?? {})
    },
    cache: 'no-store',
    credentials: 'include'
  });

  if (!response.ok) {
    const message = await response.text();
    throw new ApiError(`API request failed (${response.status}): ${message}`, response.status);
  }

  return response.json() as Promise<T>;
}
