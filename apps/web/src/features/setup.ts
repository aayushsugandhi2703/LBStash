import type { z } from 'zod';
import { formatInr, groupIndian } from '@/common';
import type { SettingsDto } from '@/contracts';
import { delayText, type Device, type LinkStatus, type TgSettings } from '@/features/devices';

/** Pure logic of the Setup guide (ui-spec 16): step states, text, numbers. */

export type Settings = z.infer<typeof SettingsDto>;

export type Step = 1 | 2 | 3 | 4 | 5;
export const STEPS = [
  { label: 'Connect your iPhone', lead: 'Your iPhone sends each bank debit and credit message to your server. Set up once in the Shortcuts app.' },
  { label: 'Connect Telegram', lead: 'Telegram shows each payment with category buttons so you can tag it. You need your own bot, one link step and a sign-in.' },
  { label: 'Telegram privacy', lead: 'Telegram keeps what it is sent, so messages carry no bank details. Choose the one optional exception.' },
  { label: 'Your first month', lead: 'So the plan, the limits and the balance start from real numbers.' },
] as const;
const DONE_LEAD = 'This is what is connected. Redo any step from Devices and Telegram in the Account menu.';

export interface StepInput {
  step: Step;
  /** Furthest step reached so far (kept between visits): steps 3 and 4 count as done once moved past. */
  reached: Step;
  /** An active token exists. */
  token: boolean;
  /** A real test message arrived from the phone. */
  test: boolean;
  botSaved: boolean;
  linked: boolean;
  signed: boolean;
}
type StepWord = 'done' | 'now' | 'todo';
interface StepStates { done: [boolean, boolean, boolean, boolean]; words: [StepWord, StepWord, StepWord, StepWord]; count: number; left: number }

/** `done` is checked before `now`, so a finished step you are standing on reads done. */
export function stepStates(i: StepInput): StepStates {
  const past = Math.max(i.step, i.reached);
  const done: StepStates['done'] = [i.token && i.test, i.botSaved && i.linked && i.signed, past > 3, past > 4];
  const words = done.map((d, n) => (d ? 'done' : i.step === n + 1 ? 'now' : 'todo')) as StepStates['words'];
  const count = done.filter(Boolean).length;
  return { done, words, count, left: 4 - count };
}
/** Anything that is not a number (a damaged saved value) falls back to step 1. */
export const clampStep = (n: number): Step => (Number.isFinite(n) ? (Math.min(5, Math.max(1, Math.round(n))) as Step) : 1);
export const stepLabel = (step: Step): string => (step === 5 ? 'ALL DONE' : `STEP ${step} OF 4`);
export const stepTitle = (step: Step): string => (step === 5 ? 'You are set up.' : STEPS[step - 1]!.label);
export const stepLead = (step: Step): string => (step === 5 ? DONE_LEAD : STEPS[step - 1]!.lead);
export const nextLabel = (step: Step): string => (step === 4 ? 'Finish' : 'Continue');

/** Step 1: a message from the phone has reached the server (the one-rupee test text, or any bank alert read since). */
export const phoneHeard = (d: Device | undefined): boolean => Boolean(d && !d.revokedAt && (d.lastSeenAt || d.lastTest?.source === 'device'));

/** Step 1: the live test line, or null while nothing has arrived. */
export function testReceived(d: Device | undefined): string | null {
  if (!d || !phoneHeard(d)) return null;
  const t = d.lastTest;
  if (t?.source === 'device') return `received · −${formatInr(t.amountMinor ?? 100, { symbol: true, forceDecimals: true })} · test message${delayText(t.delaySeconds)}`;
  return `received · your first message was read${delayText(d.lastDelaySeconds)}`;
}

/** The importable Shortcut (built and signed by scripts/make-shortcut.py). */
export const SHORTCUT_FILE = '/ledger-capture.shortcut';

/** Step 2. */
const BOT_TOKEN_MIN = 20;
export const canSaveBot = (t: string): boolean => t.trim().length >= BOT_TOKEN_MIN;
export function signWaitText(l: Pick<LinkStatus, 'linked' | 'signInPausedUntil'>, now: Date = new Date()): string {
  if (!l.linked) return 'link your account first';
  if (l.signInPausedUntil && new Date(l.signInPausedUntil) > now) return 'sign-in is paused after three wrong codes · try again in a few minutes';
  return 'waiting for /signin and your code…';
}
export const linkedText = (l: Pick<LinkStatus, 'telegramUsername' | 'telegramIdHint'>): string =>
  `linked · ${l.telegramUsername ? `@${l.telegramUsername}` : 'your account'} · id ${l.telegramIdHint ?? '••••'} · private chat only`;

/** Step 3: the preview box. */
export const previewLine2 = (reveal: boolean): string => (reveal ? 'tap Reveal to see the amount for 30 seconds' : 'no amount, no payee, no balance');
export const previewButtons = (reveal: boolean): string[] => ['Food', 'Travel', 'Fun', 'Bills', '＋ New tag', ...(reveal ? ['Reveal'] : []), 'Later'];

/** Step 4: whole rupees as a canonical string ("50000"); shown with Indian grouping, ₹0 when empty. */
export const money = (rupees: string): string => `₹${groupIndian(rupees) || '0'}`;
export const alertText = (level: number): string => `${level}% used`;

/** All-done view. */
export interface SummaryRow { label: string; value: string; ok: boolean }
export function summaryRows(i: {
  s1: boolean; s2: boolean; link: Pick<LinkStatus, 'telegramUsername' | 'telegramIdHint'> | undefined; settings: Pick<TgSettings, 'allowReveal' | 'sessionIdleDays'> | undefined; opening: string; plan: string;
}): SummaryRow[] {
  const reveal = i.settings?.allowReveal ?? true;
  return [
    { label: 'Account secured', value: 'password + second step', ok: true },
    { label: 'iPhone connected', value: i.s1 ? 'first message received' : 'not finished', ok: i.s1 },
    { label: 'Telegram linked and signed in', value: i.s2 ? `${i.link?.telegramUsername ? `@${i.link.telegramUsername}` : 'linked'} · id ${i.link?.telegramIdHint ?? '••••'}` : 'not finished', ok: i.s2 },
    { label: 'Telegram shows', value: reveal ? 'No details, Reveal on' : 'No details at all', ok: true },
    { label: 'Bot session', value: `until /signout, or ${i.settings?.sessionIdleDays ?? 30} idle days`, ok: true },
    { label: 'Opening balance (bank account)', value: money(i.opening), ok: true },
    { label: 'Money to plan this month', value: money(i.plan), ok: true },
  ];
}
