import type { z } from 'zod';
import type { AuditEntryDto, ExportRes, FactorsRes, PasskeyDto, SessionDto } from '@/contracts';
import { monthDay, timeOfDay, TZ } from '@/common';

/** Pure view logic for the Profile and Security pages (ui-spec 09, 10). */

type AuditEntry = z.infer<typeof AuditEntryDto>;
export type Session = z.infer<typeof SessionDto>;
export type Passkey = z.infer<typeof PasskeyDto>;
export type Factors = z.infer<typeof FactorsRes>;
export type ExportResult = z.infer<typeof ExportRes>;

export const isCode = (v: string): boolean => /^\d{6}$/.test(v);
export const isEmail = (v: string): boolean => /^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(v.trim());
/** The "Save name" row shows when the typed name differs from the saved one and is not empty. */
export const nameDirty = (name: string, saved: string): boolean => name.trim() !== saved && name.trim().length > 0;
const MIN_PASSWORD = 12;
export const passwordCounter = (len: number): string => (len >= MIN_PASSWORD ? `${len} characters · long enough` : `${len} of ${MIN_PASSWORD} characters`);
export const canSavePassword = (current: string, next: string, code: string): boolean => current.length > 0 && next.length >= MIN_PASSWORD && isCode(code);
export const canDelete = (typed: string, code: string): boolean => typed === 'DELETE' && isCode(code);

/** Wrong-code and lockout wording (design system §10: say how long). `null` when the error is not about a code. */
export function codeError(e: unknown): string | null {
  const x = e as { code?: string; details?: unknown; message?: string } | null;
  if (!x || typeof x !== 'object') return null;
  const d = (x.details && typeof x.details === 'object' ? x.details : {}) as { attemptsLeft?: unknown; retryAfterSeconds?: unknown };
  if (x.code === 'locked' && typeof d.retryAfterSeconds === 'number') return `Too many tries. Try again in ${waitText(d.retryAfterSeconds)}.`;
  if (x.code === 'two_factor_invalid') {
    const n = typeof d.attemptsLeft === 'number' ? d.attemptsLeft : null;
    return n === null ? 'That code did not work. Check your authenticator app and try again.' : n > 0 ? `That code did not work. ${n} ${n === 1 ? 'try' : 'tries'} left.` : 'Too many tries. Wait a minute, then try again.';
  }
  if (x.code === 'two_factor_required') return 'Enter the 6-digit code from your authenticator app.';
  return null;
}
export function waitText(s: number): string {
  if (s > 60) return `${Math.ceil(s / 60)} minutes`;
  const n = Math.max(1, Math.ceil(s));
  return `${n} ${n === 1 ? 'second' : 'seconds'}`;
}

const sentence = (s: string) => s.charAt(0).toUpperCase() + s.slice(1).toLowerCase();
/** "Oct 25", "Oct 02" (sentences and settings lines). */
export function shortDate(iso: string | Date, tz = TZ): string {
  const p = new Intl.DateTimeFormat('en-GB', { timeZone: tz, month: 'short', day: '2-digit' }).formatToParts(new Date(iso));
  return `${sentence(p.find((x) => x.type === 'month')?.value ?? '')} ${p.find((x) => x.type === 'day')?.value ?? ''}`;
}
const sameDay = (a: Date, b: Date, tz: string) => {
  const f = new Intl.DateTimeFormat('en-CA', { timeZone: tz });
  return f.format(a) === f.format(b);
};
/** "today 6:42 pm" when it is today, else "Oct 16". */
export function usedText(iso: string, now: Date = new Date(), tz = TZ): string {
  return sameDay(new Date(iso), now, tz) ? `today ${timeOfDay(iso, tz)}` : shortDate(iso, tz);
}
/** "active now", "12 minutes ago", "2 hours ago", else the date. */
export function activeText(iso: string, now: Date = new Date(), tz = TZ): string {
  const mins = Math.floor((now.getTime() - new Date(iso).getTime()) / 60_000);
  if (mins < 2) return 'active now';
  if (mins < 60) return `${mins} minutes ago`;
  if (mins < 24 * 60 && sameDay(new Date(iso), now, tz)) { const h = Math.floor(mins / 60); return `${h} ${h === 1 ? 'hour' : 'hours'} ago`; }
  return shortDate(iso, tz);
}

