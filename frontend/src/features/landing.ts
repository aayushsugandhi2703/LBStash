/** Landing page logic. Pure: which visitors see the About page at `/`, and the words for a failed demo start. */

export const LANDING_PATH = '/welcome';
/** The JS-readable cookie the gateway sets with every session (path `/`, as long-lived as the session) and clears on sign-out. */
export const SESSION_COOKIE = 'lbstash_csrf';

/** `/` is the About page for people with no session; everything else, and every signed-in visit, is untouched. */
export const shouldShowLanding = (pathname: string, hasSessionCookie: boolean): boolean => pathname === '/' && !hasSessionCookie;

/** Plain words for `POST /auth/demo` failing: 404 = the server is not in demo mode; no status = unreachable. */
export function demoFailure(status: number, message: string): string {
  if (status === 404) return 'The demo is not available on this server.';
  if (status === 0 || status >= 500) return 'Could not open the demo. Try again in a moment.';
  return message || 'Could not open the demo. Try again.';
}
