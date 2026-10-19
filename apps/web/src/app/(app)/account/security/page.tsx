'use client';
import { useState } from 'react';
import type { z } from 'zod';
import { type PublicKeyCredentialCreationOptionsJSON, startRegistration } from '@simplewebauthn/browser';
import type { AuditRes, RecoveryCodesRes, SessionsRes, TwoFactorEnableStartRes } from '@/contracts';
import { AccountShell } from '@/components/shell';
import { Button, CodeInput, ConfirmWell, Empty, ErrorLine, GhostButton, LedgerMath, Loading, SettingsRow, TextLink } from '@/components/ui';
import { api, errorText, fieldErrors, useApi } from '@/lib/api';
import { ago, auditLabel, auditPlace, auditWarn, auditWhen, canRemovePasskey, canSavePassword, codeError, type Factors, isCode, type Passkey, passkeyLabel, passkeyMeta, passwordCounter, type Session, sessionMeta, shortDate, signInStrong } from '@/features/account';
import { copyToClipboard, downloadText, useFlash } from '@/lib/browser';
import { LineStatus, LoadError, Section, Well } from '../parts';
import s from '../account.module.css';

type Audit = z.infer<typeof AuditRes>;
const AUDIT_ROWS = 20;

export default function SecurityPage() {
  const factors = useApi<Factors>('/auth/factors');
  const sessions = useApi<z.infer<typeof SessionsRes>>('/sessions');
  const audit = useApi<Audit>(`/audit?limit=${AUDIT_ROWS}`);
  const f = factors.data;
  const list = sessions.data?.sessions ?? [];

  const refreshAll = () => Promise.all([factors.mutate(), sessions.mutate(), audit.mutate()]);

  return (
    <AccountShell
      page="security" glyph="security" title="Security"
      description="How you sign in, where you are signed in, and what happened lately. Changes here ask for your code."
      label="SECURITY" heading="Sign-in and sessions"
      lead="Two-step sign-in is always on and cannot be turned off. Passkeys are the quickest way in; the authenticator app and recovery codes are your backups."
      summary={<LedgerMath rows={[
        { k: 'two-step', v: 'on' },
        { k: 'passkeys', v: f ? String(f.passkeys.length) : '—' },
        { k: 'browsers', v: sessions.data ? String(list.length) : '—' },
      ]} total={{ k: '= sign-in', v: f ? (signInStrong(f) ? 'strong' : 'needs work') : '—' }} />}
    >
      <Section first>SIGN-IN METHODS</Section>
      {factors.error && !f && <LoadError retry={() => void factors.mutate()} />}
      {!f && !factors.error && <Loading />}
      {f && (
        <>
          <PasswordRow changedAt={f.passwordChangedAt} onDone={() => void refreshAll()} />
          <AuthenticatorRow since={f.totp.since} onDone={() => void refreshAll()} />
          <PasskeysBlock passkeys={f.passkeys} onChange={() => void refreshAll()} />
          <RecoveryRow remaining={f.recoveryCodes.remaining} total={f.recoveryCodes.total} onDone={() => void refreshAll()} />
        </>
      )}

      <Section>WHERE YOU ARE SIGNED IN</Section>
      <SessionsBlock sessions={list} loading={!sessions.data && !sessions.error} failed={Boolean(sessions.error) && !sessions.data} retry={() => void sessions.mutate()} onChange={() => void refreshAll()} />

      <Section>ACTIVITY</Section>
      <div role="table" aria-label="Recent account activity">
        {!audit.data && !audit.error && <Loading />}
        {audit.error && !audit.data && <LoadError retry={() => void audit.mutate()} />}
        {audit.data?.entries.length === 0 && <Empty>Nothing yet. Account activity appears here.</Empty>}
        {audit.data?.entries.map((e) => (
          <div key={e.id} role="row" className="row" style={{ alignItems: 'baseline' }}>
            <span role="cell" className={`mono ${s.auditWhen}`}>{auditWhen(e.at)}</span>
            <span role="cell" className={`${s.auditWhat} ${auditWarn(e.action) ? s.warn : ''}`}>{auditLabel(e)}</span>
            <span role="cell" className={`mono ${s.auditWhere}`}>{auditPlace(e)}</span>
          </div>
        ))}
      </div>
      <div className={`mono ${s.footnote}`}>This log is append-only. Nobody, including you, can edit or remove an entry.</div>
    </AccountShell>
  );
}


