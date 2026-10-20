import { describe, expect, it } from 'vitest';
import type { ReportMatrixRes, ReportMonthsRes } from '@/contracts';
import { fullMonthItems, headline, keptShort, trendsChart, trendStats, usualRows } from '@/features/trends';

const R = (n: number) => n * 100;

// ui-spec §6 six months; October is day 18: 39,709 so far, 46,720 at pace, 3,280 kept at pace.
const row = (month: string, inc: number, spent: number, closing: number) => ({
  month, incomeMinor: R(inc), spentMinor: R(spent), keptMinor: R(inc - spent), keptRate: inc ? (inc - spent) / inc : 0,
  closingMinor: R(closing), inProgress: false, pace: null,
});
const months = (over: Partial<ReportMonthsRes> = {}): ReportMonthsRes => ({
  end: '2026-10',
  items: [
    row('2026-05', 50000, 41200, 6400), row('2026-06', 50000, 44800, 11600), row('2026-07', 52000, 47300, 16300),
    row('2026-08', 50000, 43100, 23200), row('2026-09', 50000, 45900, 27300),
    {
      ...row('2026-10', 50000, 39709, 37591), inProgress: true,
      pace: { dayOfMonth: 18, daysInMonth: 31, spentSoFarMinor: R(39709), flexibleSoFarMinor: R(9709), fixedMinor: R(30000), flexiblePaceMinor: R(16720), paceSpentMinor: R(46720), paceKeptMinor: R(3280) },
    },
  ],
  averages: { fullMonths: 5, avgMonthlySpendMinor: R(44460), avgKeptMinor: R(5940), avgKeptRate: 29700 / 252000, balanceSinceMinor: R(31191), balanceSinceMonth: '2026-05' },
  ...over,
});

describe('stats and headline', () => {
  it('shows the three aside figures', () => {
    expect(trendStats(months())).toEqual([
      { label: 'Avg monthly spend', value: '₹44,460', note: 'may to sep, full months', tone: 'plain' },
      { label: 'Avg kept', value: '11.8%', note: 'of income, same months', tone: 'credit' },
      { label: 'Balance since May', value: '+₹31,191', note: '6,400 to 37,591', tone: 'credit' },
    ]);
  });
  it('shows dashes with the reason before a full month', () => {
    const empty = months({
      items: [{ ...months().items[5]!, closingMinor: 0 }],
      averages: { fullMonths: 0, avgMonthlySpendMinor: 0, avgKeptMinor: 0, avgKeptRate: 0, balanceSinceMinor: 0, balanceSinceMonth: null },
    });
    const s = trendStats(empty);
    expect(s.map((x) => x.value)).toEqual(['—', '—', '—']);
    expect(s[0]!.note).toBe('no full month yet');
    expect(headline(empty)).toBeNull();
  });
  it('a negative balance change is ink with a true minus', () => {
    const s = trendStats(months({ averages: { ...months().averages, balanceSinceMinor: R(-500) } }));
    expect(s[2]).toMatchObject({ value: '−₹500', tone: 'plain' });
  });
  it('headline: tighter month than usual', () => {
    expect(headline(months())).toBe('You keep about ₹5,940 a month. October is heading for ₹3,280, a tighter month than usual.');
  });
  it('headline: better month when the pace beats the average', () => {
    const m = months();
    m.items[5] = { ...m.items[5]!, pace: { ...m.items[5]!.pace!, paceKeptMinor: R(7000) } };
    expect(headline(m)).toContain('a better month than usual.');
  });
  it('headline: handles a short month', () => {
    const m = months();
    m.items[5] = { ...m.items[5]!, pace: { ...m.items[5]!.pace!, paceKeptMinor: R(-400) } };
    expect(headline(m)).toContain('October is heading for ₹400 short, a tighter month than usual.');
  });
  it('counts only finished months with activity', () => {
    expect(fullMonthItems(months()).map((i) => i.month)).toEqual(['2026-05', '2026-06', '2026-07', '2026-08', '2026-09']);
  });
});

