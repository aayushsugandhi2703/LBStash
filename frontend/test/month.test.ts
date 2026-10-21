import { describe, expect, it } from 'vitest';
import { bars, calendar, flexibleSpent, LOGGED_DAYS, planRunsOutDay, repeatsPaid, scrub } from '@/features/month';

const R = (n: number) => n * 100;

describe('the sample month adds up', () => {
  it('day 21 is the app example: ₹26,300 flexible, ₹24,649 of repeats, ₹40,251 available', () => {
    expect(flexibleSpent(21)).toBe(R(26300));
    expect(repeatsPaid(21)).toBe(R(24649));
    expect(scrub(21)).toMatchObject({ phase: 'logged', spentMinor: R(26300), availableMinor: R(40251) });
  });
  it('the forecast days cost the pace (₹1,253) each', () => {
    expect(flexibleSpent(22) - flexibleSpent(21)).toBe(R(1253));
    expect(flexibleSpent(31)).toBe(R(26300 + 10 * 1253));
  });
  it('month end: ₹10,041 left after every repeat and the forecast', () => {
    expect(scrub(31).availableMinor).toBe(R(91200 - 42329 - 38830));
  });
  it('repeats leave on their due days', () => {
    expect(repeatsPaid(4)).toBe(0);
    expect(repeatsPaid(5)).toBe(R(24000));
    expect(repeatsPaid(28)).toBe(R(42329));
  });
});

describe('the plan runs out on day 29', () => {
  it('first day the flexible spend reaches ₹36,000', () => {
    expect(planRunsOutDay()).toBe(29);
    expect(flexibleSpent(28)).toBeLessThan(R(36000));
    expect(flexibleSpent(29)).toBeGreaterThanOrEqual(R(36000));
  });
  it('the verdict moves from on track, to forecast, to ran out', () => {
    expect(scrub(10).verdict.tone).toBe('ok');
    expect(scrub(21).verdict).toEqual({ tone: 'warn', text: 'Forecast: at this pace the plan runs out on day 29.' });
    expect(scrub(28).verdict.tone).toBe('warn');
    expect(scrub(29).verdict.tone).toBe('bad');
    expect(scrub(31).verdict.text).toContain('day 29');
  });
  it('past today it is a forecast, up to today it is logged', () => {
    expect(scrub(LOGGED_DAYS).phase).toBe('logged');
    expect(scrub(LOGGED_DAYS + 1).phase).toBe('forecast');
  });
});

describe('days outside the month are clamped', () => {
  it('0 and 99 give day 1 and day 31', () => {
    expect(scrub(0).day).toBe(1);
    expect(scrub(99).day).toBe(31);
    expect(scrub(12.4).day).toBe(12);
  });
});

describe('bars', () => {
  it('31 bars, solid up to day 21 and striped after', () => {
    const b = bars(21);
    expect(b).toHaveLength(31);
    expect(b.filter((x) => x.kind === 'logged')).toHaveLength(21);
    expect(b.every((x) => x.heightPct > 0 && x.heightPct <= 100)).toBe(true);
    expect(Math.max(...b.map((x) => x.heightPct))).toBe(100);
  });
  it('the chosen day is lit, earlier days are past, later are future', () => {
    const b = bars(12);
    expect(b.filter((x) => x.state === 'now').map((x) => x.day)).toEqual([12]);
    expect(b.filter((x) => x.state === 'past')).toHaveLength(11);
    expect(b.filter((x) => x.state === 'future')).toHaveLength(19);
  });
  it('marks the repeat days and labels a few days only', () => {
    const b = bars(21);
    expect(b.filter((x) => x.repeat).map((x) => x.day)).toEqual([5, 14, 25, 27, 28]);
    expect(b.filter((x) => x.label).map((x) => x.label)).toEqual(['1', '5', '10', '15', '20', '25', '31']);
  });
});

describe('calendar', () => {
  it('a plain grid of 31 days (no month, no weekday): 20 logged, day 21 is today, 10 forecast', () => {
    const c = calendar();
    expect(c).toHaveLength(31);
    expect(c.map((x) => x.day)).toEqual(Array.from({ length: 31 }, (_, i) => i + 1));
    expect(c.find((x) => x.state === 'today')?.day).toBe(21);
    expect(c.filter((x) => x.state === 'past')).toHaveLength(20);
    expect(c.filter((x) => x.state === 'future')).toHaveLength(10);
  });
});

describe('no dates in the words', () => {
  it('no verdict names a month, so the page never goes stale', () => {
    for (let d = 1; d <= 31; d++) expect(scrub(d).verdict.text).not.toMatch(/\b(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)/);
  });
});
