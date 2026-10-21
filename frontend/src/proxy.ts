import { type NextRequest, NextResponse } from 'next/server';
import { LANDING_PATH, SESSION_COOKIE, shouldShowLanding } from '@/features/landing';

/** Visitors with no session see the About page at `/` (the address stays `/`); the Now page itself is not touched. */
export function proxy(request: NextRequest) {
  if (!shouldShowLanding(request.nextUrl.pathname, request.cookies.has(SESSION_COOKIE))) return NextResponse.next();
  const url = request.nextUrl.clone();
  url.pathname = LANDING_PATH;
  return NextResponse.rewrite(url);
}

export const config = { matcher: '/' };
