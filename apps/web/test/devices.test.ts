import { describe, expect, it } from 'vitest';
import { type BalanceCheck, balanceView, countdown, delayText, type Device, ingestState, type LinkStatus, receiveLead, receiveTitle, sessionLead, tgMeta, tgShort, tgState, tokenLine } from '@/features/devices';

// 2026-10-18 13:20 UTC is 6:50 pm in India
const now = new Date('2026-10-18T13:20:00Z');
const dev = (over: Partial<Device> = {}): Device => ({
  id: 'd1', name: 'iPhone', lastSeenAt: '2026-10-18T13:12:00Z', revokedAt: null, createdAt: '2026-10-02T10:00:00Z', tokenHint: 'ledg_live_8f3a…b605',
  rotatedAt: null, lastDelaySeconds: 14, allowedSenders: [], lastTest: null, ...over,
});
const link = (over: Partial<LinkStatus> = {}): LinkStatus => ({
  botSaved: true, botUsername: 'my_bot', ownerTelegram: null, linked: true, telegramIdHint: '••4821', telegramUsername: null, linkedAt: '2026-10-04T10:00:00Z',
  sessionActive: true, sessionSince: '2026-10-18T13:01:00Z', lastSeenAt: null, signInPausedUntil: null, pairingPending: false, heldCount: 0, ...over,
});
const check = (over: Partial<BalanceCheck> = {}): BalanceCheck => ({
  id: 'c1', bankBalanceMinor: 3_759_100, transactionsBalanceMinor: 3_759_100, gapMinor: 0, source: 'manual', status: 'resolved',
  checkedAt: '2026-10-18T13:20:00Z', asOf: '2026-10-18T13:20:00Z', transactionId: null, graceEndsAt: null, ...over,
});

describe('countdown', () => {
  it('counts m:ss and never goes negative', () => {
    expect(countdown(292_000)).toBe('4:52');
    expect(countdown(300_000)).toBe('5:00');
    expect(countdown(999)).toBe('0:01');
    expect(countdown(-5000)).toBe('0:00');
  });
});

describe('iPhone capture', () => {
  it('a live token comes first; only a cancelled one means capture stopped; none at all is its own state', () => {
    expect(ingestState([dev()]).kind).toBe('live');
    expect(ingestState([dev(), dev({ id: 'old', revokedAt: '2026-10-10T10:00:00Z' })]).kind).toBe('live');
    expect(ingestState([dev({ revokedAt: '2026-10-10T10:00:00Z' })]).kind).toBe('gone');
    expect(ingestState([]).kind).toBe('none');
  });
  it('words the delay in seconds, then minutes', () => {
    expect(delayText(null)).toBe('');
    expect(delayText(14)).toBe(' · arrived 14 s after it was sent');
    expect(delayText(600)).toBe(' · arrived 10 min after it was sent');
  });
  it('says when the last message came, or why nothing can', () => {
    expect(receiveLead(ingestState([dev()]), now)).toBe('last message today 6:42 pm · arrived 14 s after it was sent');
    expect(receiveLead(ingestState([dev({ lastSeenAt: null })]), now)).toBe('no message yet · send a test message to check the line');
    expect(receiveLead(ingestState([dev({ revokedAt: '2026-10-10T10:00:00Z' })]), now)).toBe('the token was cancelled, so nothing can send');
    expect(receiveLead(ingestState([]), now)).toBe('no token yet, make one below');
    expect(receiveTitle(ingestState([dev()]))).toBe('Receiving');
    expect(receiveTitle(ingestState([]))).toBe('Not receiving');
  });
  it('shows the masked token with when it was made and last used', () => {
    expect(tokenLine(ingestState([dev()]), now)).toBe('ledg_live_8f3a…b605 · made Oct 02 · last used today 6:42 pm');
    expect(tokenLine(ingestState([dev({ rotatedAt: '2026-10-09T10:00:00Z', lastSeenAt: null })]), now)).toBe('ledg_live_8f3a…b605 · made Oct 09 · not used yet');
    expect(tokenLine(ingestState([dev({ revokedAt: '2026-10-10T10:00:00Z' })]), now)).toBe('cancelled');
    expect(tokenLine({ kind: 'none' }, now)).toBe('no token yet');
  });
});

describe('Telegram', () => {
  it('is unlinked, signed in or signed out', () => {
    expect(tgState(undefined).kind).toBe('unlinked');
    expect(tgState(link({ linked: false })).kind).toBe('unlinked');
    expect(tgState(link()).kind).toBe('in');
    expect(tgState(link({ sessionActive: false })).kind).toBe('out');
    expect(tgShort(tgState(link({ sessionActive: false })))).toBe('signed out');
  });
  it('shows only the hint of the id', () => {
    expect(tgMeta(link())).toBe('id ••4821 · linked Oct 04');
    expect(tgMeta(link({ linked: false }))).toBe('the bot will not send or accept anything');
  });
  it('explains the bot session, including a paused sign-in and held prompts', () => {
    expect(sessionLead(link(), now)).toBe('Since today 6:31 pm.');
    expect(sessionLead(link({ sessionActive: false, heldCount: 2 }), now)).toBe('Prompts wait here and are released when you send /signin. 2 waiting.');
    expect(sessionLead(link({ sessionActive: false, signInPausedUntil: '2026-10-18T13:30:00Z' }), now)).toContain('paused after three wrong codes');
    expect(sessionLead(link({ sessionActive: false, signInPausedUntil: '2026-10-18T13:10:00Z' }), now)).toContain('released when you send /signin');
  });
});

describe('balance check line', () => {
  it('no check yet', () => {
    expect(balanceView(undefined, now)).toMatchObject({ short: 'not checked', kind: 'none' });
  });
  it('a gap under one rupee counts as matched', () => {
    expect(balanceView(check({ gapMinor: 50 }), now)).toEqual({ short: 'matched', kind: 'ok', text: "today 6:50 pm · the bank's number matched the transactions" });
  });
  it('an open gap waits; a booked or closed one is finished business', () => {
    expect(balanceView(check({ gapMinor: -18_000, status: 'open' }), now)).toEqual({ short: 'gap open', kind: 'wait', text: 'today 6:50 pm · the bank is ₹180 lower than the transactions, still open' });
    expect(balanceView(check({ gapMinor: -18_000, status: 'booked' }), now).text).toBe('today 6:50 pm · the bank was ₹180 lower; the gap is booked as Unaccounted');
    expect(balanceView(check({ gapMinor: 25_000, status: 'resolved' }), now).text).toBe('today 6:50 pm · the bank was ₹250 higher; the gap is closed');
    expect(balanceView(check({ gapMinor: -18_000, status: 'ignored' }), now)).toMatchObject({ short: 'checked', kind: 'ok' });
  });
});
