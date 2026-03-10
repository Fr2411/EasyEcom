import { NextResponse } from 'next/server';
import type { NextRequest } from 'next/server';

export function middleware(_request: NextRequest) {
  // Auth redirects are handled by AuthProvider/AuthRouteGuard via backend /auth/me
  // to avoid cross-origin cookie desync loops.
  return NextResponse.next();
}

export const config = {
  matcher: ['/((?!.*\\..*).*)'],
};
