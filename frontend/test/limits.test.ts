import { describe, expect, it } from 'vitest';
import type { BudgetDto } from '@/contracts';
import { closest, daysLeftText, headline, heading, hitDay, limitRow, limitRows, warningText } from '@/features/limits';

const R = (n: number) => n * 100;
const display = (n: string) => n.charAt(0).toUpperCase() + n.slice(1);

// The limits sample on day 18 of 31: projected = spent ÷ 18 × 31, to the nearest ₹10
const b = (name: string, spent: number, limit: number, projected: number, over: Partial<BudgetDto> = {}): BudgetDto => ({
  id: name, categoryId: `c-${name}`, categoryName: name, limitMinor: R(limit), period: 'monthly', warnPct: null, active: true,
  spentMinor: R(spent), pct: Math.floor((spent / limit) * 100), projectedMinor: R(projected), status: 'ok', ...over,
});
const sample = [b('travel', 1350, 3000, 2330), b('fun', 1640, 2000, 2820), b('bills', 1299, 2500, 2240), b('food', 5420, 8000, 9330)];

describe('limit rows', () => {
  it('orders fullest first: Fun, Food, Bills, Travel', () => {
    expect(limitRows(sample, 80, true).map((r) => r.name)).toEqual(['fun', 'food', 'bills', 'travel']);
  });
  it('Fun is close, Food is spending fast, the rest are on track (level 80)', () => {
    const by = Object.fromEntries(limitRows(sample, 80, true).map((r) => [r.name, r]));
    expect(by.fun).toMatchObject({ status: 'close', pct: 82, leftMinor: R(360), diffMinor: R(820) });
    expect(by.food).toMatchObject({ status: 'fast', statusText: 'Spending fast', diffMinor: R(1330) });
    expect(by.bills).toMatchObject({ status: 'ok', pct: 52, leftMinor: R(1201), diffMinor: R(-260) });
    expect(by.travel).toMatchObject({ status: 'ok', diffMinor: R(-670) });
  });
  it('level 90 turns Fun into spending fast, level 70 keeps Food (68%) fast', () => {
    expect(limitRows(sample, 90, true)[0]).toMatchObject({ name: 'fun', status: 'fast', alertPct: 90 });
    expect(limitRows(sample, 70, true).find((r) => r.name === 'food')?.status).toBe('fast');
  });
  it('a limit with its own warn percentage ignores the user level', () => {
    expect(limitRow(b('fun', 1640, 2000, 2820, { warnPct: 90 }), 80, true)).toMatchObject({ alertPct: 90, status: 'fast' });
  });
  it('with the pace warning off, spending fast reads on track', () => {
    expect(limitRow(sample[3]!, 80, false).status).toBe('ok');
  });
  it('spent at the limit is over; the bar stops at the end of its track', () => {
    const r = limitRow(b('food', 8350, 8000, 14000), 80, true);
    expect(r).toMatchObject({ status: 'over', ratio: 1, leftMinor: R(-350), statusText: 'Over the limit' });
  });
  it('leaves inactive limits out', () => {
    expect(limitRows([...sample, b('gym', 0, 1000, 0, { active: false })], 80, true)).toHaveLength(4);
  });
  it('breaks a tie on the same fill by name', () => {
    expect(limitRows([b('zed', 50, 100, 90), b('amy', 50, 100, 90)], 80, true).map((r) => r.name)).toEqual(['amy', 'zed']);
  });
  it('a zero limit never divides by zero', () => {
    expect(limitRow(b('x', 0, 0, 0), 80, true)).toMatchObject({ pct: 0, ratio: 0 });
  });
});

