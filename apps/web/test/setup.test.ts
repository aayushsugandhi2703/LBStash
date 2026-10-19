import { describe, expect, it } from 'vitest';
import type { Device, LinkStatus } from '@/features/devices';
import { alertText, canSaveBot, clampStep, linkedText, money, nextLabel, phoneHeard, previewButtons, previewLine2, signWaitText, type StepInput, stepLabel, stepLead, stepStates, stepTitle, summaryRows, testReceived } from '@/features/setup';

const base: StepInput = { step: 1, reached: 1, token: false, test: false, botSaved: false, linked: false, signed: false };
const device = (over: Partial<Device> = {}): Device => ({
  id: 'd1', name: 'iPhone', lastSeenAt: null, revokedAt: null, createdAt: '2026-10-02T09:00:00Z', tokenHint: 'ledg_live_8f3a…b605', rotatedAt: null,
  lastDelaySeconds: null, allowedSenders: [], lastTest: null, ...over,
});
const link = (over: Partial<LinkStatus> = {}): LinkStatus => ({
  botSaved: true, botUsername: 'my_bot', linked: false, telegramIdHint: null, telegramUsername: null, linkedAt: null, sessionActive: false,
  sessionSince: null, lastSeenAt: null, signInPausedUntil: null, pairingPending: false, heldCount: 0, ...over,
});

describe('step states', () => {
  it('starts with nothing done and the open step marked now', () => {
    const s = stepStates(base);
    expect(s.words).toEqual(['now', 'todo', 'todo', 'todo']);
    expect(s.count).toBe(0);
    expect(s.left).toBe(4);
  });
  it('needs both the token and the test message for step 1', () => {
    expect(stepStates({ ...base, token: true }).words[0]).toBe('now');
    expect(stepStates({ ...base, test: true }).done[0]).toBe(false);
    expect(stepStates({ ...base, token: true, test: true }).words[0]).toBe('done');
  });
  it('reads done before now, so a finished step you stand on says done', () => {
    expect(stepStates({ ...base, step: 2, botSaved: true, linked: true, signed: true }).words).toEqual(['todo', 'done', 'todo', 'todo']);
  });
  it('needs the bot saved, linked and signed in for step 2', () => {
    expect(stepStates({ ...base, botSaved: true, linked: true }).done[1]).toBe(false);
  });
  it('counts steps 3 and 4 as done once moved past, including when you jump back', () => {
    expect(stepStates({ ...base, step: 4, reached: 4 }).done).toEqual([false, false, true, false]);
    expect(stepStates({ ...base, step: 5, reached: 5 }).count).toBe(2);
    expect(stepStates({ ...base, step: 4, reached: 5 }).count).toBe(2);
    expect(stepStates({ ...base, step: 1, reached: 5 }).count).toBe(2);
  });
});

describe('step headings', () => {
  it('labels, titles and leads follow the design, and the last view says all done', () => {
    expect(stepLabel(2)).toBe('STEP 2 OF 4');
    expect(stepLabel(5)).toBe('ALL DONE');
    expect(stepTitle(3)).toBe('Telegram privacy');
    expect(stepTitle(5)).toBe('You are set up.');
    expect(stepLead(4)).toBe('So the plan, the limits and the balance start from real numbers.');
    expect(nextLabel(3)).toBe('Continue');
    expect(nextLabel(4)).toBe('Finish');
  });
  it('keeps a step between 1 and 5', () => {
    expect([clampStep(0), clampStep(3), clampStep(9), clampStep(2.4)]).toEqual([1, 3, 5, 2]);
    expect(clampStep(Number('x'))).toBe(1);
  });
});

