import { compactK, displayTag, inr, inrSigned, joinPlain, type LeadPart, leadText, monthName, monthScale, type Paise, shortMonth } from '@/common';
import type { BudgetDto, ReportDailyRes, RecurringRuleDto } from '@/contracts';
import { axisDays } from './now';
import type { PlanResponse } from './plan';
import { isOn, occurrences } from './repeats';

/** Forecast page logic. Pure. "Flexible" = every category that is not one of the user's repeats (Rent, SIP, ...); all money is paise. */

const WEEK = 7;
const TEN_RUPEES = 1_000;
/** Same rounding as the server's month pace. */
export const roundTen = (p: Paise): Paise => Math.round(p / TEN_RUPEES) * TEN_RUPEES;
const floorTen = (p: Paise): Paise => Math.floor(p / TEN_RUPEES) * TEN_RUPEES;
const sum = (xs: readonly number[]): number => xs.reduce((t, x) => t + x, 0);
/** A whole-day count that ignores float dust (4.0000000001 is 4, not 5). */
const ceilDay = (x: number): number => Math.ceil(x - 1e-9);

export interface Rates { average: Paise; last7: Paise; best7: Paise }

/** Paise a day: the month so far, the last 7 days, and the calmest 7 days. Under 7 days of data all three are the average. */
export function dailyRates(daily: readonly Paise[], dayOfMonth: number): Rates {
  const days = daily.slice(0, Math.max(0, dayOfMonth));
  if (days.length === 0) return { average: 0, last7: 0, best7: 0 };
  const average = sum(days) / days.length;
  if (days.length < WEEK) return { average, last7: average, best7: average };
  let window = sum(days.slice(0, WEEK));
  let best = window;
  for (let i = WEEK; i < days.length; i++) {
    window += days[i]! - days[i - WEEK]!;
    best = Math.min(best, window);
  }
  return { average, last7: window / WEEK, best7: best / WEEK };
}

/** Flexible spending at the month's end if every remaining day costs `rate`. */
export const flexibleEnd = (spent: Paise, rate: Paise, daysLeft: number): Paise => roundTen(spent + rate * daysLeft);

export type RunOut = { kind: 'noplan' | 'inside' | 'over' } | { kind: 'day'; day: number; daysEarly: number };

/** The day the flexible plan is used up at `rate`: 'inside' if it lasts the month, 'over' if it is already spent. */
export function runOut(p: { planMinor: Paise; spentMinor: Paise; rateMinor: Paise; dayOfMonth: number; daysInMonth: number }): RunOut {
  if (p.planMinor <= 0) return { kind: 'noplan' };
  if (p.spentMinor >= p.planMinor) return { kind: 'over' };
  if (p.rateMinor <= 0) return { kind: 'inside' };
  const day = ceilDay(p.dayOfMonth + (p.planMinor - p.spentMinor) / p.rateMinor);
  return day > p.daysInMonth ? { kind: 'inside' } : { kind: 'day', day, daysEarly: p.daysInMonth - day };
}

export interface RepeatLeft { name: string; date: string; amountMinor: Paise }

/** Repeats still to leave before the month ends: running rules due from today (included) through `daysLeft` days on. */
export function repeatsLeft(rules: readonly RecurringRuleDto[], today: string, daysLeft: number): { items: RepeatLeft[]; totalMinor: Paise } {
  const items = rules.filter(isOn)
    .flatMap((r) => occurrences(r, today, Math.max(0, daysLeft)).map((date) => ({ name: r.name, date, amountMinor: r.amountMinor })))
    .sort((a, b) => a.date.localeCompare(b.date) || a.name.localeCompare(b.name));
  return { items, totalMinor: sum(items.map((i) => i.amountMinor)) };
}

export interface ForecastInput {
  month: string;
  dayOfMonth: number;
  daysInMonth: number;
  /** Flexible spend per day, day 1 first (the API sends the whole month, future days 0). */
  dailyMinor: readonly Paise[];
  /** Sum of the plan lines that are not repeats. 0 = no plan. */
  planFlexMinor: Paise;
  /** Everything spent so far this month, repeats included. */
  spentSoFarMinor: Paise;
  availableMinor: Paise;
  repeatsLeftMinor: Paise;
}

