import { displayTag, listAmount, MAX_TAG_LENGTH, monthDay, parseTag, plain, shortMonth, TZ } from '@/common';
import type { BalanceCheckDto, TransactionPageDto, TransactionRowDto } from '@/contracts';

/** Transactions page logic. Pure: the page owns fetching and state. Money is paise. */

export type TransactionRow = TransactionRowDto;
export type TransactionCounts = TransactionPageDto['counts'];

/** Rows on the first load, then per "load older entries". */
export const PAGE_FIRST = 8;
export const PAGE_NEXT = 5;
/** `GET /transactions` accepts up to 100 per request; a refresh asks for what is already on screen in one go. */
const PAGE_MAX = 100;

export type SrcFilter = 'all' | 'captured' | 'recurring' | 'manual' | 'unaccounted';
export const SOURCE_FILTERS: { value: SrcFilter; label: string }[] = [
  { value: 'all', label: 'All' },
  { value: 'captured', label: 'Auto' },
  { value: 'recurring', label: 'Repeat' },
  { value: 'manual', label: 'Manual' },
  { value: 'unaccounted', label: 'Unaccounted' },
];
export const isSrcFilter = (s: string | null | undefined): s is SrcFilter => SOURCE_FILTERS.some((f) => f.value === s);

export const CAT_ALL = 'all';
const CAT_NEEDS_TAG = 'needs-tag';

const SOURCE_CODE: Record<TransactionRow['source'], string> = { captured: 'AUTO', recurring: 'REPEAT', manual: 'MANUAL', unaccounted: 'UNACCOUNTED' };
const sourceCode = (s: TransactionRow['source']): string => SOURCE_CODE[s];

/** Query string for `GET /transactions`. */
export function transactionsQuery(q: { cat: string; src: SrcFilter; month: string | null; cursor?: string | null; limit: number }): string {
  const p = new URLSearchParams();
  if (q.cat !== CAT_ALL) p.set('cat', q.cat);
  if (q.src !== 'all') p.set('src', q.src);
  if (q.month) p.set('month', q.month);
  if (q.cursor) p.set('cursor', q.cursor);
  p.set('limit', String(q.limit));
  return p.toString();
}

/** "oct 2026" for the counter under the strip. */
export function monthCaption(month: string): string {
  return `${shortMonth(month)} ${month.slice(0, 4)}`.toLowerCase();
}
export const shownText = (shown: number, matching: number, month: string | null): string =>
  `showing ${shown} of ${matching}${month ? ` · ${monthCaption(month)}` : ''}`;

/** "LOOK  2 messages could not be read". */
export function lookText(n: number): string {
  if (n <= 0) return 'No messages are waiting';
  return `${n} message${n === 1 ? '' : 's'} could not be read`;
}

interface IndexItem {
  key: string;
  label: string;
  value: string;
  /** Colour of the right value: money out ink, money in green, counts muted. */
  tone: 'muted' | 'ink' | 'credit';
  /** The "Needs a tag" label is accent. */
  hot?: boolean;
  /** Share of the biggest category, or null for no bar. */
  bar: number | null;
}

/** All, Needs a tag, then each category biggest spend first; credit-only categories (Income) last with a green +total. */
export function categoryIndex(counts: TransactionCounts, active: string): IndexItem[] {
  const cats = counts.byCategory.filter((c) => (c.count > 0 && !c.archived) || c.categoryId === active);
  const spent = cats.filter((c) => c.spentMinor > 0).sort((a, b) => b.spentMinor - a.spentMinor || a.categoryName.localeCompare(b.categoryName));
  const rest = cats.filter((c) => c.spentMinor <= 0).sort((a, b) => b.receivedMinor - a.receivedMinor || a.categoryName.localeCompare(b.categoryName));
  const biggest = spent[0]?.spentMinor ?? 0;
  return [
    { key: CAT_ALL, label: 'All', value: `${counts.all} ${counts.all === 1 ? 'entry' : 'entries'}`, tone: 'muted', bar: null },
    { key: CAT_NEEDS_TAG, label: 'Needs a tag', value: String(counts.needsTag), tone: 'muted', hot: true, bar: null },
    ...spent.map((c): IndexItem => ({
      key: c.categoryId, label: displayTag(c.categoryName), value: plain(c.spentMinor), tone: 'ink', bar: Math.max(0.01, c.spentMinor / biggest),
    })),
    ...rest.map((c): IndexItem => ({
      key: c.categoryId, label: displayTag(c.categoryName), value: c.receivedMinor > 0 ? `+${plain(c.receivedMinor)}` : '—',
      tone: c.receivedMinor > 0 ? 'credit' : 'muted', bar: null,
    })),
  ];
}

