import { describe, expect, it } from 'vitest';
import { activeText, ago, auditLabel, auditPlace, auditWarn, auditWhen, buildExportFile, canDelete, canRemovePasskey, canSavePassword, codeError, exportLine, type Factors, formatBytes, isCode, isEmail, nameDirty, passkeyLabel, passkeyMeta, passwordCounter, profileSummary, sessionMeta, shortDate, signInStrong, usedText, waitText } from '@/features/account';

// 2026-10-18 13:20 UTC is 6:50 pm in India
const now = new Date('2026-10-18T13:20:00Z');
const minutesAgo = (m: number) => new Date(now.getTime() - m * 60_000).toISOString();

describe('form rules', () => {
  it('a code is exactly six digits', () => {
    expect(isCode('123456')).toBe(true);
    expect(['12345', '1234567', '12345a', ''].some(isCode)).toBe(false);
  });
  it('an email needs one @ and a dot after it', () => {
    expect(isEmail(' you@example.com ')).toBe(true);
    expect(['you@example', 'you example.com', '@a.b'].some(isEmail)).toBe(false);
  });
  it('the save-name row shows for a changed, non-empty name only', () => {
    expect(nameDirty('Asha', 'Aayush')).toBe(true);
    expect(nameDirty('  Aayush ', 'Aayush')).toBe(false);
    expect(nameDirty('   ', 'Aayush')).toBe(false);
  });
  it('the password needs the current one, 12 characters and a code', () => {
    expect(canSavePassword('old', 'x'.repeat(12), '123456')).toBe(true);
    expect(canSavePassword('', 'x'.repeat(12), '123456')).toBe(false);
    expect(canSavePassword('old', 'x'.repeat(11), '123456')).toBe(false);
    expect(canSavePassword('old', 'x'.repeat(12), '12345')).toBe(false);
    expect(passwordCounter(7)).toBe('7 of 12 characters');
    expect(passwordCounter(12)).toBe('12 characters · long enough');
  });
  it('deleting needs the word DELETE exactly and a code', () => {
    expect(canDelete('DELETE', '123456')).toBe(true);
    expect(canDelete('delete', '123456')).toBe(false);
    expect(canDelete('DELETE', '')).toBe(false);
  });
  it('the last passkey cannot be removed', () => {
    expect(canRemovePasskey(1)).toBe(false);
    expect(canRemovePasskey(2)).toBe(true);
  });
});

describe('code errors', () => {
  it('says how many tries are left and how long a lockout lasts', () => {
    expect(codeError({ code: 'two_factor_invalid', details: { attemptsLeft: 2 } })).toBe('That code did not work. 2 tries left.');
    expect(codeError({ code: 'two_factor_invalid', details: { attemptsLeft: 1 } })).toBe('That code did not work. 1 try left.');
    expect(codeError({ code: 'two_factor_invalid', details: { attemptsLeft: 0 } })).toBe('Too many tries. Wait a minute, then try again.');
    expect(codeError({ code: 'two_factor_invalid' })).toContain('Check your authenticator app');
    expect(codeError({ code: 'locked', details: { retryAfterSeconds: 900 } })).toBe('Too many tries. Try again in 15 minutes.');
    expect(codeError({ code: 'two_factor_required' })).toBe('Enter the 6-digit code from your authenticator app.');
  });
  it('leaves other errors to the caller', () => {
    expect(codeError({ code: 'validation_failed' })).toBeNull();
    expect(codeError(null)).toBeNull();
    expect(codeError('boom')).toBeNull();
  });
  it('rounds waits to seconds or minutes', () => {
    expect(waitText(30)).toBe('30 seconds');
    expect(waitText(0.2)).toBe('1 second');
    expect(waitText(61)).toBe('2 minutes');
  });
});

describe('dates in India time', () => {
  it('writes short dates for sentences', () => {
    expect(shortDate('2026-10-02T10:00:00Z')).toBe('Oct 02');
    expect(shortDate('2026-10-17T20:00:00Z')).toBe('Oct 18'); // past midnight in India
  });
  it('"today 6:42 pm" on the same day, the date otherwise', () => {
    expect(usedText('2026-10-18T13:12:00Z', now)).toBe('today 6:42 pm');
    expect(usedText('2026-10-16T13:12:00Z', now)).toBe('Oct 16');
  });
  it('says how long ago a browser was active', () => {
    expect(activeText(minutesAgo(1), now)).toBe('active now');
    expect(activeText(minutesAgo(12), now)).toBe('12 minutes ago');
    expect(activeText(minutesAgo(120), now)).toBe('2 hours ago');
    expect(activeText(minutesAgo(60 * 24 * 7), now)).toBe('Oct 11');
  });
  it('ago counts days up to two months', () => {
    expect(ago(minutesAgo(1), now)).toBe('just now');
    expect(ago(minutesAgo(59), now)).toBe('59 minutes ago');
    expect(ago(minutesAgo(60), now)).toBe('1 hour ago');
    expect(ago(minutesAgo(60 * 24 * 12), now)).toBe('12 days ago');
    expect(ago(minutesAgo(60 * 24), now)).toBe('1 day ago');
    expect(ago(minutesAgo(60 * 24 * 90), now)).toBe('Jul 20');
  });
  it('lists time and place for the activity log', () => {
    expect(auditWhen('2026-10-18T13:12:00Z')).toBe('OCT 18 · 6:42 PM');
    expect(auditPlace({ action: 'telegram.link', ip: '1.2.3.4' })).toBe('bot');
    expect(auditPlace({ action: 'device.revoked', ip: '1.2.3.4' })).toBe('phone');
    expect(auditPlace({ action: 'login.ok', ip: '1.2.3.4' })).toBe('1.2.3.4');
    expect(auditPlace({ action: 'login.ok', ip: null })).toBe('');
  });
});

