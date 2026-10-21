import { limitStatus, type LimitStatus } from '@/common';
import type { BudgetDto } from '@/contracts';
import { dayLabel, runOut } from './forecast';

/** Limits page logic. Statuses are recomputed here so changing the alert level or the pace switch answers at once. */

export const LEVELS = [
  { level: 70, note: 'early warning' },
  { level: 80, note: 'balanced' },
  { level: 90, note: 'last minute' },
] as const;

const STATUS_TEXT: Record<LimitStatus, string> = {
  over: 'Over the limit', close: 'Close to the limit', fast: 'Spending fast', ok: 'On track',
};

export interface LimitRow {
  id: string;
  name: string;
  spentMinor: number;
  limitMinor: number;
  /** Rounded for display (the API floors it). */
  pct: number;
  /** Bar fill 0..1, capped. */
  ratio: number;
  /** The alert level this limit uses: its own override or the user's level. */
  alertPct: number;
  status: LimitStatus;
  statusText: string;
  leftMinor: number;
  projectedMinor: number;
  /** projected − limit: positive means heading over. */
  diffMinor: number;
}

export function limitRow(b: BudgetDto, level: number, warnOnPace: boolean): LimitRow {
  const alertPct = b.warnPct ?? level;
  let status = limitStatus({ spent: b.spentMinor, limit: b.limitMinor, alertPct, projected: b.projectedMinor });
  if (status === 'fast' && !warnOnPace) status = 'ok';
  return {
    id: b.id, name: b.categoryName, spentMinor: b.spentMinor, limitMinor: b.limitMinor,
    pct: b.limitMinor > 0 ? Math.round((b.spentMinor / b.limitMinor) * 100) : 0,
    ratio: b.limitMinor > 0 ? Math.min(1, b.spentMinor / b.limitMinor) : 0,
    alertPct, status, statusText: STATUS_TEXT[status],
    leftMinor: b.limitMinor - b.spentMinor, projectedMinor: b.projectedMinor, diffMinor: b.projectedMinor - b.limitMinor,
  };
}

/** Fullest first (exact ratio, not the rounded figure), then by name. Inactive limits are not shown. */
export function limitRows(items: BudgetDto[], level: number, warnOnPace: boolean): LimitRow[] {
  return items
    .filter((b) => b.active)
    .map((b) => ({ b, r: b.limitMinor > 0 ? b.spentMinor / b.limitMinor : 0 }))
    .sort((x, y) => y.r - x.r || x.b.categoryName.localeCompare(y.b.categoryName))
    .map(({ b }) => limitRow(b, level, warnOnPace));
}

const WORDS = ['no', 'one', 'two', 'three', 'four', 'five', 'six', 'seven', 'eight', 'nine', 'ten'];
const word = (n: number) => WORDS[n] ?? String(n);
const list = (xs: string[]) => (xs.length < 2 ? xs.join('') : `${xs.slice(0, -1).join(', ')} and ${xs[xs.length - 1]}`);

/** The sentence above the rows. `names` are display names, in row order. */
export function headline(rows: LimitRow[], display: (n: string) => string): string {
  if (rows.length === 0) return 'No limits yet.';
  const needs = rows.filter((r) => r.status === 'close' || r.status === 'over').map((r) => display(r.name));
  if (needs.length === 0) return rows.length === 1 ? 'Your limit is on track.' : rows.length === 2 ? 'Both limits are on track.' : `All ${word(rows.length)} limits are on track.`;
  if (needs.length === 1) return rows.length === 1 ? `${needs[0]} needs a look.` : `${needs[0]} needs a look. The other ${rows.length - 1} ${rows.length === 2 ? 'is' : 'are'} fine.`;
  return `${needs.length} limits need a look: ${list(needs)}.`;
}

/** "13 days left in October" (days after today), "last day of October" on the 31st. */
export function daysLeftText(day: number, days: number, month: string): string {
  const left = days - day;
  return left <= 0 ? `last day of ${month}` : `${left} ${left === 1 ? 'day' : 'days'} left in ${month}`;
}

interface AlertItem { id: string; budgetId: string; categoryName: string; level: 'alert' | 'exceeded'; sentAt: string }
/** "Fun passed 80%" / "Food went over its limit". The % is the limit's current alert level (alerts don't store it). */
export function warningText(a: AlertItem, budgets: BudgetDto[], level: number, display: (n: string) => string): string {
  if (a.level === 'exceeded') return `${display(a.categoryName)} went over its limit`;
  const b = budgets.find((x) => x.id === a.budgetId);
  return `${display(a.categoryName)} passed ${b?.warnPct ?? level}%`;
}

/** "At this pace you hit it on Oct 23, in 2 days". Null when the pace stays inside the limit, or it is already passed (the status says so). */
export function hitText(r: Pick<LimitRow, 'spentMinor' | 'limitMinor'>, t: { month: string; day: number; days: number }): string | null {
  const o = runOut({ planMinor: r.limitMinor, spentMinor: r.spentMinor, rateMinor: t.day > 0 ? r.spentMinor / t.day : 0, dayOfMonth: t.day, daysInMonth: t.days });
  if (o.kind !== 'day') return null;
  const away = o.day - t.day;
  return `At this pace you hit it on ${dayLabel(t.month, o.day)}${away > 0 ? `, in ${away} ${away === 1 ? 'day' : 'days'}` : ', today'}`;
}