describe('chart', () => {
  const c = trendsChart(months());
  it('uses 60K with gridlines at 60K, 40K, 20K', () => {
    expect(c.max).toBe(R(60000));
    expect(c.grid).toEqual([{ label: '60K', topPct: 0 }, { label: '40K', topPct: 33.333 }, { label: '20K', topPct: 66.667 }]);
  });
  it('sizes bars as value / 60,000', () => {
    expect(c.columns).toHaveLength(6);
    expect(c.columns[0]).toMatchObject({ label: 'May', inPct: 83.333, outPct: 68.667, pacePct: 0, keptText: '+8.8K' });
    expect(c.columns.map((x) => x.keptText)).toEqual(['+8.8K', '+5.2K', '+4.7K', '+6.9K', '+4.1K', '+3.3K pace']);
  });
  it('October: solid to 39,709 and a hatched block up to 46,720', () => {
    const oct = c.columns[5]!;
    expect(oct.outPct).toBeCloseTo((39709 / 60000) * 100, 2);
    expect(oct.pacePct).toBeCloseTo(((46720 - 39709) / 60000) * 100, 2);
    expect(oct.outPct + oct.pacePct).toBeCloseTo((46720 / 60000) * 100, 2);
    expect(oct.inProgress).toBe(true);
  });
  it('tooltip text for a finished month and for the month in progress', () => {
    expect(c.columns[0]!.tip).toEqual({ title: 'May 2026', lines: ['in ₹50,000', 'out ₹41,200'], kept: 'kept ₹8,800 · 17.6%' });
    expect(c.columns[5]!.tip).toEqual({ title: 'Oct 2026 · day 18', lines: ['in ₹50,000', 'out ₹39,709 so far'], kept: 'heading for ₹3,280 kept' });
  });
  it('opens the tooltip right for the left half and left for the right half', () => {
    expect(c.columns.map((x) => x.tipSide)).toEqual(['right', 'right', 'right', 'left', 'left', 'left']);
  });
  it('states the totals for assistive tech', () => {
    expect(c.summary).toContain('May: in ₹50,000, out ₹41,200');
    expect(c.summary).toContain('Oct: in ₹50,000, out ₹39,709 so far, ₹46,720 at this pace');
  });
  it('rescales for bigger months and marks quiet months', () => {
    const m = months();
    m.items[1] = { ...m.items[1]!, incomeMinor: R(80000) };
    m.items[2] = row('2026-07', 0, 0, 16300);
    const big = trendsChart(m);
    expect(big.max).toBe(R(150000));
    expect(big.columns[2]).toMatchObject({ keptText: '—', active: false, tip: { lines: ['nothing recorded'], kept: '' } });
  });
  it('keptShort signs and compacts', () => {
    expect([keptShort(R(8800)), keptShort(R(-1200)), keptShort(0), keptShort(R(3280))]).toEqual(['+8.8K', '−1.2K', '0', '+3.3K']);
  });
});

const item = (name: string, usual: number, pace: number): ReportMatrixRes['items'][number] => ({
  categoryId: `00000000-0000-4000-8000-${name.length.toString().padStart(12, '0')}`, name, byMonth: [],
  usualMinor: R(usual), spentSoFarMinor: 0, paceMinor: R(pace), changeMinor: R(pace - usual),
});
const matrix = (items: ReportMatrixRes['items']): ReportMatrixRes => ({ end: '2026-10', months: [], fullMonths: 5, dayOfMonth: 18, daysInMonth: 31, items });

describe('October against a usual month', () => {
  it('lists Food, Fun, Bills, Travel with the spec figures', () => {
    const rows = usualRows(matrix([item('food', 7590, 9330), item('fun', 1430, 2820), item('bills', 2500, 2240), item('travel', 2940, 2330)]));
    expect(rows.map((r) => [r.name, r.usually, r.heading, r.change])).toEqual([
      ['Food', 'usually ₹7,590', 'heading for ₹9,330', '▲ ₹1,740 more'],
      ['Fun', 'usually ₹1,430', 'heading for ₹2,820', '▲ ₹1,390 more'],
      ['Bills', 'usually ₹2,500', 'heading for ₹2,240', '▼ ₹260 less'],
      ['Travel', 'usually ₹2,940', 'heading for ₹2,330', '▼ ₹610 less'],
    ]);
  });
  it('sorts from most above to most below even if the input is not sorted', () => {
    const rows = usualRows(matrix([item('travel', 2940, 2330), item('food', 7590, 9330), item('bills', 2500, 2240)]));
    expect(rows.map((r) => r.name)).toEqual(['Food', 'Bills', 'Travel']);
  });
  it('keeps the four biggest movers when there are more', () => {
    const rows = usualRows(matrix([item('a', 100, 110), item('b', 100, 300), item('c', 500, 100), item('d', 100, 90), item('e', 100, 150), item('f', 1000, 100)]));
    expect(rows.map((r) => r.name)).toEqual(['B', 'E', 'C', 'F']);
  });
  it('handles no change and no history', () => {
    const [fresh, same] = usualRows(matrix([item('rent', 100, 100), item('new', 0, 50)]));
    expect(fresh).toMatchObject({ name: 'New', usually: 'usually —', change: '▲ ₹50 more', dir: 'more' });
    expect(same).toMatchObject({ change: 'the same as usual', dir: 'same' });
  });
});
