import type { z } from 'zod';
import { addDays, addMonthsClamped, inr, parseTag, parseAmount } from '@/common';
import type { CreateRecurringReq, PatchRecurringReq, RecurringRes, RecurringRuleDto, Schedule } from '@/contracts';

/** Repeats page logic. Pure: schedule text, the 30-day timeline, the aside sum and the rule form. */

export type RecurringList = z.infer<typeof RecurringRes>;

const HORIZON_DAYS = 30;
/** The tallest active payment gets this share of the plot height (Rent in the sample). */
const MAX_STEM_PCT = 68;

const ordinal = (n: number): string => {
  const v = n % 100;
  if (v >= 11 && v <= 13) return `${n}th`;
  return `${n}${({ 1: 'st', 2: 'nd', 3: 'rd' } as Record<number, string>)[n % 10] ?? 'th'}`;
};
export const WEEKDAYS = [
  { value: 1, name: 'Monday' }, { value: 2, name: 'Tuesday' }, { value: 3, name: 'Wednesday' }, { value: 4, name: 'Thursday' },
  { value: 5, name: 'Friday' }, { value: 6, name: 'Saturday' }, { value: 0, name: 'Sunday' },
] as const;
export const MONTHS = ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December'];
const weekday = (n: number) => WEEKDAYS.find((w) => w.value === n)?.name ?? '';

/** Table cell: "monthly · 1st", "weekly · Monday", "yearly · 5 Mar". */
export function scheduleText(s: Schedule): string {
  if (s.kind === 'monthly') return `monthly · ${ordinal(s.day)}`;
  if (s.kind === 'weekly') return `weekly · ${weekday(s.weekday)}`;
  return `yearly · ${s.day} ${MONTHS[s.month - 1]?.slice(0, 3) ?? ''}`;
}
/** In a sentence: "monthly on the 5th", "weekly on Mondays", "yearly on 5 March". */
export function scheduleSentence(s: Schedule): string {
  if (s.kind === 'monthly') return `monthly on the ${ordinal(s.day)}`;
  if (s.kind === 'weekly') return `weekly on ${weekday(s.weekday)}s`;
  return `yearly on ${s.day} ${MONTHS[s.month - 1] ?? ''}`;
}

/** 'NOV 01' for a day key. Formatted in UTC: a day key has no time zone. */
export function dateLabel(key: string): string {
  const [y, m, d] = key.split('-').map(Number) as [number, number, number];
  const mon = new Intl.DateTimeFormat('en-GB', { month: 'short', timeZone: 'UTC' }).format(new Date(Date.UTC(y, m - 1, d))).toUpperCase();
  return `${mon} ${String(d).padStart(2, '0')}`;
}

export const daysBetween = (from: string, to: string): number => {
  const p = (k: string) => { const [y, m, d] = k.split('-').map(Number) as [number, number, number]; return Date.UTC(y, m - 1, d); };
  return Math.round((p(to) - p(from)) / 86_400_000);
};

/** A rule counts (committed total, stems) while it is running: not paused and not past its end date. */
export const isOn = (r: RecurringRuleDto): boolean => r.active && !r.paused;

const after = (s: Schedule, due: string): string =>
  s.kind === 'weekly' ? addDays(due, 7) : addMonthsClamped(due, s.kind === 'yearly' ? 12 : 1, s.day);

/** Due days of one rule from today through today+30 (a weekly rule shows up to five times). */
export function occurrences(r: RecurringRuleDto, today: string, horizon = HORIZON_DAYS): string[] {
  const last = addDays(today, horizon);
  const out: string[] = [];
  let d = r.nextDue;
  for (let i = 0; i < 40 && d <= last; i++) {
    if (r.endsOn && d > r.endsOn) break;
    if (d >= today) out.push(d);
    d = after(r.schedule, d);
  }
  return out;
}

