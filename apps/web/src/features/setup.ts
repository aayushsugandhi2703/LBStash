import type { z } from 'zod';
import { groupIndian } from '@/common';
import type { SettingsDto } from '@/contracts';
import type { LinkStatus, TgSettings } from '@/features/devices';

/** Pure logic of the Setup guide (ui-spec 16): step states, text, numbers. */

export type Settings = z.infer<typeof SettingsDto>;

export type Step = 1 | 2 | 3 | 4;
export const STEPS = [
  { label: 'Connect Telegram', lead: 'Log each payment from Telegram, like /350 food or +1500 salary.' },
  { label: 'Telegram privacy', lead: 'Telegram keeps what it is sent, so the bot shows no bank details.' },
  { label: 'Your first month', lead: 'Start the plan and limits from real numbers.' },
] as const;
const DONE_LEAD = 'Everything is connected. Change it later in Devices and Telegram.';

export interface StepInput {
  step: Step;
  /** Furthest step reached so far (kept between visits): steps 2 and 3 count as done once moved past. */
  reached: Step;
  botSaved: boolean;
  linked: boolean;
  signed: boolean;
}
type StepWord = 'done' | 'now' | 'todo';
interface StepStates { done: [boolean, boolean, boolean]; words: [StepWord, StepWord, StepWord]; count: number; left: number }

/** `done` is checked before `now`, so a finished step you are standing on reads done. */
export function stepStates(i: StepInput): StepStates {
  const past = Math.max(i.step, i.reached);
  const done: StepStates['done'] = [i.botSaved && i.linked && i.signed, past > 2, past > 3];
  const words = done.map((d, n) => (d ? 'done' : i.step === n + 1 ? 'now' : 'todo')) as StepStates['words'];
  const count = done.filter(Boolean).length;
  return { done, words, count, left: 3 - count };
}
/** Anything that is not a number (a damaged saved value) falls back to step 1. */
export const clampStep = (n: number): Step => (Number.isFinite(n) ? (Math.min(4, Math.max(1, Math.round(n))) as Step) : 1);
export const stepLabel = (step: Step): string => (step === 4 ? 'ALL DONE' : `STEP ${step} OF 3`);
export const stepTitle = (step: Step): string => (step === 4 ? 'You are set up.' : STEPS[step - 1]!.label);
export const stepLead = (step: Step): string => (step === 4 ? DONE_LEAD : STEPS[step - 1]!.lead);
export const nextLabel = (step: Step): string => (step === 3 ? 'Finish' : 'Continue');

/** Step 1: the bot. */
const BOT_TOKEN_MIN = 20;
export const canSaveBot = (t: string): boolean => t.trim().length >= BOT_TOKEN_MIN;
/** Who may link: a Telegram @username (5-32 letters, digits, underscore) or a numeric id. The server checks again. */
export const canSaveOwner = (t: string): boolean => /^@?[A-Za-z][A-Za-z0-9_]{4,31}$/.test(t.trim()) || /^\d{5,15}$/.test(t.trim());
export function signWaitText(l: Pick<LinkStatus, 'linked' | 'signInPausedUntil'>, now: Date = new Date()): string {
  if (!l.linked) return 'link your account first';
  if (l.signInPausedUntil && new Date(l.signInPausedUntil) > now) return 'paused after 3 wrong codes · try again soon';
  return 'waiting for /signin and your code…';
}
export const linkedText = (l: Pick<LinkStatus, 'telegramUsername' | 'telegramIdHint'>): string =>
  `linked · ${l.telegramUsername ? `@${l.telegramUsername}` : 'your account'} · id ${l.telegramIdHint ?? '••••'}`;

/** Step 2: the preview box. */
export const previewLine2 = (reveal: boolean): string => (reveal ? 'tap Reveal to see the amount' : 'no amount, payee or balance');
export const previewButtons = (reveal: boolean): string[] => ['Food', 'Travel', 'Fun', 'Bills', '＋ New tag', ...(reveal ? ['Reveal'] : []), 'Later'];

/** Step 3: whole rupees as a canonical string ("50000"); shown with Indian grouping, ₹0 when empty. */
export const money = (rupees: string): string => `₹${groupIndian(rupees) || '0'}`;
export const alertText = (level: number): string => `${level}% used`;

/** All-done view. */
export interface SummaryRow { label: string; value: string; ok: boolean }
export function summaryRows(i: {
  telegram: boolean; link: Pick<LinkStatus, 'telegramUsername' | 'telegramIdHint'> | undefined; settings: Pick<TgSettings, 'allowReveal' | 'sessionIdleDays'> | undefined; opening: string; plan: string;
}): SummaryRow[] {
  const reveal = i.settings?.allowReveal ?? true;
  return [
    { label: 'Account secured', value: 'password + 2-step', ok: true },
    { label: 'Telegram', value: i.telegram ? `${i.link?.telegramUsername ? `@${i.link.telegramUsername}` : 'linked'} · id ${i.link?.telegramIdHint ?? '••••'}` : 'not finished', ok: i.telegram },
    { label: 'Log a payment', value: '/350 food · +1500 salary', ok: i.telegram },
    { label: 'Bot shows', value: reveal ? 'no details · Reveal on' : 'no details', ok: true },
    { label: 'Bot sign-out', value: `/signout or ${i.settings?.sessionIdleDays ?? 30} idle days`, ok: true },
    { label: 'Opening balance', value: money(i.opening), ok: true },
    { label: 'Planned this month', value: money(i.plan), ok: true },
  ];
}