function PasswordRow({ changedAt, onDone }: { changedAt: string; onDone: () => void }) {
  const [open, setOpen] = useState(false);
  const [cur, setCur] = useState('');
  const [next, setNext] = useState('');
  const [code, setCode] = useState('');
  const [done, setDone] = useState(false);
  const [errs, setErrs] = useState<{ cur?: string; next?: string; code?: string; other?: string }>({});
  const [busy, setBusy] = useState(false);

  const toggle = () => { setOpen(!open); setCur(''); setNext(''); setCode(''); setDone(false); setErrs({}); };
  async function save() {
    setBusy(true); setErrs({});
    try {
      await api.post('/auth/password', { currentPassword: cur, newPassword: next, code });
      setOpen(false); setCur(''); setNext(''); setCode(''); setDone(true);
      onDone();
    } catch (e) {
      const fe = fieldErrors(e);
      const c = codeError(e);
      setErrs({ cur: fe.currentPassword, next: fe.newPassword, code: c ?? undefined, other: !c && !fe.currentPassword && !fe.newPassword ? errorText(e) : undefined });
      setCode('');
    } finally { setBusy(false); }
  }
  return (
    <>
      <SettingsRow title="Password" sub={`Changed ${ago(changedAt)}. Changing it signs every other browser out.`}>
        <GhostButton onClick={toggle}>{open ? 'Cancel' : 'Change password'}</GhostButton>
      </SettingsRow>
      {open && (
        <Well>
          <label htmlFor="cur" className="lbl">CURRENT PASSWORD</label>
          <input id="cur" className={`${s.input} ${errs.cur ? s.err : ''}`} type="password" autoComplete="current-password" placeholder="••••••••••••" value={cur} onChange={(e) => { setCur(e.target.value); setErrs({}); }} />
          {errs.cur && <ErrorLine>{errs.cur}</ErrorLine>}
          <div className={s.field}><label htmlFor="nw" className="lbl">NEW PASSWORD · AT LEAST 12 CHARACTERS</label></div>
          <input id="nw" className={`${s.input} ${errs.next ? s.err : ''}`} type="password" autoComplete="new-password" placeholder="••••••••••••" value={next} onChange={(e) => { setNext(e.target.value); setErrs({}); }} />
          <div className="mono" style={{ marginTop: 6, fontSize: 'var(--fs-label)', color: 'var(--muted)' }}>{passwordCounter(next.length)}</div>
          {errs.next && <ErrorLine>{errs.next}</ErrorLine>}
          <div className={`actions ${s.field}`}>
            <CodeInput value={code} onChange={(v) => { setCode(v); setErrs((x) => ({ ...x, code: undefined })); }} />
            <Button disabled={!canSavePassword(cur, next, code) || busy} onClick={() => void save()}>Save password</Button>
            {(errs.code || errs.other) && <div className={s.full}><ErrorLine>{errs.code ?? errs.other}</ErrorLine></div>}
          </div>
        </Well>
      )}
      {done && <LineStatus>Password changed. Other browsers were signed out.</LineStatus>}
    </>
  );
}


