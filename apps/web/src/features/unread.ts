import { fromPaise, listAmount, monthDay, plain, timeOfDay, TZ } from '@/common';

/** Needs a look page logic (docs/ui-spec/08-needs-a-look). Pure; the page keeps one form per message. */

type Reason = 'no_amount' | 'direction_unclear' | 'unreadable';
export type Dir = 'debit' | 'credit';
export type Done = '' | 'added' | 'dismissed';

export interface UnreadItem {
  id: string;
  receivedAt: string;
  reason: Reason;
  text: string;
  suggestion: { type: Dir | null; amountMinor: number | null; payee: string | null };
}

interface Form { dir: Dir; amount: string; name: string; done: Done }

export const REASON_TEXT: Record<Reason, string> = {
  no_amount: 'no amount found',
  direction_unclear: 'amount found, direction unclear',
  unreadable: 'could not be read',
};

/** "OCT 17 · 9:12 PM". */
export function whenLine(receivedAt: string, tz: string = TZ): string {
  return `${monthDay(receivedAt, tz)} · ${timeOfDay(receivedAt, tz).toUpperCase()}`;
}

/** What the parser could still guess fills the form; no direction guess means money out (most messages are). */
export function initialForm(it: UnreadItem): Form {
  return {
    dir: it.suggestion.type ?? 'debit',
    amount: it.suggestion.amountMinor ? fromPaise(it.suggestion.amountMinor) : '',
    name: it.suggestion.payee ?? '',
    done: '',
  };
}

export const canAdd = (amountMinor: number): boolean => amountMinor > 0;

/** The line replacing a form once the user acts. `tagged`: undefined while Undo is open, a name if the payee was known, null if untagged. */
export function doneText(f: Pick<Form, 'dir' | 'name' | 'done'>, amountMinor: number, tagged?: string | null): string {
  if (f.done === 'dismissed') return 'Deleted. The message is gone for good.';
  const sign = listAmount(amountMinor, f.dir).charAt(0);
  const tail = tagged === undefined ? (f.dir === 'debit' ? ' · needs a tag' : '') : tagged ? ` · #${tagged}` : ' · needs a tag';
  return `Added to the ledger: ${sign}₹${plain(amountMinor)}${f.name.trim() ? ` · ${f.name.trim()}` : ''}${tail}`;
}

/** The aside's ledger-math: waiting − sorted = still to look at. */
export function tally(waiting: number, dones: readonly Done[]): { waiting: number; sorted: number; left: number } {
  const sorted = dones.filter((d) => d !== '').length;
  return { waiting, sorted, left: Math.max(0, waiting - sorted) };
}

/** Body for `POST /unparsed/:id/resolve`. */
export function resolveBody(f: Pick<Form, 'dir' | 'name'>, amountMinor: number) {
  const payee = f.name.trim();
  return { type: f.dir, amountMinor, payee: payee ? payee : null };
}
