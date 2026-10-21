import { describe, expect, it } from 'vitest';
import type { BudgetDto, RecurringRuleDto } from '@/contracts';
import {
  categoryRows, dailyRates, endStat, flexibleEnd, flexibleLines, forecast, forecastChart, type ForecastInput, limitsById, repeatsLeft, roundTen, runOut, runOutStat, verdictText,
} from '@/features/forecast';

const R = (n: number) => n * 100;

// October, day 21 of 31. Flexible spending so far ₹26,300; the last 7 days ₹11,270; the calmest 7 days ₹6,160.
const DAILY = [1220, 900, 1400, 700, 1250, 1900, 1500, 800, 700, 1100, 600, 850, 1300, 810, 1700, 1550, 1543, 1800, 1452, 2619, 606].map(R);
const FUTURE = Array<number>(10).fill(0);
const input = (over: Partial<ForecastInput> = {}): ForecastInput => ({
  month: '2026-10', dayOfMonth: 21, daysInMonth: 31, dailyMinor: [...DAILY, ...FUTURE],
  planFlexMinor: R(36000), spentSoFarMinor: R(50949), availableMinor: R(40251), repeatsLeftMinor: R(17680), ...over,
});

const rule = (over: Partial<RecurringRuleDto>): RecurringRuleDto => ({
  id: 'r', name: 'Gym', categoryId: 'c', categoryName: 'gym', amountMinor: R(1500), schedule: { kind: 'monthly', day: 25 }, nextDue: '2026-10-25',
  paused: false, endsOn: null, note: null, matchHint: null, active: true, ...over,
});

describe('rates', () => {
  it('gives the month average, the last 7 days and the calmest 7 days', () => {
    const r = dailyRates(DAILY, 21);
    expect(r.average).toBeCloseTo(R(26300) / 21, 5);
    expect(r.last7).toBeCloseTo(R(11270) / 7, 5);
    expect(r.best7).toBeCloseTo(R(6160) / 7, 5);
  });
  it('uses the average until a week has passed', () => {
    const r = dailyRates([R(1000), R(2000), R(3000)], 3);
    expect(r).toEqual({ average: R(2000), last7: R(2000), best7: R(2000) });
  });
  it('is zero before anything is spent', () => {
    expect(dailyRates([], 0)).toEqual({ average: 0, last7: 0, best7: 0 });
    expect(dailyRates([0, 0, 0], 3).average).toBe(0);
  });
});

describe('end of month', () => {
  it('rounds to ₹10', () => {
    expect(roundTen(R(38823.8))).toBe(R(38820));
    expect(flexibleEnd(R(26300), R(1253), 10)).toBe(R(38830));
  });
  it('stays at what is spent on the last day', () => {
    expect(flexibleEnd(R(26300), R(1253), 0)).toBe(R(26300));
  });
});

describe('runOut', () => {
  const base = { planMinor: R(36000), spentMinor: R(26300), rateMinor: R(1253), dayOfMonth: 21, daysInMonth: 31 };
  it('names the day the plan is used up', () => {
    expect(runOut(base)).toEqual({ kind: 'day', day: 29, daysEarly: 2 });
  });
  it('is exact on a whole number of days', () => {
    expect(runOut({ ...base, planMinor: R(4500), spentMinor: R(3150), rateMinor: R(150) })).toEqual({ kind: 'day', day: 30, daysEarly: 1 });
  });
  it('says inside when the plan lasts, over when it is spent, noplan without one', () => {
    expect(runOut({ ...base, rateMinor: R(500) })).toEqual({ kind: 'inside' });
    expect(runOut({ ...base, rateMinor: 0 })).toEqual({ kind: 'inside' });
    expect(runOut({ ...base, spentMinor: R(36000) })).toEqual({ kind: 'over' });
    expect(runOut({ ...base, planMinor: 0 })).toEqual({ kind: 'noplan' });
  });
});

