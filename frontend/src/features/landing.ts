/** Landing page logic. Pure: where the app starts, whether a browser holds a session, and the words for a failed demo start. */

/** `/` is always the About page; the signed-in app starts here (Now). */
export const APP_HOME = '/now';
/** The JS-readable cookie the gateway sets with every session (path `/`, as long-lived as the session) and clears on sign-out. */
export const SESSION_COOKIE = 'lbstash_csrf';

/** True when a `document.cookie` string holds the session marker: the About page then offers "Open the app" instead of sign-in. */
export const hasSessionCookie = (cookieHeader: string): boolean => cookieHeader.split(';').some((c) => c.trim().startsWith(`${SESSION_COOKIE}=`));

/** Plain words for `POST /auth/demo` failing: 404 = the server is not in demo mode; no status = unreachable. */
export function demoFailure(status: number, message: string): string {
  if (status === 404) return 'The demo is not available on this server.';
  if (status === 0 || status >= 500) return 'Could not open the demo. Try again in a moment.';
  return message || 'Could not open the demo. Try again.';
}
