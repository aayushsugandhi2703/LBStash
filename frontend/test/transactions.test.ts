import { describe, expect, it } from 'vitest';
import { categoryIndex, checkStage, endMark, type TransactionCounts, transactionsQuery, type TransactionRow, lookText, mergePage, monthCaption, parseTagDraft, refreshSize, replaceRow, rowView, shownText, splitBody, splitCaption, splitChoices, tagBody, tagSuggestions, validateSplit } from '@/features/transactions';

// The transactions dataset: 18 rows, newest first. [date, name, note kind, tag, source, amount in rupees]
type Src = TransactionRow['source'];
const base = { recurringId: null, capturedAt: null, weakParse: false, status: 'confirmed' as const, classifiedBy: null, matchedRule: null, description: null };
let n = 0;
const row = (p: Partial<TransactionRow> & Pick<TransactionRow, 'payee' | 'source' | 'type' | 'amountMinor' | 'occurredAt' | 'categoryName'>): TransactionRow =>
  ({ ...base, id: `00000000-0000-4000-8000-${String(++n).padStart(12, '0')}`, categoryId: p.categoryName ? `cat-${p.categoryName}` : null, ...p });
const day = (d: string) => `2026-10-${d}T12:00:00+05:30`;
const debit = (d: string, payee: string, categoryName: string | null, source: Src, rupees: number, extra: Partial<TransactionRow> = {}) =>
  row({ payee, source, type: 'debit', amountMinor: rupees * 100, occurredAt: day(d), categoryName, status: categoryName ? 'confirmed' : 'pending', ...extra });

const ROWS: TransactionRow[] = [
  debit('18', 'Swiggy', 'food', 'captured', 386, { description: '#food dinner' }),
  debit('18', 'Ramesh Kumar', null, 'captured', 450),
  debit('17', 'Uber', 'travel', 'captured', 214, { classifiedBy: 'rule', matchedRule: 'uber' }),
  debit('17', 'Netflix', 'fun', 'recurring', 649, { classifiedBy: 'recurring' }),
  debit('15', 'Airtel', 'bills', 'captured', 299, { classifiedBy: 'memory' }),
  debit('01', 'Rent', 'rent', 'recurring', 20000),
  row({ payee: null, source: 'manual', type: 'credit', amountMinor: 5_000_000, occurredAt: day('01'), categoryName: 'salary' }),
];

describe('row view', () => {
  it('shows date, payee, note, tag, source code and amount like the spec table', () => {
    const v = rowView(ROWS[0]!);
    expect(v).toMatchObject({ date: 'OCT 18', name: 'Swiggy', note: '“#food dinner”', tag: '#food', needsTag: false, source: 'AUTO', amount: '−386', credit: false });
  });
  it('an untagged row offers tag it and says no note was written', () => {
    const v = rowView(ROWS[1]!);
    expect(v).toMatchObject({ name: 'Ramesh Kumar', tag: null, needsTag: true, note: 'UPI · no note was written', amount: '−450' });
  });
  it('explains where a tag came from', () => {
    expect(rowView(ROWS[2]!).note).toBe('matched rule: uber');
    expect(rowView(ROWS[3]!)).toMatchObject({ note: 'monthly rule', source: 'REPEAT' });
    expect(rowView(ROWS[4]!).note).toBe('same payee as last month');
  });
  it('uses Indian grouping, the true minus and a plus for credits', () => {
    expect(rowView(ROWS[5]!).amount).toBe('−20,000');
    const salary = rowView(ROWS[6]!);
    expect(salary).toMatchObject({ name: 'Salary', amount: '+50,000', credit: true, source: 'MANUAL', note: 'credit you entered' });
  });
  it('an Unaccounted gap is marked, splittable above ₹1 and has the design note', () => {
    const gap = row({ payee: null, source: 'unaccounted', type: 'debit', amountMinor: 18_000, occurredAt: day('18'), categoryName: null, status: 'pending' });
    expect(rowView(gap)).toMatchObject({ name: 'Unaccounted', unaccounted: true, canSplit: true, needsTag: true, source: 'UNACCOUNTED', amount: '−180', note: 'balance check · no message matched yet' });
    expect(rowView({ ...gap, amountMinor: 100 }).canSplit).toBe(false);
    expect(rowView({ ...gap, status: 'confirmed', categoryName: 'food', categoryId: 'c' })).toMatchObject({ unaccounted: false, canSplit: false, needsTag: false });
  });
  it('a split part is named after where it came from', () => {
    const part = row({ payee: null, source: 'manual', type: 'debit', amountMinor: 10_000, occurredAt: day('18'), categoryName: 'food', description: 'Split from Unaccounted' });
    expect(rowView(part)).toMatchObject({ name: 'Split from Unaccounted', note: 'part of a balance gap', tag: '#food' });
  });
  it('a reversed row is struck through and says so', () => {
    const r = rowView({ ...ROWS[0]!, status: 'reversed' });
    expect(r).toMatchObject({ reversed: true, note: 'reversed by the bank', needsTag: false });
  });
});

