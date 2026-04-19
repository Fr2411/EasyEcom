import { NextResponse } from 'next/server';
import type { NextRequest } from 'next/server';

export function middleware(request: NextRequest) {
  if (request.nextUrl.pathname === '/inventory/products') {
    const url = request.nextUrl.clone();
    url.pathname = '/inventory';
    url.searchParams.set('tab', 'receive');
    return NextResponse.redirect(url);
  }
  // Auth redirects are handled by AuthProvider/AuthRouteGuard via backend /auth/me
  // to avoid cross-origin cookie desync loops.
  return NextResponse.next();
}

export const config = {
  matcher: ['/((?!.*\\..*).*)'],
};
