import { NextResponse } from 'next/server';
import type { NextRequest } from 'next/server';

const SESSION_COOKIE = process.env.NEXT_PUBLIC_SESSION_COOKIE_NAME ?? 'easy_ecom_session';

export function middleware(request: NextRequest) {
  const { pathname } = request.nextUrl;
  if (pathname.startsWith('/_next') || pathname.startsWith('/favicon') || pathname.startsWith('/api')) {
    return NextResponse.next();
  }

  const hasSession = Boolean(request.cookies.get(SESSION_COOKIE)?.value);

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
