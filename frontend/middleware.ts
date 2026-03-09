import { NextResponse } from 'next/server';
import type { NextRequest } from 'next/server';
import { getSessionCookieName, hasUsableSessionCookie } from '@/lib/auth/session-cookie';

const SESSION_COOKIE = getSessionCookieName();

export function middleware(request: NextRequest) {
  const { pathname } = request.nextUrl;
  if (pathname.startsWith('/_next') || pathname.startsWith('/favicon') || pathname.startsWith('/api')) {
    return NextResponse.next();
  }

  const hasSession = hasUsableSessionCookie(request.cookies.get(SESSION_COOKIE)?.value);

  if (!hasSession && pathname !== '/login') {
    return NextResponse.redirect(new URL('/login', request.url));
  }

  if (hasSession && pathname === '/login') {
    return NextResponse.redirect(new URL('/dashboard', request.url));
  }

  return NextResponse.next();
}

export const config = {
  matcher: ['/((?!.*\\..*).*)']
};
