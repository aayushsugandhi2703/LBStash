import { describe, expect, it } from 'vitest';
import { cleanTag, creditBody, creditMath, creditTags, dateText, defaultPickDate, resolveDate, withTag } from '@/features/credit';
import { addRupees, groupIndian } from '@/common';

// ui-spec dataset: October 2026, day 18, balance 37,591, money to plan 50,000
const BAL = 3_759_100;
const PLAN = 5_000_000;

describe('credit math (spec examples)', () => {
  it('50,000 → new balance 87,591, new plan 1,00,000', () => {
    const m = creditMath({ balanceMinor: BAL, planMinor: PLAN, creditMinor: 5_000_000, addToPlan: true });
    expect(m.newBalanceMinor).toBe(8_759_100);
    expect(m.newPlanMinor).toBe(10_000_000);
    expect(groupIndian(String(m.newPlanMinor! / 100))).toBe('1,00,000');
  });
  it('switch off leaves the plan alone', () => {
    const m = creditMath({ balanceMinor: BAL, planMinor: PLAN, creditMinor: 5_100_000, addToPlan: false });
    expect(m.planAddMinor).toBe(0);
    expect(m.newPlanMinor).toBe(PLAN);
    expect(m.newBalanceMinor).toBe(8_859_100);
  });
  it('unknown figures stay unknown', () => {
    expect(creditMath({ balanceMinor: null, planMinor: null, creditMinor: 100, addToPlan: true })).toEqual({ newBalanceMinor: null, newPlanMinor: null, planAddMinor: 100 });
  });
  it('typing 5x0,000 then + 1,000 gives 51,000', () => {
    expect(groupIndian(addRupees('50000', 1000))).toBe('51,000');
  });
});

describe('tags', () => {
  it('a new tag is lowercase, without #, and becomes a chip once', () => {
    expect(cleanTag(' #Bonus ')).toBe('bonus');
    expect(cleanTag('#')).toBe('');
    expect(withTag(['salary'], 'bonus')).toEqual(['salary', 'bonus']);
    expect(withTag(['salary', 'bonus'], 'bonus')).toEqual(['salary', 'bonus']);
  });
  it('offers only the tags recent credits used, each once', () => {
    expect(creditTags(['salary', 'rent refund', null, 'salary', 'gift'])).toEqual(['salary', 'rent refund', 'gift']);
    expect(creditTags([])).toEqual([]);
  });
});

describe('dates', () => {
  it('resolves the three choices', () => {
    expect(resolveDate('today', '2026-10-18', '2026-10-15')).toBe('2026-10-18');
    expect(resolveDate('yesterday', '2026-10-18', '2026-10-15')).toBe('2026-10-17');
    expect(resolveDate('pick', '2026-10-18', '2026-10-15')).toBe('2026-10-15');
  });
  it('a picked day in the future or empty falls back to today', () => {
    expect(resolveDate('pick', '2026-10-18', '2026-10-19')).toBe('2026-10-18');
    expect(resolveDate('pick', '2026-10-18', '')).toBe('2026-10-18');
  });
  it('yesterday crosses month ends', () => {
    expect(resolveDate('yesterday', '2026-11-01', '')).toBe('2026-10-31');
  });
  it('formats like the design and opens the date box three days back', () => {
    expect(dateText('2026-10-18')).toBe('Oct 18, 2026');
    expect(dateText('2026-10-05')).toBe('Oct 5, 2026');
    expect(defaultPickDate('2026-10-18')).toBe('2026-10-15');
  });
});

describe('request body', () => {
  it('sends paise, the tag, the day and a null note when empty', () => {
    expect(creditBody({ amount: '51000', tag: 'bonus', date: '2026-10-18', note: '  ', addToPlan: true }))
      .toEqual({ amountMinor: 5_100_000, date: '2026-10-18', tag: 'bonus', note: null, addToPlan: true });
    expect(creditBody({ amount: '50000', tag: 'salary', date: '2026-10-01', note: 'October salary', addToPlan: false }).note).toBe('October salary');
  });
});