export type PaceKey = 'best' | 'month' | 'recent';
const PACE_LABEL: Record<PaceKey, string> = { best: 'Best week', month: 'This month', recent: 'Last 7 days' };
const PACE_SHORT: Record<PaceKey, string> = { best: 'best week', month: 'this month', recent: 'last 7 days' };

export interface Scenario {
  key: PaceKey;
  label: string;
  ratePerDay: Paise;
  flexEndMinor: Paise;
  /** Flexible spending still to come (end − so far). */
  flexLeftMinor: Paise;
  /** Everything spent in the month: so far + flexible to come + repeats to come. */
  spentEndMinor: Paise;
  balanceEndMinor: Paise;
  runOut: RunOut;
}

export interface Forecast {
  flexSpentMinor: Paise;
  daysLeft: number;
  rates: Rates;
  /** Slowest pace first. */
  scenarios: Scenario[];
  expected: Scenario;
  low: Scenario;
  high: Scenario;
  /** The three paces differ enough to draw a range (needs a week of data). */
  hasRange: boolean;
  /** Plan left ÷ days left including today, rounded down to ₹10; null without a plan. */
  safePerDayMinor: Paise | null;
  spendingNowMinor: Paise;
  /** No flexible spending yet: nothing to project. */
  empty: boolean;
  /** The sentence above the chart, with its figures marked for bold. */
  lead: LeadPart[];
  headline: string;
}

export function forecast(i: ForecastInput): Forecast {
  const flexSpentMinor = sum(i.dailyMinor.slice(0, Math.max(0, i.dayOfMonth)));
  const daysLeft = Math.max(0, i.daysInMonth - i.dayOfMonth);
  const rates = dailyRates(i.dailyMinor, i.dayOfMonth);
  const make = (key: PaceKey, rate: Paise): Scenario => {
    const flexEndMinor = flexibleEnd(flexSpentMinor, rate, daysLeft);
    const flexLeftMinor = flexEndMinor - flexSpentMinor;
    const spentEndMinor = i.spentSoFarMinor + flexLeftMinor + i.repeatsLeftMinor;
    return {
      key, label: PACE_LABEL[key], ratePerDay: rate, flexEndMinor, flexLeftMinor, spentEndMinor,
      balanceEndMinor: i.availableMinor - flexLeftMinor - i.repeatsLeftMinor,
      runOut: runOut({ planMinor: i.planFlexMinor, spentMinor: flexSpentMinor, rateMinor: rate, dayOfMonth: i.dayOfMonth, daysInMonth: i.daysInMonth }),
    };
  };
  const all = [make('best', rates.best7), make('month', rates.average), make('recent', rates.last7)];
  const scenarios = [...all].sort((a, b) => a.ratePerDay - b.ratePerDay);
  const expected = all[1]!;
  const low = scenarios[0]!;
  const high = scenarios[scenarios.length - 1]!;
  const hasRange = i.dayOfMonth >= WEEK && high.ratePerDay - low.ratePerDay > 0 && daysLeft > 0;
  const planLeft = i.planFlexMinor - flexSpentMinor;
  const safePerDayMinor = i.planFlexMinor <= 0 ? null : planLeft <= 0 ? 0 : floorTen(planLeft / Math.max(1, daysLeft + 1));
  const empty = flexSpentMinor <= 0;
  const f = { flexSpentMinor, daysLeft, rates, scenarios, expected, low, high, hasRange, safePerDayMinor, spendingNowMinor: roundTen(rates.average), empty };
  const lead = leadParts(i, f);
  return { ...f, lead, headline: leadText(lead) };
}

/** "Oct 29" for a day of the month. */
export const dayLabel = (month: string, day: number): string => `${shortMonth(month)} ${day}`;

