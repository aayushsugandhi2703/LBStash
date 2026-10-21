import { describe, expect, it } from 'vitest';
import { APP_HOME, demoFailure, hasSessionCookie } from '@/features/landing';

describe('where the app starts', () => {
  it('the signed-in app starts at /now; / is always the About page', () => {
    expect(APP_HOME).toBe('/now');
  });
});

describe('does this browser hold a session', () => {
  it('finds the session marker among other cookies', () => {
    expect(hasSessionCookie('lbstash_csrf=abc')).toBe(true);
    expect(hasSessionCookie('theme=dark; lbstash_csrf=abc; other=1')).toBe(true);
  });
  it('is false without it, and a similar name does not count', () => {
    expect(hasSessionCookie('')).toBe(false);
    expect(hasSessionCookie('theme=dark')).toBe(false);
    expect(hasSessionCookie('xlbstash_csrf=1; lbstash_csrf_old=1')).toBe(false);
  });
});

describe('demo failure text', () => {
  it('404 means the server has no demo', () => {
    expect(demoFailure(404, 'Not found')).toBe('The demo is not available on this server.');
  });
  it('offline and server errors ask to try again', () => {
    expect(demoFailure(0, 'Could not reach the server.')).toBe('Could not open the demo. Try again in a moment.');
    expect(demoFailure(502, 'bad gateway')).toBe('Could not open the demo. Try again in a moment.');
  });
  it('other errors keep the server message, or a fallback', () => {
    expect(demoFailure(429, 'Too many requests, try again later')).toBe('Too many requests, try again later');
    expect(demoFailure(400, '')).toBe('Could not open the demo. Try again.');
  });
});
