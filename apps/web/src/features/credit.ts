import { addDays, toPaise } from '@/common';

/** Add credit page logic (docs/ui-spec/07-add-credit). Pure; money is paise, the box holds whole rupees. */

/** Whole rupees, added to what is typed. */
export const QUICK_ADDS = [1_000, 5_000, 10_000, 50_000] as const;

/** "#Bonus " → "bonus"; empty when there is nothing to add. */
export const cleanTag = (draft: string): string => draft.replace(/#/g, '').trim().replace(/\s+/g, ' ').toLowerCase();

/** The chip list after adding a tag: new tags go last, an existing one is not repeated. */
export const withTag = (tags: readonly string[], tag: string): string[] => (tags.includes(tag) ? [...tags] : [...tags, tag]);

/** The tags the user's recent credits already used, each once. */
export function creditTags(recent: readonly (string | null)[]): string[] {
  return recent.reduce<string[]>((out, t) => (t ? withTag(out, t) : out), []);
}

export type DateChoice = 'today' | 'yesterday' | 'pick';
/** The local day (YYYY-MM-DD) a choice stands for. `pick` is the date box value, clamped to today at most. */
export function resolveDate(choice: DateChoice, today: string, picked: string): string {
  if (choice === 'today') return today;
  if (choice === 'yesterday') return addDays(today, -1);
  return /^\d{4}-\d{2}-\d{2}$/.test(picked) && picked <= today ? picked : today;
}
/** The box opens three days back, like the design's Oct 15 on Oct 18. */
export const defaultPickDate = (today: string): string => addDays(today, -3);

const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
/** 2026-10-18 → "Oct 18, 2026". */
export function dateText(day: string): string {
  const m = /^(\d{4})-(\d{2})-(\d{2})$/.exec(day);
  if (!m) return day;
  return `${MONTHS[Number(m[2]) - 1] ?? ''} ${Number(m[3])}, ${m[1]}`;
}

interface CreditMath {
  newBalanceMinor: number | null;
  /** Money to plan after the credit; null while the plan total is unknown. */
  newPlanMinor: number | null;
  planAddMinor: number;
}
/** The two ledger-math blocks in the aside. Unknown figures stay null so the page shows "—" instead of a made-up 0. */
export function creditMath(i: { balanceMinor: number | null; planMinor: number | null; creditMinor: number; addToPlan: boolean }): CreditMath {
  const planAddMinor = i.addToPlan ? i.creditMinor : 0;
  return {
    newBalanceMinor: i.balanceMinor === null ? null : i.balanceMinor + i.creditMinor,
    newPlanMinor: i.planMinor === null ? null : i.planMinor + planAddMinor,
    planAddMinor,
  };
}

/** Body for `POST /credits`. */
export function creditBody(i: { amount: string; tag: string; date: string; note: string; addToPlan: boolean }) {
  const note = i.note.trim();
  return { amountMinor: toPaise(i.amount), date: i.date, tag: i.tag, note: note ? note : null, addToPlan: i.addToPlan };
}
