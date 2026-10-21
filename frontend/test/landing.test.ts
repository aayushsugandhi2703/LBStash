import { describe, expect, it } from 'vitest';
import { demoFailure, shouldShowLanding } from '@/features/landing';

describe('who sees the About page', () => {
  it('a visitor with no session opening / does', () => {
    expect(shouldShowLanding('/', false)).toBe(true);
  });
  it('a signed-in visit to / still gets the Now page', () => {
    expect(shouldShowLanding('/', true)).toBe(false);
  });
  it('no other address is ever rewritten', () => {
    for (const p of ['/welcome', '/sign-in', '/create-account', '/money', '/setup', '/pay', '/api/me', '/_next/static/a.js', '/favicon.ico']) {
      expect(shouldShowLanding(p, false)).toBe(false);
    }
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