describe('headline', () => {
  it('lists every limit that is close, over or spending fast', () => {
    expect(headline(limitRows(sample, 80, true), display)).toBe('2 limits need a look: Fun and Food.');
  });
  it('names the one that needs a look, then counts the others', () => {
    expect(headline(limitRows([sample[0]!, sample[1]!, sample[2]!], 80, true), display)).toBe('Fun needs a look. The other 2 are fine.');
  });
  it('says all are on track when none are close or fast', () => {
    expect(headline(limitRows(sample, 90, false), display)).toBe('All four limits are on track.');
    expect(headline([], display)).toBe('No limits yet.');
  });
  it('lists several', () => {
    const rows = limitRows([b('fun', 1640, 2000, 2820), b('food', 8350, 8000, 14000)], 80, true);
    expect(headline(rows, display)).toBe('2 limits need a look: Food and Fun.');
  });
  it('speaks about a single limit and a pair', () => {
    expect(headline(limitRows([sample[2]!], 80, true), display)).toBe('Your limit is on track.');
    expect(headline(limitRows(sample.slice(2), 80, false), display)).toBe('Both limits are on track.');
    expect(headline(limitRows([sample[1]!], 80, true), display)).toBe('Fun needs a look.');
  });
});

describe('small copy', () => {
  it('counts the days left', () => {
    expect(daysLeftText(18, 31, 'October')).toBe('13 days left in October');
    expect(daysLeftText(30, 31, 'October')).toBe('1 day left in October');
    expect(daysLeftText(31, 31, 'October')).toBe('last day of October');
  });
  it('words a warning with the limit\'s own percentage when it has one', () => {
    const budgets = [b('fun', 1640, 2000, 2820, { warnPct: 90 })];
    const alert = { id: 'a', budgetId: 'fun', categoryName: 'fun', level: 'alert' as const, sentAt: '2026-10-17T10:00:00Z' };
    expect(warningText(alert, budgets, 80, display)).toBe('Fun passed 90%');
    expect(warningText(alert, [], 80, display)).toBe('Fun passed 80%');
    expect(warningText({ ...alert, level: 'exceeded' }, budgets, 80, display)).toBe('Fun went over its limit');
  });
});

describe('hitDay', () => {
  // October, day 21 of 31
  const t = { month: '2026-10', day: 21, days: 31 };
  it('names the day the pace reaches the limit and how far away it is', () => {
    expect(hitDay({ spentMinor: R(6420), limitMinor: R(7000) }, t)).toEqual({ day: 23, away: 2 });
    expect(hitDay({ spentMinor: R(4280), limitMinor: R(5500) }, t)).toEqual({ day: 27, away: 6 });
  });
  it('is null when the pace stays inside, or nothing is spent', () => {
    expect(hitDay({ spentMinor: R(1180), limitMinor: R(2500) }, t)).toBeNull();
    expect(hitDay({ spentMinor: 0, limitMinor: R(2500) }, t)).toBeNull();
  });
  it('is null once the limit is passed', () => {
    expect(hitDay({ spentMinor: R(7000), limitMinor: R(7000) }, t)).toBeNull();
  });
  it('lands tomorrow when one more day is enough', () => {
    expect(hitDay({ spentMinor: R(6900), limitMinor: R(7000) }, t)).toEqual({ day: 22, away: 1 });
  });
});

describe('the rows of the table', () => {
  const t = { month: '2026-10', day: 21, days: 31 };
  const shop = limitRow(b('shopping', 6420, 7000, 9480), 80, true);
  it('says when the limit is hit and what pace keeps it', () => {
    expect(heading(shop, t)).toEqual({ text: 'Hits the limit Oct 23', when: 'in 2 days', bad: true, note: 'Safe pace ₹58 a day. You spend ₹306.' });
  });
  it('says a limit stays inside when the pace is under it', () => {
    expect(heading(limitRow(b('health', 1180, 2500, 1740), 80, true), t)).toMatchObject({ text: 'Stays inside the limit', bad: false });
  });
  it('says by how much a limit is passed', () => {
    expect(heading(limitRow(b('food', 8350, 8000, 14000), 80, true), t)).toEqual({ text: 'Over by ₹350', when: '', bad: true, note: '' });
  });
  it('names the limit that is hit first', () => {
    const rows = [shop, limitRow(b('fun', 4280, 5500, 6320), 80, true)];
    expect(closest(rows, t)).toEqual({ name: 'shopping', date: 'Oct 23' });
    expect(closest([limitRow(b('health', 1180, 2500, 1740), 80, true)], t)).toBeNull();
  });
});
