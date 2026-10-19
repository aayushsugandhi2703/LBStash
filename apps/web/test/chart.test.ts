import { describe, expect, it } from 'vitest';
import { dayScale, figure, inSentence, joinPlain, monthName, monthScale, nextMonthName, pct, shortMonth, wholeRupees } from '@/common';

const R = (n: number) => n * 100;

describe('dayScale', () => {
  it('rounds up on a 1-2-5 ladder with a midline', () => {
    expect(dayScale(R(970))).toEqual({ max: R(1000), mid: R(500) });
    expect(dayScale(R(1000))).toEqual({ max: R(1000), mid: R(500) });
    expect(dayScale(R(1001)).max).toBe(R(2000));
    expect(dayScale(R(2300)).max).toBe(R(5000));
    expect(dayScale(R(5001)).max).toBe(R(10000));
  });
  it('never goes below ₹100, even with no spend', () => {
    expect(dayScale(0).max).toBe(R(100));
    expect(dayScale(R(40)).mid).toBe(R(50));
  });
});

describe('monthScale', () => {
  it('splits into three equal parts: 60K with 40K and 20K for the sample months', () => {
    const s = monthScale(R(50000));
    expect(s.max).toBe(R(60000));
    expect(s.ticks).toEqual([R(60000), R(40000), R(20000)]);
  });
  it('holds the pace block (46,720) and bigger incomes', () => {
    expect(monthScale(R(46720)).max).toBe(R(60000));
    expect(monthScale(R(61000)).max).toBe(R(75000));
    expect(monthScale(R(80000)).max).toBe(R(150000));
  });
  it('floors at ₹3,000', () => {
    expect(monthScale(0).max).toBe(R(3000));
    expect(monthScale(R(3001)).max).toBe(R(6000));
  });
});

describe('small helpers', () => {
  it('pct clamps to the plot', () => {
    expect(pct(50, 200)).toBe(25);
    expect(pct(300, 200)).toBe(100);
    expect(pct(-5, 200)).toBe(0);
    expect(pct(5, 0)).toBe(0);
  });
  it('words for the legend', () => {
    expect([inSentence('Rent'), inSentence('SIP')]).toEqual(['rent', 'SIP']);
    expect(joinPlain(['rent', 'SIP'])).toBe('rent and SIP');
    expect(joinPlain(['a', 'b', 'c'])).toBe('a, b and c');
    expect(joinPlain(['a'])).toBe('a');
    expect(joinPlain([])).toBe('');
  });
  it('figures use Indian grouping and a true minus', () => {
    expect(figure(R(5791))).toBe('5,791');
    expect(figure(R(-1200))).toBe('−1,200');
    expect(wholeRupees(53943)).toBe(53900);
  });
  it('month names', () => {
    expect(monthName('2026-10')).toBe('October');
    expect(nextMonthName('2026-10')).toBe('November');
    expect(nextMonthName('2026-12')).toBe('January');
    expect(shortMonth('2026-09')).toBe('Sep');
  });
});
