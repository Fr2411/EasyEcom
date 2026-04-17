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

export type ApiClientInit = RequestInit & {
  timeoutMs?: number;
};

const DEFAULT_API_TIMEOUT_MS = 20000;

function buildRequestSignal(sourceSignal: AbortSignal | null | undefined, timeoutMs: number) {
  const timeoutController = new AbortController();
  const combinedController = new AbortController();
  const timeoutId = globalThis.setTimeout(() => timeoutController.abort('timeout'), timeoutMs);

  const abortCombined = () => {
    combinedController.abort();
  };

  timeoutController.signal.addEventListener('abort', abortCombined, { once: true });

  if (sourceSignal) {
    if (sourceSignal.aborted) {
      combinedController.abort();
    } else {
      sourceSignal.addEventListener('abort', abortCombined, { once: true });
    }
  }

  return {
    signal: combinedController.signal,
    timeoutSignal: timeoutController.signal,
    cleanup: () => {
      globalThis.clearTimeout(timeoutId);
      timeoutController.signal.removeEventListener('abort', abortCombined);
      if (sourceSignal) {
        sourceSignal.removeEventListener('abort', abortCombined);
      }
    },
  };
}

export async function apiClient<T>(path: string, init?: ApiClientInit): Promise<T> {
  const { apiBaseUrl } = getPublicEnv();
  const url = `${apiBaseUrl}${path}`;
  const isFormData = typeof FormData !== 'undefined' && init?.body instanceof FormData;
  const timeoutMs = init?.timeoutMs ?? DEFAULT_API_TIMEOUT_MS;
  const signalState = buildRequestSignal(init?.signal, timeoutMs);

  let response: Response;
  try {
    response = await fetch(url, {
      ...init,
      signal: signalState.signal,
      credentials: 'include',
      cache: 'no-store',
      headers: {
        ...(isFormData ? {} : { 'Content-Type': 'application/json' }),
        ...(init?.headers ?? {}),
      },
    });
  } catch (error) {
    const isAbortError = error instanceof DOMException && error.name === 'AbortError';
    if (isAbortError && signalState.timeoutSignal.aborted) {
      throw new ApiNetworkError(`Request timed out after ${timeoutMs}ms (${url})`);
    }
    if (isAbortError) {
      throw new ApiNetworkError(`Request was cancelled (${url})`);
    }
    throw new ApiNetworkError(
      error instanceof Error ? `${error.message} (${url})` : `Network request failed (${url})`,
    );
  } finally {
    signalState.cleanup();
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
          : typeof payload?.detail === 'string'
            ? payload.detail
            : JSON.stringify(payload);
    } else {
      message = (await response.text()) || message;
    }
    throw new ApiError(
      response.status,
      `${message || `API request failed (${response.status})`} (${url})`,
    );
  }

  if (response.status === 204) {
    return undefined as T;
  }

  return (isJson ? await response.json() : await response.text()) as T;
}
