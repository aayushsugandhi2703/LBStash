import { describe, expect, it } from 'vitest';
import type { BudgetDto } from '@/contracts';
import { daysLeftText, headline, limitRow, limitRows, warningText } from '@/features/limits';

const R = (n: number) => n * 100;
const display = (n: string) => n.charAt(0).toUpperCase() + n.slice(1);

// docs/ui-spec/04-limits sample on day 18 of 31: projected = spent ÷ 18 × 31, to the nearest ₹10
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
  it('names the one that needs a look, then counts the others', () => {
    expect(headline(limitRows(sample, 80, true), display)).toBe('Fun needs a look. The other 3 are fine.');
  });
  it('says all are on track when none are close', () => {
    expect(headline(limitRows(sample, 90, true), display)).toBe('All four limits are on track.');
    expect(headline([], display)).toBe('No limits yet.');
  });
  it('lists several', () => {
    const rows = limitRows([b('fun', 1640, 2000, 2820), b('food', 8350, 8000, 14000)], 80, true);
    expect(headline(rows, display)).toBe('2 limits need a look: Food and Fun.');
  });
  it('speaks about a single limit and a pair', () => {
    expect(headline(limitRows([sample[2]!], 80, true), display)).toBe('Your limit is on track.');
    expect(headline(limitRows(sample.slice(2), 80, true), display)).toBe('Both limits are on track.');
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
