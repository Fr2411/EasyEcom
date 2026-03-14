import { getPublicEnv } from '@/lib/env';

export class ApiError extends Error {
  status: number;

  constructor(status: number, message: string) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
  }
}

export class ApiNetworkError extends Error {
  constructor(message = 'Network request failed') {
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
      credentials: 'include',
      cache: 'no-store',
      headers: {
        'Content-Type': 'application/json',
        ...(init?.headers ?? {}),
      },
    });
  } catch (error) {
    throw new ApiNetworkError(
      error instanceof Error ? error.message : 'Network request failed',
    );
  }

  const contentType = response.headers.get('content-type') ?? '';
  const isJson = contentType.includes('application/json');

  if (!response.ok) {
    let message = `API request failed (${response.status})`;
    if (isJson) {
      const payload = await response.json();
      message =
        typeof payload?.error?.message === 'string'
          ? payload.error.message
          : JSON.stringify(payload);
    } else {
      message = (await response.text()) || message;
    }
    throw new ApiError(response.status, message || `API request failed (${response.status})`);
  }

  if (response.status === 204) {
    return undefined as T;
  }

  return (isJson ? await response.json() : await response.text()) as T;
}