describe('repeatsLeft', () => {
  const rules = [
    rule({ id: 'gym' }),
    rule({ id: 'net', name: 'Internet', amountMinor: R(1180), nextDue: '2026-10-27', schedule: { kind: 'monthly', day: 27 } }),
    rule({ id: 'sip', name: 'SIP', amountMinor: R(15000), nextDue: '2026-10-28', schedule: { kind: 'monthly', day: 28 } }),
    rule({ id: 'rent', name: 'Rent', amountMinor: R(24000), nextDue: '2026-11-05', schedule: { kind: 'monthly', day: 5 } }),
  ];
  it('adds what is due from today to the month end', () => {
    const left = repeatsLeft(rules, '2026-10-21', 10);
    expect(left.items.map((i) => i.name)).toEqual(['Gym', 'Internet', 'SIP']);
    expect(left.totalMinor).toBe(R(17680));
  });
  it('counts a payment due today, skips paused and ended ones, and counts a weekly rule each time', () => {
    const left = repeatsLeft([
      rule({ id: 'a', name: 'Due today', nextDue: '2026-10-21', amountMinor: R(100) }),
      rule({ id: 'b', name: 'Paused', paused: true }),
      rule({ id: 'c', name: 'Ended', active: false }),
      rule({ id: 'd', name: 'Weekly', amountMinor: R(10), nextDue: '2026-10-23', schedule: { kind: 'weekly', weekday: 5 } }),
    ], '2026-10-21', 10);
    expect(left.items.map((i) => i.name)).toEqual(['Due today', 'Weekly', 'Weekly']);
    expect(left.totalMinor).toBe(R(120));
  });
  it('is empty on the last day when nothing is due', () => {
    expect(repeatsLeft(rules, '2026-10-31', 0)).toEqual({ items: [], totalMinor: 0 });
  });
});

describe('forecast', () => {
  const f = forecast(input());
  it('orders the three paces slowest first and keeps the month pace as the expected one', () => {
    expect(f.scenarios.map((s) => s.key)).toEqual(['best', 'month', 'recent']);
    expect(f.expected.key).toBe('month');
    expect(f.low.key).toBe('best');
    expect(f.high.key).toBe('recent');
    expect(f.hasRange).toBe(true);
  });
  it('adds so far, flexible to come and repeats to come', () => {
    expect(f.flexSpentMinor).toBe(R(26300));
    expect(f.expected.flexEndMinor).toBe(R(38820));
    expect(f.expected.flexLeftMinor).toBe(R(12520));
    expect(f.expected.spentEndMinor).toBe(R(50949 + 12520 + 17680));
    expect(f.expected.balanceEndMinor).toBe(R(40251 - 12520 - 17680));
    expect(f.high.balanceEndMinor).toBeLessThan(f.expected.balanceEndMinor);
    expect(f.low.balanceEndMinor).toBeGreaterThan(f.expected.balanceEndMinor);
  });
  it('finds the run-out day for each pace, the faster the earlier', () => {
    expect(f.expected.runOut).toEqual({ kind: 'day', day: 29, daysEarly: 2 });
    const fast = f.high.runOut;
    expect(fast.kind === 'day' && fast.day).toBeLessThan(29);
    expect(f.low.runOut).toEqual({ kind: 'inside' });
  });
  it('gives a safe daily figure rounded down to ₹10', () => {
    expect(f.safePerDayMinor).toBe(R(880));
    expect(f.spendingNowMinor).toBe(R(1250));
  });
  it('writes the headline', () => {
    expect(f.headline).toBe('On pace for ₹38,820, ₹2,820 over your ₹36,000 plan. It runs out Oct 29.');
  });
  it('writes the aside figures', () => {
    expect(runOutStat(f, '2026-10')).toEqual({ value: 'Oct 29', note: '2 days before month end', tone: 'bad' });
    expect(endStat(f).value).toBe('₹10,050');
    expect(endStat(f).note).toMatch(/^₹[\d,]+ to ₹[\d,]+$/);
  });

  it('says it stays inside the plan when it does', () => {
    const calm = forecast(input({ planFlexMinor: R(50000) }));
    expect(calm.headline).toBe('On pace for ₹38,820, ₹11,180 under your ₹50,000 plan.');
    expect(runOutStat(calm, '2026-10').value).toBe('Not this month');
  });
  it('says the plan has run out when it is spent', () => {
    const spent = forecast(input({ planFlexMinor: R(20000) }));
    expect(spent.expected.runOut).toEqual({ kind: 'over' });
    expect(spent.headline).toContain('The plan is already spent.');
    expect(spent.safePerDayMinor).toBe(0);
  });
  it('works without a plan', () => {
    const none = forecast(input({ planFlexMinor: 0 }));
    expect(none.safePerDayMinor).toBeNull();
    expect(none.headline).toBe('On pace for ₹38,820. Set a plan in Budget to see when it runs out.');
    expect(runOutStat(none, '2026-10').value).toBe('—');
  });
  it('is honest before anything is spent', () => {
    const empty = forecast(input({ dailyMinor: Array<number>(31).fill(0), spentSoFarMinor: 0 }));
    expect(empty.empty).toBe(true);
    expect(empty.headline).toContain('Nothing spent yet');
    expect(JSON.stringify(empty)).not.toMatch(/NaN|null.*Infinity/);
  });
  it('copes with day 1', () => {
    const day1 = forecast(input({ dayOfMonth: 1, dailyMinor: [R(500), ...Array<number>(30).fill(0)], spentSoFarMinor: R(500) }));
    expect(day1.hasRange).toBe(false);
    expect(day1.expected.flexEndMinor).toBe(R(15500));
    expect(Number.isFinite(day1.expected.balanceEndMinor)).toBe(true);
  });
  it('shows the result on the last day, not a projection', () => {
    const last = forecast(input({ dayOfMonth: 31, dailyMinor: [...DAILY, ...Array<number>(10).fill(R(100))], repeatsLeftMinor: 0 }));
    expect(last.daysLeft).toBe(0);
    expect(last.hasRange).toBe(false);
    expect(last.headline).toBe('October ends with ₹27,300 spent of a ₹36,000 plan.');
  });
});