export interface Stem {
  key: string; id: string; name: string; amountMinor: number; date: string;
  offset: number; leftPct: number; heightPct: number; align: 'start' | 'center' | 'end';
}
export function stems(rules: RecurringRuleDto[], today: string): Stem[] {
  const on = rules.filter(isOn);
  const max = Math.max(1, ...on.map((r) => r.amountMinor));
  return on
    .flatMap((r) => occurrences(r, today).map((date): Stem => {
      const offset = daysBetween(today, date);
      return {
        key: `${r.id}:${date}`, id: r.id, name: r.name, amountMinor: r.amountMinor, date, offset,
        leftPct: (offset / HORIZON_DAYS) * 100, heightPct: (r.amountMinor / max) * MAX_STEM_PCT,
        // labels at the edges grow inward so they stay inside the plot
        align: offset <= 2 ? 'start' : offset >= 28 ? 'end' : 'center',
      };
    }))
    .sort((a, b) => a.offset - b.offset);
}

/** The 31 axis ticks (days 0..30); the five labelled ones are 0, 7, 14, 21 and 30. */
export function ticks(today: string): { day: number; leftPct: number; label: string | null }[] {
  const labelled = new Set([0, 7, 14, 21, 30]);
  return Array.from({ length: HORIZON_DAYS + 1 }, (_, d) => ({
    day: d, leftPct: (d / HORIZON_DAYS) * 100, label: labelled.has(d) ? dateLabel(addDays(today, d)) : null,
  }));
}

/** Aside sum: lower-cased names joined with `+`; a rule not running is struck through and left out of the total. */
export function committedRows(rules: RecurringRuleDto[]): { id: string; label: string; amountMinor: number; off: boolean }[] {
  return rules.map((r, i) => ({ id: r.id, label: `${i === 0 ? '' : '+ '}${r.name.toLowerCase()}`, amountMinor: r.amountMinor, off: !isOn(r) }));
}
/** The running rule that leaves next (earliest due day, then name), or null when none is running. */
export function nextRule(rules: RecurringRuleDto[]): RecurringRuleDto | null {
  const on = rules.filter(isOn);
  return on.length === 0 ? null : on.reduce((a, b) => (b.nextDue < a.nextDue || (b.nextDue === a.nextDue && b.name < a.name) ? b : a));
}

export const committedTotal = (rules: RecurringRuleDto[]): number => rules.filter(isOn).reduce((s, r) => s + r.amountMinor, 0);

/** The list as the server keeps it: next due first, then by name. */
const byDue = (a: RecurringRuleDto, b: RecurringRuleDto): number => a.nextDue.localeCompare(b.nextDue) || a.name.localeCompare(b.name);
/** The list after a rule was added or changed (the server's answer replaces what was there). */
export function withRule(cur: RecurringList, rule: RecurringRuleDto): RecurringList {
  const items = (cur.items.some((r) => r.id === rule.id) ? cur.items.map((r) => (r.id === rule.id ? rule : r)) : [...cur.items, rule]).sort(byDue);
  return { items, committedMinor: committedTotal(items) };
}
export function withoutRule(cur: RecurringList, id: string): RecurringList {
  const items = cur.items.filter((r) => r.id !== id);
  return { items, committedMinor: committedTotal(items) };
}

/** "oct 18 to nov 17" under the heading. */
export const rangeText = (today: string): string => `${dateLabel(today).toLowerCase()} to ${dateLabel(addDays(today, HORIZON_DAYS)).toLowerCase()}`;
/** What a screen reader gets for the timeline: the same numbers the table below lists. */
export const timelineLabel = (st: Pick<Stem, 'name' | 'amountMinor' | 'date'>[]): string =>
  st.length === 0 ? 'No payments leave in the next 30 days' : `Payments in the next 30 days: ${st.map((x) => `${x.name} ${inr(x.amountMinor)} on ${dateLabel(x.date)}`).join(', ')}`;

/** What the NEXT column says. */
export const nextText = (r: RecurringRuleDto): string => (r.paused ? 'PAUSED' : !r.active ? 'ENDED' : dateLabel(r.nextDue));

