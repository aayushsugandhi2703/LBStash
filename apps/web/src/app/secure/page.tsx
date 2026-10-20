'use client';

import { type FormEvent, useEffect, useState } from 'react';
import { type PublicKeyCredentialCreationOptionsJSON, startRegistration } from '@simplewebauthn/browser';
import type { z } from 'zod';
import type { FactorsRes, RecoveryCodesRes, TwoFactorEnableConfirmRes, TwoFactorEnableStartRes } from '@/contracts';
import { AuthFrame } from '@/components/auth-frame';
import { Button, ErrorLine, Field } from '@/components/ui';
import { api, ApiError, errorText } from '@/lib/api';

type Part = 1 | 2 | 3;

/** `?next=` when it is a path on this site. */
function requestedPath(): string | null {
  const next = new URLSearchParams(window.location.search).get('next');
  return next?.startsWith('/') && !next.startsWith('//') ? next : null;
}

const isSignedOut = (e: unknown): boolean => e instanceof ApiError && e.code === 'unauthorized';

/** Setup that needs a session: no session (or an expired one) means signing in again, then coming back here. */
function toSignIn(): void {
  window.location.replace(`/sign-in?next=${encodeURIComponent(`${window.location.pathname}${window.location.search}`)}`);
}

export default function SecurePage() {
  const [part, setPart] = useState<Part>(1);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [secret, setSecret] = useState('');
  const [otpauthUri, setOtpauthUri] = useState('');
  const [qr, setQr] = useState('');
  const [code, setCode] = useState('');
  const [recoveryCodes, setRecoveryCodes] = useState<string[]>([]);
  const [saved, setSaved] = useState(false);
  const [passkeyAdded, setPasskeyAdded] = useState(false);
  const [passkeyRequiredOnly, setPasskeyRequiredOnly] = useState(false);
  const [firstTime, setFirstTime] = useState(false);
  const [refreshingCodes, setRefreshingCodes] = useState(false);
  const [error, setError] = useState('');
  const [copiedSecret, setCopiedSecret] = useState(false);
  const [copiedCodes, setCopiedCodes] = useState(false);

  useEffect(() => {
    let active = true;
    async function prepare() {
      try {
        const factors = await api.get<z.infer<typeof FactorsRes>>('/auth/factors');
        if (!active) return;
        const params = new URLSearchParams(window.location.search);
        const refreshCodes = params.get('refresh') === '1';
        setPasskeyAdded(factors.passkeys.length > 0);
        setFirstTime(!factors.setup.complete);
        if (factors.setup.complete && factors.passkeys.length === 0) {
          setPasskeyRequiredOnly(true);
          setRefreshingCodes(refreshCodes);
          setPart(2);
          return;
        }
        if (factors.setup.complete && !refreshCodes) {
          window.location.replace(requestedPath() ?? '/');
          return;
        }
        if (factors.setup.complete && refreshCodes) {
          setRefreshingCodes(true);
          setPart(3);
          return;
        }
        if (factors.totp.enabled) {
          setPart(2);
        } else {
          const totp = await api.post<z.infer<typeof TwoFactorEnableStartRes>>('/auth/2fa/enable', {});
          if (active) {
            setSecret(totp.secret);
            setOtpauthUri(totp.otpauthUri);
          }
        }
      } catch (e) {
        if (isSignedOut(e)) { toSignIn(); return; }
        if (active) setError(errorText(e, 'Could not load security setup. Please try again.'));
      } finally {
        if (active) setLoading(false);
      }
    }
    void prepare();
    return () => { active = false; };
  }, []);

  useEffect(() => {
    if (!otpauthUri) return;
    let active = true;
    void import('qrcode').then(({ default: QRCode }) =>
      QRCode.toDataURL(otpauthUri, { errorCorrectionLevel: 'M', margin: 1, width: 240 }),
    ).then((data) => { if (active) setQr(data); })
      .catch((e: unknown) => { if (active) setError(errorText(e, 'Could not create the authenticator QR code. Use the setup key instead.')); });
    return () => { active = false; };
  }, [otpauthUri]);

  function fail(e: unknown, fallback: string) {
    if (isSignedOut(e)) toSignIn();
    else setError(errorText(e, fallback));
  }

  async function confirmAuthenticator(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (code.length !== 6) return;
    setError('');
    setBusy(true);
    try {
      await api.post<z.infer<typeof TwoFactorEnableConfirmRes>>('/auth/2fa/enable/confirm', { code });
      setCode('');
      setPart(2);
    } catch (e) {
      fail(e, 'That code did not work. Check your authenticator app and try again.');
    } finally {
      setBusy(false);
    }
  }

  async function addPasskey() {
    setError('');
    setBusy(true);
    try {
      const { options } = await api.post<{ options: PublicKeyCredentialCreationOptionsJSON }>('/auth/passkey/register/options', {});
      const response = await startRegistration({ optionsJSON: options });
      await api.post('/auth/passkey/register/verify', { response });
      const factors = await api.get<z.infer<typeof FactorsRes>>('/auth/factors');
      setPasskeyAdded(factors.passkeys.length > 0);
      if (factors.setup.complete) {
        if (refreshingCodes) {
          setPart(3);
        } else {
          window.location.replace(requestedPath() ?? '/');
        }
        return;
      }
    } catch (e) {
      fail(e, 'Could not add the passkey. Please try again.');
    } finally {
      setBusy(false);
    }
  }

  async function showRecoveryCodes() {
    if (recoveryCodes.length > 0) { setPart(3); return; } // already made: a new set would void the one on screen
    setError('');
    setBusy(true);
    try {
      const factors = await api.get<z.infer<typeof FactorsRes>>('/auth/factors');
      setPasskeyAdded(factors.passkeys.length > 0);
      if (factors.setup.complete && factors.passkeys.length > 0 && !refreshingCodes) {
        window.location.replace(requestedPath() ?? '/');
        return;
      }
      if (factors.passkeys.length === 0 && !refreshingCodes) {
        setError('Add a passkey before continuing.');
        return;
      }
      const result = await api.post<z.infer<typeof RecoveryCodesRes>>('/auth/recovery-codes', {
        ...(refreshingCodes ? { code } : {}),
      });
      setRecoveryCodes(result.codes);
      setSaved(false);
      setCode('');
      setPart(3);
    } catch (e) {
      fail(e, 'Could not create recovery codes. Please try again.');
    } finally {
      setBusy(false);
    }
  }

  async function copyText(value: string, kind: 'secret' | 'codes') {
    try {
      await navigator.clipboard.writeText(value);
      const setCopied = kind === 'secret' ? setCopiedSecret : setCopiedCodes;
      setCopied(true);
      window.setTimeout(() => setCopied(false), 1600);
    } catch (e) {
      setError(errorText(e, 'Clipboard access is unavailable. Select and copy the text manually.'));
    }
  }

  async function signOut() {
    try { await api.post('/auth/logout'); } catch { /* the cookie is gone once the server answers; go on either way */ }
    window.location.assign('/sign-in');
  }

  const labels = ['Authenticator app', 'Passkey', 'Recovery codes'];
  const title = 'Secure your account';

  return (
    <AuthFrame
      right={<span className="mono lbl">{passkeyRequiredOnly ? 'required · sign-in setup' : 'step 2 of 3 · account setup'}</span>}
      glyph="secure"
      title={title}
      description={passkeyRequiredOnly
        ? 'Create a passkey before you can open your transactions.'
        : 'A password alone is not enough. Three quick parts, about 2 minutes.'}
      aside={
        <div className="signin-steps">
          <div className="lbl signin-steps-title">THREE PARTS</div>
          {labels.map((label, index) => {
            const state = index + 1 < part ? 'done' : index + 1 === part ? 'now' : 'next';
            return <div key={label} className="idx signin-index-static" data-active={state === 'now'}><span>{label}</span><span className="v mono" data-done={state === 'done'}>{state}</span></div>;
          })}
        </div>
      }
    >
      {loading ? <div className="signin-form"><div className="lbl" role="status">LOADING SECURITY SETUP…</div></div> : (
        <div className="signin-form rise">
          {part === 1 && (
            <form className="signin-form signin-part-form" onSubmit={confirmAuthenticator}>
              <div className="lbl">PART 1 OF 3 · AUTHENTICATOR APP</div>
              <div className="signin-qr-row">
                <div className="signin-qr-wrap">
                  {qr ? <img className="signin-qr" src={qr} alt="QR code for your authenticator app" /> : <div className="signin-qr signin-qr-loading" role="status">Creating QR…</div>}
                  <div className="mono lbl signin-qr-caption">scan with your authenticator app</div>
                </div>
                <div className="signin-qr-help">
                  <h2 className="h2">Scan it with an authenticator app</h2>
                  <p className="cap">Use any authenticator app (Apple Passwords, 1Password, Google). Cannot scan? Type the key.</p>
                  {secret && <div className="signin-secret">
                    <code className="mono">{secret.match(/.{1,4}/g)?.join(' ') ?? secret}</code>
                    <button className="signin-toggle" type="button" onClick={() => void copyText(secret, 'secret')}>{copiedSecret ? 'copied' : 'copy'}</button>
                  </div>}
                  {otpauthUri && <a className="signin-otpauth" href={otpauthUri}>Open in authenticator app</a>}
                </div>
              </div>
              <div className="signin-code-well">
                <Field
                  label="Then type the 6-digit code it shows"
                  type="text"
                  inputMode="numeric"
                  autoComplete="one-time-code"
                  maxLength={6}
                  placeholder="000000"
                  value={code}
                  onChange={(event) => { setCode(event.target.value.replace(/\D/g, '').slice(0, 6)); setError(''); }}
                />
              </div>
              {error && <ErrorLine>{error}</ErrorLine>}
              <div className="signin-actions"><Button large type="submit" disabled={code.length !== 6 || busy}>{busy ? 'Checking…' : 'Confirm and continue'}</Button></div>
            </form>
          )}

          {part === 2 && (
            <div className="signin-form signin-part-form">
              <div className="lbl">{passkeyRequiredOnly ? 'REQUIRED · PASSKEY' : 'PART 2 OF 3 · REQUIRED PASSKEY'}</div>
              <h2 className="fig-lg">{passkeyRequiredOnly ? 'Create a passkey to finish signing in.' : 'Create a passkey to secure your account.'}</h2>
              <p className="cap">A passkey is required to open your transactions. Lost the device? Use your authenticator or a recovery code.</p>
              {passkeyAdded && <div className="signin-passkey-added"><span aria-hidden="true">✓</span><strong>Passkey added</strong></div>}
              {error && <ErrorLine>{error}</ErrorLine>}
              <div className="signin-actions">
                {!passkeyAdded && <Button large type="button" disabled={busy} onClick={() => void addPasskey()}>{busy ? 'Waiting for passkey…' : 'Add a passkey'}</Button>}
                {passkeyAdded
                  ? <Button large type="button" disabled={busy} onClick={() => void showRecoveryCodes()}>Continue</Button>
                  : <p className="signin-footnote">A passkey is required to continue.</p>}
                {!passkeyRequiredOnly && <button type="button" className="signin-back" disabled={busy} onClick={() => setPart(1)}>Back</button>}
              </div>
            </div>
          )}

          {part === 3 && (
            <div className="signin-form signin-part-form">
              <div className="lbl">{refreshingCodes ? 'FRESH RECOVERY CODES' : 'PART 3 OF 3 · RECOVERY CODES'}</div>
              <h2 className="fig-lg">Keep these recovery codes somewhere safe. They are shown only once.</h2>
              {recoveryCodes.length === 0 ? (
                <form className="signin-form signin-part-form" onSubmit={(event) => { event.preventDefault(); void showRecoveryCodes(); }}>
                  <Field
                    label="Current 6-digit authenticator code"
                    type="text"
                    inputMode="numeric"
                    autoComplete="one-time-code"
                    maxLength={6}
                    placeholder="000000"
                    value={code}
                    onChange={(event) => { setCode(event.target.value.replace(/\D/g, '').slice(0, 6)); setError(''); }}
                  />
                  <Button large type="submit" disabled={code.length !== 6 || busy}>{busy ? 'Creating…' : 'Create fresh recovery codes'}</Button>
                </form>
              ) : (
                <>
                  <div className="signin-recovery-grid">
                    {recoveryCodes.map((recoveryCode) => <code className="mono" key={recoveryCode}>{recoveryCode}</code>)}
                  </div>
                  <div className="signin-actions">
                    <button className="signin-toggle" type="button" onClick={() => void copyText(recoveryCodes.join('\n'), 'codes')}>{copiedCodes ? 'copied all' : 'copy all'}</button>
                    <button className="signin-toggle" type="button" onClick={() => {
                      const blob = new Blob([`${recoveryCodes.join('\n')}\n`], { type: 'text/plain' });
                      const url = URL.createObjectURL(blob);
                      const anchor = document.createElement('a');
                      anchor.href = url;
                      anchor.download = 'lbstash-recovery-codes.txt';
                      anchor.click();
                      window.setTimeout(() => URL.revokeObjectURL(url), 1000);
                    }}>download .txt</button>
                  </div>
                  <p className="mono lbl signin-code-note">Each works once. Your only way back in if you lose your phone and authenticator.</p>
                  <label className="signin-saved-label">
                    <input type="checkbox" checked={saved} onChange={(event) => setSaved(event.target.checked)} />
                    I have saved these somewhere safe
                  </label>
                </>
              )}
              {error && <ErrorLine>{error}</ErrorLine>}
              {recoveryCodes.length > 0 && <div className="signin-actions">
                <Button large type="button" disabled={!saved} onClick={() => window.location.assign(requestedPath() ?? (firstTime ? '/setup' : '/'))}>{firstTime ? 'Finish and open the setup guide' : 'Finish'}</Button>
                {!refreshingCodes && <button type="button" className="signin-back" onClick={() => setPart(2)}>Back</button>}
              </div>}
            </div>
          )}
          <button type="button" className="signin-back" onClick={() => void signOut()}>Sign out</button>
        </div>
      )}
    </AuthFrame>
  );
}
