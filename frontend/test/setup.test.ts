import { describe, expect, it } from 'vitest';
import type { LinkStatus } from '@/features/devices';
import { alertText, canSaveBot, canSaveOwner, clampStep, linkedText, money, nextLabel, ownerHint, previewButtons, previewLine2, signWaitText, type StepInput, stepLabel, stepLead, stepStates, stepTitle, summaryRows } from '@/features/setup';

const base: StepInput = { step: 1, reached: 1, botSaved: false, linked: false, signed: false };
const link = (over: Partial<LinkStatus> = {}): LinkStatus => ({
  botSaved: true, botUsername: 'my_bot', ownerTelegram: null, linked: false, telegramIdHint: null, telegramUsername: null, linkedAt: null, sessionActive: false,
  sessionSince: null, lastSeenAt: null, signInPausedUntil: null, pairingPending: false, heldCount: 0, ...over,
});

describe('step states', () => {
  it('starts with nothing done and the open step marked now', () => {
    const s = stepStates(base);
    expect(s.words).toEqual(['now', 'todo', 'todo']);
    expect(s.count).toBe(0);
    expect(s.left).toBe(3);
  });
  it('needs the bot saved, linked and signed in for step 1', () => {
    expect(stepStates({ ...base, botSaved: true, linked: true }).done[0]).toBe(false);
    expect(stepStates({ ...base, botSaved: true, linked: true, signed: true }).words[0]).toBe('done');
  });
  it('reads done before now, so a finished step you stand on says done', () => {
    expect(stepStates({ ...base, step: 1, botSaved: true, linked: true, signed: true }).words).toEqual(['done', 'todo', 'todo']);
  });
  it('counts steps 2 and 3 as done once moved past, including when you jump back', () => {
    expect(stepStates({ ...base, step: 3, reached: 3 }).done).toEqual([false, true, false]);
    expect(stepStates({ ...base, step: 4, reached: 4 }).count).toBe(2);
    expect(stepStates({ ...base, step: 1, reached: 4 }).count).toBe(2);
  });
});

describe('step headings', () => {
  it('labels, titles and leads follow the design, and the last view says all done', () => {
    expect(stepLabel(2)).toBe('STEP 2 OF 3');
    expect(stepLabel(4)).toBe('ALL DONE');
    expect(stepTitle(2)).toBe('Telegram privacy');
    expect(stepTitle(4)).toBe('You are set up.');
    expect(stepLead(3)).toBe('Start the plan and limits from real numbers.');
    expect(nextLabel(2)).toBe('Continue');
    expect(nextLabel(3)).toBe('Finish');
  });
  it('keeps a step between 1 and 4', () => {
    expect([clampStep(0), clampStep(3), clampStep(9), clampStep(2.4)]).toEqual([1, 3, 4, 2]);
    expect(clampStep(Number('x'))).toBe(1);
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
    expect(signWaitText(link({ linked: true, signInPausedUntil: '2026-10-18T10:10:00Z' }), now)).toContain('paused after 3 wrong codes');
    expect(signWaitText(link({ linked: true, signInPausedUntil: '2026-10-18T09:50:00Z' }), now)).toBe('waiting for /signin and your code…');
  });
  it('words the linked line from the masked id only', () => {
    expect(linkedText({ telegramUsername: 'aayush', telegramIdHint: '••4821' })).toBe('linked · @aayush · id ••4821');
    expect(linkedText({ telegramUsername: null, telegramIdHint: null })).toBe('linked · your account · id ••••');
  });
});

describe('telegram owner', () => {
  it('takes a username, a pasted t.me link or a numeric id, and nothing else', () => {
    for (const ok of ['@aayush_s', 'aayush_s', ' t.me/aayush_s ', 'https://t.me/aayush_s', '123456789']) expect(canSaveOwner(ok), ok).toBe(true);
    for (const bad of ['', '@ab', 'two words', 'bad-name!', '12']) expect(canSaveOwner(bad), bad).toBe(false);
  });
  it('says what is wrong, including pasting the bot instead of yourself', () => {
    expect(ownerHint('', 'my_bot')).toBeNull();
    expect(ownerHint('@aayush_s', 'my_bot')).toBeNull();
    expect(ownerHint('@My_Bot', 'my_bot')).toMatch(/your bot/);
    expect(ownerHint('ab', 'my_bot')).toMatch(/@username/);
  });
});

describe('privacy preview', () => {
  it('shows Reveal only when it is on, and changes line two', () => {
    expect(previewButtons(true)).toEqual(['Food', 'Travel', 'Fun', 'Bills', '＋ New tag', 'Reveal', 'Later']);
    expect(previewButtons(false)).toEqual(['Food', 'Travel', 'Fun', 'Bills', '＋ New tag', 'Later']);
    expect(previewLine2(true)).toBe('tap Reveal to see the amount');
    expect(previewLine2(false)).toBe('no amount, payee or balance');
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
    const rows = summaryRows({ telegram: false, link: undefined, settings, opening: '', plan: '50000' });
    expect(rows).toHaveLength(7);
    expect(rows[1]).toEqual({ label: 'Telegram', value: 'not finished', ok: false });
    expect(rows[2]).toEqual({ label: 'Log a payment', value: '/350 food · +1500 salary', ok: false });
    expect(rows[5]).toEqual({ label: 'Opening balance', value: '₹0', ok: true });
    expect(rows[6]?.value).toBe('₹50,000');
  });
  it('fills the finished rows from what is connected', () => {
    const rows = summaryRows({ telegram: true, link: { telegramUsername: 'aayush', telegramIdHint: '••4821' }, settings: { allowReveal: false, sessionIdleDays: 90 }, opening: '27300', plan: '50000' });
    expect(rows[1]?.value).toBe('@aayush · id ••4821');
    expect(rows[3]?.value).toBe('no details');
    expect(rows[4]?.value).toBe('/signout or 90 idle days');
    expect(rows[5]?.value).toBe('₹27,300');
  });
});