export interface RuleForm {
  name: string; tag: string; amount: string; kind: Schedule['kind'];
  day: string; weekday: string; month: string; startsOn: string; endsOn: string; note: string; hint: string;
}
export const emptyForm = (today: string): RuleForm => ({
  name: '', tag: '', amount: '', kind: 'monthly', day: String(Number(today.slice(8, 10))), weekday: '1', month: String(Number(today.slice(5, 7))),
  startsOn: '', endsOn: '', note: '', hint: '',
});
export const formFrom = (r: RecurringRuleDto): RuleForm => ({
  name: r.name, tag: r.categoryName, amount: String(r.amountMinor / 100), kind: r.schedule.kind,
  day: r.schedule.kind === 'weekly' ? '1' : String(r.schedule.day),
  weekday: r.schedule.kind === 'weekly' ? String(r.schedule.weekday) : '1',
  month: r.schedule.kind === 'yearly' ? String(r.schedule.month) : '1',
  startsOn: '', endsOn: r.endsOn ?? '', note: r.note ?? '', hint: r.matchHint ?? '',
});

export type FormErrors = Partial<Record<keyof RuleForm, string>>;
interface Common { name: string; tag: string; amountMinor: number; schedule: Schedule; note: string | null; matchHint: string | null; endsOn: string | null }

function parseForm(f: RuleForm, today?: string): { ok: true; v: Common } | { ok: false; errors: FormErrors } {
  const errors: FormErrors = {};
  const name = f.name.trim();
  if (!name) errors.name = 'Give it a name.';
  const parsedTag = parseTag(f.tag);
  if (!parsedTag.ok) errors.tag = parsedTag.error;
  const tag = parsedTag.ok ? parsedTag.tag : '';
  const amountMinor = parseAmount(f.amount);
  if (amountMinor === null) errors.amount = 'Enter an amount like ₹649.';
  const intIn = (s: string, lo: number, hi: number) => { const n = Number(s); return s.trim() !== '' && Number.isInteger(n) && n >= lo && n <= hi ? n : null; };
  let schedule: Schedule | null = null;
  if (f.kind === 'weekly') {
    const w = intIn(f.weekday, 0, 6);
    if (w === null) errors.weekday = 'Pick a day of the week.'; else schedule = { kind: 'weekly', weekday: w };
  } else {
    const d = intIn(f.day, 1, 31);
    if (d === null) errors.day = 'A day from 1 to 31.';
    else if (f.kind === 'monthly') schedule = { kind: 'monthly', day: d };
    else {
      const m = intIn(f.month, 1, 12);
      if (m === null) errors.month = 'Pick a month.'; else schedule = { kind: 'yearly', month: m, day: d };
    }
  }
  if (today && f.startsOn && f.startsOn < today) errors.startsOn = 'The first payment cannot be in the past.';
  if (f.endsOn && f.startsOn && f.endsOn < f.startsOn) errors.endsOn = 'The end date is before the start.';
  if (Object.keys(errors).length || !schedule || amountMinor === null) return { ok: false, errors };
  return { ok: true, v: { name, tag, amountMinor, schedule, note: f.note.trim() || null, matchHint: f.hint.trim() || null, endsOn: f.endsOn || null } };
}

export function createBody(f: RuleForm, today: string): { ok: true; body: CreateRecurringReq } | { ok: false; errors: FormErrors } {
  const r = parseForm(f, today);
  if (!r.ok) return r;
  return { ok: true, body: { ...r.v, ...(f.startsOn ? { startsOn: f.startsOn } : {}) } };
}
export function patchBody(f: RuleForm): { ok: true; body: PatchRecurringReq } | { ok: false; errors: FormErrors } {
  const r = parseForm(f);
  return r.ok ? { ok: true, body: r.v } : r;
}

/** The due day after the next (what "skip next" lands on), or null if that was the last payment before the end date. */
export function dayAfterNext(r: RecurringRuleDto): string | null {
  const d = after(r.schedule, r.nextDue);
  return r.endsOn && d > r.endsOn ? null : d;
}
export const isEnded = (r: RecurringRuleDto): boolean => r.endsOn !== null && r.nextDue > r.endsOn;

/** The server's `{ field: message }` answer shown under the fields it names (request names → form names). */
export function formErrorsFrom(fields: Record<string, string>): FormErrors {
  const names: Record<string, keyof RuleForm> = {
    name: 'name', tag: 'tag', categoryId: 'tag', amountMinor: 'amount', schedule: 'day', startsOn: 'startsOn', endsOn: 'endsOn', note: 'note', matchHint: 'hint',
  };
  const out: FormErrors = {};
  for (const [k, v] of Object.entries(fields)) { const to = names[k]; if (to) out[to] = v; }
  return out;
}