/** The sentence above the chart. */
function leadParts(i: ForecastInput, f: Pick<Forecast, 'flexSpentMinor' | 'daysLeft' | 'expected' | 'empty'>): LeadPart[] {
  if (f.empty) return ['Nothing spent yet. Log a payment in Telegram to see the forecast.'];
  const end = f.expected.flexEndMinor;
  if (f.daysLeft === 0) {
    const base = `${monthName(i.month)} ends with ${inr(f.flexSpentMinor)} spent`;
    return [i.planFlexMinor > 0 ? `${base} of a ${inr(i.planFlexMinor)} plan.` : `${base}.`];
  }
  const first: LeadPart[] = ['At this pace you will spend ', { b: inr(end) }, '.'];
  if (i.planFlexMinor <= 0) return [...first, ' Set a plan in Budget to see when it runs out.'];
  const diff = end - i.planFlexMinor;
  const plan = ` your ${inr(i.planFlexMinor)} plan.`;
  const vs: LeadPart[] = diff > 0 ? [' That is ', { b: `${inr(diff)} over`, bad: true }, plan] : diff < 0 ? [' That is ', { b: `${inr(-diff)} under` }, plan] : [' That is exactly on', plan];
  return f.expected.runOut.kind === 'over' ? [...first, ...vs, ' The plan is already spent.'] : [...first, ...vs];
}

type RunOutDay = Extract<RunOut, { kind: 'day' }>;
const isDay = (r: RunOut): r is RunOutDay => r.kind === 'day';

/** Aside figure for the run-out date. */
export function runOutStat(f: Forecast, month: string): { value: string; note: string; tone: 'bad' | 'plain' } {
  const r = f.expected.runOut;
  if (r.kind === 'noplan') return { value: '—', note: 'no plan set', tone: 'plain' };
  if (r.kind === 'over') return { value: 'Now', note: 'plan is spent', tone: 'bad' };
  if (!isDay(r)) return { value: 'Not this month', note: 'plan lasts', tone: 'plain' };
  return { value: dayLabel(month, r.day), note: r.daysEarly === 0 ? 'on the last day' : `${r.daysEarly} ${r.daysEarly === 1 ? 'day' : 'days'} early`, tone: 'bad' };
}

/** Aside figure for the balance on the last day: "₹10,040 at this pace". */
export const endStat = (f: Forecast): { value: string; note: string } => ({ value: inrSigned(roundTen(f.expected.balanceEndMinor)), note: 'at this pace' });

export interface CategoryRow {
  id: string;
  name: string;
  spentMinor: Paise;
  planMinor: Paise;
  /** The line the bar is drawn against: the limit when there is one, else the plan. */
  lineMinor: Paise;
  kind: 'limit' | 'plan';
  projectedMinor: Paise;
  /** 'over' = already at or past the line. */
  verdict: 'over' | 'limit' | 'plan' | 'inside';
  /** Day of the month the line is reached (null when inside or already over). */
  day: number | null;
  daysAway: number | null;
  /** Bar fills in % of the track, the line itself sits at LINE_AT. */
  spentPct: number;
  projectedPct: number;
}
/** Where the plan/limit tick sits on a category bar. */
export const LINE_AT = 70;

export const flexibleLines = (lines: PlanResponse['lines'], fixed: readonly string[]): PlanResponse['lines'] => {
  const skip = new Set(fixed.map((n) => n.toLowerCase()));
  return lines.filter((l) => !skip.has(l.categoryName.toLowerCase()));
};

/** Active limits by category id. */
export function limitsById(items: readonly BudgetDto[]): Map<string, Paise> {
  return new Map(items.filter((b) => b.active && b.limitMinor > 0).map((b) => [b.categoryId, b.limitMinor]));
}

