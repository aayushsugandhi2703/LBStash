'use client';

import { APP_HOME } from '@/features/landing';
import { type FormEvent, useEffect, useState } from 'react';
import Link from 'next/link';
import type { z } from 'zod';
import { type PublicKeyCredentialRequestOptionsJSON, startAuthentication } from '@simplewebauthn/browser';
import type { AuthSessionRes, LoginRes } from '@/contracts';
import { AuthEm, AuthFrame } from '@/components/auth-frame';
import { Button, ErrorLine, Field, Segmented } from '@/components/ui';
import { api, ApiError, errorText } from '@/lib/api';
import { codeError } from '@/features/account';

const MISMATCH = "That email and password don't match.";

type Step = 'password' | 'verify' | 'done';
type Method = 'authenticator' | 'passkey' | 'recovery';

/** Where the person was headed when sign-in was asked for (`?next=`), if anywhere. */
function requestedPath(): string | null {
  const requested = new URLSearchParams(window.location.search).get('next');
  return requested?.startsWith('/') && !requested.startsWith('//') ? requested : null;
}
const nextPath = (): string => requestedPath() ?? APP_HOME;
/** `/secure` finishes at the setup guide for a new account unless the person was headed somewhere else. */
function secureUrl(extra: Record<string, string> = {}): string {
  const query = new URLSearchParams(extra);
  const requested = requestedPath();
  if (requested) query.set('next', requested);
  const text = query.toString();
  return text ? `/secure?${text}` : '/secure';
}

