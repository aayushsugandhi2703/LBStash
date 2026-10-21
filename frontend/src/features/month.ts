import type { Paise } from '@/common';

/** The About page's sample month ("scrub October"). Pure. Made-up numbers that add up: nothing here is read from an account. */

const R = (rupees: number): Paise => rupees * 100;

export const MONTH_DAYS = 31;
/** The sample "today": days up to here are logged, the rest is the forecast. */
export const LOGGED_DAYS = 21;
/** October 2026 starts on a Thursday (Monday-first calendar: three blanks). */
export const FIRST_WEEKDAY = 3;

/** Flexible spending logged on days 1..21 (sums to ₹26,300). */
const DAILY: readonly Paise[] = [1220, 900, 1400, 700, 1250, 1900, 1500, 800, 700, 1100, 600, 850, 1300, 810, 1700, 1550, 1543, 1800, 1452, 2619, 606].map(R);
/** What a forecast day costs: the month's average so far, rounded (₹1,253). */
const PACE: Paise = R(1253);
const PLAN: Paise = R(36000);
/** Carried over + income. */
const STARTING: Paise = R(6200 + 85000);
/** Repeats leaving on their due day. */
const REPEATS: Readonly<Record<number, Paise>> = { 5: R(24000), 14: R(649), 25: R(1500), 27: R(1180), 28: R(15000) };

const dayCost = (d: number): Paise => (d <= LOGGED_DAYS ? DAILY[d - 1]! : PACE);
const clampDay = (d: number): number => Math.min(MONTH_DAYS, Math.max(1, Math.round(d)));

/** Flexible spending from day 1 to `day` (logged, then forecast at the pace). */
export function flexibleSpent(day: number): Paise {
  let total = 0;
  for (let d = 1; d <= clampDay(day); d++) total += dayCost(d);
  return total;
}

/** Repeats that have left by `day`. */
export function repeatsPaid(day: number): Paise {
  return Object.entries(REPEATS).reduce((t, [d, amount]) => t + (Number(d) <= clampDay(day) ? amount : 0), 0);
}

/** First day the flexible plan is used up at the pace (null if it never is). */
export function planRunsOutDay(): number | null {
  for (let d = 1; d <= MONTH_DAYS; d++) if (flexibleSpent(d) >= PLAN) return d;
  return null;
}

export interface Scrub {
  day: number;
  phase: 'logged' | 'forecast';
  availableMinor: Paise;
  spentMinor: Paise;
  planMinor: Paise;
  runOutDay: number | null;
  verdict: { tone: 'ok' | 'warn' | 'bad'; text: string };
}

/** What the page shows for one day of the sample month. */
export function scrub(day: number): Scrub {
  const d = clampDay(day);
  const runOutDay = planRunsOutDay();
  const spentMinor = flexibleSpent(d);
  let verdict: Scrub['verdict'];
  if (runOutDay !== null && d >= runOutDay) verdict = { tone: 'bad', text: `The flexible plan ran out on Oct ${runOutDay}. Everything since is over plan.` };
  else if (d >= LOGGED_DAYS) verdict = { tone: 'warn', text: runOutDay === null ? 'Forecast: at this pace the plan lasts the month.' : `Forecast: at this pace the plan runs out on Oct ${runOutDay}.` };
  else verdict = { tone: 'ok', text: runOutDay === null ? 'On track so far.' : `On track so far. Keep going and the plan runs out around Oct ${runOutDay}.` };
  return {
    day: d, phase: d <= LOGGED_DAYS ? 'logged' : 'forecast', availableMinor: STARTING - repeatsPaid(d) - spentMinor,
    spentMinor, planMinor: PLAN, runOutDay, verdict,
  };
}

export interface Bar {
  day: number;
  /** 0..100, share of the busiest day. */
  heightPct: number;
  /** logged days are solid, forecast days are striped */
  kind: 'logged' | 'forecast';
  state: 'past' | 'now' | 'future';
  /** a repeat leaves on this day */
  repeat: boolean;
  /** axis label, empty for most days */
  label: string;
}

const AXIS_DAYS = [1, 5, 10, 15, 20, 25, 31];
const BUSIEST = Math.max(...DAILY, PACE);

/** One bar per day, with the chosen day lit. */
export function bars(day: number): Bar[] {
  const chosen = clampDay(day);
  return Array.from({ length: MONTH_DAYS }, (_, i) => {
    const d = i + 1;
    return {
      day: d, heightPct: Math.round((dayCost(d) / BUSIEST) * 100), kind: d <= LOGGED_DAYS ? 'logged' : 'forecast',
      state: d < chosen ? 'past' : d === chosen ? 'now' : 'future', repeat: d in REPEATS, label: AXIS_DAYS.includes(d) ? String(d) : '',
    };
  });
}

export interface CalendarCell { day: number | null; state: 'blank' | 'past' | 'today' | 'future' }

/** Monday-first October grid: blanks, then the 31 days. */
export function calendar(): CalendarCell[] {
  return [
    ...Array.from({ length: FIRST_WEEKDAY }, (): CalendarCell => ({ day: null, state: 'blank' })),
    ...Array.from({ length: MONTH_DAYS }, (_, i): CalendarCell => ({ day: i + 1, state: i + 1 < LOGGED_DAYS ? 'past' : i + 1 === LOGGED_DAYS ? 'today' : 'future' })),
  ];
}