/** One row per flexible category with a plan, a limit or spending, earliest line first. */
export function categoryRows(lines: PlanResponse['lines'], limits: ReadonlyMap<string, Paise>, dayOfMonth: number, daysInMonth: number): CategoryRow[] {
  const rows = lines.flatMap((l): CategoryRow[] => {
    const limit = limits.get(l.categoryId);
    const lineMinor = limit ?? l.allocatedMinor;
    if (lineMinor <= 0 && l.spentMinor <= 0) return [];
    const kind = limit === undefined ? 'plan' : 'limit';
    const rate = dayOfMonth > 0 ? l.spentMinor / dayOfMonth : 0;
    const projectedMinor = roundTen(rate * daysInMonth);
    let verdict: CategoryRow['verdict'] = 'inside';
    let day: number | null = null;
    if (l.spentMinor >= lineMinor) verdict = 'over';
    else if (rate > 0) {
      const d = ceilDay(dayOfMonth + (lineMinor - l.spentMinor) / rate);
      if (d <= daysInMonth) { verdict = kind; day = d; }
    }
    const pct = (v: Paise): number => (lineMinor > 0 ? Math.min(100, (v / lineMinor) * LINE_AT) : 100);
    return [{
      id: l.categoryId, name: displayTag(l.categoryName), spentMinor: l.spentMinor, planMinor: l.allocatedMinor, lineMinor, kind, projectedMinor,
      verdict, day, daysAway: verdict === 'over' ? 0 : day === null ? null : day - dayOfMonth, spentPct: pct(l.spentMinor), projectedPct: pct(projectedMinor),
    }];
  });
  const order = (r: CategoryRow): number => (r.verdict === 'over' ? -1 : r.day ?? Infinity);
  return rows.sort((a, b) => order(a) - order(b) || a.name.localeCompare(b.name));
}

/** "Out by Oct 23" / "Over its limit" / "On track". */
export function verdictText(r: CategoryRow, month: string): string {
  if (r.verdict === 'over') return r.kind === 'limit' ? 'Over its limit' : 'Over its plan';
  if (r.verdict === 'inside' || r.day === null) return 'On track';
  return `Out by ${dayLabel(month, r.day)}`;
}

/** The sentence above the category list: who runs out first and who follows. Empty when there is nothing to say. */
export function categoriesLead(rows: readonly CategoryRow[], month: string): LeadPart[] {
  if (rows.length === 0) return [];
  const out = rows.filter((r) => r.verdict !== 'inside');
  const first = out[0];
  if (!first) return ['Every category is on track for the month.'];
  const names = out.slice(1).map((r) => r.name);
  const follow = names.length === 0 ? [] : [` ${names.length <= 3 ? joinPlain(names) : `${names.slice(0, 2).join(', ')} and ${names.length - 2} more`} ${names.length === 1 ? 'follows' : 'follow'}.`];
  const lead: LeadPart[] = first.day === null
    ? [{ b: first.name }, ' is already over.']
    : [{ b: first.name }, ' runs out first, on ', { b: dayLabel(month, first.day), bad: true }, '.'];
  return [...lead, ...follow];
}

/** What `/reports/daily`, `/plans`, `/budgets`, `/dashboard` and `/recurring` add up to. */
export function forecastInput(p: {
  daily: ReportDailyRes; planLines: PlanResponse['lines']; spentSoFarMinor: Paise; availableMinor: Paise; repeatsLeftMinor: Paise;
}): ForecastInput {
  const flex = flexibleLines(p.planLines, p.daily.fixedCategories);
  return {
    month: p.daily.month, dayOfMonth: p.daily.dayOfMonth, daysInMonth: p.daily.daysInMonth,
    dailyMinor: p.daily.items.map((d) => d.spentMinor),
    planFlexMinor: sum(flex.map((l) => l.allocatedMinor)),
    spentSoFarMinor: p.spentSoFarMinor, availableMinor: p.availableMinor, repeatsLeftMinor: p.repeatsLeftMinor,
  };
}

// ---- chart ----

export const CHART = { width: 960, height: 310, left: 52, right: 800, top: 16, bottom: 272 } as const;
const n1 = (x: number): string => x.toFixed(1);

