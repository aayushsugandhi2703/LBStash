import { compactK, css3, displayTag, formatInr, inr, inrSigned, monthName, monthScale, type Paise, pct, pct1, shortMonth, wholeRupees } from '@/common';
import type { ReportMatrixRes, ReportMonthsRes } from '@/contracts';

/** Trends page view-model: stats, headline, in/out columns with pace, "against a usual month" list. */

type MonthItem = ReportMonthsRes['items'][number];

const signedPct = (ratio: number): string => (ratio < 0 ? `−${pct1(-ratio)}` : pct1(ratio));
/** +8.8K, −1.2K, 0 (compact kept figure under a month name). */
export const keptShort = (p: Paise): string => (p === 0 ? '0' : `${p < 0 ? '−' : '+'}${compactK(Math.abs(p))}`);

/** Finished months with any activity: the months the averages are over (same rule as the server). */
export const fullMonthItems = (m: ReportMonthsRes): MonthItem[] => m.items.filter((i) => !i.inProgress && (i.incomeMinor > 0 || i.spentMinor > 0));

export interface TrendStat { label: string; value: string; note: string; tone: 'credit' | 'plain' }

export function trendStats(m: ReportMonthsRes): TrendStat[] {
  const full = fullMonthItems(m);
  if (m.averages.fullMonths === 0 || full.length === 0) {
    return [
      { label: 'Avg monthly spend', value: '—', note: 'no full month yet', tone: 'plain' },
      { label: 'Avg kept', value: '—', note: 'no full month yet', tone: 'plain' },
      { label: 'Balance since start', value: '—', note: 'no full month yet', tone: 'plain' },
    ];
  }
  const first = shortMonth(full[0]!.month).toLowerCase();
  const last = shortMonth(full[full.length - 1]!.month).toLowerCase();
  const a = m.averages;
  const start = m.items.find((i) => i.month === a.balanceSinceMonth);
  const now = m.items[m.items.length - 1];
  const since = a.balanceSinceMinor;
  return [
    { label: 'Avg monthly spend', value: inr(wholeRupees(a.avgMonthlySpendMinor)), note: full.length === 1 ? `${first}, one full month` : `${first} to ${last}, full months`, tone: 'plain' },
    { label: 'Avg kept', value: signedPct(a.avgKeptRate), note: 'of income, same months', tone: 'credit' },
    {
      label: a.balanceSinceMonth ? `Balance since ${shortMonth(a.balanceSinceMonth)}` : 'Balance since start',
      value: since === 0 ? inr(0) : `${since < 0 ? '−' : '+'}${inr(since)}`,
      note: start && now ? `${formatInr(start.closingMinor)} to ${formatInr(now.closingMinor)}` : '',
      tone: since >= 0 ? 'credit' : 'plain',
    },
  ];
}

/** "You keep about ₹5,940 a month. October is on pace for ₹3,280, below usual." (null before a full month). */
export function headline(m: ReportMonthsRes): string | null {
  const cur = m.items[m.items.length - 1];
  if (m.averages.fullMonths === 0 || !cur?.pace) return null;
  const avg = wholeRupees(m.averages.avgKeptMinor);
  const pace = wholeRupees(cur.pace.paceKeptMinor);
  const diff = pace - avg;
  const verdict = diff < 0 ? 'below usual' : diff > 0 ? 'above usual' : 'a usual month';
  const s1 = avg >= 0 ? `You keep about ${inr(avg)} a month.` : `You spend about ${inr(avg)} more than you earn in a month.`;
  const s2 = pace >= 0 ? `${monthName(cur.month)} is on pace for ${inr(pace)}` : `${monthName(cur.month)} is on pace for ${inr(pace)} short`;
  return `${s1} ${s2}, ${verdict}.`;
}