/** "just now", "5 minutes ago", "3 hours ago", "12 days ago", else the date. */
export function ago(iso: string, now: Date = new Date(), tz = TZ): string {
  const mins = Math.max(0, Math.floor((now.getTime() - new Date(iso).getTime()) / 60_000));
  if (mins < 2) return 'just now';
  if (mins < 60) return `${mins} minutes ago`;
  if (mins < 24 * 60) { const h = Math.floor(mins / 60); return `${h} ${h === 1 ? 'hour' : 'hours'} ago`; }
  const d = Math.floor(mins / (24 * 60));
  return d < 60 ? `${d} ${d === 1 ? 'day' : 'days'} ago` : shortDate(iso, tz);
}

export const sessionMeta = (s: Session, now: Date = new Date()): string => [s.ip, activeText(s.lastActiveAt, now)].filter(Boolean).join(' · ');
export const passkeyMeta = (p: Passkey, now: Date = new Date()): string =>
  `added ${shortDate(p.createdAt)} · ${p.lastUsedAt ? `used ${usedText(p.lastUsedAt, now)}` : 'not used yet'}`;

/** "Mac · Chrome" from a user-agent string: the default name of a new passkey. */
export function passkeyLabel(ua: string): string {
  const os = /iPhone|iPad/.test(ua) ? 'iPhone' : /Android/.test(ua) ? 'Android' : /Macintosh|Mac OS X/.test(ua) ? 'Mac' : /Windows/.test(ua) ? 'Windows' : /Linux/.test(ua) ? 'Linux' : 'This device';
  const browser = /Edg\//.test(ua) ? 'Edge' : /Firefox\//.test(ua) ? 'Firefox' : /Chrome\/|CriOS/.test(ua) ? 'Chrome' : /Safari\//.test(ua) ? 'Safari' : '';
  return `${os}${browser ? ` · ${browser}` : ''} · passkey`.slice(0, 60);
}

/** Aside line: sign-in is strong when the authenticator, a passkey and unused recovery codes all exist. */
export const signInStrong = (f: Factors): boolean => f.totp.enabled && f.passkeys.length > 0 && f.recoveryCodes.remaining > 0;
/** Passkeys are required to sign in, so the last one cannot be removed from here. */
export const canRemovePasskey = (count: number): boolean => count > 1;