describe('query and captions', () => {
  it('builds the API query', () => {
    expect(transactionsQuery({ cat: 'all', src: 'all', month: '2026-10', limit: 8 })).toBe('month=2026-10&limit=8');
    expect(transactionsQuery({ cat: 'needs-tag', src: 'unaccounted', month: '2026-10', cursor: 'abc', limit: 5 })).toBe('cat=needs-tag&src=unaccounted&month=2026-10&cursor=abc&limit=5');
  });
  it('words the counter and the look link', () => {
    expect(monthCaption('2026-10')).toBe('oct 2026');
    expect(shownText(8, 18, '2026-10')).toBe('showing 8 of 18 · oct 2026');
    expect(lookText(2)).toBe('2 messages could not be read');
    expect(lookText(1)).toBe('1 message could not be read');
    expect(lookText(0)).toBe('No messages are waiting');
  });
});

describe('category index', () => {
  const stat = (name: string, spent: number, received = 0, count = 1) => ({ categoryId: `id-${name}`, categoryName: name, archived: false, count, spentMinor: spent * 100, receivedMinor: received * 100 });
  const counts: TransactionCounts = {
    all: 18, needsTag: 1, unaccounted: 0,
    byCategory: [stat('food', 5420), stat('fun', 1640), stat('travel', 1350), stat('bills', 1299), stat('sip', 10000), stat('rent', 20000), stat('income', 0, 50000)],
  };
  it('lists All, Needs a tag, then spend biggest first and Income last', () => {
    const items = categoryIndex(counts, 'all');
    expect(items.map((i) => i.label)).toEqual(['All', 'Needs a tag', 'Rent', 'Sip', 'Food', 'Fun', 'Travel', 'Bills', 'Income']);
    expect(items[0]).toMatchObject({ value: '18 entries', tone: 'muted', bar: null });
    expect(items[1]).toMatchObject({ value: '1', hot: true, bar: null });
  });
  it('right values: spend ink with grouping, income green with a plus', () => {
    const byLabel = Object.fromEntries(categoryIndex(counts, 'all').map((i) => [i.label, i]));
    expect(byLabel['Rent']).toMatchObject({ value: '20,000', tone: 'ink', bar: 1 });
    expect(byLabel['Food']).toMatchObject({ value: '5,420', tone: 'ink' });
    expect(byLabel['Food']!.bar).toBeCloseTo(5420 / 20000);
    expect(byLabel['Income']).toMatchObject({ value: '+50,000', tone: 'credit', bar: null });
  });
  it('a tiny category still gets a visible bar (at least 1%)', () => {
    const tiny: TransactionCounts = { ...counts, byCategory: [stat('rent', 20000), stat('chai', 1)] };
    expect(categoryIndex(tiny, 'all').find((i) => i.label === 'Chai')!.bar).toBe(0.01);
  });
  it('hides empty and archived categories unless they are the active one', () => {
    const c: TransactionCounts = { ...counts, byCategory: [stat('food', 100), { ...stat('old', 5), archived: true }, stat('none', 0, 0, 0)] };
    expect(categoryIndex(c, 'all').map((i) => i.label)).toEqual(['All', 'Needs a tag', 'Food']);
    expect(categoryIndex(c, 'id-old').map((i) => i.label)).toContain('Old');
  });
});

describe('paging', () => {
  const mk = (...ids: string[]) => ids.map((id) => ({ id }));
  it('first page 8, the rest in fives (spec: 18 rows → 8, 13, 18)', () => {
    expect(endMark(8, 'c1')).toBe('more');
    expect(endMark(13, 'c2')).toBe('more');
    expect(endMark(18, null)).toBe('end');
  });
  it('says nothing at the end of a short list', () => {
    expect(endMark(1, null)).toBe('none');
    expect(endMark(8, null)).toBe('none');
    expect(endMark(0, null)).toBe('none');
  });
  it('merges an older page without repeating rows that moved', () => {
    expect(mergePage(mk('a', 'b'), mk('b', 'c', 'd')).map((r) => r.id)).toEqual(['a', 'b', 'c', 'd']);
    expect(mergePage([], mk('a'))).toEqual(mk('a'));
  });
  it('replaces one row in place', () => {
    const rows = [{ id: 'a', tag: null as string | null }, { id: 'b', tag: null as string | null }];
    expect(replaceRow(rows, { id: 'b', tag: 'food' })).toEqual([{ id: 'a', tag: null }, { id: 'b', tag: 'food' }]);
  });
  it('a refresh keeps the list length within the API limit', () => {
    expect(refreshSize(0)).toBe(8);
    expect(refreshSize(13)).toBe(13);
    expect(refreshSize(180)).toBe(100);
  });
});

