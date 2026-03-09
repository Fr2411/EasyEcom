import { describe, expect, test } from 'vitest';
import { getSessionCookieName, hasUsableSessionCookie } from '@/lib/auth/session-cookie';

describe('env contract', () => {
  test('exposes API base URL variable name for Amplify', () => {
    expect('NEXT_PUBLIC_API_BASE_URL').toContain('NEXT_PUBLIC_');
  });

  test('normalizes quoted session cookie config values', () => {
    expect(getSessionCookieName('"easy_ecom_session"')).toBe('easy_ecom_session');
  });

  test('treats quoted cookie values as usable', () => {
    expect(hasUsableSessionCookie('"token"')).toBe(true);
  });
});