/** Replace the app: the current code starts it, a QR for the new secret, then a code from the new app confirms. */
function AuthenticatorRow({ since, onDone }: { since: string | null; onDone: () => void }) {
  const [open, setOpen] = useState(false);
  const [code, setCode] = useState('');
  const [scan, setScan] = useState<{ secret: string; uri: string; qr: string } | null>(null);
  const [confirm, setConfirm] = useState('');
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const [done, setDone] = useState(false);
  const [flags, flash] = useFlash();

  const reset = () => { setCode(''); setScan(null); setConfirm(''); setError(''); };
  const toggle = () => { setOpen(!open); reset(); setDone(false); };
  async function start() {
    setBusy(true); setError('');
    try {
      const r = await api.post<z.infer<typeof TwoFactorEnableStartRes>>('/auth/2fa/enable', { currentCode: code });
      const { default: QRCode } = await import('qrcode');
      const qr = await QRCode.toDataURL(r.otpauthUri, { errorCorrectionLevel: 'M', margin: 1, width: 240 });
      setScan({ secret: r.secret, uri: r.otpauthUri, qr }); setCode('');
    } catch (e) {
      setError(codeError(e) ?? errorText(e)); setCode('');
    } finally { setBusy(false); }
  }
  async function finish() {
    setBusy(true); setError('');
    try {
      await api.post('/auth/2fa/enable/confirm', { code: confirm });
      setOpen(false); reset(); setDone(true); onDone();
    } catch (e) {
      setError(codeError(e) ?? errorText(e)); setConfirm('');
    } finally { setBusy(false); }
  }
  return (
    <>
      <SettingsRow title="Authenticator app" sub={`${since ? `On since ${shortDate(since)}` : 'On'}. Asked for at every password sign-in.`}>
        <GhostButton onClick={toggle}>{open ? 'Cancel' : 'Replace'}</GhostButton>
      </SettingsRow>
      {open && !scan && (
        <ConfirmWell text="You will scan a new QR code, as when you first set up. The old app stops working the moment you confirm the new one. Enter a code from the current app to begin.">
          <CodeInput value={code} onChange={(v) => { setCode(v); setError(''); }} />
          <Button disabled={!isCode(code) || busy} onClick={() => void start()}>Scan a new code</Button>
          {error && <div className={s.full}><ErrorLine>{error}</ErrorLine></div>}
        </ConfirmWell>
      )}
      {open && scan && (
        <Well>
          <div className="actions">
            <div className={s.qrRow}>
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img className={s.qr} src={scan.qr} alt="QR code for your new authenticator app" />
              <div className={s.min0} style={{ flex: '1 1 260px' }}>
                <p style={{ margin: 0 }}>Scan this with your authenticator app, or type the key.</p>
                <div className={`mono ${s.secret}`} style={{ marginTop: 8 }}>{scan.secret.match(/.{1,4}/g)?.join(' ') ?? scan.secret}</div>
                <div style={{ marginTop: 6 }}><TextLink mono onClick={() => void copyToClipboard(scan.secret).then((ok) => ok && flash('secret'))}>{flags.secret ? 'copied' : 'copy'}</TextLink></div>
              </div>
            </div>
            <CodeInput label="Code from the new app" value={confirm} onChange={(v) => { setConfirm(v); setError(''); }} />
            <Button disabled={!isCode(confirm) || busy} onClick={() => void finish()}>Confirm the new app</Button>
            {error && <div className={s.full}><ErrorLine>{error}</ErrorLine></div>}
          </div>
          <div className={s.note}>If the code is refused, wait for the next one to appear in the app and try again.</div>
        </Well>
      )}
      {done && <LineStatus>Authenticator replaced. The old app no longer works.</LineStatus>}
    </>
  );
}


function PasskeysBlock({ passkeys, onChange }: { passkeys: Passkey[]; onChange: () => void }) {
  const [removing, setRemoving] = useState('');
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);

  async function add() {
    setBusy(true); setError('');
    try {
      const { options } = await api.post<{ options: PublicKeyCredentialCreationOptionsJSON }>('/auth/passkey/register/options', {});
      const response = await startRegistration({ optionsJSON: options });
      await api.post('/auth/passkey/register/verify', { response, label: passkeyLabel(navigator.userAgent) });
      onChange();
    } catch (e) {
      setError((e as { name?: string })?.name === 'NotAllowedError' ? 'The passkey was cancelled. Nothing was added.' : errorText(e, 'Could not add the passkey. Try again.'));
    } finally { setBusy(false); }
  }
  async function remove(id: string) {
    if (removing !== id) { setRemoving(id); return; }
    setError('');
    try { await api.del(`/auth/passkey/${id}`); setRemoving(''); onChange(); } catch (e) { setRemoving(''); setError(errorText(e)); }
  }
  const last = !canRemovePasskey(passkeys.length);
  return (
    <>
      <div className="settings-row" style={{ alignItems: 'flex-start' }}>
        <div style={{ minWidth: 0 }}>
          <div className="t">Passkeys</div>
          <div className="s">Face ID, Touch ID or a security key. A passkey never leaves the device that made it.</div>
        </div>
        <GhostButton disabled={busy} onClick={() => void add()}>{busy ? 'Waiting for passkey…' : 'Add a passkey'}</GhostButton>
      </div>
      {error && <div className={s.indent}><ErrorLine>{error}</ErrorLine></div>}
      {passkeys.map((k) => (
        <div key={k.id} className="row" style={{ justifyContent: 'space-between', paddingLeft: 16 }}>
          <span style={{ minWidth: 0 }}>
            <span style={{ display: 'block', fontSize: 'var(--fs-body)', fontWeight: 500 }}>{k.label}</span>
            <span className={`mono ${s.mono11}`} style={{ display: 'block', marginTop: 2 }}>{passkeyMeta(k)}</span>
          </span>
          {last
            ? <span className={`mono ${s.mono11}`}>needed to sign in</span>
            : <button type="button" className={`mono ${s.removeLink}`} onClick={() => void remove(k.id)}>{removing === k.id ? 'Tap again to remove' : 'Remove'}</button>}
        </div>
      ))}
      {passkeys.length === 0 && <div className={`mono ${s.line} ${s.indent}`} style={{ fontSize: 'var(--fs-s)', color: 'var(--muted)' }}>no passkeys · you sign in with password and authenticator code</div>}
    </>
  );
}


