import type { z } from 'zod';
import type { BalanceCheckDto, DeviceDto, TelegramLinkStatus, TelegramSettings } from '@/contracts';
import { inr } from '@/common';
import { shortDate, usedText } from '@/features/account';

/** Pure view logic for the Devices page and the Telegram settings shared with the Setup guide (ui-spec 11, 16). */

export type Device = z.infer<typeof DeviceDto>;
export type LinkStatus = z.infer<typeof TelegramLinkStatus>;
export type TgSettings = z.infer<typeof TelegramSettings>;
export type BalanceCheck = z.infer<typeof BalanceCheckDto>;

/** m:ss, never negative. */
export function countdown(ms: number): string {
  const s = Math.max(0, Math.ceil(ms / 1000));
  return `${Math.floor(s / 60)}:${String(s % 60).padStart(2, '0')}`;
}

export const IDLE_OPTIONS = [{ value: 7, label: '7 days' }, { value: 30, label: '30 days' }, { value: 90, label: '90 days' }] as const;
export const DIGEST_OPTIONS: { value: TgSettings['digestMode']; label: string }[] = [{ value: 'off', label: 'Off' }, { value: 'daily', label: 'Daily, 9 pm' }, { value: 'twice', label: 'Twice a day' }];
export const AFTER_OPTIONS: { value: TgSettings['afterTag']; label: string }[] = [{ value: 'keep', label: 'Keep it' }, { value: 'line', label: 'One line' }, { value: 'delete', label: 'Delete it' }];


export type Ingest = { kind: 'none' } | { kind: 'live'; device: Device } | { kind: 'gone'; device: Device };
/** `GET /devices` lists the active token first. A cancelled token alone means capture has stopped. */
export function ingestState(devices: Device[]): Ingest {
  const live = devices.find((d) => !d.revokedAt);
  if (live) return { kind: 'live', device: live };
  const gone = devices[0];
  return gone ? { kind: 'gone', device: gone } : { kind: 'none' };
}
export const delayText = (s: number | null): string => (s === null ? '' : s < 120 ? ` · arrived ${s} s after it was sent` : ` · arrived ${Math.round(s / 60)} min after it was sent`);
export function receiveLead(i: Ingest, now: Date = new Date()): string {
  if (i.kind === 'none') return 'no token yet, make one below';
  if (i.kind === 'gone') return 'the token was cancelled, so nothing can send';
  const d = i.device;
  return d.lastSeenAt ? `last message ${usedText(d.lastSeenAt, now)}${delayText(d.lastDelaySeconds)}` : 'no message yet · send a test message to check the line';
}
export const receiveTitle = (i: Ingest): string => (i.kind === 'live' ? 'Receiving' : 'Not receiving');
/** `ledg_live_8f3a…b605 · made Oct 02 · last used today 6:42 pm` */
export function tokenLine(i: Ingest, now: Date = new Date()): string {
  if (i.kind === 'none') return 'no token yet';
  if (i.kind === 'gone') return 'cancelled';
  const d = i.device;
  return `${d.tokenHint} · made ${shortDate(d.rotatedAt ?? d.createdAt)} · ${d.lastSeenAt ? `last used ${usedText(d.lastSeenAt, now)}` : 'not used yet'}`;
}


type Tg = { kind: 'unlinked' } | { kind: 'in' } | { kind: 'out' };
export const tgState = (l: LinkStatus | undefined): Tg => (!l || !l.linked ? { kind: 'unlinked' } : l.sessionActive ? { kind: 'in' } : { kind: 'out' });
export const tgShort = (t: Tg): string => (t.kind === 'unlinked' ? 'unlinked' : t.kind === 'in' ? 'signed in' : 'signed out');
export function tgMeta(l: LinkStatus): string {
  if (!l.linked) return 'the bot will not send or accept anything';
  return `id ${l.telegramIdHint ?? '••••'} · linked ${l.linkedAt ? shortDate(l.linkedAt) : 'recently'}`;
}
export function sessionLead(l: LinkStatus, now: Date = new Date()): string {
  if (l.sessionActive) return `Since ${l.sessionSince ? usedText(l.sessionSince, now) : 'now'}.`;
  if (l.signInPausedUntil && new Date(l.signInPausedUntil) > now) return 'Sign-in is paused after three wrong codes. Try again in a few minutes.';
  return `Prompts wait here and are released when you send /signin.${l.heldCount > 0 ? ` ${l.heldCount} waiting.` : ''}`;
}


/** Aside word and row text for the last balance check. */
export function balanceView(c: BalanceCheck | undefined, now: Date = new Date()): { short: string; kind: 'ok' | 'wait' | 'none'; text: string } {
  if (!c) return { short: 'not checked', kind: 'none', text: 'no check yet · compare with your bank from the Ledger' };
  const when = usedText(c.checkedAt, now);
  if (Math.abs(c.gapMinor) < 100) return { short: 'matched', kind: 'ok', text: `${when} · the bank's number matched the ledger` };
  const diff = `${inr(Math.abs(c.gapMinor))} ${c.gapMinor < 0 ? 'lower' : 'higher'}`;
  if (c.status === 'booked' || c.status === 'resolved') return { short: 'checked', kind: 'ok', text: `${when} · the bank was ${diff}; the gap is ${c.status === 'booked' ? 'booked as Unaccounted' : 'closed'}` };
  if (c.status === 'ignored') return { short: 'checked', kind: 'ok', text: `${when} · the bank was ${diff}; you left the gap as it is` };
  return { short: 'gap open', kind: 'wait', text: `${when} · the bank is ${diff} than the ledger, still open` };
}