const line = (id: string, categoryName: string, allocated: number, spent: number) => ({ categoryId: id, categoryName, allocatedMinor: R(allocated), spentMinor: R(spent) });
const LINES = [
  line('shop', 'shopping', 7000, 6420), line('fun', 'fun', 5500, 4280), line('food', 'food', 14000, 9870), line('tr', 'transport', 4500, 3150),
  line('oth', 'other', 2500, 1400), line('hl', 'health', 2500, 1180), line('rent', 'rent', 24000, 24000),
];
const budget = (categoryId: string, limit: number, active = true): BudgetDto => ({ id: `b-${categoryId}`, categoryId, categoryName: '', limitMinor: R(limit), period: 'monthly', warnPct: null, active, spentMinor: 0, pct: 0, projectedMinor: 0, status: 'ok' });

describe('categories', () => {
  it('leaves out the categories that are repeats', () => {
    expect(flexibleLines(LINES, ['Rent']).map((l) => l.categoryId)).not.toContain('rent');
  });
  it('lists the active limits by category', () => {
    const m = limitsById([budget('shop', 7000), budget('fun', 5500), budget('food', 14000, false), budget('tr', 0)]);
    expect([...m.keys()]).toEqual(['shop', 'fun']);
  });
  const rows = categoryRows(flexibleLines(LINES, ['Rent']), limitsById([budget('shop', 7000), budget('fun', 5500), budget('food', 14000)]), 21, 31);
  it('puts the category that breaks first on top', () => {
    expect(rows.map((r) => r.name)).toEqual(['Shopping', 'Fun', 'Food', 'Transport', 'Health', 'Other']);
  });
  it('finds the day each one reaches its limit, or its plan when it has no limit', () => {
    const by = Object.fromEntries(rows.map((r) => [r.name, r]));
    expect(by.Shopping).toMatchObject({ verdict: 'limit', day: 23, daysAway: 2, kind: 'limit', projectedMinor: R(9480) });
    expect(by.Fun).toMatchObject({ verdict: 'limit', day: 27, daysAway: 6 });
    expect(by.Food).toMatchObject({ verdict: 'limit', day: 30, daysAway: 9 });
    expect(by.Transport).toMatchObject({ verdict: 'plan', day: 30, kind: 'plan' });
    expect(by.Health).toMatchObject({ verdict: 'inside', day: null, daysAway: null });
  });
  it('draws the line at 70% of the bar', () => {
    const shop = rows[0]!;
    expect(shop.spentPct).toBeCloseTo((6420 / 7000) * 70, 5);
    expect(shop.projectedPct).toBeLessThanOrEqual(100);
  });
  it('puts a category that is already past its line first', () => {
    const over = categoryRows([line('a', 'fun', 1000, 1500), line('b', 'food', 1000, 100)], new Map(), 10, 30);
    expect(over[0]).toMatchObject({ name: 'Fun', verdict: 'over', daysAway: 0 });
  });
  it('skips a category with no plan and no spending, and copes with day 0', () => {
    expect(categoryRows([line('a', 'misc', 0, 0)], new Map(), 21, 31)).toEqual([]);
    const r = categoryRows([line('a', 'fun', 1000, 0)], new Map(), 0, 31);
    expect(r[0]).toMatchObject({ verdict: 'inside', projectedMinor: 0 });
  });
  it('words each verdict', () => {
    expect(verdictText(rows[0]!, '2026-10')).toEqual({ text: 'Limit hit Oct 23', when: 'in 2 days' });
    expect(verdictText(rows[3]!, '2026-10')).toEqual({ text: 'Plan reached Oct 30', when: 'in 9 days' });
    expect(verdictText(rows[4]!, '2026-10')).toEqual({ text: 'Stays inside the plan', when: '' });
  });
});