const METHOD_WORDS: Record<string, string> = { totp: 'an authenticator code', passkey: 'a passkey', recovery: 'a recovery code' };
const LABELS: Record<string, string | ((m: Record<string, unknown>) => string)> = {
  register: 'Account created',
  'login.ok': (m) => (m.setup ? 'Signed in with a password, setup still to finish' : 'Password accepted'),
  'login.failed': (m) => (m.step === 'reset' ? 'Wrong recovery code on the reset page' : 'Wrong password'),
  'login.locked': 'Sign-in paused after too many wrong tries',
  '2fa.ok': (m) => `Signed in with ${METHOD_WORDS[String(m.method)] ?? 'a second step'}`,
  '2fa.failed': (m) => (m.method === 'recovery' ? 'Wrong recovery code' : m.method === 'passkey' ? 'A passkey was refused' : 'Wrong authenticator code'),
  '2fa.enabled': 'Authenticator app turned on',
  '2fa.replaced': 'Authenticator app replaced',
  'password.changed': (m) => (typeof m.signedOutOthers === 'number' && m.signedOutOthers > 0 ? `Password changed, ${m.signedOutOthers} other ${m.signedOutOthers === 1 ? 'browser' : 'browsers'} signed out` : 'Password changed'),
  'password.reset': 'Password reset with a recovery code',
  'passkey.added': 'Passkey added',
  'passkey.removed': 'Passkey removed',
  'recovery_codes.regenerated': 'New recovery codes made',
  'recovery_code.used': 'A recovery code was used up',
  'session.revoked': 'A browser was signed out',
  'sessions.revoked_others': 'Other browsers were signed out',
  'allowlist.changed': (m) => (m.count === 0 ? 'Address limit turned off' : `Allowed addresses changed (${String(m.count)})`),
  logout: 'Signed out',
  'email.change_requested': 'Email change asked for',
  'email.changed': 'Sign-in email changed',
  'profile.updated': 'Name changed',
  export: 'Data export made',
  'delete.scheduled': 'Account deletion scheduled',
  'delete.restored': 'Account deletion cancelled',
  'device.token_created': 'Bank-message token created',
  'device.token_rotated': 'Ingest token replaced',
  'device.revoked': 'Ingest token cancelled',
  'telegram.link': 'Telegram linked',
  'telegram.signin': 'Telegram bot signed in',
  'telegram.signin_paused': 'Bot sign-in paused after wrong codes',
  'telegram.signout': 'Telegram bot signed out',
  'telegram.signout_web': 'Telegram bot signed out from the web',
  'telegram.bot_replaced': 'Telegram bot replaced',
};
export function auditLabel(e: Pick<AuditEntry, 'action' | 'meta'>): string {
  const l = LABELS[e.action];
  if (typeof l === 'function') return l(e.meta ?? {});
  if (l) return l;
  const words = e.action.replace(/[._]/g, ' ');
  return words.charAt(0).toUpperCase() + words.slice(1);
}
/** The wrong-code and paused entries are drawn in the dark yellow of the design. */
export const auditWarn = (action: string): boolean => ['login.failed', 'login.locked', '2fa.failed', 'telegram.signin_paused'].includes(action);
export const auditPlace = (e: Pick<AuditEntry, 'action' | 'ip'>): string => (e.action.startsWith('telegram.') ? 'bot' : e.action.startsWith('device.') ? 'token' : e.ip ?? '');
/** OCT 18 · 6:42 PM */
export const auditWhen = (iso: string, tz = TZ): string => `${monthDay(iso, tz)} · ${timeOfDay(iso, tz).toUpperCase()}`;

/** Profile aside: member since / last export, read from the activity log (newest first, `limit` entries). */
export function profileSummary(entries: Pick<AuditEntry, 'action' | 'at'>[], limit: number, tz = TZ): { memberSince: string; lastExport: string } {
  const reg = [...entries].reverse().find((e) => e.action === 'register');
  const exp = entries.find((e) => e.action === 'export');
  const complete = entries.length < limit; // the whole log fits: absence means "never"
  return {
    memberSince: reg ? monthDay(reg.at, tz).toLowerCase() : '—',
    lastExport: exp ? monthDay(exp.at, tz).toLowerCase() : complete ? 'never' : '—',
  };
}


export const formatBytes = (n: number): string => (n < 1024 ? `${n} B` : n < 1024 * 1024 ? `${Math.max(1, Math.round(n / 1024))} KB` : `${(n / 1024 / 1024).toFixed(1)} MB`);

/** The download: one JSON document built in the browser from the `POST /account/export` answer. */
export function buildExportFile(res: ExportResult): { filename: string; text: string; bytes: number; entries: number } {
  const text = `${JSON.stringify({ exportedAt: res.exportedAt, entries: res.entries, parts: res.parts }, null, 2)}\n`;
  return { filename: res.filename, text, bytes: new TextEncoder().encode(text).length, entries: res.entries };
}
export const exportLine = (f: { filename: string; entries: number; bytes: number }): string => `${f.filename} · ${f.entries} ${f.entries === 1 ? 'entry' : 'entries'} · ${formatBytes(f.bytes)}`;

/** The address box: one per line, commas and spaces also split, blanks and repeats dropped. */
export const parseIps = (text: string): string[] => [...new Set(text.split(/[\s,;]+/).map((x) => x.trim()).filter(Boolean))];
