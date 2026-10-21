import { displayTag, inr, limitStatus, type LimitStatus, wholeRupees } from '@/common';
import type { BudgetDto } from '@/contracts';
import { dayLabel, runOut } from './forecast';
import type { PlanResponse } from './plan';

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
  const needs = rows.filter((r) => r.status !== 'ok').map((r) => display(r.name));
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

interface Clock { month: string; day: number; days: number }

/** The day the pace reaches the limit and how many days away it is (0 = today). Null when the pace stays inside, or the limit is already passed (the state says so). */
export function hitDay(r: Pick<LimitRow, 'spentMinor' | 'limitMinor'>, t: Pick<Clock, 'day' | 'days'>): { day: number; away: number } | null {
  const o = runOut({ planMinor: r.limitMinor, spentMinor: r.spentMinor, rateMinor: t.day > 0 ? r.spentMinor / t.day : 0, dayOfMonth: t.day, daysInMonth: t.days });
  return o.kind === 'day' ? { day: o.day, away: o.day - t.day } : null;
}

const awayText = (away: number): string => (away > 0 ? `in ${away} ${away === 1 ? 'day' : 'days'}` : 'today');

/** The limit that is hit first, for the sentence above the rows. Null when no pace reaches its limit. */
export function closest(rows: LimitRow[], t: Clock): { name: string; date: string } | null {
  const hits = rows.flatMap((r) => { const h = hitDay(r, t); return h ? [{ name: r.name, day: h.day }] : []; }).sort((a, b) => a.day - b.day);
  return hits[0] ? { name: hits[0].name, date: dayLabel(t.month, hits[0].day) } : null;
}

/** The "Where it is heading" cell: a verdict, when it lands, and the daily pace that keeps the limit. */
export function heading(r: LimitRow, t: Clock): { text: string; when: string; bad: boolean; note: string } {
  if (r.status === 'over') return { text: r.leftMinor < 0 ? `Over by ${inr(-r.leftMinor)}` : 'Limit reached', when: '', bad: true, note: '' };
  const daysLeft = Math.max(1, t.days - t.day);
  const safe = Math.floor(r.leftMinor / daysLeft / 100) * 100;
  const spend = wholeRupees(t.day > 0 ? r.spentMinor / t.day : 0);
  const note = `Safe pace ${inr(safe)} a day. You spend ${inr(spend)}.`;
  const h = hitDay(r, t);
  return h ? { text: `Hits the limit ${dayLabel(t.month, h.day)}`, when: awayText(h.away), bad: true, note } : { text: 'Stays inside the limit', when: '', bad: false, note };
}

export const STATE_MARK: Record<LimitStatus, string> = { ok: '●', fast: '»', close: '◆', over: '■' };

export interface LimitChoice { tag: string; name: string; planMinor: number }

/** Plan categories that can take a limit: not a repeat (Rent, SIP), and no limit yet. */
export function limitChoices(lines: PlanResponse['lines'], fixedIds: ReadonlySet<string>, budgets: readonly BudgetDto[]): LimitChoice[] {
  const limited = new Set(budgets.filter((b) => b.active).map((b) => b.categoryId));
  return lines
    .filter((l) => !fixedIds.has(l.categoryId) && !limited.has(l.categoryId))
    .map((l) => ({ tag: l.categoryName, name: displayTag(l.categoryName), planMinor: l.allocatedMinor }));
}