export default function SignInPage() {
  const [step, setStep] = useState<Step>('password');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [twoFactorToken, setTwoFactorToken] = useState('');
  const [methods, setMethods] = useState<Method[]>(['authenticator', 'recovery']);
  const [method, setMethod] = useState<Method>('authenticator');
  const [code, setCode] = useState('');
  const [recoveryCode, setRecoveryCode] = useState('');
  const [attemptsLeft, setAttemptsLeft] = useState(3);
  const [retryAfter, setRetryAfter] = useState(0);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [recoveryCodeUsed, setRecoveryCodeUsed] = useState(false);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (retryAfter <= 0) return;
    const timer = window.setTimeout(() => {
      setRetryAfter(retryAfter - 1);
      if (retryAfter === 1) {
        setAttemptsLeft(3);
        setError('');
      }
    }, 1000);
    return () => window.clearTimeout(timer);
  }, [retryAfter]);

  async function submitPassword(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError('');
    setNotice('');
    if (!/^\S+@\S+\.\S+$/.test(email) || password.length < 1) {
      setError(MISMATCH);
      return;
    }
    setBusy(true);
    try {
      const result = await api.post<z.infer<typeof LoginRes>>('/auth/login', { email, password });
      if (result.setupRequired) {
        window.location.assign(secureUrl());
        return;
      }
      if (!result.twoFactorToken) {
        setError('Could not start sign-in. Please try again.');
        return;
      }
      const availableMethods = result.methods.flatMap((item): Method[] =>
        item === 'totp' ? ['authenticator'] : item === 'recovery' ? ['recovery'] : item === 'passkey' ? ['passkey'] : []);
      setTwoFactorToken(result.twoFactorToken);
      setMethods(availableMethods);
      setMethod(availableMethods[0] ?? 'authenticator');
      setStep('verify');
    } catch (e) {
      setError(errorText(e, MISMATCH));
    } finally {
      setBusy(false);
    }
  }

  async function submitSecondStep(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError('');
    setBusy(true);
    try {
      let session: z.infer<typeof AuthSessionRes>;
      if (method === 'passkey') {
        const result = await api.post<{ options: PublicKeyCredentialRequestOptionsJSON }>('/auth/passkey/login/options', { twoFactorToken });
        const response = await startAuthentication({ optionsJSON: result.options });
        session = await api.post<z.infer<typeof AuthSessionRes>>('/auth/passkey/login/verify', { twoFactorToken, response });
      } else {
        const body = method === 'authenticator'
          ? { twoFactorToken, code }
          : { twoFactorToken, recoveryCode };
        session = await api.post<z.infer<typeof AuthSessionRes>>('/auth/2fa/verify', body);
      }
      if (!session.setup.complete || !methods.includes('passkey')) {
        window.location.assign(secureUrl(session.recoveryCodeUsed ? { refresh: '1' } : {}));
        return;
      }
      if (session.recoveryCodeUsed) {
        setRecoveryCodeUsed(true);
        setNotice('You used a recovery code. Create a fresh set before you need them again.');
      }
      setStep('done');
    } catch (e) {
      const details = e instanceof ApiError && e.details && typeof e.details === 'object' ? e.details : {};
      if (e instanceof ApiError && e.code === 'two_factor_invalid' && 'attemptsLeft' in details && typeof details.attemptsLeft === 'number') {
        setAttemptsLeft(details.attemptsLeft);
        setError(codeError(e) ?? errorText(e));
      } else if (e instanceof ApiError && e.code === 'locked' && 'retryAfterSeconds' in details && typeof details.retryAfterSeconds === 'number') {
        setAttemptsLeft(0);
        setRetryAfter(details.retryAfterSeconds);
        setError(codeError(e) ?? errorText(e));
      } else if (e instanceof ApiError && e.code === 'unauthorized') {
        // the password step has expired: start from the password again
        backToPassword();
        setError(errorText(e));
      } else {
        setError(errorText(e));
      }
    } finally {
      setBusy(false);
    }
  }

  function backToPassword() {
    setStep('password');
    setPassword('');
    setTwoFactorToken('');
    setCode('');
    setRecoveryCode('');
    setAttemptsLeft(3);
    setRetryAfter(0);
    setError('');
    setNotice('');
  }

  const canVerify = method === 'passkey' || (method === 'authenticator' ? code.length === 6 : recoveryCode.trim().length >= 9);

  return (
    <AuthFrame
      right={<Link href="/" className="mono lbl signin-header-link">← about LBStash</Link>}
      glyph="signin"
      title={step === 'password' ? 'Sign in' : step === 'verify' ? 'Second step' : 'Signed in'}
      description={
        step === 'password'
          ? 'Your transactions is private. Sign in with your password, then a second step.'
          : step === 'verify'
            ? 'Prove it is you with your authenticator app, passkey or recovery code.'
            : 'You are in. Nothing else to do.'
      }
      aside={
        <div className="math mono signin-math">
          <div className="r"><span className="k">two-step</span><span>required</span></div>
          <div className="r"><span className="k">session</span><span>15 min, renews</span></div>
          <div className="r"><span className="k">your data</span><span>encrypted</span></div>
          <div className="r total"><span className="k">= only you</span><span className="v">in</span></div>
        </div>
      }
    >
      <>
          {step === 'password' && (
            <form className="signin-form rise" onSubmit={submitPassword} noValidate>
              <div className="lbl">STEP 1 OF 2 · PASSWORD</div>
              <Field
                label="Email"
                type="email"
                autoComplete="username" placeholder="you@example.com"
                value={email}
                onChange={(event) => { setEmail(event.target.value); setError(''); setNotice(''); }}
                required
              />
              <div className="field">
                <div className="signin-password-label">
                  <label className="lbl" htmlFor="signin-password">Password</label>
                  <button className="signin-toggle" type="button" onClick={() => setShowPassword((shown) => !shown)}>
                    {showPassword ? 'hide' : 'show'}
                  </button>
                </div>
                <input
                  id="signin-password"
                  className="uline"
                  type={showPassword ? 'text' : 'password'}
                  autoComplete="current-password"
                  placeholder="••••••••••••"
                  value={password}
                  onChange={(event) => { setPassword(event.target.value); setError(''); setNotice(''); }}
                  required
                />
              </div>
              {error && <ErrorLine>{error}</ErrorLine>}
              {notice && <p className="signin-notice" role="status">{notice}</p>}
              <div className="signin-actions">
                <Button large type="submit" disabled={busy}>{busy ? 'Checking…' : 'Continue'}</Button>
                <Link className="signin-back signin-link" href="/reset">Reset with a recovery code</Link>
              </div>
              <p className="signin-footnote opt">
                New here? <Link href="/create-account" className="signin-inline-link">Create the account</Link>. This app has a single account, so this link only works before it exists.
              </p>
            </form>
          )}

          {step === 'verify' && (
            <form className="signin-form rise" onSubmit={submitSecondStep}>
              <div className="lbl">STEP 2 OF 2 · SECOND STEP FOR {email.split('@')[0] || 'you'}</div>
              {methods.length > 1 && (
                <Segmented
                  value={method}
                  options={[
                    ...(methods.includes('authenticator') ? [{ value: 'authenticator' as const, label: 'Authenticator' }] : []),
                    ...(methods.includes('passkey') ? [{ value: 'passkey' as const, label: 'Passkey' }] : []),
                    ...(methods.includes('recovery') ? [{ value: 'recovery' as const, label: 'Recovery code' }] : []),
                  ]}
                  onChange={(value) => { setMethod(value); setCode(''); setRecoveryCode(''); setError(''); }}
                  label="Method"
                />
              )}
              {method === 'authenticator' ? (
                <Field
                  label="6-digit code from your authenticator app"
                  type="text"
                  inputMode="numeric"
                  autoComplete="one-time-code"
                  maxLength={6}
                  placeholder="000000"
                  value={code}
                  onChange={(event) => { setCode(event.target.value.replace(/\D/g, '').slice(0, 6)); setError(''); }}
                />
              ) : method === 'recovery' ? (
                <Field
                  label="One of your recovery codes"
                  type="text"
                  className="mono"
                  autoComplete="off"
                  placeholder="xxxx-xxxx"
                  value={recoveryCode}
                  onChange={(event) => { setRecoveryCode(event.target.value); setError(''); }}
                />
              ) : (
                <div className="signin-passkey-panel">
                  <strong>Use your passkey</strong>
                  <p className="cap">Face ID or Touch ID on this device. Nothing to type.</p>
                </div>
              )}
              {error && <ErrorLine>{error}</ErrorLine>}
              {notice && <p className="signin-notice" role="status">{notice}</p>}
              <div className="signin-actions">
                <Button large type="submit" disabled={!canVerify || attemptsLeft <= 0 || busy}>
                  {busy ? method === 'passkey' ? 'Waiting for passkey…' : 'Verifying…' : method === 'passkey' ? 'Use passkey' : 'Verify'}
                </Button>
                <button type="button" className="signin-back" onClick={backToPassword}>Use a different account</button>
              </div>
            </form>
          )}

          {step === 'done' && (
            <div className="signin-form rise">
              <div className="signin-success" aria-hidden="true">✓</div>
              <div className="lbl">SIGNED IN</div>
              <p className="lead">Welcome back, <AuthEm>{email.split('@')[0]}</AuthEm>. This session lasts 15 minutes and renews while you are active.</p>
              {notice && <p className="signin-notice" role="status">{notice}</p>}
              <div className="signin-actions">
                {recoveryCodeUsed && <Link className="signin-back signin-link" href="/secure?refresh=1">Create fresh recovery codes</Link>}
                <Link className="btn lg" href={nextPath()}>{nextPath() === '/' ? 'Open Now' : 'Continue'}</Link>
                <Link className="signin-back signin-link" href="/setup">Finish setup guide</Link>
              </div>
            </div>
          )}
      </>
    </AuthFrame>
  );
}