describe('the phone test', () => {
  it('is waiting until a message from the phone arrives', () => {
    expect(phoneHeard(undefined)).toBe(false);
    expect(phoneHeard(device())).toBe(false);
    expect(testReceived(device())).toBeNull();
  });
  it('ignores the test the Devices page sends from the web', () => {
    const d = device({ lastTest: { at: '2026-10-18T10:00:00Z', source: 'web', delaySeconds: 0, amountMinor: 100 } });
    expect(phoneHeard(d)).toBe(false);
    expect(testReceived(d)).toBeNull();
  });
  it('words the one-rupee test with how long it took', () => {
    const d = device({ lastSeenAt: '2026-10-18T10:00:14Z', lastTest: { at: '2026-10-18T10:00:14Z', source: 'device', delaySeconds: 14, amountMinor: 100 } });
    expect(testReceived(d)).toBe('received · −₹1.00 · test message · arrived 14 s after it was sent');
    const slow = device({ lastSeenAt: 'x', lastTest: { at: 'x', source: 'device', delaySeconds: 600, amountMinor: 100 } });
    expect(testReceived(slow)).toContain('arrived 10 min after');
  });
  it('accepts a real bank message as proof that the line works', () => {
    expect(testReceived(device({ lastSeenAt: '2026-10-18T10:00:14Z', lastDelaySeconds: 30 }))).toBe('received · your first message was read · arrived 30 s after it was sent');
  });
  it('does not count a cancelled token', () => {
    expect(phoneHeard(device({ lastSeenAt: 'x', revokedAt: 'y' }))).toBe(false);
  });
});

describe('telegram steps', () => {
  it('enables Save token from 20 characters', () => {
    expect(canSaveBot('123456789:AAH')).toBe(false);
    expect(canSaveBot('123456789:AAHdLxk3-abcdefghij')).toBe(true);
    expect(canSaveBot(`  ${'1'.repeat(19)}  `)).toBe(false);
  });
  it('says what sign-in waits for', () => {
    const now = new Date('2026-10-18T10:00:00Z');
    expect(signWaitText(link(), now)).toBe('link your account first');
    expect(signWaitText(link({ linked: true }), now)).toBe('waiting for /signin and your code…');
    expect(signWaitText(link({ linked: true, signInPausedUntil: '2026-10-18T10:10:00Z' }), now)).toContain('paused after three wrong codes');
    expect(signWaitText(link({ linked: true, signInPausedUntil: '2026-10-18T09:50:00Z' }), now)).toBe('waiting for /signin and your code…');
  });
  it('words the linked line from the masked id only', () => {
    expect(linkedText({ telegramUsername: 'aayush', telegramIdHint: '••4821' })).toBe('linked · @aayush · id ••4821 · private chat only');
    expect(linkedText({ telegramUsername: null, telegramIdHint: null })).toBe('linked · your account · id •••• · private chat only');
  });
});

describe('privacy preview', () => {
  it('shows Reveal only when it is on, and changes line two', () => {
    expect(previewButtons(true)).toEqual(['Food', 'Travel', 'Fun', 'Bills', '＋ New tag', 'Reveal', 'Later']);
    expect(previewButtons(false)).toEqual(['Food', 'Travel', 'Fun', 'Bills', '＋ New tag', 'Later']);
    expect(previewLine2(true)).toBe('tap Reveal to see the amount for 30 seconds');
    expect(previewLine2(false)).toBe('no amount, no payee, no balance');
  });
});

describe('first month numbers', () => {
  it('groups whole rupees the Indian way and shows ₹0 when empty', () => {
    expect(money('')).toBe('₹0');
    expect(money('50000')).toBe('₹50,000');
    expect(money('1250000')).toBe('₹12,50,000');
    expect(alertText(80)).toBe('80% used');
  });
});

describe('all-done summary', () => {
  const settings = { allowReveal: true, sessionIdleDays: 30 };
  it('lists seven rows and marks unfinished steps', () => {
    const rows = summaryRows({ s1: false, s2: false, link: undefined, settings, opening: '', plan: '50000' });
    expect(rows).toHaveLength(7);
    expect(rows[1]).toEqual({ label: 'iPhone connected', value: 'not finished', ok: false });
    expect(rows[2]).toEqual({ label: 'Telegram linked and signed in', value: 'not finished', ok: false });
    expect(rows[5]).toEqual({ label: 'Opening balance (bank account)', value: '₹0', ok: true });
    expect(rows[6]?.value).toBe('₹50,000');
  });
  it('fills the finished rows from what is connected', () => {
    const rows = summaryRows({ s1: true, s2: true, link: { telegramUsername: 'aayush', telegramIdHint: '••4821' }, settings: { allowReveal: false, sessionIdleDays: 90 }, opening: '27300', plan: '50000' });
    expect(rows[1]?.value).toBe('first message received');
    expect(rows[2]?.value).toBe('@aayush · id ••4821');
    expect(rows[3]?.value).toBe('No details at all');
    expect(rows[4]?.value).toBe('until /signout, or 90 idle days');
    expect(rows[5]?.value).toBe('₹27,300');
  });
});