const SPLIT_NOTE = 'Split from Unaccounted';
export const isUnaccountedOpen = (r: Pick<TransactionRow, 'source' | 'status'>): boolean => r.source === 'unaccounted' && r.status === 'pending';

/** Smallest entry that can be split into two parts of at least 1 paisa each; shown as "more than ₹1". */
const MIN_SPLITTABLE: number = 100;

type NameInput = Pick<TransactionRow, 'payee' | 'description' | 'source' | 'type' | 'categoryName'>;
/** The bold line of a row: the payee, else what the entry is. */
export function rowName(r: NameInput): string {
  if (r.payee) return r.payee;
  if (r.source === 'unaccounted') return 'Unaccounted';
  if (r.description === SPLIT_NOTE) return SPLIT_NOTE;
  if (r.type === 'credit' && r.categoryName) return displayTag(r.categoryName);
  return r.type === 'credit' ? 'Money in' : 'Payment';
}

/** The grey line under the name: where the tag came from, or the user's own words. */
export function rowNote(r: TransactionRow): string {
  if (r.status === 'reversed') return 'reversed by the bank';
  if (r.source === 'unaccounted') return 'balance check · no message matched yet';
  if (r.description === SPLIT_NOTE) return 'part of a balance gap';
  if (r.source === 'recurring' || r.classifiedBy === 'recurring') return 'monthly rule';
  if (r.description) return `“${r.description}”`;
  if (r.classifiedBy === 'rule' && r.matchedRule) return `matched rule: ${r.matchedRule}`;
  if (r.classifiedBy === 'memory') return 'same payee as last month';
  if (r.source === 'manual' && r.type === 'credit') return 'credit you entered';
  if (r.source === 'captured' && !r.categoryId) return 'UPI · no note was written';
  return '';
}

export interface RowView {
  id: string;
  date: string;
  name: string;
  note: string;
  /** `#food` or null when there is no tag. */
  tag: string | null;
  needsTag: boolean;
  /** A balance gap waiting for a tag: yellow square before the name. */
  unaccounted: boolean;
  canSplit: boolean;
  reversed: boolean;
  source: string;
  amount: string;
  credit: boolean;
}

export function rowView(r: TransactionRow, tz: string = TZ): RowView {
  const open = isUnaccountedOpen(r);
  return {
    id: r.id,
    date: monthDay(r.occurredAt, tz),
    name: rowName(r),
    note: rowNote(r),
    tag: r.categoryName ? `#${r.categoryName}` : null,
    needsTag: r.status === 'pending' && !r.categoryId,
    unaccounted: open,
    canSplit: open && r.amountMinor > MIN_SPLITTABLE,
    reversed: r.status === 'reversed',
    source: sourceCode(r.source),
    amount: listAmount(r.amountMinor, r.type),
    credit: r.type === 'credit',
  };
}

/** Append a page of older rows; rows already listed (moved while scrolling) are skipped. */
export function mergePage<T extends { id: string }>(current: readonly T[], incoming: readonly T[]): T[] {
  const seen = new Set(current.map((r) => r.id));
  return [...current, ...incoming.filter((r) => !seen.has(r.id))];
}
export function replaceRow<T extends { id: string }>(rows: readonly T[], next: Partial<T> & { id: string }): T[] {
  return rows.map((r) => (r.id === next.id ? { ...r, ...next } : r));
}
/** How many rows a refresh should ask for so the list keeps its length (one request, API maximum 100). */
export const refreshSize = (shown: number): number => Math.min(PAGE_MAX, Math.max(PAGE_FIRST, shown));