function RecoveryRow({ remaining, total, onDone }: { remaining: number; total: number; onDone: () => void }) {
  const [ask, setAsk] = useState(false);
  const [code, setCode] = useState('');
  const [codes, setCodes] = useState<string[] | null>(null);
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const [flags, flash] = useFlash();

  const toggle = () => { setAsk(!ask); setCode(''); setCodes(null); setError(''); };
  async function make() {
    setBusy(true); setError('');
    try {
      const r = await api.post<z.infer<typeof RecoveryCodesRes>>('/auth/recovery-codes', { code });
      setAsk(false); setCode(''); setCodes(r.codes); onDone();
    } catch (e) {
      setError(codeError(e) ?? errorText(e)); setCode('');
    } finally { setBusy(false); }
  }
  return (
    <>
      <SettingsRow title="Recovery codes" sub={`${remaining} of ${total} unused. Each works once, if you lose your authenticator.`}>
        <GhostButton onClick={toggle}>{ask ? 'Cancel' : 'Make new codes'}</GhostButton>
      </SettingsRow>
      {ask && (
        <ConfirmWell text="Making new codes cancels all the old ones, used or not.">
          <CodeInput value={code} onChange={(v) => { setCode(v); setError(''); }} />
          <Button disabled={!isCode(code) || busy} onClick={() => void make()}>Make new codes</Button>
          {error && <div className={s.full}><ErrorLine>{error}</ErrorLine></div>}
        </ConfirmWell>
      )}
      {codes && (
        <Well>
          <div className="lbl">SHOWN ONCE · SAVE THEM SOMEWHERE SAFE</div>
          <div className={`mono ${s.codes}`}>{codes.map((c) => <span key={c}>{c}</span>)}</div>
          <div className={s.actionsRow} style={{ paddingBottom: 0 }}>
            <TextLink mono onClick={() => void copyToClipboard(codes.join('\n')).then((ok) => ok && flash('all'))}>{flags.all ? 'copied all' : 'copy all'}</TextLink>
            <TextLink mono onClick={() => downloadText('ledger-recovery-codes.txt', `${codes.join('\n')}\n`, 'text/plain')}>download .txt</TextLink>
          </div>
        </Well>
      )}
    </>
  );
}


function SessionsBlock({ sessions, loading, failed, retry, onChange }: { sessions: Session[]; loading: boolean; failed: boolean; retry: () => void; onChange: () => void }) {
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const others = sessions.filter((x) => !x.current);

  async function end(id: string) {
    setError('');
    try { await api.del(`/sessions/${id}`); onChange(); } catch (e) { setError(errorText(e)); }
  }
  async function endAll() {
    setBusy(true); setError('');
    try { await api.del('/sessions'); onChange(); } catch (e) { setError(errorText(e)); } finally { setBusy(false); }
  }
  return (
    <>
      {loading && <Loading />}
      {failed && <LoadError retry={retry} />}
      {!loading && !failed && sessions.length === 0 && <Empty>No signed-in browsers found.</Empty>}
      {sessions.map((x) => (
        <div key={x.id} className="row" style={{ justifyContent: 'space-between' }}>
          <span style={{ minWidth: 0 }}>
            <span style={{ display: 'block', fontSize: 'var(--fs-body)', fontWeight: 500 }}>{x.device}{x.current && <span className={`mono ${s.badge}`}>this browser</span>}</span>
            <span className={`mono ${s.mono11}`} style={{ display: 'block', marginTop: 2 }}>{sessionMeta(x)}</span>
          </span>
          {!x.current && <TextLink mono onClick={() => void end(x.id)}>Sign out</TextLink>}
        </div>
      ))}
      {error && <ErrorLine>{error}</ErrorLine>}
      <div className={s.actionsRow}>
        <GhostButton bad disabled={others.length === 0 || busy} onClick={() => void endAll()}>Sign out all other browsers</GhostButton>
        <span className={`mono ${s.mono11}`}>the Telegram bot session is on Devices</span>
      </div>
    </>
  );
}
