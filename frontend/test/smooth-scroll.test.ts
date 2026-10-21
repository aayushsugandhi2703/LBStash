import { describe, expect, it } from 'vitest';
import { canScroll, clampTarget, stepToward, wheelPixels } from '@/lib/smooth-scroll';

describe('wheelPixels', () => {
  it('pixels stay, lines become 40 px, pages become the page height', () => {
    expect(wheelPixels({ deltaY: 100, deltaMode: 0 }, 800)).toBe(100);
    expect(wheelPixels({ deltaY: 3, deltaMode: 1 }, 800)).toBe(120);
    expect(wheelPixels({ deltaY: 1, deltaMode: 2 }, 800)).toBe(800);
    expect(wheelPixels({ deltaY: -2, deltaMode: 1 }, 800)).toBe(-80);
  });
});

describe('clampTarget', () => {
  it('stays inside 0..max, and max is never negative', () => {
    expect(clampTarget(-50, 1000)).toBe(0);
    expect(clampTarget(1500, 1000)).toBe(1000);
    expect(clampTarget(420, 1000)).toBe(420);
    expect(clampTarget(10, -5)).toBe(0);
  });
});

describe('canScroll', () => {
  it('up needs room above, down needs room below (1 px of slack)', () => {
    expect(canScroll(0, 600, 2000, -10)).toBe(false);
    expect(canScroll(5, 600, 2000, -10)).toBe(true);
    expect(canScroll(1400, 600, 2000, 10)).toBe(false);
    expect(canScroll(1399, 600, 2000, 10)).toBe(false);
    expect(canScroll(1000, 600, 2000, 10)).toBe(true);
  });
});

describe('stepToward', () => {
  it('moves part of the way and never overshoots', () => {
    const a = stepToward(0, 100, 16);
    expect(a).toBeGreaterThan(0);
    expect(a).toBeLessThan(100);
    expect(stepToward(100, 0, 16)).toBeGreaterThan(0);
  });
  it('is frame-rate independent: two 8 ms steps equal one 16 ms step', () => {
    const one = stepToward(0, 100, 16);
    const two = stepToward(stepToward(0, 100, 8), 100, 8);
    expect(two).toBeCloseTo(one, 6);
  });
  it('snaps when within half a pixel, and converges', () => {
    expect(stepToward(99.7, 100, 16)).toBe(100);
    let y = 0;
    for (let i = 0; i < 200; i++) y = stepToward(y, 800, 16);
    expect(y).toBe(800);
  });
  it('a stalled frame does not move', () => {
    expect(stepToward(10, 100, 0)).toBe(10);
  });
});