type EndMark = 'more' | 'end' | 'none';
/** Load more, "that's everything" (only once past a first page), or nothing. */
export function endMark(shown: number, nextCursor: string | null): EndMark {
  if (nextCursor) return 'more';
  return shown > PAGE_FIRST ? 'end' : 'none';
}

export interface TagChoice { name: string; categoryId?: string }
export interface UsageCategory { id: string; name: string; archived: boolean }

/** Typed text → the tag to send, or a plain-words reason (empty input has none). */
export function parseTagDraft(raw: string): { ok: true; tag: string } | { ok: false; error: string } {
  if (!raw.replace(/#/g, '').trim()) return { ok: false, error: '' };
  const r = parseTag(raw);
  return r.ok ? r : { ok: false, error: `Use letters, numbers and simple punctuation, up to ${MAX_TAG_LENGTH} characters.` };
}

/** Chips under the tag box: your categories, most used first; while typing, matches with prefix first. */
export function tagSuggestions(draft: string, categories: readonly UsageCategory[], limit = 6): TagChoice[] {
  const live = categories.filter((c) => !c.archived);
  const q = draft.replace(/#/g, '').trim().toLowerCase();
  if (!q) {
    return live.slice(0, limit).map((c) => ({ name: c.name, categoryId: c.id }));
  }
  const starts = live.filter((c) => c.name.startsWith(q));
  const inside = live.filter((c) => !c.name.startsWith(q) && c.name.includes(q));
  return [...starts, ...inside].slice(0, limit).map((c) => ({ name: c.name, categoryId: c.id }));
}

/** `PATCH /transactions/:id` body: an existing category by id, else typed text as a tag (the server creates it). */
export function tagBody(choice: TagChoice, recategorize = false): { categoryId?: string; tag?: string; recategorize?: boolean } {
  const base = choice.categoryId ? { categoryId: choice.categoryId } : { tag: choice.name };
  return recategorize ? { ...base, recategorize: true } : base;
}

type CheckStage = 'match' | 'gap' | 'booked';
/** Where a balance check stands: the books match, a gap waits for a message, or it was booked as Unaccounted. */
export function checkStage(r: { matches: boolean; check: Pick<BalanceCheckDto, 'status'> }): CheckStage {
  if (r.matches || r.check.status === 'resolved') return 'match';
  return r.check.status === 'booked' ? 'booked' : 'gap';
}

/** Parts must add up: this part is more than nothing and less than the whole, the rest stays Unaccounted. */
export function validateSplit(leftMinor: number, partMinor: number): { ok: boolean; restMinor: number } {
  const ok = Number.isInteger(partMinor) && partMinor > 0 && partMinor < leftMinor;
  return { ok, restMinor: ok ? leftMinor - partMinor : leftMinor };
}
export const splitCaption = (restMinor: number): string => `the rest, ₹${plain(restMinor)}, stays Unaccounted`;

/** `POST /transactions/:id/split` body: the tagged part, then the untagged rest (the sum is exact). */
export function splitBody(leftMinor: number, partMinor: number, to: TagChoice): { parts: { amountMinor: number; tag?: string; categoryId?: string }[] } {
  const target = to.categoryId ? { categoryId: to.categoryId } : { tag: to.name };
  return { parts: [{ amountMinor: partMinor, ...target }, { amountMinor: leftMinor - partMinor }] };
}

/** The choices under "GOES TO": the user's four most used spending categories. */
export function splitChoices(counts: TransactionCounts | null): TagChoice[] {
  const used = (counts?.byCategory ?? []).filter((c) => c.spentMinor > 0 && !c.archived).sort((a, b) => b.count - a.count || b.spentMinor - a.spentMinor)
    .map((c): TagChoice => ({ name: c.categoryName, categoryId: c.categoryId }));
  return used.slice(0, 4);
}