describe('chart', () => {
  const i = input();
  const f = forecast(i);
  const c = forecastChart(i, f);
  it('has finite geometry', () => {
    const all = [c.actual, c.band, c.expected, c.low, c.high].join(' ');
    expect(all).not.toMatch(/NaN|Infinity/);
    expect(c.actual.startsWith('M52.0')).toBe(true);
    expect(c.todayX).toBeGreaterThan(52);
    expect(c.todayX).toBeLessThan(800);
  });
  it('marks where the plan runs out, on the plan line, left of the month end', () => {
    expect(c.runOut).not.toBeNull();
    expect(c.runOut!.y).toBe(c.planY);
    expect(c.runOut!.x).toBeGreaterThan(c.todayX);
    expect(c.runOut!.x).toBeLessThan(800);
    expect(c.runOut!.label).toBe('plan runs out Oct 29');
    expect(c.early?.label).toMatch(/at the faster pace$/);
  });
  it('labels the three end points without overlap', () => {
    expect(c.ends.map((e) => e.label)).toEqual(['₹42,400 last 7 days', '₹38,820 this month', '₹35,100 best week']);
    for (let k = 1; k < c.ends.length; k++) expect(c.ends[k]!.y - c.ends[k - 1]!.y).toBeGreaterThanOrEqual(17);
    expect(c.ends.filter((e) => e.strong)).toHaveLength(1);
  });
  it('has axis labels with today lit', () => {
    expect(c.yTicks[0]).toMatchObject({ label: '0' });
    expect(c.xTicks.filter((t) => t.today).map((t) => t.label)).toEqual(['21']);
    expect(c.summary).toContain('₹26,300 by day 21');
  });
  it('draws no projection on the last day and no range inside the first week', () => {
    const last = forecastChart(input({ dayOfMonth: 31 }), forecast(input({ dayOfMonth: 31 })));
    expect(last.expected).toBe('');
    expect(last.ends).toEqual([]);
    const early = input({ dayOfMonth: 3, dailyMinor: [R(100), R(200), R(300), ...Array<number>(28).fill(0)] });
    const e = forecastChart(early, forecast(early));
    expect(e.band).toBe('');
    expect(e.ends).toHaveLength(1);
  });
  it('has no plan line without a plan', () => {
    const none = input({ planFlexMinor: 0 });
    const n = forecastChart(none, forecast(none));
    expect(n.planY).toBeNull();
    expect(n.runOut).toBeNull();
  });
});