describe('tagging', () => {
  const cats = [{ id: 'c1', name: 'food', archived: false }, { id: 'c2', name: 'fun', archived: false }, { id: 'c3', name: 'travel', archived: false }, { id: 'c4', name: 'old', archived: true }, { id: 'c5', name: 'salary', archived: false }];
  it('accepts a tag with or without #, any case', () => {
    expect(parseTagDraft('#Food')).toEqual({ ok: true, tag: 'food' });
    expect(parseTagDraft('  bank  charges ')).toEqual({ ok: true, tag: 'bank charges' });
  });
  it('rejects empty quietly and junk with a sentence', () => {
    expect(parseTagDraft('  # ')).toEqual({ ok: false, error: '' });
    const bad = parseTagDraft('!!');
    expect(bad.ok).toBe(false);
    expect(!bad.ok && bad.error).toMatch(/letters, numbers/);
    expect(parseTagDraft('x'.repeat(40)).ok).toBe(false);
  });
  it('suggests the user\'s own categories when nothing is typed', () => {
    expect(tagSuggestions('', cats).map((c) => c.name)).toEqual(['food', 'fun', 'travel', 'salary']);
  });
  it('filters while typing, prefix first, never archived', () => {
    expect(tagSuggestions('#f', cats).map((c) => c.name)).toEqual(['food', 'fun']);
    expect(tagSuggestions('l', cats).map((c) => c.name)).toEqual(['travel', 'salary']);
    expect(tagSuggestions('old', cats)).toEqual([]);
  });
  it('sends an existing category by id and a new tag by name; recategorize only on purpose', () => {
    expect(tagBody({ name: 'food', categoryId: 'c1' })).toEqual({ categoryId: 'c1' });
    expect(tagBody({ name: 'bonus' })).toEqual({ tag: 'bonus' });
    expect(tagBody({ name: 'bonus' }, true)).toEqual({ tag: 'bonus', recategorize: true });
  });
});

describe('check panel', () => {
  it('tells match, gap and booked apart', () => {
    expect(checkStage({ matches: true, check: { status: 'ignored' } })).toBe('match');
    expect(checkStage({ matches: false, check: { status: 'resolved' } })).toBe('match');
    expect(checkStage({ matches: false, check: { status: 'open' } })).toBe('gap');
    expect(checkStage({ matches: false, check: { status: 'booked' } })).toBe('booked');
  });
});

describe('split panel', () => {
  it('parts must add up: more than nothing, less than the whole', () => {
    expect(validateSplit(18_000, 10_000)).toEqual({ ok: true, restMinor: 8_000 });
    expect(validateSplit(18_000, 0)).toEqual({ ok: false, restMinor: 18_000 });
    expect(validateSplit(18_000, 18_000).ok).toBe(false);
    expect(validateSplit(18_000, 18_001).ok).toBe(false);
    expect(validateSplit(18_000, 10.5).ok).toBe(false);
    expect(validateSplit(18_000, -5).ok).toBe(false);
  });
  it('splitting 100 to Food leaves ₹80 Unaccounted', () => {
    const v = validateSplit(18_000, 10_000);
    expect(splitCaption(v.restMinor)).toBe('the rest, ₹80, stays Unaccounted');
    const body = splitBody(18_000, 10_000, { name: 'food', categoryId: 'c1' });
    expect(body.parts).toEqual([{ amountMinor: 10_000, categoryId: 'c1' }, { amountMinor: 8_000 }]);
    expect(body.parts.reduce((t, p) => t + p.amountMinor, 0)).toBe(18_000);
    expect(splitBody(18_000, 10_000, { name: 'fun' }).parts[0]).toEqual({ amountMinor: 10_000, tag: 'fun' });
  });
  it('offers only the busiest spending categories the user has', () => {
    expect(splitChoices(null)).toEqual([]);
    const counts: TransactionCounts = {
      all: 3, needsTag: 0, unaccounted: 0,
      byCategory: [
        { categoryId: 'a', categoryName: 'rent', archived: false, count: 1, spentMinor: 100, receivedMinor: 0 },
        { categoryId: 'b', categoryName: 'food', archived: false, count: 9, spentMinor: 100, receivedMinor: 0 },
        { categoryId: 'c', categoryName: 'income', archived: false, count: 3, spentMinor: 0, receivedMinor: 100 },
      ],
    };
    expect(splitChoices(counts)).toEqual([{ name: 'food', categoryId: 'b' }, { name: 'rent', categoryId: 'a' }]);
  });
});