describe('sessions and passkeys', () => {
  it('joins address and activity, skipping a missing address', () => {
    const base = { id: 'a', device: 'Chrome on Mac', createdAt: minutesAgo(500), lastActiveAt: minutesAgo(0), current: true };
    expect(sessionMeta({ ...base, ip: '10.0.0.2' }, now)).toBe('10.0.0.2 · active now');
    expect(sessionMeta({ ...base, ip: null }, now)).toBe('active now');
  });
  it('describes a passkey', () => {
    const k = { id: 'k', label: 'iPhone', createdAt: '2026-10-02T10:00:00Z', lastUsedAt: '2026-10-18T13:12:00Z' };
    expect(passkeyMeta(k, now)).toBe('added Oct 02 · used today 6:42 pm');
    expect(passkeyMeta({ ...k, lastUsedAt: null }, now)).toBe('added Oct 02 · not used yet');
  });
  it('names a new passkey after the device and browser', () => {
    expect(passkeyLabel('Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/120.0 Safari/537.36')).toBe('Mac · Chrome · passkey');
    expect(passkeyLabel('Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit Version/17.0 Safari/604.1')).toBe('iPhone · Safari · passkey');
    expect(passkeyLabel('curl/8')).toBe('This device · passkey');
  });
  it('sign-in is strong with an authenticator, a passkey and unused codes', () => {
    const f: Factors = {
      totp: { enabled: true, since: null }, passkeys: [{ id: 'k', label: 'x', createdAt: '', lastUsedAt: null }],
      recoveryCodes: { remaining: 8, total: 10 }, passwordChangedAt: '', setup: { totpEnabled: true, recoveryCodes: true, complete: true },
    };
    expect(signInStrong(f)).toBe(true);
    expect(signInStrong({ ...f, passkeys: [] })).toBe(false);
    expect(signInStrong({ ...f, recoveryCodes: { remaining: 0, total: 10 } })).toBe(false);
  });
});

describe('activity wording', () => {
  it('uses plain sentences, with the method for second steps', () => {
    expect(auditLabel({ action: 'register', meta: null })).toBe('Account created');
    expect(auditLabel({ action: '2fa.ok', meta: { method: 'passkey' } })).toBe('Signed in with a passkey');
    expect(auditLabel({ action: '2fa.failed', meta: { method: 'recovery' } })).toBe('Wrong recovery code');
    expect(auditLabel({ action: 'login.ok', meta: { setup: true } })).toBe('Signed in with a password, setup still to finish');
    expect(auditLabel({ action: 'password.changed', meta: { signedOutOthers: 1 } })).toBe('Password changed, 1 other browser signed out');
    expect(auditLabel({ action: 'password.changed', meta: { signedOutOthers: 0 } })).toBe('Password changed');
  });
  it('falls back to the action name for one it does not know', () => {
    expect(auditLabel({ action: 'thing.did_happen', meta: null })).toBe('Thing did happen');
  });
  it('marks wrong codes and pauses as warnings', () => {
    expect(auditWarn('2fa.failed')).toBe(true);
    expect(auditWarn('login.ok')).toBe(false);
  });
});

describe('profile summary', () => {
  const e = (action: string, at: string) => ({ action, at });
  it('reads member since from the oldest register entry and last export from the newest', () => {
    const entries = [e('export', '2026-10-17T10:00:00Z'), e('login.ok', '2026-10-10T10:00:00Z'), e('export', '2026-10-05T10:00:00Z'), e('register', '2026-10-02T10:00:00Z')];
    expect(profileSummary(entries, 200)).toEqual({ memberSince: 'oct 2', lastExport: 'oct 17' });
  });
  it('says never only when the whole log is in hand', () => {
    expect(profileSummary([e('login.ok', '2026-10-10T10:00:00Z')], 200).lastExport).toBe('never');
    expect(profileSummary([e('login.ok', '2026-10-10T10:00:00Z')], 1)).toEqual({ memberSince: '—', lastExport: '—' });
  });
});

describe('export file', () => {
  it('sizes in plain units', () => {
    expect(formatBytes(512)).toBe('512 B');
    expect(formatBytes(3000)).toBe('3 KB');
    expect(formatBytes(2 * 1024 * 1024)).toBe('2.0 MB');
  });
  it('builds one JSON document and describes it', () => {
    const f = buildExportFile({ exportedAt: '2026-10-18T13:20:00Z', filename: 'ledger-export-2026-10-18.json', entries: 18, parts: [{ service: 'auth', tables: {} }] });
    expect(JSON.parse(f.text)).toEqual({ exportedAt: '2026-10-18T13:20:00Z', entries: 18, parts: [{ service: 'auth', tables: {} }] });
    expect(f.text.endsWith('\n')).toBe(true);
    expect(f.bytes).toBe(new TextEncoder().encode(f.text).length);
    expect(exportLine({ filename: 'a.json', entries: 1, bytes: 3000 })).toBe('a.json · 1 entry · 3 KB');
    expect(exportLine({ filename: 'a.json', entries: 18, bytes: 100 })).toBe('a.json · 18 entries · 100 B');
  });
});
