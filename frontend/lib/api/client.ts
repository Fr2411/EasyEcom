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

export class ApiNetworkError extends Error {
  constructor(message: string) {
    super(message);
    this.name = 'ApiNetworkError';
  }
}

export async function apiClient<T>(path: string, init?: RequestInit): Promise<T> {
  const { apiBaseUrl } = getPublicEnv();
  let response: Response;

  try {
    response = await fetch(`${apiBaseUrl}${path}`, {
      ...init,
      headers: {
        'Content-Type': 'application/json',
        ...(init?.headers ?? {})
      },
      cache: 'no-store',
      credentials: 'include'
    });
  } catch (error: unknown) {
    throw new ApiNetworkError(`API request failed before receiving a response: ${String(error)}`);
  }

  if (!response.ok) {
    const message = await response.text();
    throw new ApiError(`API request failed (${response.status}): ${message}`, response.status);
  }

  return response.json() as Promise<T>;
}
