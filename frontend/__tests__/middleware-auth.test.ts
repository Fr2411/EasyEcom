import { describe, expect, test, vi } from 'vitest';
import { NextRequest } from 'next/server';

describe('auth middleware', () => {
  test('valid cookie allows dashboard', async () => {
    vi.resetModules();
    vi.stubEnv('NEXT_PUBLIC_SESSION_COOKIE_NAME', 'easy_ecom_session');
    const { middleware } = await import('@/middleware');

    const request = new NextRequest('https://example.com/dashboard', {
      headers: { cookie: 'easy_ecom_session=session-token-123' }
    });

    const response = middleware(request);
    expect(response.headers.get('location')).toBeNull();
  });

  test('missing cookie redirects to login', async () => {
    vi.resetModules();
    vi.stubEnv('NEXT_PUBLIC_SESSION_COOKIE_NAME', 'easy_ecom_session');
    const { middleware } = await import('@/middleware');

    const request = new NextRequest('https://example.com/dashboard');

    const response = middleware(request);
    expect(response.headers.get('location')).toBe('https://example.com/login');
  });

  test('authenticated user can still access login path (client guard handles redirect)', async () => {
    vi.resetModules();
    vi.stubEnv('NEXT_PUBLIC_SESSION_COOKIE_NAME', 'easy_ecom_session');
    const { middleware } = await import('@/middleware');

    const request = new NextRequest('https://example.com/login', {
      headers: { cookie: 'easy_ecom_session=session-token-123' }
    });

    const response = middleware(request);
    expect(response.headers.get('location')).toBeNull();
  });

  test('quoted cookie values still count as a valid session cookie', async () => {
    vi.resetModules();
    vi.stubEnv('NEXT_PUBLIC_SESSION_COOKIE_NAME', '"easy_ecom_session"');
    const { middleware } = await import('@/middleware');

    const request = new NextRequest('https://example.com/dashboard', {
      headers: { cookie: 'easy_ecom_session="quoted-token"' }
    });

    const response = middleware(request);
    expect(response.headers.get('location')).toBeNull();
  });
});