interface Marker { x: number; y: number; label: string }
export interface ForecastChart {
  yTicks: { label: string; y: number }[];
  xTicks: { label: string; x: number; today: boolean }[];
  /** SVG path data. Projection paths are '' on the last day. */
  actual: string;
  band: string;
  expected: string;
  low: string;
  high: string;
  planY: number | null;
  todayX: number;
  todayY: number;
  todayLabel: string;
  runOut: Marker | null;
  ends: { y: number; label: string; strong: boolean }[];
  summary: string;
}

export function forecastChart(i: ForecastInput, f: Forecast): ForecastChart {
  const { left, right, top, bottom } = CHART;
  const spent = f.flexSpentMinor;
  const todayD = Math.max(1, i.dayOfMonth);
  const end = (rate: Paise): Paise => spent + rate * f.daysLeft;
  const rawHigh = end(f.high.ratePerDay);
  const scale = monthScale(Math.max(i.planFlexMinor, rawHigh, spent));
  const x = (d: number): number => left + ((d - 1) / Math.max(1, i.daysInMonth - 1)) * (right - left);
  const y = (v: Paise): number => bottom - (v / scale.max) * (bottom - top);

  let run = 0;
  const actualPts = i.dailyMinor.slice(0, todayD).map((v, k) => `${n1(x(k + 1))} ${n1(y((run += v)))}`);
  const tx = x(todayD);
  const ty = y(spent);
  const projecting = f.daysLeft > 0;
  const line = (rate: Paise): string => (projecting ? `M${n1(tx)} ${n1(ty)} L${n1(right)} ${n1(y(end(rate)))}` : '');
  const planY = i.planFlexMinor > 0 ? y(i.planFlexMinor) : null;

  const crossing = (s: Scenario, label: string): Marker | null => {
    if (s.runOut.kind !== 'day' || planY === null || s.ratePerDay <= 0) return null;
    const d = Math.min(i.daysInMonth, i.dayOfMonth + (i.planFlexMinor - spent) / s.ratePerDay);
    return { x: x(d), y: planY, label: label.replace('{day}', dayLabel(i.month, s.runOut.day)) };
  };
  const runOutMarker = crossing(f.expected, 'plan runs out {day}');
  const ends = projecting ? [{ y: y(end(f.expected.ratePerDay)), label: `${inr(f.expected.flexEndMinor)} by ${dayLabel(i.month, i.daysInMonth)}`, strong: true }] : [];

  const days = axisDays(i.daysInMonth, i.dayOfMonth);
  const xTicks = [...days].sort((a, b) => a - b).map((d) => ({ label: d === 1 ? `${shortMonth(i.month)} 1` : String(d), x: x(d), today: d === i.dayOfMonth }));
  const summary = `Running total of flexible spending: ${inr(spent)} by day ${i.dayOfMonth}.`
    + (projecting ? ` At this pace it reaches ${inr(f.expected.flexEndMinor)} on day ${i.daysInMonth}${i.planFlexMinor > 0 ? `, against a ${inr(i.planFlexMinor)} plan` : ''}.` : '')
    + (f.hasRange ? ` The range runs from ${inr(f.low.flexEndMinor)} at the ${PACE_SHORT[f.low.key]} pace to ${inr(f.high.flexEndMinor)} at the ${PACE_SHORT[f.high.key]} pace.` : '');

  return {
    yTicks: [0, 1 / 3, 2 / 3, 1].map((t) => ({ label: t === 0 ? '0' : compactK(scale.max * t), y: y(scale.max * t) })),
    xTicks,
    actual: actualPts.length ? `M${actualPts.join(' L')}` : '',
    band: projecting && f.hasRange ? `M${n1(tx)} ${n1(ty)} L${n1(right)} ${n1(y(end(f.low.ratePerDay)))} L${n1(right)} ${n1(y(rawHigh))} Z` : '',
    expected: line(f.expected.ratePerDay),
    low: projecting && f.hasRange ? line(f.low.ratePerDay) : '',
    high: projecting && f.hasRange ? line(f.high.ratePerDay) : '',
    planY, todayX: tx, todayY: ty, todayLabel: `today · ${inr(spent)}`,
    runOut: runOutMarker, ends, summary,
  };
}
