import { describe, expect, it } from 'vitest';
import { canAdd, doneText, initialForm, REASON_TEXT, resolveBody, tally, type UnreadItem, whenLine } from '@/features/unread';

// ui-spec sample data: u1 (amount found, direction unclear, 1,250 Amazon Pay) and u2 (no amount found)
const u1: UnreadItem = {
  id: 'u1', receivedAt: '2026-10-17T21:12:00+05:30', reason: 'direction_unclear',
  text: 'Txn of INR 1,250.00 on card ending •••• at AMAZON PAY INDIA, 17-Oct.',
  suggestion: { type: null, amountMinor: 125_000, payee: 'Amazon Pay' },
};
const u2: UnreadItem = {
  id: 'u2', receivedAt: '2026-10-14T08:03:00+05:30', reason: 'no_amount', text: 'Your a/c ending •••• has been updated.',
  suggestion: { type: null, amountMinor: null, payee: null },
};

describe('needs a look', () => {
  it('prefills from what the parser guessed', () => {
    expect(initialForm(u1)).toEqual({ dir: 'debit', amount: '1250', name: 'Amazon Pay', done: '' });
    expect(initialForm(u2)).toEqual({ dir: 'debit', amount: '', name: '', done: '' });
    expect(initialForm({ ...u1, suggestion: { type: 'credit', amountMinor: 125_050, payee: null } }).amount).toBe('1250.5');
  });
  it('words the when line and the reason like the design', () => {
    expect(whenLine(u1.receivedAt)).toBe('OCT 17 · 9:12 PM');
    expect(whenLine(u2.receivedAt)).toBe('OCT 14 · 8:03 AM');
    expect(REASON_TEXT[u1.reason]).toBe('amount found, direction unclear');
    expect(REASON_TEXT[u2.reason]).toBe('no amount found');
  });
  it('Add needs an amount', () => {
    expect(canAdd(0)).toBe(false);
    expect(canAdd(125_000)).toBe(true);
  });
  it('done lines', () => {
    expect(doneText({ dir: 'debit', name: 'Amazon Pay', done: 'added' }, 125_000)).toBe('Added to the transactions: −₹1,250 · Amazon Pay · needs a tag');
    expect(doneText({ dir: 'credit', name: '', done: 'added' }, 5_000_000)).toBe('Added to the transactions: +₹50,000');
    expect(doneText({ dir: 'debit', name: 'Amazon Pay', done: 'added' }, 125_000, 'shopping')).toBe('Added to the transactions: −₹1,250 · Amazon Pay · #shopping');
    expect(doneText({ dir: 'credit', name: '', done: 'added' }, 100, null)).toBe('Added to the transactions: +₹1 · needs a tag');
    expect(doneText({ dir: 'debit', name: '', done: 'dismissed' }, 0)).toBe('Deleted. The message is gone for good.');
  });
  it('counts waiting − sorted = still to look at', () => {
    expect(tally(2, ['', ''])).toEqual({ waiting: 2, sorted: 0, left: 2 });
    expect(tally(2, ['added', ''])).toEqual({ waiting: 2, sorted: 1, left: 1 });
    expect(tally(2, ['added', 'dismissed'])).toEqual({ waiting: 2, sorted: 2, left: 0 });
  });
  it('resolve body trims the payee and sends null when blank', () => {
    expect(resolveBody({ dir: 'debit', name: ' Amazon Pay ' }, 125_000)).toEqual({ type: 'debit', amountMinor: 125_000, payee: 'Amazon Pay' });
    expect(resolveBody({ dir: 'credit', name: ' ' }, 100)).toEqual({ type: 'credit', amountMinor: 100, payee: null });
  });
});
