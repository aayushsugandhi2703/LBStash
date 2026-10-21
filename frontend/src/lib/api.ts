'use client';
import useSWR, { type SWRConfiguration } from 'swr';

/** Browser → gateway. Same origin under /api, so the SameSite=Strict cookies travel (README 7.3). */
const BASE = '/api';

export class ApiError extends Error {
  constructor(readonly status: number, readonly code: string, message: string, readonly details?: unknown) {
    super(message);
  }
}

const cookie = (name: string): string | undefined =>
  typeof document === 'undefined' ? undefined : document.cookie.split('; ').find((c) => c.startsWith(`${name}=`))?.slice(name.length + 1);

let refreshing: Promise<boolean> | null = null;
/** One refresh at a time; every request that hit 401 waits for the same one. */
function refreshSession(): Promise<boolean> {
  refreshing ??= fetch(`${BASE}/auth/refresh`, {
    method: 'POST', credentials: 'same-origin', headers: { 'x-csrf-token': decodeURIComponent(cookie('lbstash_csrf') ?? '') },
  }).then((r) => r.ok).catch(() => false).finally(() => { refreshing = null; });
  return refreshing;
}

const AUTH_PAGES = ['/sign-in', '/create-account', '/secure', '/reset'];
/** Sign-in style calls have no session to refresh (a 401 there is an answer); other /auth calls do (README 7.3). */
const SESSIONLESS = /^\/auth\/(login|register|refresh|2fa\/verify|reset\/|passkey\/login\/|demo$)/;

async function send<T>(method: string, path: string, body: unknown, retry: boolean): Promise<T> {
  const mutating = method !== 'GET';
  let res: Response;
  try {
    res = await fetch(`${BASE}${path}`, {
      method, credentials: 'same-origin',
      headers: {
        ...(body !== undefined ? { 'content-type': 'application/json' } : {}),
        ...(mutating ? { 'x-csrf-token': decodeURIComponent(cookie('lbstash_csrf') ?? '') } : {}),
      },
      body: body !== undefined ? JSON.stringify(body) : undefined,
    });
  } catch {
    throw new ApiError(0, 'offline', 'Could not reach the server.');
  }
  const text = await res.text();
  const json = text ? (() => { try { return JSON.parse(text); } catch { return undefined; } })() : undefined;
  const error = (json as { error?: { code?: string; message?: string; details?: unknown } } | undefined)?.error;
  // A wrong authenticator code is a 401 too, but only `unauthorized` means the session ran out.
  if (res.status === 401 && error?.code === 'unauthorized' && retry && !SESSIONLESS.test(path)) {
    if (await refreshSession()) return send<T>(method, path, body, false);
    if (typeof window !== 'undefined' && !AUTH_PAGES.some((p) => window.location.pathname.startsWith(p))) {
      window.location.assign(`/sign-in?next=${encodeURIComponent(`${window.location.pathname}${window.location.search}`)}`);
    }
  }
  const setupRequired = error?.details !== null && typeof error?.details === 'object'
    && 'setupRequired' in error.details && error.details.setupRequired === true;
  if (res.status === 403 && setupRequired && typeof window !== 'undefined' && window.location.pathname !== '/secure') {
    const next = `${window.location.pathname}${window.location.search}`;
    window.location.assign(`/secure?next=${encodeURIComponent(next)}`);
  }
  if (!res.ok) {
    throw new ApiError(res.status, error?.code ?? 'error', error?.message ?? 'Something went wrong.', error?.details);
  }
  return json as T;
}

export const api = {
  get: <T>(path: string) => send<T>('GET', path, undefined, true),
  post: <T>(path: string, body?: unknown) => send<T>('POST', path, body ?? {}, true),
  put: <T>(path: string, body?: unknown) => send<T>('PUT', path, body ?? {}, true),
  patch: <T>(path: string, body?: unknown) => send<T>('PATCH', path, body ?? {}, true),
  del: <T>(path: string, body?: unknown) => send<T>('DELETE', path, body, true),
};

/** Read a resource; refetches on focus (README 16: start with refetch-on-focus, no push). `null` path = don't fetch. */
export function useApi<T>(path: string | null, config?: SWRConfiguration<T, ApiError>) {
  return useSWR<T, ApiError>(path, (p: string) => api.get<T>(p), { revalidateOnFocus: true, shouldRetryOnError: false, ...config });
}

/** Plain-words message for a failed call (design system §10: never codes or stack traces). */
export function errorText(e: unknown, fallback = 'Something went wrong. Try again.'): string {
  if (e instanceof ApiError) {
    if (e.code === 'offline') return 'Could not reach the server. Your entry is kept. Try again.';
    if (e.status >= 500) return fallback;
    return e.message || fallback;
  }
  return fallback;
}

/** `details` of a validation error as { field: message }, for showing under the field. */
export function fieldErrors(e: unknown): Record<string, string> {
  if (e instanceof ApiError && e.code === 'validation_failed' && e.details && typeof e.details === 'object' && !Array.isArray(e.details)) {
    return e.details as Record<string, string>;
  }
  return {};
}