interface MonthColumn {
  month: string;
  label: string;
  inPct: number;
  outPct: number;
  /** Hatched block on top of the solid money-out bar (month in progress only). */
  pacePct: number;
  keptText: string;
  /** The month has any income or spending; an empty month shows a dash under its name. */
  active: boolean;
  inProgress: boolean;
  tip: { title: string; lines: string[]; kept: string };
  /** Tooltip opens right of the column in the left half, left of it in the right half. */
  tipSide: 'right' | 'left';
}
export interface TrendsChart {
  max: Paise;
  grid: { label: string; topPct: number }[];
  columns: MonthColumn[];
  /** Totals for the chart's aria-label. */
  summary: string;
}

export function trendsChart(m: ReportMonthsRes): TrendsChart {
  const n = m.items.length;
  const peak = Math.max(0, ...m.items.flatMap((i) => [i.incomeMinor, i.spentMinor, i.pace?.paceSpentMinor ?? 0]));
  const scale = monthScale(peak);
  const grid = scale.ticks.map((t, i) => ({ label: compactK(t), topPct: css3((i / 3) * 100) }));
  const columns = m.items.map((i, idx): MonthColumn => {
    const year = i.month.slice(0, 4);
    const base = `${shortMonth(i.month)} ${year}`;
    const active = i.incomeMinor > 0 || i.spentMinor > 0;
    const pace = i.inProgress ? i.pace : null;
    const out = `out ${inr(i.spentMinor)}${i.inProgress ? ' so far' : ''}`;
    const kept = pace ? `heading for ${inrSigned(pace.paceKeptMinor)} kept` : `kept ${inrSigned(i.keptMinor)} · ${signedPct(i.keptRate)}`;
    return {
      month: i.month,
      label: shortMonth(i.month),
      inPct: css3(pct(i.incomeMinor, scale.max)),
      outPct: css3(pct(i.spentMinor, scale.max)),
      pacePct: pace ? css3(pct(Math.max(0, pace.paceSpentMinor - i.spentMinor), scale.max)) : 0,
      keptText: !active ? '—' : pace ? `${keptShort(pace.paceKeptMinor)} pace` : keptShort(i.keptMinor),
      active,
      inProgress: i.inProgress,
      tip: {
        title: i.inProgress && pace ? `${base} · day ${pace.dayOfMonth}` : base,
        lines: active ? [`in ${inr(i.incomeMinor)}`, out] : ['nothing recorded'],
        kept: active ? kept : '',
      },
      tipSide: idx < n / 2 ? 'right' : 'left',
    };
  });
  const cur = m.items[n - 1];
  const summary = `Money in and out for ${n} months. ` + m.items.map((i) => `${shortMonth(i.month)}: in ${inr(i.incomeMinor)}, out ${inr(i.spentMinor)}${i.inProgress && i.pace ? ` so far, ${inr(i.pace.paceSpentMinor)} at this pace` : ''}`).join('; ') + (cur ? '.' : '');
  return { max: scale.max, grid, columns, summary };
}

interface UsualRow { id: string; name: string; usually: string; heading: string; change: string; dir: 'more' | 'less' | 'same' }

/** At most `limit` rows: the biggest movers, shown from most above usual to most below. */
export function usualRows(mx: ReportMatrixRes, limit = 4): UsualRow[] {
  const rows = mx.items.map((it) => {
    const usual = wholeRupees(it.usualMinor);
    const pace = wholeRupees(it.paceMinor);
    const d = pace - usual;
    return {
      d, id: it.categoryId, name: displayTag(it.name),
      usually: usual === 0 ? 'usually —' : `usually ${inr(usual)}`,
      heading: `heading for ${inr(pace)}`,
      change: d === 0 ? 'the same as usual' : `${d > 0 ? '▲' : '▼'} ${inr(d)} ${d > 0 ? 'more' : 'less'}`,
      dir: d === 0 ? ('same' as const) : d > 0 ? ('more' as const) : ('less' as const),
    };
  });
  const picked = rows.length > limit ? [...rows].sort((a, b) => Math.abs(b.d) - Math.abs(a.d)).slice(0, limit) : rows;
  return picked.sort((a, b) => b.d - a.d).map(({ d: _d, ...r }) => r);
}
